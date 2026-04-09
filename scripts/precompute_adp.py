"""
Precompute ADP summary tables from the picks + drafts + players tables.

Populates three tables:
  adp_player_summary   — per-player/season: avg pick, ownership %, draft count
  adp_scarcity_cache   — cumulative % of each position drafted by pick number
  adp_round_composition — position breakdown per round per season

Run from the project root:
  python -m scripts.precompute_adp
  # or
  python scripts/precompute_adp.py
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

DB_PATH = Path("data/bestball.db")


def _ensure_tables(conn: sqlite3.Connection) -> None:
    """Create pre-computed ADP tables if they don't already exist."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS adp_player_summary (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id INTEGER NOT NULL REFERENCES players(player_id),
            season INTEGER NOT NULL,
            player_name TEXT NOT NULL,
            position TEXT NOT NULL,
            avg_pick REAL NOT NULL,
            pick_std REAL,
            ownership_pct REAL NOT NULL,
            draft_count INTEGER NOT NULL,
            total_season_drafts INTEGER NOT NULL,
            UNIQUE(player_id, season)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS adp_scarcity_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            season INTEGER NOT NULL,
            position TEXT NOT NULL,
            pick_number INTEGER NOT NULL,
            cumulative_pct REAL NOT NULL,
            avg_per_draft REAL NOT NULL DEFAULT 0,
            UNIQUE(season, position, pick_number)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS adp_round_composition (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            season INTEGER NOT NULL,
            round_number INTEGER NOT NULL,
            position TEXT NOT NULL,
            count INTEGER NOT NULL,
            pct_of_round REAL NOT NULL,
            UNIQUE(season, round_number, position)
        )
    """)
    conn.commit()


def main() -> None:
    print(f"Connecting to {DB_PATH} ...")
    conn = sqlite3.connect(DB_PATH, timeout=60)
    conn.execute("PRAGMA busy_timeout=30000")
    _ensure_tables(conn)

    # ------------------------------------------------------------------
    # Load raw picks with player position + season
    # ------------------------------------------------------------------
    print("Loading picks ...")
    picks_df = pd.read_sql(
        """
        SELECT
            pk.draft_id,
            pk.pick_number,
            pk.round_number,
            pk.player_id,
            p.name AS player_name,
            p.position,
            d.season
        FROM picks pk
        JOIN players p ON pk.player_id = p.player_id
        JOIN drafts d ON pk.draft_id = d.draft_id
        WHERE p.position IN ('P', 'IF', 'OF')
        """,
        conn,
    )
    print(f"  Loaded {len(picks_df):,} picks across {picks_df['season'].nunique()} seasons")

    # Total drafts per season (needed for ownership %)
    season_draft_counts = (
        picks_df.groupby("season")["draft_id"].nunique().rename("total_season_drafts")
    )

    # ------------------------------------------------------------------
    # 1. AdpPlayerSummary
    # ------------------------------------------------------------------
    print("Computing player ADP summaries ...")
    player_summary = (
        picks_df.groupby(["player_id", "player_name", "position", "season"])
        .agg(
            avg_pick=("pick_number", "mean"),
            pick_std=("pick_number", "std"),
            draft_count=("draft_id", "nunique"),
        )
        .reset_index()
    )
    player_summary = player_summary.merge(season_draft_counts, on="season")
    # Ownership = % of all team entries (12 teams per draft) that selected this player
    player_summary["ownership_pct"] = (
        player_summary["draft_count"] * 12 / player_summary["total_season_drafts"] * 100
    ).round(2)
    player_summary["avg_pick"] = player_summary["avg_pick"].round(2)
    player_summary["pick_std"] = player_summary["pick_std"].round(2)

    # Write to DB
    conn.execute("DELETE FROM adp_player_summary")
    player_summary[
        ["player_id", "season", "player_name", "position", "avg_pick", "pick_std",
         "ownership_pct", "draft_count", "total_season_drafts"]
    ].to_sql("adp_player_summary", conn, if_exists="append", index=False)
    conn.commit()
    print(f"  Wrote {len(player_summary):,} player-season rows")

    # ------------------------------------------------------------------
    # 2. AdpScarcityCache
    # ------------------------------------------------------------------
    print("Computing scarcity curves ...")
    scarcity_rows = []

    for season in picks_df["season"].unique():
        season_picks = picks_df[picks_df["season"] == season]
        total_drafts = int(season_draft_counts[season])

        for position in ["P", "IF", "OF"]:
            pos_picks = season_picks[season_picks["position"] == position]["pick_number"]
            total = len(pos_picks)
            if total == 0:
                continue

            for pick_num in range(1, 241):
                cumulative = int((pos_picks <= pick_num).sum())
                scarcity_rows.append(
                    {
                        "season": season,
                        "position": position,
                        "pick_number": pick_num,
                        "cumulative_pct": round(cumulative / total * 100, 2),
                        "avg_per_draft": round(cumulative / total_drafts, 3),
                    }
                )

    scarcity_df = pd.DataFrame(scarcity_rows)
    conn.execute("DELETE FROM adp_scarcity_cache")
    scarcity_df.to_sql("adp_scarcity_cache", conn, if_exists="append", index=False)
    conn.commit()
    print(f"  Wrote {len(scarcity_df):,} scarcity curve rows")

    # ------------------------------------------------------------------
    # 3. AdpRoundComposition
    # ------------------------------------------------------------------
    print("Computing round composition ...")
    round_comp = (
        picks_df.groupby(["season", "round_number", "position"])
        .size()
        .rename("count")
        .reset_index()
    )
    round_totals = (
        picks_df.groupby(["season", "round_number"])
        .size()
        .rename("round_total")
        .reset_index()
    )
    round_comp = round_comp.merge(round_totals, on=["season", "round_number"])
    round_comp["pct_of_round"] = (round_comp["count"] / round_comp["round_total"] * 100).round(2)

    conn.execute("DELETE FROM adp_round_composition")
    round_comp[["season", "round_number", "position", "count", "pct_of_round"]].to_sql(
        "adp_round_composition", conn, if_exists="append", index=False
    )
    conn.commit()
    print(f"  Wrote {len(round_comp):,} round composition rows")

    conn.close()
    print("Done.")


if __name__ == "__main__":
    main()
