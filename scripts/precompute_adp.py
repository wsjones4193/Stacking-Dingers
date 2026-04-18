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
            avg_projection_adp REAL,
            min_projection_adp REAL,
            max_projection_adp REAL,
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
        CREATE TABLE IF NOT EXISTS adp_pick_distribution (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id INTEGER NOT NULL,
            season INTEGER NOT NULL,
            pick_number INTEGER NOT NULL,
            count INTEGER NOT NULL,
            UNIQUE(player_id, season, pick_number)
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
            pk.username,
            pk.pick_number,
            pk.round_number,
            pk.player_id,
            pk.projection_adp,
            p.name AS player_name,
            p.position,
            d.season,
            d.draft_date
        FROM picks pk
        JOIN players p ON pk.player_id = p.player_id
        JOIN drafts d ON pk.draft_id = d.draft_id
        WHERE p.position IN ('P', 'IF', 'OF')
          AND d.season >= 2024
        """,
        conn,
    )
    print(f"  Loaded {len(picks_df):,} picks across {picks_df['season'].nunique()} seasons")
    picks_df["projection_adp"] = pd.to_numeric(picks_df["projection_adp"], errors="coerce")
    null_proj = picks_df["projection_adp"].isna().sum()
    print(f"  projection_adp null before fill: {null_proj:,} picks — filling with 240 for timeseries only")

    # Compute min/max/avg from real values only (before filling nulls)
    proj_adp_stats = (
        picks_df.dropna(subset=["projection_adp"])
        .groupby(["player_id", "season"])["projection_adp"]
        .agg(avg_projection_adp="mean", min_projection_adp="min", max_projection_adp="max")
        .round(2)
        .reset_index()
    )

    # Fill nulls with 240 only for timeseries calculation downstream
    picks_df["projection_adp"] = picks_df["projection_adp"].fillna(240.0)
    has_proj_adp = True  # always True after fill

    # Total draft rooms per season (denominator for ownership %).
    # 2024-2025: draft_id = roster-level (12 per room) → total_draft_ids // 12 = rooms
    # 2026+:     draft_id = room-level → total_draft_ids = rooms directly
    raw_draft_ids = picks_df.groupby("season")["draft_id"].nunique()
    season_draft_counts = pd.DataFrame([
        {"season": s, "total_season_drafts": (c if s >= 2026 else c // 12)}
        for s, c in raw_draft_ids.items()
    ])

    # Total unique rosters per season (draft_id × username) — used for scarcity avg_per_draft
    picks_df["roster_key"] = picks_df["draft_id"] + "|" + picks_df["username"]
    season_roster_counts = (
        picks_df.groupby("season")["roster_key"].nunique().rename("total_rosters")
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
            draft_count=("draft_id", "nunique"),  # unique draft_ids containing this player
        )
        .reset_index()
    )
    player_summary = player_summary.merge(season_draft_counts, on="season")
    # Ownership = % of draft rooms that included this player
    player_summary["ownership_pct"] = (
        player_summary["draft_count"] / player_summary["total_season_drafts"] * 100
    ).round(2)
    player_summary["avg_pick"] = player_summary["avg_pick"].round(2)
    player_summary["pick_std"] = player_summary["pick_std"].round(2)

    player_summary = player_summary.merge(proj_adp_stats, on=["player_id", "season"], how="left")

    # ------------------------------------------------------------------
    # 1b. AdpDailyTimeseries (requires projection_adp in picks)
    # ------------------------------------------------------------------
    print("Computing daily ADP time series ...")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS adp_daily_timeseries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id INTEGER NOT NULL,
            player_name TEXT NOT NULL,
            position TEXT NOT NULL,
            season INTEGER NOT NULL,
            snapshot_date TEXT NOT NULL,
            adp REAL NOT NULL,
            UNIQUE(player_id, season, snapshot_date)
        )
    """)
    conn.commit()
    conn.execute("DELETE FROM adp_daily_timeseries")
    conn.commit()

    if has_proj_adp:
        proj_picks = picks_df.copy()
        proj_picks["draft_date"] = pd.to_datetime(proj_picks["draft_date"]).dt.date

        # Daily avg projection_adp per player/season — exclude 240-filled nulls
        daily_adp = (
            proj_picks[proj_picks["projection_adp"] != 240.0]
            .groupby(["player_id", "player_name", "position", "season", "draft_date"])
            ["projection_adp"]
            .mean()
            .reset_index()
            .rename(columns={"draft_date": "snapshot_date", "projection_adp": "adp"})
        )

        # Forward-fill: for each player/season build a full date range and ffill gaps
        ffilled_rows = []
        for (player_id, player_name, position, season), grp in daily_adp.groupby(
            ["player_id", "player_name", "position", "season"]
        ):
            grp = grp.sort_values("snapshot_date").set_index("snapshot_date")
            min_date = grp.index.min()
            max_date = daily_adp[daily_adp["season"] == season]["snapshot_date"].max()
            all_dates = pd.date_range(min_date, max_date, freq="D").date
            grp = grp.reindex(all_dates)
            grp["adp"] = grp["adp"].ffill()
            grp = grp.dropna(subset=["adp"])
            for snap_date, row in grp.iterrows():
                ffilled_rows.append({
                    "player_id": player_id,
                    "player_name": player_name,
                    "position": position,
                    "season": season,
                    "snapshot_date": str(snap_date),
                    "adp": round(row["adp"], 2),
                })

        if ffilled_rows:
            ts_df = pd.DataFrame(ffilled_rows)
            ts_df.to_sql("adp_daily_timeseries", conn, if_exists="append", index=False)
            conn.commit()
            print(f"  Wrote {len(ffilled_rows):,} daily ADP rows")
        else:
            print("  No projection_adp data to build time series from")

    # Write to DB
    conn.execute("DELETE FROM adp_player_summary")
    player_summary[
        ["player_id", "season", "player_name", "position", "avg_pick", "pick_std",
         "ownership_pct", "draft_count", "total_season_drafts",
         "avg_projection_adp", "min_projection_adp", "max_projection_adp"]
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
        total_rosters = int(season_roster_counts[season])

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
                        "avg_per_draft": round(cumulative / total_rosters, 3),
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

    # ------------------------------------------------------------------
    # 4. AdpPickDistribution — per player/season, pick count per pick number
    # ------------------------------------------------------------------
    print("Computing pick distributions ...")
    pick_dist = (
        picks_df.groupby(["player_id", "season", "pick_number"])
        .size()
        .rename("count")
        .reset_index()
    )
    conn.execute("DELETE FROM adp_pick_distribution")
    pick_dist[["player_id", "season", "pick_number", "count"]].to_sql(
        "adp_pick_distribution", conn, if_exists="append", index=False
    )
    conn.commit()
    print(f"  Wrote {len(pick_dist):,} pick distribution rows")

    conn.close()
    print("Done.")


if __name__ == "__main__":
    main()
