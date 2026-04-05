"""
Team season profiles: peak 2-week windows, consistency scores,
ceiling tiers, and draft archetypes.

Computes and stores:
  - peak_2wk_score: highest combined score from any consecutive week pair
  - peak_window_weeks: [week_a, week_b] for that peak
  - consistency_score: std dev of weekly team scores
  - ceiling_tier: "top1", "top10", "advancing", or None
  - draft archetypes: rule-based binning of pick sequences

Historical data integrity: R1 advance rate uses top-2-of-12 recalculated
independently for all seasons, not the original tournament advancement data.
"""

from __future__ import annotations

import json
import logging
import statistics
from collections import defaultdict
from typing import Optional

from sqlmodel import Session, select

from backend.constants import (
    ARCHETYPE_RULES,
    R1_ADVANCE_COUNT,
    R1_GROUP_SIZE,
    ROUND_CONFIG,
)
from backend.db.models import (
    Draft,
    DraftSequence,
    GroupStanding,
    Pick,
    Player,
    TeamSeasonProfile,
    WeeklyScore,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Peak 2-week window computation
# ---------------------------------------------------------------------------

def compute_peak_2wk_window(
    weekly_scores: dict[int, float],   # {week_number: team_score}
    consecutive_week_pairs: list[tuple[int, int]],
) -> tuple[float, Optional[list[int]]]:
    """
    Find the highest combined score from any consecutive week pair.

    consecutive_week_pairs: list of (week_a, week_b) that are adjacent
    tournament weeks (e.g., [(1,2), (2,3), ..., (17,18), (18,19), ...])
    Note: week 17 spans two calendar weeks but is one tournament week.

    Returns (peak_score, [week_a, week_b]) or (0.0, None) if no data.
    """
    best_score = 0.0
    best_pair: Optional[list[int]] = None

    for week_a, week_b in consecutive_week_pairs:
        score_a = weekly_scores.get(week_a, 0.0)
        score_b = weekly_scores.get(week_b, 0.0)
        combined = score_a + score_b
        if combined > best_score:
            best_score = combined
            best_pair = [week_a, week_b]

    return best_score, best_pair


# All consecutive tournament week pairs for a 24-week season
CONSECUTIVE_WEEK_PAIRS = [(w, w + 1) for w in range(1, 24)]


# ---------------------------------------------------------------------------
# Consistency score
# ---------------------------------------------------------------------------

def compute_consistency_score(weekly_scores: dict[int, float]) -> Optional[float]:
    """
    Standard deviation of weekly team scores.
    Low SD = consistent grinder. High SD = boom/bust peaker.
    Returns None if fewer than 2 data points.
    """
    scores = [v for v in weekly_scores.values() if v > 0]
    if len(scores) < 2:
        return None
    return round(statistics.stdev(scores), 3)


# ---------------------------------------------------------------------------
# Ceiling tier assignment
# ---------------------------------------------------------------------------

def assign_ceiling_tiers(
    team_peaks: dict[str, float],   # {draft_id: peak_2wk_score}
    advancing_draft_ids: set[str],
) -> dict[str, Optional[str]]:
    """
    Assign ceiling tier to each team.
    Tiers: "top1", "top10", "advancing", None

    "advancing" is mutually exclusive from percentile tiers —
    only advancing teams that aren't in top1/top10 get "advancing".
    """
    if not team_peaks:
        return {}

    scores = sorted(team_peaks.values(), reverse=True)
    n = len(scores)
    top1_threshold = scores[max(0, int(n * 0.01) - 1)]
    top10_threshold = scores[max(0, int(n * 0.10) - 1)]

    tiers: dict[str, Optional[str]] = {}
    for draft_id, peak in team_peaks.items():
        if peak >= top1_threshold:
            tiers[draft_id] = "top1"
        elif peak >= top10_threshold:
            tiers[draft_id] = "top10"
        elif draft_id in advancing_draft_ids:
            tiers[draft_id] = "advancing"
        else:
            tiers[draft_id] = None

    return tiers


# ---------------------------------------------------------------------------
# Draft archetype tagging
# ---------------------------------------------------------------------------

def tag_archetype(pick_sequence: list[str]) -> str:
    """
    Rule-based archetype tagging from a pick sequence (list of positions).

    Archetypes (applied in priority order — first match wins):
      p_heavy  : 2+ P picks in first 5 picks (very early pitcher investment)
      late_p   : no P picked until round 8+ (pick 85+ in a 12-person draft)
      if_heavy : 3+ of first 5 picks = IF
      of_heavy : 3+ of first 5 picks = OF
      balanced : default
    """
    if not pick_sequence:
        return "balanced"

    first_5 = pick_sequence[:5]

    p_in_first_5 = sum(1 for pos in first_5 if pos == "P")
    if_in_first_5 = sum(1 for pos in first_5 if pos == "IF")
    of_in_first_5 = sum(1 for pos in first_5 if pos == "OF")

    # Find first P pick index (0-based)
    first_p_idx = next(
        (i for i, pos in enumerate(pick_sequence) if pos == "P"), None
    )
    first_p_round = (first_p_idx // 12 + 1) if first_p_idx is not None else None

    if p_in_first_5 >= 2:
        return "p_heavy"
    if first_p_round is None or first_p_round >= 8:
        return "late_p"
    if if_in_first_5 >= 3:
        return "if_heavy"
    if of_in_first_5 >= 3:
        return "of_heavy"
    return "balanced"


# ---------------------------------------------------------------------------
# Recalculate R1 advancement (historical data integrity)
# ---------------------------------------------------------------------------

def recalculate_r1_advancement(
    season: int,
    session: Session,
) -> dict[str, bool]:
    """
    Independently calculate which teams advanced in R1 as top-2-of-12,
    based on computed total points — ignoring original tournament advancement data.

    Returns {draft_id: advanced_bool}.
    """
    # Get all R1 group standings for this season
    stmt = (
        select(GroupStanding)
        .where(GroupStanding.season == season)
        .where(GroupStanding.round_number == 1)
    )
    standings = session.exec(stmt).all()

    # Group by group_id, sort by total_points desc, top 2 advance
    by_group: dict[int, list[GroupStanding]] = defaultdict(list)
    for s in standings:
        by_group[s.group_id].append(s)

    advancement: dict[str, bool] = {}
    for group_id, group_standings in by_group.items():
        sorted_standings = sorted(group_standings, key=lambda x: x.total_points, reverse=True)
        for i, standing in enumerate(sorted_standings):
            advancement[standing.draft_id] = i < R1_ADVANCE_COUNT

    return advancement


# ---------------------------------------------------------------------------
# Build and store team season profiles
# ---------------------------------------------------------------------------

def compute_and_store_team_profiles(
    season: int,
    session: Session,
) -> dict:
    """
    For every team in a season:
    1. Compute peak 2-week window and consistency score
    2. Assign ceiling tiers
    3. Store in team_season_profiles
    4. Build draft sequences and tag archetypes
    5. Store in draft_sequences

    Returns a summary dict.
    """
    # Load all weekly scores for this season
    stmt = select(WeeklyScore).where(WeeklyScore.season == season)
    all_scores = session.exec(stmt).all()

    # Group weekly scores by draft_id
    team_weekly: dict[str, dict[int, float]] = defaultdict(dict)
    for score in all_scores:
        team_weekly[score.draft_id][score.week_number] = (
            team_weekly[score.draft_id].get(score.week_number, 0.0) + score.calculated_score
            if score.is_starter or score.is_flex else
            team_weekly[score.draft_id].get(score.week_number, 0.0)
        )

    # Load advancement data
    advancing = recalculate_r1_advancement(season, session)
    advancing_ids = {did for did, adv in advancing.items() if adv}

    # Compute peaks
    team_peaks = {}
    for draft_id, weekly_scores in team_weekly.items():
        peak, _ = compute_peak_2wk_window(weekly_scores, CONSECUTIVE_WEEK_PAIRS)
        team_peaks[draft_id] = peak

    # Assign tiers
    tiers = assign_ceiling_tiers(team_peaks, advancing_ids)

    # Load existing profiles to update vs. insert
    existing_profiles = {
        p.draft_id: p
        for p in session.exec(
            select(TeamSeasonProfile).where(TeamSeasonProfile.season == season)
        ).all()
    }

    profiles_written = 0
    for draft_id, weekly_scores in team_weekly.items():
        peak_score, peak_weeks = compute_peak_2wk_window(
            weekly_scores, CONSECUTIVE_WEEK_PAIRS
        )
        consistency = compute_consistency_score(weekly_scores)
        ceiling_tier = tiers.get(draft_id)

        # Load round scores from group standings
        standing_stmt = (
            select(GroupStanding)
            .where(GroupStanding.draft_id == draft_id)
            .where(GroupStanding.season == season)
        )
        standings_by_round = {s.round_number: s for s in session.exec(standing_stmt).all()}
        round_reached = max(
            (r for r in standings_by_round if standings_by_round[r].advanced or r == 1),
            default=1,
        )

        if draft_id in existing_profiles:
            profile = existing_profiles[draft_id]
        else:
            profile = TeamSeasonProfile(draft_id=draft_id, season=season)

        profile.peak_2wk_score = round(peak_score, 2)
        profile.peak_window_weeks_json = json.dumps(peak_weeks) if peak_weeks else None
        profile.consistency_score = consistency
        profile.ceiling_tier = ceiling_tier
        profile.round_reached = round_reached
        profile.r2_score = standings_by_round[2].total_points if 2 in standings_by_round else None
        profile.r3_score = standings_by_round[3].total_points if 3 in standings_by_round else None
        profile.r4_score = standings_by_round[4].total_points if 4 in standings_by_round else None

        session.add(profile)
        profiles_written += 1

    session.commit()

    # Build draft sequences and archetypes
    sequences_written = _build_draft_sequences(season, session)

    return {
        "season": season,
        "profiles_written": profiles_written,
        "sequences_written": sequences_written,
    }


def _build_draft_sequences(season: int, session: Session) -> int:
    """Build pick sequence arrays and tag archetypes for all drafts in a season."""
    # Load all picks for this season, ordered by pick_number
    draft_ids = {
        d.draft_id
        for d in session.exec(select(Draft).where(Draft.season == season)).all()
    }
    stmt = (
        select(Pick, Player)
        .join(Player, Pick.player_id == Player.player_id)
        .where(Pick.draft_id.in_(draft_ids))
        .order_by(Pick.draft_id, Pick.pick_number)
    )
    rows = session.exec(stmt).all()

    # Group by draft_id
    picks_by_draft: dict[str, list[str]] = defaultdict(list)
    for pick, player in rows:
        picks_by_draft[pick.draft_id].append(player.position)

    existing = {
        s.draft_id: s
        for s in session.exec(
            select(DraftSequence).where(DraftSequence.season == season)
        ).all()
    }

    # Load advancement for advance_round
    standing_stmt = (
        select(GroupStanding)
        .where(GroupStanding.season == season)
    )
    advance_round_map: dict[str, int] = {}
    for standing in session.exec(standing_stmt).all():
        if standing.advanced:
            current = advance_round_map.get(standing.draft_id, 1)
            advance_round_map[standing.draft_id] = max(current, standing.round_number + 1)

    written = 0
    for draft_id, sequence in picks_by_draft.items():
        archetype = tag_archetype(sequence)
        advance_round = advance_round_map.get(draft_id, 1)

        if draft_id in existing:
            seq = existing[draft_id]
        else:
            seq = DraftSequence(draft_id=draft_id, season=season)

        seq.pick_sequence = sequence
        seq.archetype_tag = archetype
        seq.advance_round = advance_round
        session.add(seq)
        written += 1

    session.commit()
    return written
