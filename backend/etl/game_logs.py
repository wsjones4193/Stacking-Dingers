"""
MLB Stats API game log ingestion.

Pulls per-player game logs for all players in the Underdog player pool,
calculates best ball points, and appends to the season Parquet file.

Hitters: PA, AB, H, 2B, 3B, HR, R, RBI, SB, BB, HBP
Pitchers: IP, ER, SO (strikeouts), W (decision)
Derived: 1B = H - 2B - 3B - HR; QS = (IP >= 6.0 and ER <= 3)

The player pool is driven by what's in the Underdog CSV data — we only
pull MLB stats for players who have a confirmed mapping in player_id_map.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Optional

import pandas as pd
import statsapi  # mlb-statsapi library

from backend.db.parquet_helpers import append_gamelogs, get_last_gamelog_date
from backend.services.scoring import score_hitter_row, score_pitcher_row

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# MLB Stats API field mappings
# ---------------------------------------------------------------------------

# Hitting stat keys as returned by statsapi.player_stat_data
HITTING_STAT_KEYS = [
    "plateAppearances",
    "atBats",
    "hits",
    "doubles",
    "triples",
    "homeRuns",
    "runs",
    "rbi",
    "stolenBases",
    "baseOnBalls",
    "hitByPitch",
]

# Pitching stat keys
PITCHING_STAT_KEYS = [
    "inningsPitched",
    "earnedRuns",
    "strikeOuts",
    "wins",
]


# ---------------------------------------------------------------------------
# Single-player game log fetch
# ---------------------------------------------------------------------------

def fetch_player_gamelogs(
    mlb_id: int,
    season: int,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> list[dict]:
    """
    Fetch game-level stats for a player from the MLB Stats API.
    Returns a list of raw game dicts (one per game appearance).

    start_date / end_date format: "MM/DD/YYYY" (MLB Stats API format)
    """
    params = {
        "personId": mlb_id,
        "group": "[hitting,pitching]",
        "type": "gameLog",
        "season": season,
    }
    if start_date:
        params["startDate"] = start_date
    if end_date:
        params["endDate"] = end_date

    try:
        data = statsapi.get("people", {
            "personIds": mlb_id,
            "hydrate": f"stats(group=[hitting,pitching],type=gameLog,season={season})",
        })
        people = data.get("people", [])
        if not people:
            return []
        stats = people[0].get("stats", [])
        games = []
        for stat_group in stats:
            splits = stat_group.get("splits", [])
            for split in splits:
                games.append(split)
        return games
    except Exception as e:
        logger.warning(f"Failed to fetch gamelogs for mlb_id={mlb_id}: {e}")
        return []


# ---------------------------------------------------------------------------
# Parse and score a single game split dict
# ---------------------------------------------------------------------------

def parse_hitting_split(
    split: dict,
    player_id: int,
    mlb_id: int,
    position: str,
    season: int,
) -> Optional[dict]:
    """Convert a hitting game split dict into a scored row for Parquet."""
    try:
        stats = split.get("stat", {})
        game_date = split.get("date", "")
        if not game_date:
            return None

        h = int(stats.get("hits", 0))
        doubles = int(stats.get("doubles", 0))
        triples = int(stats.get("triples", 0))
        home_runs = int(stats.get("homeRuns", 0))
        singles = max(0, h - doubles - triples - home_runs)

        row = {
            "game_date": game_date,
            "player_id": player_id,
            "mlb_id": mlb_id,
            "position": position,
            "season": season,
            "pa": int(stats.get("plateAppearances", 0)),
            "ab": int(stats.get("atBats", 0)),
            "h": h,
            "singles": singles,
            "doubles": doubles,
            "triples": triples,
            "home_runs": home_runs,
            "runs": int(stats.get("runs", 0)),
            "rbi": int(stats.get("rbi", 0)),
            "stolen_bases": int(stats.get("stolenBases", 0)),
            "walks": int(stats.get("baseOnBalls", 0)),
            "hit_by_pitch": int(stats.get("hitByPitch", 0)),
            # Pitcher fields (zero for hitters)
            "ip": 0.0,
            "ip_true": 0.0,
            "earned_runs": 0,
            "strikeouts": 0,
            "wins": 0,
            "qs_flag": 0,
        }
        row["calculated_points"] = score_hitter_row(row)
        return row
    except Exception as e:
        logger.warning(f"Failed to parse hitting split for player_id={player_id}: {e}")
        return None


def parse_pitching_split(
    split: dict,
    player_id: int,
    mlb_id: int,
    season: int,
) -> Optional[dict]:
    """Convert a pitching game split dict into a scored row for Parquet."""
    try:
        stats = split.get("stat", {})
        game_date = split.get("date", "")
        if not game_date:
            return None

        ip_str = str(stats.get("inningsPitched", "0.0"))
        try:
            ip = float(ip_str)
        except ValueError:
            ip = 0.0

        earned_runs = int(stats.get("earnedRuns", 0))

        row = {
            "game_date": game_date,
            "player_id": player_id,
            "mlb_id": mlb_id,
            "position": "P",
            "season": season,
            # Hitting fields (zero for pitchers)
            "pa": 0, "ab": 0, "h": 0, "singles": 0,
            "doubles": 0, "triples": 0, "home_runs": 0,
            "runs": 0, "rbi": 0, "stolen_bases": 0, "walks": 0, "hit_by_pitch": 0,
            # Pitching
            "ip": ip,
            "earned_runs": earned_runs,
            "strikeouts": int(stats.get("strikeOuts", 0)),
            "wins": 1 if stats.get("wins", 0) else 0,
        }
        pts, qs = score_pitcher_row(row)
        row["calculated_points"] = pts
        row["qs_flag"] = qs

        from backend.services.scoring import ip_to_true_innings
        row["ip_true"] = ip_to_true_innings(ip)

        return row
    except Exception as e:
        logger.warning(f"Failed to parse pitching split for player_id={player_id}: {e}")
        return None


# ---------------------------------------------------------------------------
# Bulk ingestion for a list of players
# ---------------------------------------------------------------------------

def ingest_gamelogs_for_players(
    player_list: list[dict],  # [{"player_id": int, "mlb_id": int, "position": str}, ...]
    season: int,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> dict:
    """
    Fetch, score, and append game logs for a list of players.

    If start_date/end_date are not provided, fetches the full season.
    Returns a summary dict with counts.
    """
    all_rows: list[dict] = []
    errors: list[int] = []

    for player_info in player_list:
        player_id = player_info["player_id"]
        mlb_id = player_info["mlb_id"]
        position = player_info["position"]

        splits = fetch_player_gamelogs(mlb_id, season, start_date, end_date)
        if not splits:
            continue

        for split in splits:
            stat_group = split.get("group", {}).get("displayName", "").lower()
            if position == "P" and stat_group == "pitching":
                row = parse_pitching_split(split, player_id, mlb_id, season)
            elif position in {"IF", "OF"} and stat_group == "hitting":
                row = parse_hitting_split(split, player_id, mlb_id, position, season)
            else:
                continue

            if row:
                all_rows.append(row)
            else:
                errors.append(player_id)

    if all_rows:
        df = pd.DataFrame(all_rows)
        # Normalize date format to YYYY-MM-DD
        df["game_date"] = pd.to_datetime(df["game_date"]).dt.strftime("%Y-%m-%d")
        append_gamelogs(season, df)
        logger.info(f"Appended {len(all_rows)} game log rows for season {season}")

    return {
        "rows_written": len(all_rows),
        "players_processed": len(player_list),
        "parse_errors": len(errors),
    }


# ---------------------------------------------------------------------------
# Nightly incremental ingest (previous day only)
# ---------------------------------------------------------------------------

def ingest_yesterday(
    player_list: list[dict],
    season: int,
) -> dict:
    """Fetch only the previous day's game logs."""
    yesterday = (date.today() - timedelta(days=1)).strftime("%m/%d/%Y")
    return ingest_gamelogs_for_players(
        player_list, season, start_date=yesterday, end_date=yesterday
    )
