"""
Fast vectorized historical scoring builder.

Replaces the per-draft set_lineup() loop in build_historical_scoring.py with
fully vectorized pandas operations. Processes all drafts for all weeks in one
pass — typically 10-50x faster for historical loads.

Requires player_weekly_scores to be populated first (Stage 1):
  python scripts/build_player_weekly_scores.py --seasons 2025

Usage:
  python scripts/build_historical_scoring_fast.py --season 2025
  python scripts/build_historical_scoring_fast.py --season 2025 --force
"""

from __future__ import annotations

import argparse
import logging
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import numpy as np

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

DB_PATH = Path("data/bestball.db")


# ---------------------------------------------------------------------------
# Mapping helpers (shared with original script)
# ---------------------------------------------------------------------------

def load_mapping_from_excel(season: int, conn: sqlite3.Connection) -> None:
    """Update player_id_map and players.mlb_id from cleaned mapping Excel."""
    from pathlib import Path as P
    import pandas as pd2

    path = P("data/mapping") / f"{season}_player_mapping.xlsx"
    if not path.exists():
        raise FileNotFoundError(f"Mapping file not found: {path}")

    df = pd2.read_excel(path, sheet_name="mapping")
    mapped = df[df["mlb_id"].notna() & df["underdog_player_id"].notna()].copy()
    mapped["mlb_id"] = mapped["mlb_id"].astype(int)

    cur = conn.cursor()
    updated = 0
    for _, row in mapped.iterrows():
        ud_id = str(row["underdog_player_id"]).strip()
        mlb_id = int(row["mlb_id"])
        if not ud_id or ud_id == "nan":
            continue
        cur.execute(
            "UPDATE player_id_map SET mlb_id=?, mlb_name=?, confirmed=1 WHERE underdog_id=? AND season=?",
            (mlb_id, str(row.get("mlb_player_name", "")), ud_id, season),
        )
        if cur.rowcount == 0:
            cur.execute(
                """INSERT OR IGNORE INTO player_id_map
                   (underdog_id, underdog_name, mlb_id, mlb_name, confirmed, match_score, season)
                   VALUES (?,?,?,?,1,?,?)""",
                (ud_id, str(row.get("ud_player_name", "")), mlb_id,
                 str(row.get("mlb_player_name", "")),
                 float(row.get("match_score", 0)), season),
            )
        updated += 1

    cur.execute(
        """UPDATE players SET mlb_id = (
               SELECT m.mlb_id FROM player_id_map m
               WHERE m.underdog_id = players.underdog_id AND m.season = ? AND m.mlb_id IS NOT NULL
           )
           WHERE EXISTS (
               SELECT 1 FROM player_id_map m
               WHERE m.underdog_id = players.underdog_id AND m.season = ? AND m.mlb_id IS NOT NULL
           )""",
        (season, season),
    )
    conn.commit()
    logger.info(f"Mapping loaded: {updated} UD→MLB pairs updated for {season}")


def build_player_mlb_lookup(season: int, conn: sqlite3.Connection) -> pd.DataFrame:
    """
    Returns DataFrame with columns: player_id, mlb_id, position (P/IF/OF).
    """
    df = pd.read_sql(
        """
        SELECT p.player_id, COALESCE(p.mlb_id, m.mlb_id) AS mlb_id, p.position
        FROM players p
        LEFT JOIN player_id_map m ON m.underdog_id = p.underdog_id AND m.season = ?
        WHERE COALESCE(p.mlb_id, m.mlb_id) IS NOT NULL
        """,
        conn,
        params=(season,),
    )
    df["mlb_id"] = df["mlb_id"].astype(int)
    logger.info(f"Player→MLB lookup: {len(df):,} players with MLB IDs for {season}")
    return df


# ---------------------------------------------------------------------------
# Core vectorized scoring
# ---------------------------------------------------------------------------

def compute_weekly_scores_fast(
    season: int,
    conn: sqlite3.Connection,
    force: bool = False,
) -> dict:
    """
    Vectorized replacement for compute_weekly_scores().
    Processes all drafts × all weeks in one pandas pipeline — no Python loops.
    """
    cur = conn.cursor()

    # Check existing
    existing = cur.execute(
        "SELECT COUNT(*) FROM weekly_scores WHERE season=?", (season,)
    ).fetchone()[0]
    if existing > 0 and not force:
        logger.info(
            f"Season {season} already has {existing:,} weekly score rows. "
            f"Use --force to recompute."
        )
        return {"skipped": True, "existing_rows": existing}

    if force and existing > 0:
        logger.info(f"--force: deleting {existing:,} existing weekly_score rows for {season}")
        cur.execute("DELETE FROM weekly_scores WHERE season=?", (season,))
        conn.commit()

    # Verify Stage 1
    pws_count = cur.execute(
        "SELECT COUNT(*) FROM player_weekly_scores WHERE season=?", (season,)
    ).fetchone()[0]
    if pws_count == 0:
        raise RuntimeError(
            f"No player_weekly_scores found for {season}. "
            f"Run Stage 1: python scripts/build_player_weekly_scores.py --seasons {season}"
        )
    logger.info(f"Stage 1 data: {pws_count:,} player-weekly rows for {season}")

    # -----------------------------------------------------------------------
    # Step A: Load picks from CSV
    # -----------------------------------------------------------------------
    logger.info("Loading picks from CSV...")
    csv_path = Path(f"data/csv/{season}.csv")
    if not csv_path.exists():
        raise FileNotFoundError(f"No CSV for season {season}: {csv_path}")

    picks = pd.read_csv(csv_path, usecols=["draft_id", "underdog_player_id", "player_name"])

    # Resolve underdog_player_id → player_id
    ud_to_pid = dict(cur.execute(
        "SELECT p.underdog_id, p.player_id FROM players p WHERE p.underdog_id IS NOT NULL"
    ).fetchall())

    if picks["underdog_player_id"].isna().all():
        # 2022 fallback: name-based
        name_to_pid = dict(cur.execute("SELECT name, player_id FROM players").fetchall())
        picks["player_id"] = picks["player_name"].map(name_to_pid)
    else:
        picks["player_id"] = picks["underdog_player_id"].map(ud_to_pid)

    picks = picks.dropna(subset=["player_id"])
    picks["player_id"] = picks["player_id"].astype(int)

    # Filter to only drafts in DB for this season
    draft_ids = set(r[0] for r in cur.execute(
        "SELECT draft_id FROM drafts WHERE season=?", (season,)
    ).fetchall())
    picks = picks[picks["draft_id"].isin(draft_ids)][["draft_id", "player_id"]].drop_duplicates()
    logger.info(f"  {len(picks):,} draft-player pairs across {picks['draft_id'].nunique():,} drafts")

    # -----------------------------------------------------------------------
    # Step B: Load player→mlb→position lookup
    # -----------------------------------------------------------------------
    player_info = build_player_mlb_lookup(season, conn)
    # Normalize position to P/IF/OF
    def norm_pos(p):
        if p == "P": return "P"
        if p == "OF": return "OF"
        return "IF"
    player_info["pos_norm"] = player_info["position"].apply(norm_pos)

    # -----------------------------------------------------------------------
    # Step C: Load player_weekly_scores — all weeks at once
    # -----------------------------------------------------------------------
    logger.info("Loading player_weekly_scores from DB...")
    pws = pd.read_sql(
        "SELECT mlb_id, week_number, stat_type, calculated_points "
        "FROM player_weekly_scores WHERE season=?",
        conn,
        params=(season,),
    )
    pws["mlb_id"] = pws["mlb_id"].astype(int)
    logger.info(f"  {len(pws):,} player-week-stattype rows loaded")

    # -----------------------------------------------------------------------
    # Step D: Join everything into one flat DataFrame
    # -----------------------------------------------------------------------
    # picks → player_id → (mlb_id, pos_norm)
    df = picks.merge(
        player_info[["player_id", "mlb_id", "pos_norm"]],
        on="player_id", how="inner",
    )

    # Determine stat_type from position (pitchers → pitching, else hitting)
    df["stat_type"] = df["pos_norm"].apply(lambda p: "pitching" if p == "P" else "hitting")

    # Explode across all weeks (cross join each player to every week number)
    week_numbers = sorted(pws["week_number"].unique())
    weeks_df = pd.DataFrame({"week_number": week_numbers})
    df = df.merge(weeks_df, how="cross")

    # Join player_weekly_scores on (mlb_id, week_number, stat_type)
    df = df.merge(
        pws[["mlb_id", "week_number", "stat_type", "calculated_points"]],
        on=["mlb_id", "week_number", "stat_type"],
        how="left",
    )
    df["calculated_points"] = df["calculated_points"].fillna(0.0)

    logger.info(f"  Flat DataFrame: {len(df):,} rows (drafts × players × weeks)")

    # -----------------------------------------------------------------------
    # Step E: Vectorized lineup setting
    # -----------------------------------------------------------------------
    logger.info("Setting lineups (vectorized)...")

    # Rank each player within their position group within each (draft_id, week_number)
    df["pos_rank"] = (
        df.groupby(["draft_id", "week_number", "pos_norm"])["calculated_points"]
        .rank(ascending=False, method="first")
    )

    # Starters: top 3 at each position
    df["is_starter"] = (df["pos_rank"] <= 3).astype(bool)

    # FLEX: among non-starters who are IF or OF, pick the top scorer per (draft, week)
    non_starter_hitters = df[~df["is_starter"] & (df["pos_norm"] != "P")].copy()
    if len(non_starter_hitters) > 0:
        flex_idx = non_starter_hitters.groupby(
            ["draft_id", "week_number"]
        )["calculated_points"].idxmax()
        df["is_flex"] = False
        df.loc[flex_idx.values, "is_flex"] = True
    else:
        df["is_flex"] = False

    df["is_bench"] = ~df["is_starter"] & ~df["is_flex"]

    # -----------------------------------------------------------------------
    # Step F: Write to weekly_scores
    # -----------------------------------------------------------------------
    logger.info("Writing to weekly_scores...")

    df["season"] = season
    df["calculated_score"] = df["calculated_points"].round(2)

    # Ensure indexes exist
    cur.execute("CREATE INDEX IF NOT EXISTS idx_drafts_season ON drafts(season)")
    conn.commit()

    out = df[["draft_id", "week_number", "season", "player_id",
              "calculated_score", "is_starter", "is_flex", "is_bench"]].copy()
    out["is_starter"] = out["is_starter"].astype(int)
    out["is_flex"] = out["is_flex"].astype(int)
    out["is_bench"] = out["is_bench"].astype(int)

    rows = list(out.itertuples(index=False, name=None))

    chunk_size = 100_000
    for i in range(0, len(rows), chunk_size):
        chunk = rows[i: i + chunk_size]
        cur.executemany(
            """INSERT INTO weekly_scores
               (draft_id, week_number, season, player_id, calculated_score,
                is_starter, is_flex, is_bench)
               VALUES (?,?,?,?,?,?,?,?)""",
            chunk,
        )
        conn.commit()
        logger.info(f"  Inserted {min(i + chunk_size, len(rows)):,} / {len(rows):,} rows")

    logger.info(f"Season {season} complete: {len(rows):,} total rows")
    return {"total_rows": len(rows)}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Fast vectorized historical scoring (Stage 2)"
    )
    parser.add_argument("--season", type=int, required=True)
    parser.add_argument("--force", action="store_true",
                        help="Delete and recompute existing scores")
    parser.add_argument("--skip-mapping-update", action="store_true",
                        help="Skip Excel→DB mapping update")
    args = parser.parse_args()

    conn = sqlite3.connect(str(DB_PATH), timeout=60)

    if not args.skip_mapping_update:
        load_mapping_from_excel(args.season, conn)
    else:
        logger.info("Skipping mapping update (--skip-mapping-update)")

    result = compute_weekly_scores_fast(args.season, conn, force=args.force)
    conn.close()

    if result.get("skipped"):
        logger.info("Nothing to do. Run with --force to recompute.")
    else:
        logger.info(f"Done. {result.get('total_rows', 0):,} rows written.")


if __name__ == "__main__":
    main()
