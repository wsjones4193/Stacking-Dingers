"""
Export ADP daily timeseries to Excel.

One sheet per season. Dates across the top, players on the left.
Cell values = ADP on that date (forward-filled; blank if player not yet in data).

Usage:
  python scripts/export_adp_excel.py
  python scripts/export_adp_excel.py --out data/adp_export.xlsx
"""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

import pandas as pd

DB_PATH = Path("data/bestball.db")
DEFAULT_OUT = Path("data/adp_export.xlsx")


def build_sheet(conn: sqlite3.Connection, season: int) -> pd.DataFrame:
    df = pd.read_sql(
        "SELECT player_id, player_name, position, snapshot_date, adp "
        "FROM adp_daily_timeseries WHERE season=? ORDER BY snapshot_date, adp",
        conn,
        params=(season,),
    )
    if df.empty:
        return df

    # Pivot: rows = players, columns = dates
    pivot = df.pivot_table(
        index=["player_id", "player_name", "position"],
        columns="snapshot_date",
        values="adp",
        aggfunc="first",
    )

    # Sort rows by earliest non-null ADP (best pick = top row)
    first_adp = pivot.apply(lambda row: row.dropna().iloc[0] if row.notna().any() else 9999, axis=1)
    pivot = pivot.loc[first_adp.sort_values().index]

    pivot.index.names = ["player_id", "player_name", "position"]
    pivot.columns.name = None
    return pivot


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    args.out.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(DB_PATH))
    seasons = [r[0] for r in conn.execute(
        "SELECT DISTINCT season FROM adp_daily_timeseries ORDER BY season"
    ).fetchall()]

    print(f"Writing {args.out} ...")
    with pd.ExcelWriter(args.out, engine="openpyxl") as writer:
        for season in seasons:
            df = build_sheet(conn, season)
            if df.empty:
                print(f"  {season}: no data, skipping")
                continue

            df.to_excel(writer, sheet_name=str(season))

            # Auto-size columns for readability
            ws = writer.sheets[str(season)]
            # Fixed widths for the index columns
            ws.column_dimensions["A"].width = 10   # player_id
            ws.column_dimensions["B"].width = 22   # player_name
            ws.column_dimensions["C"].width = 6    # position
            # Narrow date columns
            for i, col in enumerate(ws.iter_cols(min_col=4, max_col=ws.max_column), start=4):
                letter = col[0].column_letter
                ws.column_dimensions[letter].width = 8

            print(f"  {season}: {len(df):,} players × {len(df.columns)} dates")

    conn.close()
    print(f"Done: {args.out}")


if __name__ == "__main__":
    main()
