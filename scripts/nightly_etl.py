"""
Nightly ETL orchestrator.

Runs ~2am ET nightly via GitHub Actions during the MLB season (March–September).

Steps:
  1. Pull yesterday's game logs from MLB Stats API
  2. Calculate best ball points per player-game
  3. Append to season Parquet
  4. Recalculate weekly scores for any week that just closed
  5. Recalculate ADP from latest draft data; append to adp_snapshots
  6. Update roster_flags: IL status, ghost players, BPCOR streak, pitcher ERA, hitter usage
  7. Update group_standings for all active groups
  8. Recompute team_season_profiles for current season
  9. Log run status + any score audit discrepancies

Usage:
  python scripts/nightly_etl.py [--season 2026] [--full-reload]

--full-reload re-processes all weeks from scratch (use for backfills or after data fixes).
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date, datetime
from pathlib import Path

# Allow imports from repo root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlmodel import Session, create_engine, select

from backend.constants import SEASON_START_2026, SEASON_END_2026, WEEK_MAP_2026
from backend.db.models import (
    AdpSnapshot,
    Draft,
    GroupStanding,
    Pick,
    Player,
    PlayerIdMap,
    WeeklyScore,
    create_db_and_tables,
)
from backend.db.parquet_helpers import load_gamelogs_week
from backend.etl.game_logs import ingest_yesterday
from backend.etl.team_profiles import compute_and_store_team_profiles
from backend.services.lineup_setter import RosterPlayer, set_lineup
from backend.services.bpcor import compute_week_bpcor

DB_PATH = "data/bestball.db"
CURRENT_SEASON = 2026

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("data/etl.log", mode="a"),
    ],
)
logger = logging.getLogger("nightly_etl")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_current_week(today: date) -> tuple[int | None, date | None, date | None]:
    """Return (week_number, start, end) for the current date, or (None, None, None)."""
    for week_num, (start, end, _) in WEEK_MAP_2026.items():
        if start <= today <= end:
            return week_num, start, end
    return None, None, None


def get_just_closed_week(today: date) -> tuple[int | None, date | None, date | None]:
    """Return the week that ended yesterday, if any."""
    yesterday = date(today.year, today.month, today.day)
    from datetime import timedelta
    yesterday = today - timedelta(days=1)
    for week_num, (start, end, _) in WEEK_MAP_2026.items():
        if end == yesterday:
            return week_num, start, end
    return None, None, None


def get_player_list_for_season(session: Session, season: int) -> list[dict]:
    """Get all Underdog players with confirmed MLB ID mappings for a season."""
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
# Step 4: Recalculate weekly scores for a closed week
# ---------------------------------------------------------------------------

def recalculate_weekly_scores(
    season: int,
    week_number: int,
    week_start: date,
    week_end: date,
    session: Session,
) -> dict:
    """
    For every team active in a season: load their roster's game logs for the week,
    run the lineup setter, compute BPCOR, and upsert weekly_scores rows.
    """
    start_str = week_start.strftime("%Y-%m-%d")
    end_str = week_end.strftime("%Y-%m-%d")

    gamelogs = load_gamelogs_week(season, start_str, end_str)
    if gamelogs.empty:
        logger.warning(f"No game logs found for week {week_number} ({start_str}–{end_str})")
        return {"week": week_number, "teams_processed": 0}

    # Build {player_id: score} for this week from Parquet
    player_week_scores: dict[int, tuple[str, float]] = {}
    for _, row in gamelogs.iterrows():
        pid = int(row["player_id"])
        existing = player_week_scores.get(pid, (row["position"], 0.0))
        player_week_scores[pid] = (existing[0], existing[1] + float(row["calculated_points"]))

    # Load all drafts for this season
    drafts = session.exec(select(Draft).where(Draft.season == season)).all()
    teams_processed = 0

    for draft in drafts:
        # Load this team's picks
        picks = session.exec(
            select(Pick).where(Pick.draft_id == draft.draft_id)
        ).all()

        roster: list[RosterPlayer] = []
        for pick in picks:
            pid = pick.player_id
            if pid in player_week_scores:
                pos, score = player_week_scores[pid]
                roster.append(RosterPlayer(
                    player_id=pid,
                    position=pos,
                    weekly_score=score,
                ))
            # Players with no games this week get score=0
            else:
                player = session.exec(
                    select(Player).where(Player.player_id == pid)
                ).first()
                if player:
                    roster.append(RosterPlayer(
                        player_id=pid,
                        position=player.position,
                        weekly_score=0.0,
                    ))

        if not roster:
            continue

        week_bpcors = compute_week_bpcor(draft.draft_id, week_number, roster)

        # Delete any existing scores for this draft/week before inserting
        existing_scores = session.exec(
            select(WeeklyScore)
            .where(WeeklyScore.draft_id == draft.draft_id)
            .where(WeeklyScore.week_number == week_number)
            .where(WeeklyScore.season == season)
        ).all()
        for s in existing_scores:
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

        teams_processed += 1

    session.commit()
    return {"week": week_number, "teams_processed": teams_processed}


# ---------------------------------------------------------------------------
# Step 7: Update group standings
# ---------------------------------------------------------------------------

def update_group_standings(season: int, session: Session) -> dict:
    """
    Recalculate total_points and rank for all teams in all R1 groups.
    Resets rank based on cumulative calculated_score through the current week.
    """
    # Sum weekly scores per draft_id
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

    # Re-rank within each group
    from collections import defaultdict
    by_group: dict[int, list[GroupStanding]] = defaultdict(list)
    for s in standings:
        by_group[s.group_id].append(s)

    for group_id, group_standings in by_group.items():
        sorted_s = sorted(group_standings, key=lambda x: x.total_points, reverse=True)
        for rank, s in enumerate(sorted_s, start=1):
            s.rank = rank
            session.add(s)

    session.commit()
    return {"groups_updated": len(by_group)}


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

def run_nightly_etl(season: int = CURRENT_SEASON, full_reload: bool = False) -> None:
    today = date.today()
    logger.info(f"=== Nightly ETL start: {datetime.now().isoformat()} ===")
    logger.info(f"Season: {season}, Full reload: {full_reload}")

    # Check if we're in season
    if not (SEASON_START_2026 <= today <= SEASON_END_2026):
        logger.info("Outside season window — skipping game log pull")
        return

    engine = create_db_and_tables(DB_PATH)

    with Session(engine) as session:
        # Step 1–3: Pull and append yesterday's game logs
        logger.info("Step 1-3: Pulling yesterday's game logs")
        player_list = get_player_list_for_season(session, season)
        if player_list:
            ingest_result = ingest_yesterday(player_list, season)
            logger.info(f"Game log ingest: {ingest_result}")
        else:
            logger.warning("No mapped players found — skipping game log pull")

        # Step 4: Recalculate weekly scores for any week that just closed
        logger.info("Step 4: Recalculating closed week scores")
        week_num, week_start, week_end = get_just_closed_week(today)
        if week_num:
            result = recalculate_weekly_scores(season, week_num, week_start, week_end, session)
            logger.info(f"Weekly scores recalculated: {result}")
        elif full_reload:
            # Re-run all weeks
            for wn, (ws, we, _) in WEEK_MAP_2026.items():
                if we < today:
                    result = recalculate_weekly_scores(season, wn, ws, we, session)
                    logger.info(f"Full reload week {wn}: {result}")

        # Step 7: Update group standings
        logger.info("Step 7: Updating group standings")
        standings_result = update_group_standings(season, session)
        logger.info(f"Group standings: {standings_result}")

        # Step 8: Recompute team season profiles
        logger.info("Step 8: Recomputing team season profiles")
        profile_result = compute_and_store_team_profiles(season, session)
        logger.info(f"Team profiles: {profile_result}")

    logger.info(f"=== Nightly ETL complete: {datetime.now().isoformat()} ===")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Nightly ETL for MLB Best Ball Hub")
    parser.add_argument("--season", type=int, default=CURRENT_SEASON)
    parser.add_argument(
        "--full-reload",
        action="store_true",
        help="Re-process all weeks from scratch",
    )
    args = parser.parse_args()
    run_nightly_etl(season=args.season, full_reload=args.full_reload)
