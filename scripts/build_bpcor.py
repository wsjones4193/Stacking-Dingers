"""
BPCOR computation script.

For each (draft_id, week_number) in weekly_scores:
  - Hitter replacement = max calculated_score among bench IF/OF players
  - Pitcher replacement = max calculated_score among bench P players
  - replacement_score = the appropriate replacement for each player's position group
  - bpcor = max(0, calculated_score - replacement_score) if is_starter or is_flex, else 0

Uses a SQL-only approach — no pandas load of 50M rows. Runs entirely in SQLite.

Usage:
  python scripts/build_bpcor.py --season 2025
  python scripts/build_bpcor.py --season 2025 --force
"""

from __future__ import annotations

import argparse
import logging
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

DB_PATH = Path("data/bestball.db")


def add_columns_if_missing(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
    cols = {row[1] for row in cur.execute("PRAGMA table_info(weekly_scores)")}
    if "replacement_score" not in cols:
        cur.execute("ALTER TABLE weekly_scores ADD COLUMN replacement_score REAL")
        logger.info("Added column: replacement_score")
    if "bpcor" not in cols:
        cur.execute("ALTER TABLE weekly_scores ADD COLUMN bpcor REAL")
        logger.info("Added column: bpcor")
    conn.commit()


def build_bpcor(season: int, conn: sqlite3.Connection, force: bool = False) -> dict:
    cur = conn.cursor()

    # Check if already computed
    if not force:
        already = cur.execute(
            "SELECT COUNT(*) FROM weekly_scores WHERE season=? AND bpcor IS NOT NULL",
            (season,),
        ).fetchone()[0]
        if already > 0:
            logger.info(
                f"Season {season}: {already:,} rows already have bpcor. "
                f"Use --force to recompute."
            )
            return {"skipped": True, "existing_rows": already}

    if force:
        logger.info(f"--force: clearing bpcor/replacement_score for {season}")
        cur.execute(
            "UPDATE weekly_scores SET bpcor=NULL, replacement_score=NULL WHERE season=?",
            (season,),
        )
        conn.commit()

    # Performance settings
    cur.execute("PRAGMA journal_mode=WAL")
    cur.execute("PRAGMA synchronous=NORMAL")
    cur.execute("PRAGMA temp_store=MEMORY")
    cur.execute("PRAGMA cache_size=-512000")  # 512MB cache

    # Ensure required indexes exist
    logger.info("Ensuring indexes...")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_ws_season ON weekly_scores(season)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_ws_draft_week ON weekly_scores(draft_id, week_number)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_ws_score_id ON weekly_scores(score_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_players_pid ON players(player_id)")
    conn.commit()

    total_rows = cur.execute(
        "SELECT COUNT(*) FROM weekly_scores WHERE season=?", (season,)
    ).fetchone()[0]
    logger.info(f"Computing BPCOR for {total_rows:,} rows (season {season})...")

    # Step 1: Compute hitter replacement level per (draft_id, week_number)
    # = max score among bench IF/OF players
    logger.info("Step 1: Computing hitter replacement levels...")
    cur.execute(
        """
        CREATE TEMP TABLE IF NOT EXISTS _hitter_rep AS
        SELECT ws.draft_id, ws.week_number,
               MAX(ws.calculated_score) AS hitter_rep
        FROM weekly_scores ws
        JOIN players p ON p.player_id = ws.player_id
        WHERE ws.season = ?
          AND ws.is_bench = 1
          AND p.position IN ('IF', 'OF')
        GROUP BY ws.draft_id, ws.week_number
        """,
        (season,),
    )
    conn.commit()
    logger.info("  Done.")

    # Step 2: Compute pitcher replacement level per (draft_id, week_number)
    logger.info("Step 2: Computing pitcher replacement levels...")
    cur.execute(
        """
        CREATE TEMP TABLE IF NOT EXISTS _pitcher_rep AS
        SELECT ws.draft_id, ws.week_number,
               MAX(ws.calculated_score) AS pitcher_rep
        FROM weekly_scores ws
        JOIN players p ON p.player_id = ws.player_id
        WHERE ws.season = ?
          AND ws.is_bench = 1
          AND p.position = 'P'
        GROUP BY ws.draft_id, ws.week_number
        """,
        (season,),
    )
    conn.commit()
    logger.info("  Done.")

    # Step 3: Update replacement_score on every row
    logger.info("Step 3: Writing replacement_score...")
    cur.execute(
        """
        UPDATE weekly_scores
        SET replacement_score = CASE
            WHEN (SELECT p.position FROM players p WHERE p.player_id = weekly_scores.player_id) = 'P'
            THEN COALESCE(
                (SELECT pr.pitcher_rep FROM _pitcher_rep pr
                 WHERE pr.draft_id = weekly_scores.draft_id
                   AND pr.week_number = weekly_scores.week_number),
                0.0)
            ELSE COALESCE(
                (SELECT hr.hitter_rep FROM _hitter_rep hr
                 WHERE hr.draft_id = weekly_scores.draft_id
                   AND hr.week_number = weekly_scores.week_number),
                0.0)
            END
        WHERE season = ?
        """,
        (season,),
    )
    conn.commit()
    logger.info("  Done.")

    # Step 4: Compute bpcor
    logger.info("Step 4: Computing bpcor...")
    cur.execute(
        """
        UPDATE weekly_scores
        SET bpcor = CASE
            WHEN (is_starter = 1 OR is_flex = 1)
            THEN MAX(0.0, calculated_score - replacement_score)
            ELSE 0.0
            END
        WHERE season = ?
        """,
        (season,),
    )
    conn.commit()
    logger.info("  Done.")

    # Cleanup temp tables
    cur.execute("DROP TABLE IF EXISTS _hitter_rep")
    cur.execute("DROP TABLE IF EXISTS _pitcher_rep")
    conn.commit()

    updated = cur.execute(
        "SELECT COUNT(*) FROM weekly_scores WHERE season=? AND bpcor IS NOT NULL",
        (season,),
    ).fetchone()[0]

    logger.info(f"Season {season} BPCOR complete: {updated:,} rows updated")
    return {"updated_rows": updated}


def main():
    parser = argparse.ArgumentParser(description="Compute BPCOR for weekly_scores")
    parser.add_argument("--season", type=int, required=True)
    parser.add_argument("--force", action="store_true",
                        help="Recompute even if bpcor already populated")
    args = parser.parse_args()

    conn = sqlite3.connect(str(DB_PATH), timeout=120)
    add_columns_if_missing(conn)
    result = build_bpcor(args.season, conn, force=args.force)
    conn.close()

    if result.get("skipped"):
        logger.info("Nothing to do. Run with --force to recompute.")
    else:
        logger.info(f"Done. {result.get('updated_rows', 0):,} rows updated.")


if __name__ == "__main__":
    main()
