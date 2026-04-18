"""
Precompute player combo co-ownership tables.

For each season and combo size (2, 3, 4), counts how many rosters contained
every player in the combination. Stores the top combos by pair_rate.

Tables written to bestball.db:
  combo_pairs  — per-season/combo_size co-ownership leaderboard

Run:
  python -m scripts.precompute_combos
"""

from __future__ import annotations

import sqlite3
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

import pandas as pd

DB_PATH = Path("data/bestball.db")

# Store all pairs (k=2) above this minimum count; for k=3/4 store top N
MIN_PAIR_COUNT = 5
TOP_N_K3 = 1000
TOP_N_K4 = 500
# For k>=3, only include players in the top-N by total appearances per season
TOP_PLAYERS_FOR_LARGE_COMBOS = 100


def _ensure_table(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS combo_pairs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            season INTEGER NOT NULL,
            combo_size INTEGER NOT NULL,
            p1_id INTEGER NOT NULL,
            p1_name TEXT NOT NULL,
            p1_total INTEGER NOT NULL,
            p2_id INTEGER NOT NULL,
            p2_name TEXT NOT NULL,
            p3_id INTEGER,
            p3_name TEXT,
            p4_id INTEGER,
            p4_name TEXT,
            pair_count INTEGER NOT NULL,
            pair_rate REAL NOT NULL
        )
    """)
    conn.commit()


def main() -> None:
    print(f"Connecting to {DB_PATH} ...")
    conn = sqlite3.connect(DB_PATH, timeout=60)

    _ensure_table(conn)

    print("Loading picks ...")
    picks_df = pd.read_sql(
        """
        SELECT
            pk.draft_id,
            pk.username,
            pk.player_id,
            p.name AS player_name,
            d.season
        FROM picks pk
        JOIN players p  ON pk.player_id = p.player_id
        JOIN drafts  d  ON pk.draft_id  = d.draft_id
        WHERE d.season >= 2024
          AND p.position IN ('P', 'IF', 'OF')
        """,
        conn,
    )
    print(f"  Loaded {len(picks_df):,} picks across {picks_df['season'].nunique()} seasons")

    # Build roster key — unique per team
    # 2026+: draft_id is room-level (shared by 12 teams) → key = draft_id|username
    # pre-2026: draft_id is already team-level (tournament_entry_id) → key = draft_id
    picks_df["draft_id_str"] = picks_df["draft_id"].astype(str)
    picks_df["username_str"] = picks_df["username"].fillna("").astype(str)
    picks_df["roster_key"] = picks_df.apply(
        lambda r: f"{r['draft_id_str']}|{r['username_str']}"
        if r["season"] >= 2026
        else r["draft_id_str"],
        axis=1,
    )

    # Player name lookup
    name_lookup: dict[int, str] = dict(
        zip(picks_df["player_id"], picks_df["player_name"])
    )

    conn.execute("DELETE FROM combo_pairs")
    conn.commit()

    all_rows: list[dict] = []

    for season in sorted(picks_df["season"].unique()):
        season_picks = picks_df[picks_df["season"] == season]
        print(f"\nSeason {season}")

        # Per-roster player sets
        rosters: list[frozenset[int]] = [
            frozenset(grp["player_id"])
            for _, grp in season_picks.groupby("roster_key")
        ]
        total_rosters = len(rosters)
        print(f"  {total_rosters:,} rosters")

        # Individual player totals
        player_totals: Counter[int] = Counter()
        for roster in rosters:
            for pid in roster:
                player_totals[pid] += 1

        # Top players for k=3/4 (limit combo explosion)
        top_players = set(
            pid for pid, _ in player_totals.most_common(TOP_PLAYERS_FOR_LARGE_COMBOS)
        )

        for k in [2, 3, 4]:
            print(f"  k={k} ...", end=" ", flush=True)
            combo_counts: Counter[tuple[int, ...]] = Counter()

            for roster in rosters:
                if k == 2:
                    pool = sorted(roster)
                else:
                    pool = sorted(roster & top_players)

                for combo in combinations(pool, k):
                    combo_counts[combo] += 1

            # Build rows
            rows: list[dict] = []
            for combo, count in combo_counts.items():
                if count < MIN_PAIR_COUNT:
                    continue

                # p1 = rarest player (min total) → highest conditional pair_rate
                sorted_combo = sorted(combo, key=lambda p: player_totals[p])
                p1_id = sorted_combo[0]
                p1_total = player_totals[p1_id]
                pair_rate = round(count / p1_total * 100, 2)

                row: dict = {
                    "season": season,
                    "combo_size": k,
                    "p1_id": p1_id,
                    "p1_name": name_lookup.get(p1_id, str(p1_id)),
                    "p1_total": p1_total,
                    "p2_id": sorted_combo[1],
                    "p2_name": name_lookup.get(sorted_combo[1], str(sorted_combo[1])),
                    "p3_id": sorted_combo[2] if k >= 3 else None,
                    "p3_name": name_lookup.get(sorted_combo[2], str(sorted_combo[2])) if k >= 3 else None,
                    "p4_id": sorted_combo[3] if k == 4 else None,
                    "p4_name": name_lookup.get(sorted_combo[3], str(sorted_combo[3])) if k == 4 else None,
                    "pair_count": count,
                    "pair_rate": pair_rate,
                }
                rows.append(row)

            # For k>=3 cap to top N by pair_rate
            rows.sort(key=lambda r: r["pair_rate"], reverse=True)
            if k == 3:
                rows = rows[:TOP_N_K3]
            elif k == 4:
                rows = rows[:TOP_N_K4]

            print(f"{len(rows):,} rows")
            all_rows.extend(rows)

    if all_rows:
        df = pd.DataFrame(all_rows)
        df.to_sql("combo_pairs", conn, if_exists="append", index=False)
        conn.commit()
        print(f"\nWrote {len(all_rows):,} total combo rows")
    else:
        print("No rows to write.")

    conn.close()
    print("Done.")


if __name__ == "__main__":
    main()
