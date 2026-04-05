"""
Weekly lineup setting algorithm for Underdog best ball.

Given a roster of up to 20 players and their scores for a given week:
1. Split by position: P, IF, OF
2. Sort each group by score descending
3. Starters = top 3P + top 3IF + top 3OF
4. FLEX = highest scorer among remaining IF/OF not already starting
5. Bench = everyone else
6. Weekly score = sum of starters + FLEX

Pitchers are NEVER eligible for FLEX.
This algorithm is called for every historical week when computing BPCOR,
team weekly scores, and peak 2-week window calculations.
"""

from __future__ import annotations

from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Input / output types
# ---------------------------------------------------------------------------

@dataclass
class RosterPlayer:
    player_id: int
    position: str     # "P", "IF", "OF"
    weekly_score: float
    name: str = ""


@dataclass
class LineupResult:
    starters: list[RosterPlayer]    # 3P + 3IF + 3OF (9 total)
    flex: RosterPlayer | None       # 1 IF or OF
    bench: list[RosterPlayer]
    total_score: float

    # Replacement level scores for BPCOR calculation
    hitter_replacement_score: float = 0.0   # highest bench IF/OF score
    pitcher_replacement_score: float = 0.0  # highest bench P score


# ---------------------------------------------------------------------------
# Core algorithm
# ---------------------------------------------------------------------------

STARTERS_PER_POSITION = {"P": 3, "IF": 3, "OF": 3}
FLEX_ELIGIBLE = {"IF", "OF"}


def set_lineup(players: list[RosterPlayer]) -> LineupResult:
    """
    Set the optimal weekly lineup for a best ball roster.

    Rules:
    - Fill 3P, 3IF, 3OF starter slots from the top scorers at each position.
    - Fill 1 FLEX slot from the highest-scoring remaining IF or OF.
    - Everyone else is bench.
    - Replacement levels are the highest bench scores at each position group.

    Players missing a valid position are silently excluded.
    """
    pitchers = [p for p in players if p.position == "P"]
    infielders = [p for p in players if p.position == "IF"]
    outfielders = [p for p in players if p.position == "OF"]

    # Sort each group descending by score
    pitchers.sort(key=lambda p: p.weekly_score, reverse=True)
    infielders.sort(key=lambda p: p.weekly_score, reverse=True)
    outfielders.sort(key=lambda p: p.weekly_score, reverse=True)

    # Select starters
    p_starters = pitchers[:3]
    if_starters = infielders[:3]
    of_starters = outfielders[:3]

    starters = p_starters + if_starters + of_starters

    # FLEX candidates: remaining IF + remaining OF not already starting
    if_bench_candidates = infielders[3:]
    of_bench_candidates = outfielders[3:]
    flex_candidates = if_bench_candidates + of_bench_candidates
    flex_candidates.sort(key=lambda p: p.weekly_score, reverse=True)

    flex_player = flex_candidates[0] if flex_candidates else None
    non_flex_bench = flex_candidates[1:] if flex_candidates else []

    # Remaining pitchers are bench
    p_bench = pitchers[3:]

    bench = p_bench + non_flex_bench

    # Total score
    starter_scores = sum(p.weekly_score for p in starters)
    flex_score = flex_player.weekly_score if flex_player else 0.0
    total = starter_scores + flex_score

    # Replacement level
    hitter_replacement = _highest_score(non_flex_bench)
    pitcher_replacement = _highest_score(p_bench)

    return LineupResult(
        starters=starters,
        flex=flex_player,
        bench=bench,
        total_score=round(total, 2),
        hitter_replacement_score=hitter_replacement,
        pitcher_replacement_score=pitcher_replacement,
    )


def _highest_score(players: list[RosterPlayer]) -> float:
    """Return the highest weekly score among a list of players, or 0.0."""
    if not players:
        return 0.0
    return max(p.weekly_score for p in players)


# ---------------------------------------------------------------------------
# Helper: build RosterPlayer list from a DataFrame week slice
# ---------------------------------------------------------------------------

def roster_players_from_df_rows(rows: list[dict]) -> list[RosterPlayer]:
    """
    Convert a list of row dicts (from game log Parquet) into RosterPlayer objects.
    Each dict should have: player_id, position, weekly_score (or calculated_points).
    """
    result = []
    for row in rows:
        score = float(row.get("weekly_score", row.get("calculated_points", 0.0)))
        result.append(RosterPlayer(
            player_id=int(row["player_id"]),
            position=str(row["position"]),
            weekly_score=score,
            name=str(row.get("name", "")),
        ))
    return result


# ---------------------------------------------------------------------------
# Weekly team score from raw player-week scores (simple interface)
# ---------------------------------------------------------------------------

def compute_weekly_score(
    player_week_scores: dict[int, tuple[str, float]]  # {player_id: (position, score)}
) -> LineupResult:
    """
    Convenience wrapper. Input is a dict mapping player_id to (position, score).
    """
    players = [
        RosterPlayer(player_id=pid, position=pos, weekly_score=score)
        for pid, (pos, score) in player_week_scores.items()
    ]
    return set_lineup(players)
