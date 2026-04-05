"""
One-time historical data loader for MLB Best Ball Hub.

Loads 2022–2025 Underdog draft CSVs, pulls MLB game logs for all
mapped players, calculates weekly scores, and computes team profiles.

Usage:
  python scripts/load_historical.py --csv-dir <path-to-csvs>

  # Skip game log fetching (useful for re-running after game logs are cached)
  python scripts/load_historical.py --csv-dir <path> --skip-gamelogs

  # Load only specific seasons
  python scripts/load_historical.py --csv-dir <path> --seasons 2024 2025

CSV files must be named {season}.csv (e.g. 2022.csv, 2023.csv).
Download them from:
  2025: https://underdognetwork.com/baseball/analysis/mlb-best-ball-downloadable-pick-by-pick-data
  2024: https://underdognetwork.com/baseball/analysis/the-dinger-2024-downloadable-pick-by-pick-data
  2023: https://underdognetwork.com/baseball/analysis/downloadable-fantasy-baseball-pick-by-pick-data-the-dinger-2023
  2022: https://underdognetwork.com/baseball/news-and-lineups/downloadable-fantasy-baseball-pick-by-pick-data-the-dinger-2022
"""

from __future__ import annotations

import argparse
import logging
import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

# Allow imports from repo root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import statsapi  # mlb-statsapi
from sqlmodel import Session, create_engine, select

from backend.db.models import (
    AdpSnapshot,
    Draft,
    Group,
    GroupStanding,
    Pick,
    Player,
    PlayerIdMap,
    WeeklyScore,
    create_db_and_tables,
)
from backend.etl.draft_data import ingest_all_historical
from backend.etl.game_logs import ingest_gamelogs_for_players
from backend.etl.team_profiles import compute_and_store_team_profiles
from backend.services.lineup_setter import RosterPlayer, set_lineup
from backend.services.bpcor import compute_week_bpcor
from backend.db.parquet_helpers import load_gamelogs_week

DB_PATH = "data/bestball.db"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("load_historical")


# ---------------------------------------------------------------------------
# Historical season week maps
# Approximate boundaries based on actual Opening Day dates for each season.
# Week 17 spans 2 calendar weeks (All-Star break).
# Playoffs: R2 = wks 19-20, R3 = wks 21-22, Finals = wks 23-24.
# ---------------------------------------------------------------------------

def _build_week_map(
    opening_day: date,
    allstar_start: date,
) -> dict[int, tuple[date, date, int]]:
    """
    Generate a 24-week tournament calendar from an opening day date.

    Structure mirrors the 2026 calendar:
      - Week 1: opening day through Sunday (short first week)
      - Weeks 2–16: Monday–Sunday (7 days each)
      - Week 17: All-Star break week (2 calendar weeks = 14 days)
      - Weeks 18–24: Monday–Sunday (7 days each)
    """
    weeks: list[tuple[int, date, date, int]] = []

    # Week 1 ends on the nearest Sunday after opening day
    # Approximate: run week 1 through the first Sunday
    day = opening_day
    # Find first Sunday on or after opening_day (weekday 6 = Sunday)
    days_to_sunday = (6 - day.weekday()) % 7
    week1_end = day + timedelta(days=days_to_sunday if days_to_sunday else 6)
    weeks.append((1, opening_day, week1_end, 1))

    cursor = week1_end + timedelta(days=1)

    # Weeks 2–16 (regular 7-day weeks), skip over All-Star break with week 17
    for wk in range(2, 18):
        start = cursor
        if wk == 17:
            # Week 17 runs from Monday before All-Star through 2 weeks
            end = start + timedelta(days=13)
        else:
            end = start + timedelta(days=6)
        round_num = 1
        weeks.append((wk, start, end, round_num))
        cursor = end + timedelta(days=1)

    # Weeks 18–24 (post All-Star)
    for wk in range(18, 25):
        start = cursor
        end = start + timedelta(days=6)
        if wk in (19, 20):
            round_num = 2
        elif wk in (21, 22):
            round_num = 3
        elif wk in (23, 24):
            round_num = 4
        else:
            round_num = 1
        weeks.append((wk, start, end, round_num))
        cursor = end + timedelta(days=1)

    return {w: (s, e, r) for w, s, e, r in weeks}


# Approximate Opening Day dates for historical seasons
HISTORICAL_OPENING_DAYS = {
    2022: date(2022, 4, 7),   # delayed by lockout
    2023: date(2023, 3, 30),
    2024: date(2024, 3, 20),
    2025: date(2025, 3, 27),
}

HISTORICAL_ALLSTAR_STARTS = {
    2022: date(2022, 7, 11),
    2023: date(2023, 7, 10),
    2024: date(2024, 7, 15),
    2025: date(2025, 7, 14),
}

HISTORICAL_WEEK_MAPS: dict[int, dict[int, tuple[date, date, int]]] = {
    season: _build_week_map(
        HISTORICAL_OPENING_DAYS[season],
        HISTORICAL_ALLSTAR_STARTS[season],
    )
    for season in [2022, 2023, 2024, 2025]
}


# ---------------------------------------------------------------------------
# MLB player list fetch
# ---------------------------------------------------------------------------

def fetch_mlb_player_list() -> list[tuple[int, str]]:
    """
    Fetch all active MLB players from the Stats API.
    Returns a list of (mlb_id, full_name) tuples for fuzzy matching.
    """
    logger.info("Fetching MLB player list from Stats API …")
    try:
        data = statsapi.get("sports_players", {"sportId": 1, "season": 2025})
        players = data.get("people", [])
        result = [
            (int(p["id"]), p["fullName"])
            for p in players
            if "id" in p and "fullName" in p
        ]
        logger.info(f"  Fetched {len(result)} MLB players")
        return result
    except Exception as e:
        logger.warning(f"  Failed to fetch MLB player list: {e}")
        logger.warning("  Continuing without auto-matching — all mappings will need manual review")
        return []


# ---------------------------------------------------------------------------
# Game log ingestion for a season
# ---------------------------------------------------------------------------

def get_player_list_for_season(session: Session, season: int) -> list[dict]:
    """Get all Underdog players with an MLB ID mapping (confirmed or auto) for a season."""
    stmt = (
        select(PlayerIdMap, Player)
        .join(Player, PlayerIdMap.underdog_id == Player.underdog_id)
        .where(PlayerIdMap.season == season)
        .where(PlayerIdMap.mlb_id.is_not(None))
    )
    rows = session.exec(stmt).all()
    return [
        {
            "player_id": player.player_id,
            "mlb_id": mapping.mlb_id,
            "position": player.position,
        }
        for mapping, player in rows
    ]


# ---------------------------------------------------------------------------
# Weekly score calculation for historical seasons
# ---------------------------------------------------------------------------

def calculate_all_weekly_scores(
    season: int,
    session: Session,
    week_map: dict[int, tuple[date, date, int]],
) -> dict:
    """
    Calculate and store weekly best-ball scores for all teams in a season.
    Loops over all 24 weeks, loads game logs from Parquet, runs lineup setter.
    """
    total_teams = 0
    total_weeks = 0

    for week_number, (week_start, week_end, _round) in sorted(week_map.items()):
        start_str = week_start.strftime("%Y-%m-%d")
        end_str = week_end.strftime("%Y-%m-%d")

        gamelogs = load_gamelogs_week(season, start_str, end_str)
        if gamelogs.empty:
            logger.debug(f"  No game logs for week {week_number} ({start_str}–{end_str})")
            continue

        # Build {player_id: (position, score)} for this week
        player_week_scores: dict[int, tuple[str, float]] = {}
        for _, row in gamelogs.iterrows():
            pid = int(row["player_id"])
            pos = str(row["position"])
            pts = float(row.get("calculated_points", 0.0))
            existing_pos, existing_pts = player_week_scores.get(pid, (pos, 0.0))
            player_week_scores[pid] = (existing_pos, existing_pts + pts)

        # Load all drafts for this season
        drafts = session.exec(select(Draft).where(Draft.season == season)).all()
        teams_this_week = 0

        for draft in drafts:
            picks = session.exec(
                select(Pick).where(Pick.draft_id == draft.draft_id)
            ).all()

            roster: list[RosterPlayer] = []
            for pick in picks:
                pid = pick.player_id
                if pid in player_week_scores:
                    pos, score = player_week_scores[pid]
                else:
                    player = session.get(Player, pid)
                    pos = player.position if player else "IF"
                    score = 0.0
                roster.append(RosterPlayer(
                    player_id=pid,
                    position=pos,
                    weekly_score=score,
                ))

            if not roster:
                continue

            week_bpcors = compute_week_bpcor(draft.draft_id, week_number, roster)

            # Delete existing scores for this draft/week before inserting
            existing = session.exec(
                select(WeeklyScore)
                .where(WeeklyScore.draft_id == draft.draft_id)
                .where(WeeklyScore.week_number == week_number)
                .where(WeeklyScore.season == season)
            ).all()
            for s in existing:
                session.delete(s)

            for wb in week_bpcors:
                ws = WeeklyScore(
                    draft_id=draft.draft_id,
                    week_number=week_number,
                    season=season,
                    player_id=wb.player_id,
                    calculated_score=wb.weekly_score,
                    is_starter=wb.is_starter,
                    is_flex=wb.is_flex,
                    is_bench=wb.is_bench,
                )
                session.add(ws)

            teams_this_week += 1

        if teams_this_week:
            session.commit()
            logger.info(f"  Week {week_number}: scored {teams_this_week} teams")
            total_teams = max(total_teams, teams_this_week)
            total_weeks += 1

    return {"season": season, "weeks_calculated": total_weeks, "max_teams_per_week": total_teams}


# ---------------------------------------------------------------------------
# ADP snapshot for historical seasons
# ---------------------------------------------------------------------------

def calculate_adp_snapshot(season: int, snapshot_date: date, session: Session) -> dict:
    """
    Compute a single ADP snapshot from all drafts in a season.
    For historical loads, we store one snapshot at the end of the draft window.
    """
    total_drafts = len(session.exec(select(Draft).where(Draft.season == season)).all())
    if total_drafts == 0:
        return {"players_updated": 0}

    all_picks = session.exec(
        select(Pick, Draft)
        .join(Draft, Pick.draft_id == Draft.draft_id)
        .where(Draft.season == season)
    ).all()

    pick_data: dict[int, list[int]] = {}
    for pick, _ in all_picks:
        pick_data.setdefault(pick.player_id, []).append(pick.pick_number)

    players_updated = 0
    for player_id, pick_numbers in pick_data.items():
        adp_val = round(sum(pick_numbers) / len(pick_numbers), 2)
        draft_rate_val = round(len(pick_numbers) / total_drafts, 4)

        # Upsert: delete existing snapshot for this date if present
        existing = session.exec(
            select(AdpSnapshot)
            .where(AdpSnapshot.player_id == player_id)
            .where(AdpSnapshot.season == season)
            .where(AdpSnapshot.snapshot_date == snapshot_date)
        ).first()
        if existing:
            session.delete(existing)

        session.add(AdpSnapshot(
            player_id=player_id,
            snapshot_date=snapshot_date,
            season=season,
            adp=adp_val,
            draft_rate=draft_rate_val,
        ))
        players_updated += 1

    session.commit()
    return {"players_updated": players_updated, "total_drafts": total_drafts}


# ---------------------------------------------------------------------------
# Group assignment from cleaned CSV group_id column
# ---------------------------------------------------------------------------

def assign_r1_groups(season: int, session: Session, csv_path: str) -> dict:
    """
    Create R1 groups and standings using the group_id column from the cleaned CSV.

    For 2022/2023/2025: group_id is the real tournament pod ID (draft_id in raw data).
    For 2024:           group_id is also the real pod ID (same structure).
    Each group_id corresponds to a 12-team pod.

    Uses made_playoffs from the CSV to mark advancement rather than recomputing it.
    """
    # Check if groups already exist for this season
    existing = session.exec(
        select(Group).where(Group.season == season).where(Group.round_number == 1)
    ).all()
    if existing:
        logger.info(f"  R1 groups already exist for season {season} -- skipping")
        return {"groups": len(existing), "skipped": True}

    import pandas as pd
    logger.info(f"  Loading group assignments from {csv_path} ...")
    # Only need one row per team (draft_id + group_id + made_playoffs)
    df = pd.read_csv(
        csv_path,
        usecols=["draft_id", "group_id", "made_playoffs", "roster_points"],
        dtype=str,
    )
    # One row per team: take the first pick per draft_id
    team_groups = df.drop_duplicates("draft_id")[["draft_id", "group_id", "made_playoffs", "roster_points"]].copy()
    team_groups["made_playoffs"] = pd.to_numeric(team_groups["made_playoffs"], errors="coerce").fillna(0).astype(int)
    team_groups["roster_points"] = pd.to_numeric(team_groups["roster_points"], errors="coerce").fillna(0)

    # Verify teams are in the DB before creating groups
    known_draft_ids = {
        d.draft_id
        for d in session.exec(select(Draft).where(Draft.season == season)).all()
    }
    team_groups = team_groups[team_groups["draft_id"].isin(known_draft_ids)]

    groups_created = 0
    standings_created = 0

    for group_id_str, group_df in team_groups.groupby("group_id"):
        if pd.isna(group_id_str) or str(group_id_str).strip() == "":
            continue

        draft_ids = group_df["draft_id"].tolist()

        group = Group(season=season, round_number=1)
        group.team_ids = draft_ids
        session.add(group)
        session.flush()  # get auto-assigned group_id PK

        for _, row in group_df.iterrows():
            standing = GroupStanding(
                group_id=group.group_id,
                draft_id=row["draft_id"],
                round_number=1,
                season=season,
                total_points=float(row["roster_points"]),
                advanced=bool(row["made_playoffs"]),
            )
            session.add(standing)
            standings_created += 1

        groups_created += 1

    session.commit()
    logger.info(
        f"  Season {season}: created {groups_created} R1 groups "
        f"({standings_created} team standings)"
    )
    return {
        "groups": groups_created,
        "standings": standings_created,
        "drafts_assigned": standings_created,
    }


def update_group_standings_from_scores(season: int, session: Session) -> dict:
    """
    Sum weekly scores per team and update group standings total_points + rank.
    """
    all_scores = session.exec(
        select(WeeklyScore).where(WeeklyScore.season == season)
    ).all()

    totals: dict[str, float] = {}
    for ws in all_scores:
        if ws.is_starter or ws.is_flex:
            totals[ws.draft_id] = totals.get(ws.draft_id, 0.0) + ws.calculated_score

    standings = session.exec(
        select(GroupStanding).where(GroupStanding.season == season)
    ).all()

    for standing in standings:
        standing.total_points = round(totals.get(standing.draft_id, 0.0), 2)
        session.add(standing)
    session.commit()

    # Re-rank within each group, mark top 2 as advanced
    by_group: dict[int, list[GroupStanding]] = defaultdict(list)
    for s in standings:
        by_group[s.group_id].append(s)

    for group_standings in by_group.values():
        sorted_s = sorted(group_standings, key=lambda x: x.total_points, reverse=True)
        for rank, s in enumerate(sorted_s, start=1):
            s.rank = rank
            s.advanced = rank <= 2
            session.add(s)

    session.commit()
    return {"groups_updated": len(by_group)}


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def run(
    csv_dir: str,
    seasons: list[int],
    skip_gamelogs: bool = False,
) -> None:
    logger.info("=" * 60)
    logger.info("MLB Best Ball Hub — Historical Data Load")
    logger.info("=" * 60)

    # Initialize DB
    logger.info(f"\n[1/7] Initializing database at {DB_PATH}")
    Path("data/gamelogs").mkdir(parents=True, exist_ok=True)
    Path("data/adp_history").mkdir(parents=True, exist_ok=True)
    engine = create_db_and_tables(DB_PATH)
    logger.info("  DB initialized")

    # Fetch MLB player list for auto-matching
    logger.info("\n[2/7] Fetching MLB player list for name matching")
    mlb_players = fetch_mlb_player_list()

    # Ingest Underdog CSVs
    logger.info(f"\n[3/7] Ingesting Underdog CSVs from {csv_dir}")
    with Session(engine) as session:
        results = ingest_all_historical(csv_dir, session, mlb_players)
        for r in results:
            logger.info(f"  Season {r['season']}: "
                        f"{r['drafts_inserted']} drafts, "
                        f"{r['picks_inserted']} picks, "
                        f"{r['players_auto_matched']} auto-matched, "
                        f"{r['players_unmatched']} unmatched")

    if not results:
        logger.warning("No CSVs found — check that csv_dir contains {season}.csv files")
        return

    # Pull game logs
    if skip_gamelogs:
        logger.info("\n[4/7] Skipping game log fetch (--skip-gamelogs)")
    else:
        logger.info("\n[4/7] Fetching MLB game logs (this will take a while …)")
        with Session(engine) as session:
            for season in seasons:
                player_list = get_player_list_for_season(session, season)
                if not player_list:
                    logger.warning(f"  Season {season}: no mapped players found — skipping game logs")
                    continue
                logger.info(f"  Season {season}: fetching logs for {len(player_list)} players")
                result = ingest_gamelogs_for_players(player_list, season)
                logger.info(f"  Season {season}: {result}")

    # Calculate weekly scores
    logger.info("\n[5/7] Calculating weekly scores for all teams")
    with Session(engine) as session:
        for season in seasons:
            week_map = HISTORICAL_WEEK_MAPS.get(season)
            if not week_map:
                logger.warning(f"  No week map for season {season} — skipping")
                continue
            logger.info(f"  Season {season}: calculating weekly scores …")
            result = calculate_all_weekly_scores(season, session, week_map)
            logger.info(f"  Season {season}: {result}")

    # ADP snapshots
    logger.info("\n[6/7] Computing ADP snapshots")
    with Session(engine) as session:
        for season in seasons:
            # Use a date near the end of the draft window as the canonical snapshot
            snapshot_date = HISTORICAL_OPENING_DAYS.get(season, date(season, 4, 1))
            result = calculate_adp_snapshot(season, snapshot_date, session)
            logger.info(f"  Season {season}: {result['players_updated']} players, "
                        f"{result.get('total_drafts', 0)} drafts")

    # Assign groups + compute team profiles
    logger.info("\n[7/7] Assigning groups and computing team profiles")
    with Session(engine) as session:
        for season in seasons:
            csv_path = str(Path(csv_dir) / f"{season}.csv")
            logger.info(f"  Season {season}: assigning R1 groups from {csv_path} ...")
            groups_result = assign_r1_groups(season, session, csv_path)
            logger.info(f"    {groups_result}")

            # Group standings already populated with roster_points from CSV;
            # still rank within groups so rank field is set
            logger.info(f"  Season {season}: ranking within groups ...")
            standings_result = update_group_standings_from_scores(season, session)
            logger.info(f"    {standings_result}")

            logger.info(f"  Season {season}: computing team profiles ...")
            profiles_result = compute_and_store_team_profiles(season, session)
            logger.info(f"    {profiles_result}")

    logger.info("\n" + "=" * 60)
    logger.info("Historical data load complete!")
    logger.info("Next steps:")
    logger.info("  1. Review unmatched players at /admin/player-mapping")
    logger.info("  2. Confirm or correct any low-confidence fuzzy matches")
    logger.info("  3. Re-run with --skip-gamelogs --seasons <season> after fixing mappings")
    logger.info("     to re-fetch game logs for previously unmatched players")
    logger.info("=" * 60)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="One-time historical data loader for MLB Best Ball Hub"
    )
    parser.add_argument(
        "--csv-dir",
        required=True,
        help="Directory containing {season}.csv files (e.g. 2022.csv, 2025.csv)",
    )
    parser.add_argument(
        "--seasons",
        type=int,
        nargs="+",
        default=[2022, 2023, 2024, 2025],
        help="Seasons to load (default: all four historical seasons)",
    )
    parser.add_argument(
        "--skip-gamelogs",
        action="store_true",
        help="Skip the MLB Stats API game log fetch (use if already loaded)",
    )
    args = parser.parse_args()
    run(
        csv_dir=args.csv_dir,
        seasons=args.seasons,
        skip_gamelogs=args.skip_gamelogs,
    )
