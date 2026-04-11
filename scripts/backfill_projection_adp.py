"""
Backfill projection_adp on existing picks rows from the original Underdog CSVs.

Since the historical load didn't capture projection_adp, this script reads the
raw CSVs, matches picks by (draft_id, underdog_player_id), and UPDATEs the
projection_adp column in the picks table.

Also creates/populates adp_daily_timeseries via precompute_adp.py after backfill.

Usage:
  python scripts/backfill_projection_adp.py
"""

from __future__ import annotations

import glob
import sqlite3
from pathlib import Path

import pandas as pd

DB_PATH = Path("data/bestball.db")

# Where the raw Underdog CSVs live (subfolders by season)
CSV_BASE = Path(r"C:\Users\wsjon\OneDrive\Stacking Dingers\Historical Dinger Data")

SEASONS = {
    2023: sorted(glob.glob(str(CSV_BASE / "2023" / "*.csv"))),
    2024: sorted(glob.glob(str(CSV_BASE / "2024" / "*.csv"))),
    2025: sorted(glob.glob(str(CSV_BASE / "2025" / "*.csv"))),
}


def load_season_csvs(season: int) -> pd.DataFrame:
    files = SEASONS[season]
    if not files:
        print(f"  No CSV files found for {season}")
        return pd.DataFrame()
    frames = [pd.read_csv(f, dtype=str) for f in files]
    df = pd.concat(frames, ignore_index=True)
    print(f"  {season}: loaded {len(df):,} rows from {len(files)} file(s)")
    return df


def main() -> None:
    conn = sqlite3.connect(str(DB_PATH), timeout=60)
    conn.execute("PRAGMA busy_timeout=30000")
    conn.execute("PRAGMA journal_mode=WAL")

    # Build underdog_id → internal player_id lookup
    print("Building player ID lookup ...")
    player_rows = conn.execute("SELECT underdog_id, player_id FROM players WHERE underdog_id IS NOT NULL").fetchall()
    ud_to_pid = {r[0]: r[1] for r in player_rows}
    print(f"  {len(ud_to_pid):,} players with underdog_id")

    total_updated = 0

    for season, files in SEASONS.items():
        if not files:
            print(f"\nSeason {season}: no files, skipping")
            continue

        print(f"\nSeason {season}:")
        df = load_season_csvs(season)

        if "projection_adp" not in df.columns or "overall_pick_number" not in df.columns:
            print(f"  Missing required columns, skipping")
            continue

        # The cleaned/loaded draft_id = tournament_entry_id in the raw CSV
        if "tournament_entry_id" not in df.columns:
            print(f"  No tournament_entry_id column, skipping")
            continue
        df = df.rename(columns={"tournament_entry_id": "db_draft_id"})

        # Keep only picks with projection_adp
        df = df[df["projection_adp"].notna() & (df["projection_adp"] != "")].copy()
        df["projection_adp"] = pd.to_numeric(df["projection_adp"], errors="coerce")
        df = df[df["projection_adp"].notna()]

        # Map underdog player UUID → internal player_id
        df["internal_player_id"] = df["player_id"].map(ud_to_pid)
        df = df[df["internal_player_id"].notna()]
        df["internal_player_id"] = df["internal_player_id"].astype(int)

        print(f"  {len(df):,} rows with valid projection_adp and player mapping")

        # Batch UPDATE: group by (db_draft_id, internal_player_id)
        updates = (
            df.groupby(["db_draft_id", "internal_player_id"])["projection_adp"]
            .mean()
            .reset_index()
        )

        batch = [
            (round(row["projection_adp"], 2), str(row["db_draft_id"]), int(row["internal_player_id"]))
            for _, row in updates.iterrows()
        ]

        conn.executemany(
            "UPDATE picks SET projection_adp=? WHERE draft_id=? AND player_id=?",
            batch,
        )
        conn.commit()
        print(f"  Updated {len(batch):,} pick rows")
        total_updated += len(batch)

    print(f"\nTotal: {total_updated:,} picks updated with projection_adp")

    # Verify
    count = conn.execute("SELECT COUNT(*) FROM picks WHERE projection_adp IS NOT NULL").fetchone()[0]
    print(f"Picks with projection_adp in DB: {count:,}")

    conn.close()
    print("\nDone. Now run: python scripts/precompute_adp.py")


if __name__ == "__main__":
    main()
