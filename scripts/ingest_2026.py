"""
2026 Underdog draft data ingestion.

Handles column format differences in the 2026 CSV vs prior seasons:
  - position_name (SP/RF/1B/etc.) → normalized to P/IF/OF
  - overall_pick_number → pick_number
  - team_pick_number → used to derive round_number
  - pick_order → draft_position (seat 1-12)
  - draft_time → draft_date (actual draft time, not signup time)
  - player_id → underdog_player_id

After ingestion, copies normalized CSV to data/csv/2026.csv for
use by build_historical_scoring_fast.py and build_player_mapping_workbooks.py.

Usage:
  python scripts/ingest_2026.py --csv "path/to/the_dinger_rd1.csv"
  python scripts/ingest_2026.py --csv "path/to/the_dinger_rd1.csv" --force
"""

from __future__ import annotations

import argparse
import logging
import shutil
import sqlite3
import sys
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
SEASON = 2026

# Raw position → P / IF / OF
POSITION_MAP = {
    "SP": "P", "RP": "P", "P": "P",
    "RF": "OF", "LF": "OF", "CF": "OF", "OF": "OF",
    "1B": "IF", "2B": "IF", "3B": "IF", "SS": "IF",
    "C": "IF", "DH": "IF", "IF": "IF",
}


def load_and_normalize(csv_path: Path) -> pd.DataFrame:
    logger.info(f"Loading {csv_path} ...")
    df = pd.read_csv(csv_path, dtype=str)
    logger.info(f"  {len(df):,} rows, {df['draft_id'].nunique():,} unique draft_ids")

    # Normalize positions
    df["position"] = df["position_name"].str.upper().map(POSITION_MAP).fillna("IF")

    # Column renames
    df = df.rename(columns={
        "player_id": "underdog_player_id",
        "overall_pick_number": "pick_number",
        "pick_order": "draft_position",
    })

    # Derive round_number from pick_number (20 rounds of 12)
    df["pick_number"] = pd.to_numeric(df["pick_number"], errors="coerce").fillna(0).astype(int)
    df["round_number"] = ((df["pick_number"] - 1) // 12 + 1).clip(upper=20)

    # Draft position (seat 1-12)
    df["draft_position"] = pd.to_numeric(df["draft_position"], errors="coerce").fillna(1).astype(int)

    # Draft date from draft_time (when the draft actually ran, not when the entry was created)
    df["draft_date"] = pd.to_datetime(df["draft_time"], errors="coerce").dt.date

    # ADP
    df["projection_adp"] = pd.to_numeric(df["projection_adp"], errors="coerce")

    df["season"] = SEASON
    df["entry_type"] = "the_dinger"

    return df


def ingest_players(df: pd.DataFrame, conn: sqlite3.Connection) -> dict[str, int]:
    """Upsert all unique players. Returns {underdog_player_id: player_id}."""
    cur = conn.cursor()
    players = df.drop_duplicates("underdog_player_id")[
        ["underdog_player_id", "player_name", "position"]
    ].copy()

    inserted = 0
    id_map: dict[str, int] = {}

    for _, row in players.iterrows():
        ud_id = str(row["underdog_player_id"])
        name = str(row["player_name"])
        pos = str(row["position"])

        existing = cur.execute(
            "SELECT player_id FROM players WHERE underdog_id=?", (ud_id,)
        ).fetchone()

        if existing:
            id_map[ud_id] = existing[0]
            # Update position if changed
            cur.execute(
                "UPDATE players SET position=?, name=? WHERE underdog_id=? AND player_id=?",
                (pos, name, ud_id, existing[0]),
            )
        else:
            cur.execute(
                "INSERT INTO players (name, position, underdog_id, active) VALUES (?,?,?,1)",
                (name, pos, ud_id),
            )
            id_map[ud_id] = cur.lastrowid
            inserted += 1

    conn.commit()
    logger.info(f"  Players: {len(id_map):,} total, {inserted:,} new")
    return id_map


def ingest_drafts(df: pd.DataFrame, conn: sqlite3.Connection, force: bool) -> set[str]:
    """Insert drafts. Returns set of draft_ids ingested."""
    cur = conn.cursor()

    if force:
        cur.execute("DELETE FROM drafts WHERE season=?", (SEASON,))
        conn.commit()
        logger.info("  --force: cleared existing 2026 drafts")

    existing = {r[0] for r in cur.execute(
        "SELECT draft_id FROM drafts WHERE season=?", (SEASON,)
    ).fetchall()}

    drafts = (
        df.drop_duplicates(["draft_id", "username"])
        [[  "draft_id", "username", "draft_date", "entry_type",
            "draft_position", "season"]]
        .copy()
    )

    new_drafts = drafts[~drafts["draft_id"].isin(existing)]
    rows = [
        (
            str(r.draft_id), SEASON,
            str(r.draft_date) if r.draft_date else None,
            str(r.entry_type),
            str(r.username),
            int(r.draft_position),
        )
        for r in new_drafts.itertuples(index=False)
    ]

    cur.executemany(
        "INSERT OR IGNORE INTO drafts (draft_id, season, draft_date, entry_type, username, draft_position) VALUES (?,?,?,?,?,?)",
        rows,
    )
    conn.commit()

    all_draft_ids = existing | set(new_drafts["draft_id"])
    logger.info(f"  Drafts: {len(all_draft_ids):,} total ({len(rows):,} new)")
    return all_draft_ids


def ingest_picks(
    df: pd.DataFrame,
    id_map: dict[str, int],
    conn: sqlite3.Connection,
    force: bool,
) -> None:
    cur = conn.cursor()

    if force:
        cur.execute(
            "DELETE FROM picks WHERE draft_id IN (SELECT draft_id FROM drafts WHERE season=?)",
            (SEASON,),
        )
        conn.commit()

    df["player_id"] = df["underdog_player_id"].map(id_map)
    df = df.dropna(subset=["player_id"])
    df["player_id"] = df["player_id"].astype(int)

    df["projection_adp_val"] = pd.to_numeric(df.get("projection_adp", None), errors="coerce")

    rows = [
        (
            str(r.draft_id), int(r.pick_number), int(r.round_number),
            int(r.player_id), str(r.username),
            float(r.projection_adp_val) if not pd.isna(r.projection_adp_val) else None,
        )
        for r in df[["draft_id", "pick_number", "round_number", "player_id", "username", "projection_adp_val"]].itertuples(index=False)
    ]

    chunk_size = 100_000
    total = 0
    for i in range(0, len(rows), chunk_size):
        cur.executemany(
            "INSERT OR IGNORE INTO picks (draft_id, pick_number, round_number, player_id, username, projection_adp) VALUES (?,?,?,?,?,?)",
            rows[i: i + chunk_size],
        )
        conn.commit()
        total += len(rows[i: i + chunk_size])
        logger.info(f"  Picks: {total:,} / {len(rows):,} inserted")

    logger.info(f"  Picks: {len(rows):,} total")


def save_normalized_csv(df: pd.DataFrame) -> None:
    """Save normalized CSV to data/csv/2026.csv for use by scoring scripts."""
    out = Path("data/csv/2026.csv")
    out.parent.mkdir(parents=True, exist_ok=True)
    df[["draft_id", "underdog_player_id", "player_name", "position",
        "pick_number", "round_number", "username", "projection_adp"]].to_csv(out, index=False)
    logger.info(f"  Normalized CSV saved → {out}")


def ingest_adp_snapshots(df: pd.DataFrame, id_map: dict[str, int], conn: sqlite3.Connection) -> None:
    """Write adp_snapshots rows from projection_adp in the CSV."""
    cur = conn.cursor()
    cur.execute("DELETE FROM adp_snapshots WHERE season=?", (SEASON,))

    adp_df = (
        df.dropna(subset=["projection_adp"])
        .groupby("underdog_player_id")["projection_adp"]
        .mean()
        .reset_index()
    )
    adp_df.columns = ["underdog_player_id", "adp"]
    adp_df["player_id"] = adp_df["underdog_player_id"].map(id_map)
    adp_df = adp_df.dropna(subset=["player_id"])
    adp_df["player_id"] = adp_df["player_id"].astype(int)

    # Snapshot date = earliest draft date in the file
    snapshot_date = df["draft_date"].dropna().min()

    rows = [
        (int(r.player_id), str(snapshot_date), SEASON, round(r.adp, 2))
        for r in adp_df.itertuples(index=False)
    ]
    cur.executemany(
        "INSERT OR IGNORE INTO adp_snapshots (player_id, snapshot_date, season, adp) VALUES (?,?,?,?)",
        rows,
    )
    conn.commit()
    logger.info(f"  ADP snapshots: {len(rows):,} rows written")


def main():
    parser = argparse.ArgumentParser(description="Ingest 2026 Underdog draft CSV")
    parser.add_argument("--csv", type=Path, required=True, help="Path to the_dinger CSV")
    parser.add_argument("--force", action="store_true", help="Delete and re-ingest existing 2026 data")
    args = parser.parse_args()

    if not args.csv.exists():
        logger.error(f"CSV not found: {args.csv}")
        sys.exit(1)

    conn = sqlite3.connect(str(DB_PATH), timeout=60)

    df = load_and_normalize(args.csv)
    id_map = ingest_players(df, conn)
    ingest_drafts(df, conn, force=args.force)
    ingest_picks(df, id_map, conn, force=args.force)
    save_normalized_csv(df)
    ingest_adp_snapshots(df, id_map, conn)

    conn.close()
    logger.info("Done. Run next:")
    logger.info("  python scripts/precompute_adp.py")
    logger.info("  python scripts/build_player_mapping_workbooks.py --seasons 2026")


if __name__ == "__main__":
    main()
