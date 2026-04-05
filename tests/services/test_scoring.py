"""
Tests for backend/services/scoring.py

Covers:
- Hitter scoring with all categories
- Pitcher scoring with QS derivation
- IP conversion edge cases
- Singles derivation
- Zero-stat games
- Boundary conditions for QS
"""

import pytest

from backend.services.scoring import (
    HitterGameLog,
    PitcherGameLog,
    ip_to_true_innings,
    score_hitter_game,
    score_hitter_row,
    score_pitcher_game,
    score_pitcher_row,
)


# ---------------------------------------------------------------------------
# IP conversion
# ---------------------------------------------------------------------------

class TestIpToTrueInnings:
    def test_whole_innings(self):
        assert ip_to_true_innings(6.0) == pytest.approx(6.0)
        assert ip_to_true_innings(7.0) == pytest.approx(7.0)

    def test_one_out(self):
        # 6.1 = 6 innings + 1/3
        assert ip_to_true_innings(6.1) == pytest.approx(6 + 1/3, rel=1e-4)

    def test_two_outs(self):
        # 6.2 = 6 innings + 2/3
        assert ip_to_true_innings(6.2) == pytest.approx(6 + 2/3, rel=1e-4)

    def test_zero(self):
        assert ip_to_true_innings(0.0) == pytest.approx(0.0)

    def test_complete_game(self):
        assert ip_to_true_innings(9.0) == pytest.approx(9.0)


# ---------------------------------------------------------------------------
# Hitter scoring
# ---------------------------------------------------------------------------

class TestScoreHitterGame:
    def _make_log(self, **kwargs) -> HitterGameLog:
        defaults = dict(
            player_id=1, game_date="2026-04-01", season=2026, position="IF",
            pa=4, ab=4, h=0, doubles=0, triples=0, home_runs=0,
            runs=0, rbi=0, stolen_bases=0, walks=0, hit_by_pitch=0,
        )
        defaults.update(kwargs)
        return HitterGameLog(**defaults)

    def test_zero_game(self):
        result = score_hitter_game(self._make_log())
        assert result.calculated_points == 0.0

    def test_single(self):
        result = score_hitter_game(self._make_log(h=1))
        assert result.calculated_points == 3.0  # 1B = 3
        assert result.singles == 1

    def test_double(self):
        result = score_hitter_game(self._make_log(h=1, doubles=1))
        assert result.calculated_points == 6.0  # 2B = 6
        assert result.singles == 0

    def test_triple(self):
        result = score_hitter_game(self._make_log(h=1, triples=1))
        assert result.calculated_points == 8.0  # 3B = 8

    def test_home_run(self):
        result = score_hitter_game(self._make_log(h=1, home_runs=1))
        assert result.calculated_points == 10.0  # HR = 10

    def test_rbi_and_run(self):
        result = score_hitter_game(self._make_log(rbi=2, runs=1))
        assert result.calculated_points == 6.0  # 2*2 + 1*2

    def test_stolen_base(self):
        result = score_hitter_game(self._make_log(stolen_bases=1))
        assert result.calculated_points == 4.0

    def test_walk(self):
        result = score_hitter_game(self._make_log(walks=1))
        assert result.calculated_points == 3.0

    def test_hbp(self):
        result = score_hitter_game(self._make_log(hit_by_pitch=1))
        assert result.calculated_points == 3.0

    def test_big_game(self):
        # HR(10) + 2B(6) + 1B(3) + 2 RBI(4) + R(2) + SB(4) = 29
        result = score_hitter_game(self._make_log(
            h=3, home_runs=1, doubles=1,  # singles=1
            rbi=2, runs=1, stolen_bases=1,
        ))
        assert result.calculated_points == pytest.approx(10 + 6 + 3 + 4 + 2 + 4)

    def test_singles_derivation(self):
        # 4 hits: 1 HR, 1 2B, 1 3B → 1 single
        result = score_hitter_game(self._make_log(
            h=4, home_runs=1, doubles=1, triples=1
        ))
        assert result.singles == 1
        assert result.calculated_points == pytest.approx(10 + 6 + 8 + 3)

    def test_singles_never_negative(self):
        # Edge case: API data quirk where counts don't add up cleanly
        result = score_hitter_game(self._make_log(h=0, doubles=1))
        assert result.singles == 0  # clamped to 0, not -1


# ---------------------------------------------------------------------------
# Pitcher scoring and QS derivation
# ---------------------------------------------------------------------------

class TestScorePitcherGame:
    def _make_log(self, **kwargs) -> PitcherGameLog:
        defaults = dict(
            player_id=99, game_date="2026-04-01", season=2026,
            ip=0.0, earned_runs=0, strikeouts=0, wins=0,
        )
        defaults.update(kwargs)
        return PitcherGameLog(**defaults)

    def test_zero_game(self):
        result = score_pitcher_game(self._make_log())
        assert result.calculated_points == 0.0

    def test_ip_scoring(self):
        # 5.0 IP × 3 = 15 pts (below QS threshold, no other scoring factors)
        result = score_pitcher_game(self._make_log(ip=5.0))
        assert result.calculated_points == pytest.approx(15.0)

    def test_strikeouts(self):
        result = score_pitcher_game(self._make_log(strikeouts=7))
        assert result.calculated_points == pytest.approx(7 * 3)

    def test_win(self):
        result = score_pitcher_game(self._make_log(wins=1))
        assert result.calculated_points == pytest.approx(5.0)

    def test_earned_runs_penalty(self):
        result = score_pitcher_game(self._make_log(earned_runs=3))
        assert result.calculated_points == pytest.approx(-9.0)

    def test_qs_exactly_6ip_3er(self):
        # Exactly 6 IP, 3 ER → qualifies for QS
        result = score_pitcher_game(self._make_log(ip=6.0, earned_runs=3))
        assert result.qs_flag == 1
        # 6*3 + 5 + 3*(-3) = 18 + 5 - 9 = 14
        assert result.calculated_points == pytest.approx(18.0 + 5.0 - 9.0)

    def test_qs_not_enough_ip(self):
        # 5.2 IP (5.667) < 6.0 → no QS
        result = score_pitcher_game(self._make_log(ip=5.2, earned_runs=2))
        assert result.qs_flag == 0

    def test_qs_too_many_er(self):
        # 6.0 IP but 4 ER → no QS
        result = score_pitcher_game(self._make_log(ip=6.0, earned_runs=4))
        assert result.qs_flag == 0

    def test_qs_7ip_0er(self):
        # Clear dominant start
        result = score_pitcher_game(self._make_log(ip=7.0, earned_runs=0))
        assert result.qs_flag == 1

    def test_complete_line(self):
        # 7.0 IP, 8K, W, 1 ER → QS: 21 + 24 + 5 + 5 - 3 = 52
        result = score_pitcher_game(self._make_log(
            ip=7.0, strikeouts=8, wins=1, earned_runs=1
        ))
        assert result.qs_flag == 1
        expected = 7.0 * 3 + 8 * 3 + 5 + 5 + 1 * (-3)
        assert result.calculated_points == pytest.approx(expected)

    def test_fractional_ip_scoring(self):
        # 5.2 IP = 5.667 true innings × 3 (below QS threshold, no other factors)
        result = score_pitcher_game(self._make_log(ip=5.2))
        expected_ip_pts = (5 + 2/3) * 3
        assert result.calculated_points == pytest.approx(expected_ip_pts, rel=1e-3)

    def test_qs_with_fractional_ip(self):
        # 6.1 IP (6.333) >= 6.0, 2 ER <= 3 → QS
        result = score_pitcher_game(self._make_log(ip=6.1, earned_runs=2))
        assert result.qs_flag == 1


# ---------------------------------------------------------------------------
# Row-based scoring (dict interface for ETL DataFrames)
# ---------------------------------------------------------------------------

class TestScoreRows:
    def test_hitter_row(self):
        row = {"h": 2, "doubles": 1, "triples": 0, "home_runs": 0,
               "rbi": 1, "runs": 1, "stolen_bases": 0, "walks": 0, "hit_by_pitch": 0}
        # 1 single(3) + 1 double(6) + 1 rbi(2) + 1 run(2) = 13
        assert score_hitter_row(row) == pytest.approx(13.0)

    def test_pitcher_row_qs(self):
        row = {"ip": 6.0, "earned_runs": 2, "strikeouts": 5, "wins": 1}
        pts, qs = score_pitcher_row(row)
        assert qs == 1
        expected = 6.0 * 3 + 5 * 3 + 5 + 5 + 2 * (-3)
        assert pts == pytest.approx(expected)

    def test_pitcher_row_no_qs(self):
        row = {"ip": 5.0, "earned_runs": 2, "strikeouts": 4, "wins": 0}
        pts, qs = score_pitcher_row(row)
        assert qs == 0
