"""
Stage 1 of the best ball scoring pipeline: pre-compute weekly best ball
scores for every MLB player, independent of any draft data.

Reads the season's game-log parquet ONCE, splits games into tournament weeks,
aggregates calculated_points by (mlb_id, stat_type) per week, and writes to
the player_weekly_scores table in SQLite.

This table is MLB-wide and position-agnostic. Position (P/IF/OF) lives in the
players table and is applied during draft scoring (Stage 2).

Two-way players like Ohtani get two rows per week:
  stat_type="hitting"  → cumulative hitting points
  stat_type="pitching" → cumulative pitching points
Stage 2 picks the right row based on the player's Underdog position.

Usage:
  python scripts/build_player_weekly_scores.py --seasons 2025 --week-csv data/weeks/2025_weeks.csv
  python scripts/build_player_weekly_scores.py --seasons 2022 2023 2024 2025 --force
"""

from __future__ import annotations

import argparse
import logging
import sqlite3
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

DB_PATH = Path("data/bestball.db")
GAMELOGS_DIR = Path("data/gamelogs")
WEEKS_DIR = Path("data/weeks")

# Approximate opening days per season — used only when no --week-csv is provided
SEASON_OPENING_DAYS: dict[int, date] = {
    2022: date(2022, 4, 7),
    2023: date(2023, 3, 30),
    2024: date(2024, 3, 20),
    2025: date(2025, 3, 27),
    2026: date(2026, 3, 26),
}


# ---------------------------------------------------------------------------
# Week map helpers
# ---------------------------------------------------------------------------

def load_week_map(season: int, week_csv: Path | None) -> dict[int, tuple[date, date, int]]:
    """
    Load week boundaries from CSV if provided, else look for data/weeks/{season}_weeks.csv,
    else derive approximate 7-day windows from opening day.
    Returns dict: week_number → (start_date, end_date, round_number)
    """
    candidates = [week_csv] if week_csv else []
    candidates.append(WEEKS_DIR / f"{season}_weeks.csv")

    for path in candidates:
        if path and path.exists():
            df = pd.read_csv(path)
            wmap = {}
            for _, row in df.iterrows():
                wmap[int(row["week_number"])] = (
                    date.fromisoformat(str(row["start_date"])[:10]),
                    date.fromisoformat(str(row["end_date"])[:10]),
                    int(row["round_number"]),
                )
            logger.info(f"  Loaded {len(wmap)} weeks from {path}")
            return wmap

    # Fallback: derive from opening day
    opening = SEASON_OPENING_DAYS.get(season)
    if not opening:
        raise ValueError(
            f"No week CSV found and no opening day configured for {season}. "
            f"Provide --week-csv data/weeks/{season}_weeks.csv"
        )
    logger.warning(f"  No week CSV for {season} — deriving approximate 7-day windows from {opening}")
    wmap = {}
    start = opening
    for wk in range(1, 25):
        end = start + __import__("datetime").timedelta(days=6)
        round_num = 1 if wk <= 18 else 2 if wk <= 20 else 3 if wk <= 22 else 4
        wmap[wk] = (start, end, round_num)
        start = end + __import__("datetime").timedelta(days=1)
    return wmap


# ---------------------------------------------------------------------------
# Core aggregation
# ---------------------------------------------------------------------------

def build_player_weekly_scores(
    season: int,
    conn: sqlite3.Connection,
    week_map: dict[int, tuple[date, date, int]],
    force: bool = False,
) -> dict:
    """
    Load the season's parquet once, aggregate into weekly scores per player,
    and write to player_weekly_scores.
    """
    cur = conn.cursor()

    # Check existing rows
    existing = cur.execute(
        "SELECT COUNT(*) FROM player_weekly_scores WHERE season=?", (season,)
    ).fetchone()[0]

    if existing > 0 and not force:
        logger.info(
            f"  Season {season}: already has {existing:,} player-weekly rows. "
            f"Use --force to recompute."
        )
        return {"skipped": True, "existing_rows": existing}

    if force and existing > 0:
        logger.info(f"  --force: deleting {existing:,} existing player_weekly_scores for {season}")
        cur.execute("DELETE FROM player_weekly_scores WHERE season=?", (season,))
        conn.commit()

    # Load parquet once
    parquet_path = GAMELOGS_DIR / f"{season}.parquet"
    if not parquet_path.exists():
        raise FileNotFoundError(
            f"No game log parquet for {season}: {parquet_path}\n"
            f"Run: python scripts/load_mlb_gamelogs.py --seasons {season}"
        )

    logger.info(f"  Loading {parquet_path} ...")
    df = pd.read_parquet(parquet_path)
    logger.info(f"  {len(df):,} game rows loaded")

    # Normalize game_date to date objects for comparison
    df["game_date"] = pd.to_datetime(df["game_date"]).dt.date

    total_rows = 0

    for week_number, (week_start, week_end, _round_number) in sorted(week_map.items()):
        week_df = df[(df["game_date"] >= week_start) & (df["game_date"] <= week_end)]

        if week_df.empty:
            logger.debug(f"  Week {week_number}: no games ({week_start}–{week_end})")
            continue

        # Aggregate: sum calculated_points by (mlb_id, stat_type), keep player_name
        agg = (
            week_df
            .groupby(["mlb_id", "stat_type"], as_index=False)
            .agg(
                player_name=("player_name", "first"),
                calculated_points=("calculated_points", "sum"),
            )
        )

        rows = [
            (
                int(r.mlb_id),
                str(r.player_name),
                season,
                week_number,
                str(r.stat_type),
                round(float(r.calculated_points), 4),
            )
            for r in agg.itertuples(index=False)
        ]

        cur.executemany(
            """INSERT OR REPLACE INTO player_weekly_scores
               (mlb_id, player_name, season, week_number, stat_type, calculated_points)
               VALUES (?,?,?,?,?,?)""",
            rows,
        )
        conn.commit()
        total_rows += len(rows)
        logger.info(
            f"  Week {week_number:2d} ({week_start}–{week_end}): "
            f"{len(rows):,} player-week rows written"
        )

    logger.info(f"  Season {season} complete: {total_rows:,} total player-weekly rows")
    return {"total_rows": total_rows, "weeks_processed": len(week_map)}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Build player-level weekly best ball scores (Stage 1 of scoring pipeline)"
    )
    parser.add_argument(
        "--seasons", type=int, nargs="+", required=True,
        help="Seasons to process (e.g. 2022 2023 2024 2025)"
    )
    parser.add_argument(
        "--week-csv", type=Path, default=None,
        help=(
            "Path to week boundaries CSV (week_number, start_date, end_date, round_number). "
            "Falls back to data/weeks/{season}_weeks.csv if not provided."
        ),
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Delete and recompute existing rows for the specified seasons"
    )
    args = parser.parse_args()

    conn = sqlite3.connect(str(DB_PATH), timeout=60)

    # Ensure table exists (safe to run multiple times)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS player_weekly_scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mlb_id INTEGER NOT NULL,
            player_name TEXT NOT NULL,
            season INTEGER NOT NULL,
            week_number INTEGER NOT NULL,
            stat_type TEXT NOT NULL,
            calculated_points REAL NOT NULL DEFAULT 0.0,
            UNIQUE(mlb_id, season, week_number, stat_type)
        )"""
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_pws_season ON player_weekly_scores(season)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_pws_mlb_id ON player_weekly_scores(mlb_id)"
    )
    conn.commit()

    for season in args.seasons:
        logger.info(f"Processing season {season} ...")
        week_map = load_week_map(season, args.week_csv)
        result = build_player_weekly_scores(season, conn, week_map, force=args.force)
        if result.get("skipped"):
            logger.info(f"  Season {season}: skipped (already loaded).")

    conn.close()
    logger.info("Done.")


if __name__ == "__main__":
    main()
