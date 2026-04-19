"""
Precompute player combo co-ownership tables using association rule mining metrics.

Metrics computed per combination:
  support    = pair_count / total_rosters        (% of all rosters with this combo)
  confidence = pair_count / p1_total             (given p1, how often the rest appear)
  lift       = support / product(P(each player)) (how much more often than chance)
  conviction = (1 - P(p2)) / (1 - confidence)   (strength of implication; k=2 only)

Tables written to bestball.db:
  combo_pairs — per-season/combo_size association rule leaderboard

Run:
  python -m scripts.precompute_combos
"""

from __future__ import annotations

import sqlite3
from collections import Counter
from itertools import combinations
from pathlib import Path
from functools import reduce

import pandas as pd

DB_PATH = Path("data/bestball.db")

MIN_PAIR_COUNT = 5
TOP_N_K3 = 1000
TOP_N_K4 = 500
TOP_PLAYERS_FOR_LARGE_COMBOS = 100


def _ensure_table(conn: sqlite3.Connection) -> None:
    conn.execute("DROP TABLE IF EXISTS combo_pairs")
    conn.execute("""
        CREATE TABLE combo_pairs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            season INTEGER NOT NULL,
            combo_size INTEGER NOT NULL,
            p1_id INTEGER NOT NULL,
            p1_name TEXT NOT NULL,
            p1_total INTEGER NOT NULL,
            p2_id INTEGER NOT NULL,
            p2_name TEXT NOT NULL,
            p2_total INTEGER NOT NULL,
            p3_id INTEGER,
            p3_name TEXT,
            p4_id INTEGER,
            p4_name TEXT,
            pair_count INTEGER NOT NULL,
            support REAL NOT NULL,
            confidence REAL NOT NULL,
            lift REAL NOT NULL,
            conviction REAL
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
    # 2026+: draft_id is room-level → key = draft_id|username
    # pre-2026: draft_id is already team-level → key = draft_id
    picks_df["draft_id_str"] = picks_df["draft_id"].astype(str)
    picks_df["username_str"] = picks_df["username"].fillna("").astype(str)
    picks_df["roster_key"] = picks_df.apply(
        lambda r: f"{r['draft_id_str']}|{r['username_str']}"
        if r["season"] >= 2026
        else r["draft_id_str"],
        axis=1,
    )

    name_lookup: dict[int, str] = dict(zip(picks_df["player_id"], picks_df["player_name"]))

    all_rows: list[dict] = []

    for season in sorted(picks_df["season"].unique()):
        season_picks = picks_df[picks_df["season"] == season]
        print(f"\nSeason {season}")

        rosters: list[frozenset[int]] = [
            frozenset(grp["player_id"])
            for _, grp in season_picks.groupby("roster_key")
        ]
        total_rosters = len(rosters)
        print(f"  {total_rosters:,} rosters")

        # Individual player totals → P(player)
        player_totals: Counter[int] = Counter()
        for roster in rosters:
            for pid in roster:
                player_totals[pid] += 1

        top_players = set(
            pid for pid, _ in player_totals.most_common(TOP_PLAYERS_FOR_LARGE_COMBOS)
        )

        for k in [2, 3, 4]:
            print(f"  k={k} ...", end=" ", flush=True)
            combo_counts: Counter[tuple[int, ...]] = Counter()

            for roster in rosters:
                pool = sorted(roster) if k == 2 else sorted(roster & top_players)
                for combo in combinations(pool, k):
                    combo_counts[combo] += 1

            rows: list[dict] = []
            for combo, count in combo_counts.items():
                if count < MIN_PAIR_COUNT:
                    continue

                sorted_combo = sorted(combo)
                p1_id = sorted_combo[0]
                p2_id = sorted_combo[1]
                p1_total = player_totals[p1_id]
                p2_total = player_totals[p2_id]

                # Association rule metrics
                support    = count / total_rosters
                confidence = count / p1_total
                # lift = P(all) / product(P(each)) — adjusted for k
                p_each = [player_totals[pid] / total_rosters for pid in sorted_combo]
                p_all  = count / total_rosters
                p_product = reduce(lambda a, b: a * b, p_each)
                lift = round(p_all / p_product, 4) if p_product > 0 else None

                # Conviction only meaningful for k=2 (direction: p1 → p2)
                conviction = None
                if k == 2:
                    p2_rate = p2_total / total_rosters
                    conf_denom = 1 - confidence
                    conviction = round((1 - p2_rate) / conf_denom, 4) if conf_denom > 0 else None

                row: dict = {
                    "season": season,
                    "combo_size": k,
                    "p1_id": p1_id,
                    "p1_name": name_lookup.get(p1_id, str(p1_id)),
                    "p1_total": p1_total,
                    "p2_id": p2_id,
                    "p2_name": name_lookup.get(p2_id, str(p2_id)),
                    "p2_total": p2_total,
                    "p3_id":   sorted_combo[2] if k >= 3 else None,
                    "p3_name": name_lookup.get(sorted_combo[2], str(sorted_combo[2])) if k >= 3 else None,
                    "p4_id":   sorted_combo[3] if k == 4 else None,
                    "p4_name": name_lookup.get(sorted_combo[3], str(sorted_combo[3])) if k == 4 else None,
                    "pair_count": count,
                    "support":    round(support * 100, 4),    # stored as %
                    "confidence": round(confidence * 100, 4), # stored as %
                    "lift":       lift,
                    "conviction": conviction,
                }
                rows.append(row)

            # Cap k=3/4 by lift (most interesting metric beyond raw count)
            rows.sort(key=lambda r: r["lift"] or 0, reverse=True)
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
