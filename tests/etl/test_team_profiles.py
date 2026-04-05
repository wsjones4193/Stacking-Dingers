"""
Tests for backend/etl/team_profiles.py

Covers:
- Peak 2-week window calculation
- Consistency score
- Ceiling tier assignment
- Draft archetype tagging
"""

import pytest

from backend.etl.team_profiles import (
    CONSECUTIVE_WEEK_PAIRS,
    assign_ceiling_tiers,
    compute_consistency_score,
    compute_peak_2wk_window,
    tag_archetype,
)


# ---------------------------------------------------------------------------
# Peak 2-week window
# ---------------------------------------------------------------------------

class TestComputePeak2wkWindow:
    def test_basic_peak(self):
        scores = {1: 100, 2: 120, 3: 80, 4: 150, 5: 90}
        # Week 3+4 = 230, Week 4+5 = 240, Week 2+3 = 200
        peak, weeks = compute_peak_2wk_window(scores, [(w, w+1) for w in range(1, 5)])
        assert peak == pytest.approx(240.0)
        assert weeks == [4, 5]

    def test_empty_scores(self):
        peak, weeks = compute_peak_2wk_window({}, CONSECUTIVE_WEEK_PAIRS)
        assert peak == 0.0
        assert weeks is None

    def test_single_week(self):
        scores = {1: 100}
        peak, weeks = compute_peak_2wk_window(scores, [(1, 2)])
        # Week 2 missing → treated as 0
        assert peak == pytest.approx(100.0)
        assert weeks == [1, 2]

    def test_missing_weeks_treated_as_zero(self):
        scores = {5: 200, 7: 150}
        # Only pair (5,6) and (6,7) etc. Week 6 missing = 0
        peak, weeks = compute_peak_2wk_window(scores, [(5, 6), (6, 7)])
        # (5,6) = 200+0=200, (6,7) = 0+150=150 → peak = 200
        assert peak == pytest.approx(200.0)
        assert weeks == [5, 6]

    def test_consecutive_week_pairs_count(self):
        # 24-week season has 23 consecutive pairs
        assert len(CONSECUTIVE_WEEK_PAIRS) == 23

    def test_uses_tournament_weeks_not_calendar(self):
        # Week 17 is one tournament week (2 calendar weeks) — still counts as one
        scores = {16: 100, 17: 200, 18: 150}
        peak, weeks = compute_peak_2wk_window(scores, [(16, 17), (17, 18)])
        assert peak == pytest.approx(350.0)  # 17+18 = 200+150
        assert weeks == [17, 18]


# ---------------------------------------------------------------------------
# Consistency score
# ---------------------------------------------------------------------------

class TestComputeConsistencyScore:
    def test_consistent_team(self):
        scores = {w: 100.0 for w in range(1, 19)}
        result = compute_consistency_score(scores)
        assert result == pytest.approx(0.0, abs=1e-6)

    def test_volatile_team(self):
        scores = {1: 50, 2: 200, 3: 50, 4: 200}
        result = compute_consistency_score(scores)
        assert result > 0

    def test_too_few_weeks(self):
        assert compute_consistency_score({1: 100}) is None
        assert compute_consistency_score({}) is None

    def test_ignores_zero_score_weeks(self):
        # Zero-score weeks (e.g. bye weeks) shouldn't drag down the SD
        scores = {1: 100, 2: 110, 3: 0, 4: 105}
        # Only non-zero: [100, 110, 105] → std dev ~5
        result = compute_consistency_score(scores)
        non_zero_scores = [100, 110, 105]
        import statistics
        expected = round(statistics.stdev(non_zero_scores), 3)
        assert result == pytest.approx(expected)


# ---------------------------------------------------------------------------
# Ceiling tier assignment
# ---------------------------------------------------------------------------

class TestAssignCeilingTiers:
    def test_top1_assigned(self):
        peaks = {str(i): float(100 - i) for i in range(100)}
        advancing = set()
        tiers = assign_ceiling_tiers(peaks, advancing)
        assert tiers["0"] == "top1"

    def test_top10_assigned(self):
        peaks = {str(i): float(100 - i) for i in range(100)}
        tiers = assign_ceiling_tiers(peaks, set())
        # Top 1% = index 0. Top 10% = indices 0-9. Index 5 should be top10 (not top1).
        assert tiers["5"] in ("top1", "top10")

    def test_advancing_assigned_when_not_top_percentile(self):
        peaks = {"a": 50.0, "b": 49.0, "c": 10.0}
        advancing = {"c"}
        tiers = assign_ceiling_tiers(peaks, advancing)
        assert tiers["c"] == "advancing"

    def test_none_assigned_to_low_performers(self):
        peaks = {str(i): float(100 - i) for i in range(200)}
        tiers = assign_ceiling_tiers(peaks, set())
        # Last item has peak = 100-199 = -99 → None
        assert tiers["199"] is None

    def test_empty_input(self):
        assert assign_ceiling_tiers({}, set()) == {}


# ---------------------------------------------------------------------------
# Draft archetype tagging
# ---------------------------------------------------------------------------

class TestTagArchetype:
    def _seq(self, positions: list[str]) -> list[str]:
        return positions

    def test_p_heavy(self):
        # 2 P picks in first 4 rounds (first 48 picks of a 12-person draft)
        seq = ["P", "IF", "P", "OF"] + ["IF"] * 16
        assert tag_archetype(seq) == "p_heavy"

    def test_if_heavy(self):
        seq = ["IF", "IF", "IF", "OF", "P"] + ["OF"] * 15
        assert tag_archetype(seq) == "if_heavy"

    def test_of_heavy(self):
        seq = ["OF", "OF", "OF", "IF", "P"] + ["IF"] * 15
        assert tag_archetype(seq) == "of_heavy"

    def test_late_p(self):
        # First P is at pick index 90+ (round 8+ in 12-person draft)
        seq = ["IF", "OF"] * 44 + ["P"] + ["IF"] * 3
        assert tag_archetype(seq) == "late_p"

    def test_balanced(self):
        # No dominant pattern
        seq = ["IF", "OF", "P", "IF", "OF", "P", "IF", "OF"] * 3
        assert tag_archetype(seq) == "balanced"

    def test_p_heavy_takes_priority_over_balanced(self):
        # 2 P in first 4 picks — even if otherwise balanced
        seq = ["P", "IF", "P", "OF", "OF", "IF"] * 4
        assert tag_archetype(seq) == "p_heavy"

    def test_no_p_at_all(self):
        seq = ["IF", "OF"] * 10
        assert tag_archetype(seq) == "late_p"

    def test_empty_sequence(self):
        assert tag_archetype([]) == "balanced"
