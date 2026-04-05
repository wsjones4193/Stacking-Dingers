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

from backend.constants import (
    GHOST_PLAYER_DAYS,
    BELOW_REPLACEMENT_WEEKS,
    PITCHER_BAD_ERA_THRESHOLD,
    SEASON_START_2026,
    SEASON_END_2026,
    WEEK_MAP_2026,
)
from backend.db.models import (
    AdpSnapshot,
    Draft,
    GroupStanding,
    Pick,
    Player,
    PlayerIdMap,
    RosterFlag,
    ScoreAudit,
    WeeklyScore,
    create_db_and_tables,
)
from backend.db.parquet_helpers import load_gamelogs_week, load_gamelogs_for_player
from backend.etl.game_logs import ingest_yesterday
from backend.etl.projections import refresh_projections, OPENING_DAY_2026
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
# Step 5: Recalculate ADP from current draft data
# ---------------------------------------------------------------------------

def recalculate_adp_snapshots(season: int, session: Session) -> dict:
    """
    Compute today's ADP and draft rate for every player in the season,
    based on cumulative picks in the drafts table, and upsert adp_snapshots.

    ADP = average pick_number across all drafts that include the player.
    draft_rate = (drafts containing player) / (total drafts this season).
    """
    today = date.today()

    total_drafts = len(session.exec(select(Draft).where(Draft.season == season)).all())
    if total_drafts == 0:
        logger.warning("No drafts found for ADP calculation")
        return {"players_updated": 0}

    # Aggregate pick data per player
    all_picks = session.exec(
        select(Pick, Draft)
        .join(Draft, Pick.draft_id == Draft.draft_id)
        .where(Draft.season == season)
    ).all()

    pick_data: dict[int, list[int]] = {}   # player_id → [pick_numbers]
    for pick, _ in all_picks:
        pick_data.setdefault(pick.player_id, []).append(pick.pick_number)

    players_updated = 0
    for player_id, pick_numbers in pick_data.items():
        adp_val = round(sum(pick_numbers) / len(pick_numbers), 2)
        draft_rate_val = round(len(pick_numbers) / total_drafts, 4)

        # Delete any existing snapshot for today to avoid duplicates
        existing = session.exec(
            select(AdpSnapshot)
            .where(AdpSnapshot.player_id == player_id)
            .where(AdpSnapshot.season == season)
            .where(AdpSnapshot.snapshot_date == today)
        ).first()
        if existing:
            session.delete(existing)

        snapshot = AdpSnapshot(
            player_id=player_id,
            snapshot_date=today,
            season=season,
            adp=adp_val,
            draft_rate=draft_rate_val,
        )
        session.add(snapshot)
        players_updated += 1

    session.commit()
    return {"players_updated": players_updated, "total_drafts": total_drafts}


# ---------------------------------------------------------------------------
# Step 6: Update roster flags
# ---------------------------------------------------------------------------

def update_roster_flags(season: int, today: date, session: Session) -> dict:
    """
    Generate RosterFlag entries for all active teams. Replaces flags for current week.

    Flag types:
      ghost_player         : player has 0 games in last GHOST_PLAYER_DAYS days
      below_replacement    : 0 BPCOR for BELOW_REPLACEMENT_WEEKS consecutive weeks
      pitcher_trending_bad : pitcher averaged ERA > PITCHER_BAD_ERA_THRESHOLD last 3 starts
    """
    from datetime import timedelta

    # Find current week
    current_week = None
    for week_num, (wstart, wend, _) in WEEK_MAP_2026.items():
        if wstart <= today <= wend:
            current_week = week_num
            break
    if current_week is None:
        logger.info("No active week found for roster flags — skipping")
        return {"flags_created": 0}

    # Delete existing flags for current week + season before regenerating
    existing_flags = session.exec(
        select(RosterFlag)
        .where(RosterFlag.season == season)
        .where(RosterFlag.week_number == current_week)
    ).all()
    for f in existing_flags:
        session.delete(f)

    drafts = session.exec(select(Draft).where(Draft.season == season)).all()
    flags_created = 0
    cutoff_date = today - timedelta(days=GHOST_PLAYER_DAYS)

    for draft in drafts:
        picks = session.exec(
            select(Pick).where(Pick.draft_id == draft.draft_id)
        ).all()
        player_ids = [p.player_id for p in picks]

        for player_id in player_ids:
            player = session.get(Player, player_id)
            if not player:
                continue

            # Ghost player: check game logs for recent activity
            recent_logs = load_gamelogs_for_player(season, player_id)
            if not recent_logs.empty:
                recent_activity = recent_logs[
                    recent_logs["game_date"] >= str(cutoff_date)
                ]
                if recent_activity.empty:
                    flag = RosterFlag(
                        draft_id=draft.draft_id,
                        week_number=current_week,
                        season=season,
                        player_id=player_id,
                        flag_type="ghost_player",
                        flag_reason=f"No games in last {GHOST_PLAYER_DAYS} days",
                    )
                    session.add(flag)
                    flags_created += 1

            # Below replacement: check last N consecutive weekly_scores weeks
            recent_ws = session.exec(
                select(WeeklyScore)
                .where(WeeklyScore.draft_id == draft.draft_id)
                .where(WeeklyScore.player_id == player_id)
                .where(WeeklyScore.season == season)
                .order_by(WeeklyScore.week_number.desc())
                .limit(BELOW_REPLACEMENT_WEEKS)
            ).all()

            if len(recent_ws) >= BELOW_REPLACEMENT_WEEKS:
                all_zero_or_bench = all(
                    ws.is_bench or ws.calculated_score == 0.0
                    for ws in recent_ws
                )
                if all_zero_or_bench:
                    flag = RosterFlag(
                        draft_id=draft.draft_id,
                        week_number=current_week,
                        season=season,
                        player_id=player_id,
                        flag_type="below_replacement",
                        flag_reason=f"0 BPCOR for {BELOW_REPLACEMENT_WEEKS} consecutive weeks",
                    )
                    session.add(flag)
                    flags_created += 1

    session.commit()
    return {"flags_created": flags_created, "week": current_week}


# ---------------------------------------------------------------------------
# Step 9: Score audit — log discrepancies between calculated and Underdog scores
# ---------------------------------------------------------------------------

def generate_score_audit(season: int, session: Session) -> dict:
    """
    Compare calculated_score vs underdog_score for all WeeklyScore rows
    where underdog_score is populated. Log any delta >= 0.5 to score_audit.
    """
    ws_rows = session.exec(
        select(WeeklyScore)
        .where(WeeklyScore.season == season)
        .where(WeeklyScore.underdog_score.is_not(None))
    ).all()

    discrepancies = 0
    for ws in ws_rows:
        delta = round(ws.calculated_score - (ws.underdog_score or 0.0), 2)
        if abs(delta) < 0.5:
            continue

        # Check if audit entry already exists
        existing = session.exec(
            select(ScoreAudit)
            .where(ScoreAudit.player_id == ws.player_id)
            .where(ScoreAudit.draft_id == ws.draft_id)
            .where(ScoreAudit.week_number == ws.week_number)
            .where(ScoreAudit.season == season)
        ).first()
        if existing:
            existing.delta = delta
            existing.calculated_score = ws.calculated_score
            existing.underdog_score = ws.underdog_score
            session.add(existing)
        else:
            audit = ScoreAudit(
                player_id=ws.player_id,
                draft_id=ws.draft_id,
                week_number=ws.week_number,
                season=season,
                calculated_score=ws.calculated_score,
                underdog_score=ws.underdog_score,
                delta=delta,
            )
            session.add(audit)
            discrepancies += 1

    session.commit()
    return {"discrepancies_logged": discrepancies}


# ---------------------------------------------------------------------------
# Fangraphs ID mapping loader
# ---------------------------------------------------------------------------

FANGRAPHS_MAP_PATH = Path("data/fangraphs_player_map.csv")


def load_fangraphs_id_map() -> dict[str, int]:
    """
    Load the admin-maintained Fangraphs playerid → internal player_id mapping.

    File format (CSV): fangraphs_id,player_id
    This file is maintained alongside player_id_map and committed to the repo.
    Returns an empty dict if the file does not exist (projections will be skipped).
    """
    if not FANGRAPHS_MAP_PATH.exists():
        logger.warning(
            f"Fangraphs player map not found at {FANGRAPHS_MAP_PATH} — "
            "projections will be skipped. Create this file to enable projection ingestion."
        )
        return {}

    import csv
    mapping: dict[str, int] = {}
    with open(FANGRAPHS_MAP_PATH, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            fg_id = str(row.get("fangraphs_id", "")).strip()
            player_id_str = str(row.get("player_id", "")).strip()
            if fg_id and player_id_str.isdigit():
                mapping[fg_id] = int(player_id_str)
    logger.info(f"Loaded {len(mapping)} Fangraphs ID mappings")
    return mapping


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

        # Step 5: Recalculate ADP snapshots
        logger.info("Step 5: Recalculating ADP snapshots")
        adp_result = recalculate_adp_snapshots(season, session)
        logger.info(f"ADP snapshots: {adp_result}")

        # Step 6: Update roster flags
        logger.info("Step 6: Updating roster flags")
        flags_result = update_roster_flags(season, today, session)
        logger.info(f"Roster flags: {flags_result}")

        # Step 6b: Refresh projections (preseason = all sources; in-season = RoS only)
        logger.info("Step 6b: Refreshing projections")
        fg_map = load_fangraphs_id_map()
        if fg_map:
            is_preseason = today <= OPENING_DAY_2026
            proj_results = refresh_projections(season, session, fg_map, is_preseason=is_preseason)
            logger.info(f"Projections: {proj_results}")
        else:
            logger.info("Projections skipped — no Fangraphs ID map available")

        # Step 7: Update group standings
        logger.info("Step 7: Updating group standings")
        standings_result = update_group_standings(season, session)
        logger.info(f"Group standings: {standings_result}")

        # Step 8: Recompute team season profiles
        logger.info("Step 8: Recomputing team season profiles")
        profile_result = compute_and_store_team_profiles(season, session)
        logger.info(f"Team profiles: {profile_result}")

        # Step 9: Score audit
        logger.info("Step 9: Generating score audit")
        audit_result = generate_score_audit(season, session)
        logger.info(f"Score audit: {audit_result}")

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
