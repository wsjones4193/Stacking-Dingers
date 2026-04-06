"""
Historical best ball scoring builder.

Reads the cleaned player mapping Excel files, updates player_id_map.mlb_id in
the DB, then computes weekly best ball scores for every draft in a season and
stores them in the weekly_scores table.

These records are treated as locked historical data — the nightly ETL will
not overwrite them (it only processes the current season going forward).

Usage:
  python scripts/build_historical_scoring.py --season 2025
  python scripts/build_historical_scoring.py --season 2025 --force  # re-compute even if scores exist

Week map:
  Uses approximate week boundaries by default.
  Once you have the actual tournament week dates, provide them via
  --week-csv path/to/weeks.csv with columns: week_number, start_date, end_date, round_number
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import sqlite3

from backend.services.lineup_setter import RosterPlayer, set_lineup
from backend.db.parquet_helpers import load_gamelogs_date_range

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

DB_PATH = Path("data/bestball.db")
MAPPING_DIR = Path("data/mapping")


# ---------------------------------------------------------------------------
# Week map — approximate boundaries (user will supply actual dates)
# ---------------------------------------------------------------------------

def _build_week_map(opening_day: date, allstar_start: date) -> dict[int, tuple[date, date, int]]:
    """Generate a 24-week tournament calendar from opening day."""
    weeks = []
    days_to_sunday = (6 - opening_day.weekday()) % 7
    week1_end = opening_day + timedelta(days=days_to_sunday if days_to_sunday else 6)
    weeks.append((1, opening_day, week1_end, 1))
    cursor = week1_end + timedelta(days=1)

    for wk in range(2, 18):
        start = cursor
        end = start + timedelta(days=13 if wk == 17 else 6)
        weeks.append((wk, start, end, 1))
        cursor = end + timedelta(days=1)

    for wk in range(18, 25):
        start = cursor
        end = start + timedelta(days=6)
        round_num = 2 if wk in (19, 20) else 3 if wk in (21, 22) else 4 if wk in (23, 24) else 1
        weeks.append((wk, start, end, round_num))
        cursor = end + timedelta(days=1)

    return {w: (s, e, r) for w, s, e, r in weeks}


SEASON_CONFIG = {
    2022: {"opening_day": date(2022, 4, 7),  "allstar": date(2022, 7, 11)},
    2023: {"opening_day": date(2023, 3, 30), "allstar": date(2023, 7, 10)},
    2024: {"opening_day": date(2024, 3, 20), "allstar": date(2024, 7, 15)},
    2025: {"opening_day": date(2025, 3, 27), "allstar": date(2025, 7, 14)},
}


def get_week_map(season: int, week_csv: Path | None = None) -> dict[int, tuple[date, date, int]]:
    """Load week map from CSV if provided, else use approximate calendar."""
    if week_csv and week_csv.exists():
        df = pd.read_csv(week_csv)
        wmap = {}
        for _, row in df.iterrows():
            wmap[int(row["week_number"])] = (
                date.fromisoformat(str(row["start_date"])[:10]),
                date.fromisoformat(str(row["end_date"])[:10]),
                int(row["round_number"]),
            )
        logger.info(f"Loaded {len(wmap)} weeks from {week_csv}")
        return wmap

    cfg = SEASON_CONFIG.get(season)
    if not cfg:
        raise ValueError(f"No season config for {season}. Provide --week-csv.")
    wmap = _build_week_map(cfg["opening_day"], cfg["allstar"])
    logger.info(f"Using approximate week map for {season} (provide --week-csv for exact boundaries)")
    return wmap


# ---------------------------------------------------------------------------
# Step 1 — Load cleaned mapping from Excel → update player_id_map in DB
# ---------------------------------------------------------------------------

def load_mapping_from_excel(season: int, conn: sqlite3.Connection) -> dict[str, int]:
    """
    Read cleaned mapping Excel for a season.
    Updates player_id_map.mlb_id where mlb_id is present and confirmed.
    Returns dict: underdog_player_id (UUID str) → mlb_id (int)
    """
    path = MAPPING_DIR / f"{season}_player_mapping.xlsx"
    if not path.exists():
        raise FileNotFoundError(f"Mapping file not found: {path}")

    df = pd.read_excel(path, sheet_name="mapping")
    # Only use rows with a valid mlb_id
    mapped = df[df["mlb_id"].notna() & (df["underdog_player_id"].notna())].copy()
    mapped["mlb_id"] = mapped["mlb_id"].astype(int)

    cur = conn.cursor()
    updated = 0
    mapping: dict[str, int] = {}

    for _, row in mapped.iterrows():
        ud_id = str(row["underdog_player_id"]).strip()
        mlb_id = int(row["mlb_id"])
        if not ud_id or ud_id == "nan":
            continue
        mapping[ud_id] = mlb_id

        # Update player_id_map
        cur.execute(
            "UPDATE player_id_map SET mlb_id=?, mlb_name=?, confirmed=1 WHERE underdog_id=? AND season=?",
            (mlb_id, str(row.get("mlb_player_name", "")), ud_id, season)
        )
        if cur.rowcount == 0:
            # Insert if not exists
            cur.execute(
                """INSERT OR IGNORE INTO player_id_map
                   (underdog_id, underdog_name, mlb_id, mlb_name, confirmed, match_score, season)
                   VALUES (?,?,?,?,1,?,?)""",
                (ud_id, str(row.get("ud_player_name", "")), mlb_id,
                 str(row.get("mlb_player_name", "")),
                 float(row.get("match_score", 0)), season)
            )
        updated += 1

    # Also update players.mlb_id
    cur.execute(
        """UPDATE players SET mlb_id = (
               SELECT m.mlb_id FROM player_id_map m
               WHERE m.underdog_id = players.underdog_id AND m.season = ? AND m.mlb_id IS NOT NULL
           )
           WHERE EXISTS (
               SELECT 1 FROM player_id_map m
               WHERE m.underdog_id = players.underdog_id AND m.season = ? AND m.mlb_id IS NOT NULL
           )""",
        (season, season)
    )

    conn.commit()
    logger.info(f"Mapping loaded: {len(mapping)} UD→MLB pairs for {season} ({updated} DB rows updated)")
    return mapping


# ---------------------------------------------------------------------------
# Step 2 — Build mlb_id lookup keyed from player_id
# ---------------------------------------------------------------------------

def build_player_mlb_lookup(season: int, conn: sqlite3.Connection) -> dict[int, tuple[int, str]]:
    """
    Returns dict: player_id → (mlb_id, position)
    Uses players.mlb_id if set, otherwise joins via player_id_map.
    """
    cur = conn.cursor()
    rows = cur.execute(
        """
        SELECT p.player_id, COALESCE(p.mlb_id, m.mlb_id), p.position
        FROM players p
        LEFT JOIN player_id_map m ON m.underdog_id = p.underdog_id AND m.season = ?
        WHERE COALESCE(p.mlb_id, m.mlb_id) IS NOT NULL
        """,
        (season,)
    ).fetchall()

    lookup = {row[0]: (row[1], row[2]) for row in rows}
    logger.info(f"Player→MLB lookup: {len(lookup)} players with MLB IDs for {season}")
    return lookup


# ---------------------------------------------------------------------------
# Step 3 — Compute and store weekly scores for all drafts in a season
# ---------------------------------------------------------------------------

def compute_weekly_scores(
    season: int,
    conn: sqlite3.Connection,
    week_map: dict[int, tuple[date, date, int]],
    player_mlb_lookup: dict[int, tuple[int, str]],
    force: bool = False,
) -> dict:
    """
    For each week, load game logs, score every draft, write to weekly_scores.
    Skips drafts that already have scores for that week (unless --force).
    """
    cur = conn.cursor()

    # Check existing coverage
    existing = cur.execute(
        "SELECT COUNT(*) FROM weekly_scores WHERE season=?", (season,)
    ).fetchone()[0]
    if existing > 0 and not force:
        logger.info(f"Season {season} already has {existing:,} weekly score rows. Use --force to recompute.")
        return {"skipped": True, "existing_rows": existing}

    if force and existing > 0:
        logger.info(f"--force: deleting {existing:,} existing weekly_score rows for {season}")
        cur.execute("DELETE FROM weekly_scores WHERE season=?", (season,))
        conn.commit()

    # Load all drafts + picks for the season into memory
    logger.info(f"Loading drafts and picks for {season}...")
    drafts = cur.execute(
        "SELECT draft_id FROM drafts WHERE season=?", (season,)
    ).fetchall()
    draft_ids = [r[0] for r in drafts]
    logger.info(f"  {len(draft_ids):,} drafts")

    # Load all picks: {draft_id: [(player_id, position), ...]}
    logger.info("Loading picks...")
    all_picks_rows = cur.execute(
        """SELECT p.draft_id, p.player_id
           FROM picks p
           JOIN drafts d ON p.draft_id = d.draft_id
           WHERE d.season = ?""",
        (season,)
    ).fetchall()

    draft_picks: dict[str, list[int]] = {}
    for draft_id, player_id in all_picks_rows:
        draft_picks.setdefault(draft_id, []).append(player_id)
    logger.info(f"  {len(all_picks_rows):,} picks across {len(draft_picks):,} drafts")

    total_rows = 0
    total_weeks_processed = 0

    for week_number, (week_start, week_end, round_number) in sorted(week_map.items()):
        start_str = week_start.strftime("%Y-%m-%d")
        end_str = week_end.strftime("%Y-%m-%d")

        # Load game logs for this week from parquet
        gamelogs = load_gamelogs_date_range(season, start_str, end_str)
        if gamelogs.empty:
            logger.debug(f"  Week {week_number}: no game logs ({start_str}–{end_str})")
            continue

        # Build mlb_id → (position, week_total_points) for this week
        # Sum across all games in the week per player
        mlb_week_scores: dict[int, tuple[str, float]] = {}
        for _, row in gamelogs.iterrows():
            mlb_id = int(row["mlb_id"])
            # Use position from game log (more accurate than player master)
            pos = str(row.get("position", ""))
            # Normalize position to P/IF/OF
            if pos == "P":
                norm_pos = "P"
            elif pos in ("CF", "LF", "RF", "OF"):
                norm_pos = "OF"
            else:
                norm_pos = "IF"  # 1B, 2B, 3B, SS, C, DH, etc.

            pts = float(row.get("calculated_points", 0.0))
            existing_pos, existing_pts = mlb_week_scores.get(mlb_id, (norm_pos, 0.0))
            mlb_week_scores[mlb_id] = (existing_pos, existing_pts + pts)

        # Build player_id → (position, week_score) via mlb lookup
        player_week_scores: dict[int, tuple[str, float]] = {}
        for player_id, (mlb_id, ud_position) in player_mlb_lookup.items():
            if mlb_id in mlb_week_scores:
                _pos, score = mlb_week_scores[mlb_id]
                # Use Underdog position for lineup setting (P/IF/OF)
                if ud_position == "P":
                    norm_pos = "P"
                elif ud_position in ("OF",):
                    norm_pos = "OF"
                else:
                    norm_pos = "IF"
                player_week_scores[player_id] = (norm_pos, score)

        # Score each draft for this week
        week_rows: list[tuple] = []
        for draft_id in draft_ids:
            picks_for_draft = draft_picks.get(draft_id, [])
            if not picks_for_draft:
                continue

            # Build roster for lineup setter
            roster = []
            for pid in picks_for_draft:
                if pid in player_week_scores:
                    pos, score = player_week_scores[pid]
                    roster.append(RosterPlayer(
                        player_id=pid,
                        position=pos,
                        weekly_score=score,
                    ))
                else:
                    # Player had no game log this week — score 0
                    # Still need their position for lineup setting
                    if pid in player_mlb_lookup:
                        _, ud_pos = player_mlb_lookup[pid]
                        norm_pos = "P" if ud_pos == "P" else "OF" if ud_pos == "OF" else "IF"
                        roster.append(RosterPlayer(
                            player_id=pid,
                            position=norm_pos,
                            weekly_score=0.0,
                        ))

            if not roster:
                continue

            result = set_lineup(roster)

            starter_ids = {p.player_id for p in result.starters}
            flex_id = result.flex.player_id if result.flex else None

            for player in roster:
                is_starter = player.player_id in starter_ids
                is_flex = player.player_id == flex_id
                is_bench = not is_starter and not is_flex
                week_rows.append((
                    draft_id,
                    week_number,
                    season,
                    player.player_id,
                    round(player.weekly_score, 2),
                    is_starter,
                    is_flex,
                    is_bench,
                ))

        if week_rows:
            cur.executemany(
                """INSERT INTO weekly_scores
                   (draft_id, week_number, season, player_id, calculated_score,
                    is_starter, is_flex, is_bench)
                   VALUES (?,?,?,?,?,?,?,?)""",
                week_rows,
            )
            conn.commit()
            total_rows += len(week_rows)
            total_weeks_processed += 1
            logger.info(
                f"  Week {week_number:2d} ({start_str}–{end_str}): "
                f"{len(draft_ids):,} drafts scored, {len(week_rows):,} rows written"
            )

    logger.info(f"Season {season} complete: {total_rows:,} total rows across {total_weeks_processed} weeks")
    return {"total_rows": total_rows, "weeks_processed": total_weeks_processed}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Build historical best ball weekly scores")
    parser.add_argument("--season", type=int, required=True, help="Season to process (e.g. 2025)")
    parser.add_argument("--force", action="store_true", help="Delete and recompute existing scores")
    parser.add_argument("--week-csv", type=Path, default=None,
                        help="CSV with exact week boundaries (week_number, start_date, end_date, round_number)")
    parser.add_argument("--skip-mapping-update", action="store_true",
                        help="Skip Excel→DB mapping update (use existing DB mappings)")
    args = parser.parse_args()

    conn = sqlite3.connect(str(DB_PATH))

    # Step 1: Load cleaned mapping from Excel
    if not args.skip_mapping_update:
        mapping = load_mapping_from_excel(args.season, conn)
    else:
        logger.info("Skipping mapping update (--skip-mapping-update)")

    # Step 2: Build player_id → mlb_id lookup
    player_mlb_lookup = build_player_mlb_lookup(args.season, conn)

    # Step 3: Get week map
    week_map = get_week_map(args.season, args.week_csv)

    # Step 4: Compute and store weekly scores
    result = compute_weekly_scores(
        args.season, conn, week_map, player_mlb_lookup, force=args.force
    )

    conn.close()
    if result.get("skipped"):
        logger.info("Nothing to do. Run with --force to recompute.")
    else:
        logger.info(f"Done. {result.get('total_rows', 0):,} rows written.")


if __name__ == "__main__":
    main()
