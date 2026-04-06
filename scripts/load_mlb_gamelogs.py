"""
Full-MLB game log loader — independent of Underdog draft data.

Pulls game logs for ALL players who appeared in MLB games for each requested
season. Scores every game appearance using Underdog best ball scoring rules.
Writes one Parquet per season to data/gamelogs/{season}.parquet.

Schema (keyed on mlb_id + game_date):
  mlb_id, player_name, position, season, game_date,
  pa, ab, h, singles, doubles, triples, home_runs,
  runs, rbi, stolen_bases, walks, hit_by_pitch,
  ip, ip_true, earned_runs, strikeouts, wins, qs_flag,
  calculated_points

The Underdog player_id is NOT stored here — join at query time via
player_id_map.mlb_id when you need to link to draft/roster data.

Usage:
  python scripts/load_mlb_gamelogs.py --seasons 2022 2023 2024 2025
  python scripts/load_mlb_gamelogs.py --seasons 2025          # single year
  python scripts/load_mlb_gamelogs.py --seasons 2022 --force  # overwrite existing
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import statsapi

from backend.services.scoring import (
    ip_to_true_innings,
    score_hitter_row,
    score_pitcher_row,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

GAMELOGS_DIR = Path("data/gamelogs")

# MLB Stats API season start/end dates (used to bound the roster pull)
SEASON_BOUNDS = {
    2022: ("2022-04-07", "2022-10-05"),
    2023: ("2023-03-30", "2023-10-01"),
    2024: ("2024-03-20", "2024-09-29"),
    2025: ("2025-03-18", "2025-09-28"),
    2026: ("2026-03-26", "2026-09-27"),
}

# Positions we score — pitchers and position players only
# Two-way players (e.g. Ohtani) will appear in both hitting and pitching
POSITION_GROUP_MAP = {
    "hitting": "hitter",
    "pitching": "pitcher",
}


# ---------------------------------------------------------------------------
# Step 1 — Get all players who appeared in games for a season
# ---------------------------------------------------------------------------

def get_all_mlb_players(season: int) -> list[dict]:
    """
    Fetch all players who were on an active roster at any point in the season.
    Returns list of {mlb_id, name, position_type} dicts.
    position_type: "P" for pitchers, "H" for hitters (two-way players get both).
    """
    logger.info(f"Fetching player roster for {season}...")
    try:
        # Get all players on 40-man rosters + active during the season
        data = statsapi.get("sports_players", {
            "season": season,
            "gameType": "R",  # Regular season
        })
        players = data.get("people", [])
    except Exception as e:
        logger.error(f"Failed to fetch player list for {season}: {e}")
        return []

    result = []
    for p in players:
        mlb_id = p.get("id")
        name = p.get("fullName", "Unknown")
        pos = p.get("primaryPosition", {}).get("abbreviation", "")

        if not mlb_id:
            continue

        # Classify position
        if pos == "P" or pos == "TWP":
            result.append({"mlb_id": mlb_id, "name": name, "position": "P"})
        else:
            # All non-pitchers: classify as hitter
            # Store the actual position abbreviation (1B, 2B, SS, 3B, OF, C, DH)
            result.append({"mlb_id": mlb_id, "name": name, "position": pos})

    # Two-way players: add them as pitchers too if their primary position isn't P
    # Ohtani-type players — we'll catch them via the pitching stat group
    logger.info(f"Found {len(result)} players for {season}")
    return result


# ---------------------------------------------------------------------------
# Step 2 — Fetch and parse game logs for a single player
# ---------------------------------------------------------------------------

def fetch_and_score_player(
    mlb_id: int,
    name: str,
    position: str,
    season: int,
) -> list[dict]:
    """
    Fetch all game logs for a player in a season.
    Returns a list of scored row dicts.
    Handles two-way players by scoring both hitting and pitching splits.
    """
    try:
        data = statsapi.get("people", {
            "personIds": mlb_id,
            "hydrate": f"stats(group=[hitting,pitching],type=gameLog,season={season})",
        })
        people = data.get("people", [])
        if not people:
            return []
        stats = people[0].get("stats", [])
    except Exception as e:
        logger.warning(f"  Failed to fetch {name} ({mlb_id}): {e}")
        return []

    rows = []
    for stat_group in stats:
        group_name = stat_group.get("group", {}).get("displayName", "").lower()
        splits = stat_group.get("splits", [])

        for split in splits:
            game_date = split.get("date", "")
            if not game_date:
                continue

            s = split.get("stat", {})

            if group_name == "hitting":
                h = int(s.get("hits", 0))
                doubles = int(s.get("doubles", 0))
                triples = int(s.get("triples", 0))
                home_runs = int(s.get("homeRuns", 0))
                singles = max(0, h - doubles - triples - home_runs)

                row = {
                    "mlb_id": mlb_id,
                    "player_name": name,
                    "position": position if position != "P" else "DH",
                    "season": season,
                    "game_date": game_date,
                    "stat_type": "hitting",
                    "pa": int(s.get("plateAppearances", 0)),
                    "ab": int(s.get("atBats", 0)),
                    "h": h,
                    "singles": singles,
                    "doubles": doubles,
                    "triples": triples,
                    "home_runs": home_runs,
                    "runs": int(s.get("runs", 0)),
                    "rbi": int(s.get("rbi", 0)),
                    "stolen_bases": int(s.get("stolenBases", 0)),
                    "walks": int(s.get("baseOnBalls", 0)),
                    "hit_by_pitch": int(s.get("hitByPitch", 0)),
                    "ip": 0.0,
                    "ip_true": 0.0,
                    "earned_runs": 0,
                    "strikeouts": 0,
                    "wins": 0,
                    "qs_flag": 0,
                }
                row["calculated_points"] = score_hitter_row(row)
                rows.append(row)

            elif group_name == "pitching":
                ip_str = str(s.get("inningsPitched", "0.0"))
                try:
                    ip = float(ip_str)
                except ValueError:
                    ip = 0.0

                earned_runs = int(s.get("earnedRuns", 0))
                pitch_row = {
                    "ip": ip,
                    "earned_runs": earned_runs,
                    "strikeouts": int(s.get("strikeOuts", 0)),
                    "wins": 1 if s.get("wins", 0) else 0,
                }
                pts, qs = score_pitcher_row(pitch_row)

                row = {
                    "mlb_id": mlb_id,
                    "player_name": name,
                    "position": "P",
                    "season": season,
                    "game_date": game_date,
                    "stat_type": "pitching",
                    "pa": 0, "ab": 0, "h": 0, "singles": 0,
                    "doubles": 0, "triples": 0, "home_runs": 0,
                    "runs": 0, "rbi": 0, "stolen_bases": 0,
                    "walks": 0, "hit_by_pitch": 0,
                    "ip": ip,
                    "ip_true": ip_to_true_innings(ip),
                    "earned_runs": earned_runs,
                    "strikeouts": pitch_row["strikeouts"],
                    "wins": pitch_row["wins"],
                    "qs_flag": qs,
                    "calculated_points": pts,
                }
                rows.append(row)

    return rows


# ---------------------------------------------------------------------------
# Step 3 — Load a full season
# ---------------------------------------------------------------------------

def load_season(season: int, force: bool = False) -> None:
    out_path = GAMELOGS_DIR / f"{season}.parquet"
    GAMELOGS_DIR.mkdir(parents=True, exist_ok=True)

    if out_path.exists() and not force:
        existing = pd.read_parquet(out_path)
        logger.info(
            f"Season {season} already has {len(existing):,} rows. "
            f"Use --force to overwrite."
        )
        return

    players = get_all_mlb_players(season)
    if not players:
        logger.error(f"No players found for {season}, skipping.")
        return

    all_rows: list[dict] = []
    errors = 0
    total = len(players)

    for i, p in enumerate(players, 1):
        mlb_id = p["mlb_id"]
        name = p["name"]
        position = p["position"]

        if i % 50 == 0 or i == total:
            logger.info(f"  {i}/{total} players processed ({len(all_rows):,} rows so far)...")

        rows = fetch_and_score_player(mlb_id, name, position, season)
        if rows:
            all_rows.extend(rows)
        else:
            errors += 1

        # Polite rate limiting — MLB Stats API is free but has rate limits
        time.sleep(0.1)

    if not all_rows:
        logger.error(f"No rows collected for {season}.")
        return

    df = pd.DataFrame(all_rows)
    df["game_date"] = pd.to_datetime(df["game_date"]).dt.strftime("%Y-%m-%d")

    # Deduplicate: keep one row per (mlb_id, game_date, stat_type)
    # Two-way players legitimately have both a hitting and pitching row per game
    df = df.drop_duplicates(subset=["mlb_id", "game_date", "stat_type"], keep="last")
    df = df.sort_values(["mlb_id", "game_date"]).reset_index(drop=True)

    # Enforce column order
    col_order = [
        "mlb_id", "player_name", "position", "season", "game_date", "stat_type",
        "pa", "ab", "h", "singles", "doubles", "triples", "home_runs",
        "runs", "rbi", "stolen_bases", "walks", "hit_by_pitch",
        "ip", "ip_true", "earned_runs", "strikeouts", "wins", "qs_flag",
        "calculated_points",
    ]
    df = df[col_order]

    df.to_parquet(out_path, index=False)

    unique_players = df["mlb_id"].nunique()
    date_min = df["game_date"].min()
    date_max = df["game_date"].max()
    logger.info(
        f"Season {season}: wrote {len(df):,} rows, "
        f"{unique_players} players, {date_min} to {date_max} "
        f"({errors} players with no data)"
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Load full-MLB game logs by season")
    parser.add_argument(
        "--seasons",
        nargs="+",
        type=int,
        default=[2022, 2023, 2024, 2025],
        help="Seasons to load (default: 2022 2023 2024 2025)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing Parquet files",
    )
    args = parser.parse_args()

    for season in args.seasons:
        logger.info(f"=== Loading season {season} ===")
        load_season(season, force=args.force)

    logger.info("Done.")


if __name__ == "__main__":
    main()
