"""
Tests for backend/services/bpcor.py

Covers:
- Weekly BPCOR: starters contribute score - replacement, bench contributes 0
- BPCOR is always >= 0
- Replacement level correctly sourced from lineup result
- Pitchers use pitcher replacement level, hitters use hitter replacement level
- Season BPCOR = sum of weekly BPCORs
- Consecutive zero streak detection (for Below Replacement flag)
- Tournament-level BPCOR aggregation
"""

import pytest

from backend.services.bpcor import (
    TournamentPlayerBPCOR,
    compute_season_bpcor,
    compute_tournament_bpcor,
    compute_week_bpcor,
)
from backend.services.lineup_setter import RosterPlayer


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def make_player(player_id: int, position: str, score: float) -> RosterPlayer:
    return RosterPlayer(player_id=player_id, position=position, weekly_score=score)


def standard_roster() -> list[RosterPlayer]:
    """
    3P (scores 30,25,20,15,10), 7IF (scores 40,35,30,25,20,15,10),
    8OF (scores 50,45,40,35,30,25,20,15) = 18 players

    Lineup:
      P starters: 1(30), 2(25), 3(20) — bench P: 4(15), 5(10)
      IF starters: 11(40), 12(35), 13(30) — remaining IF: 14(25),15(20),16(15),17(10)
      OF starters: 21(50), 22(45), 23(40) — remaining OF: 24(35),25(30),26(25),27(20),28(15)
      FLEX: 24 (35, highest remaining hitter)
      Bench hitters (non-flex): 14(25),15(20),16(15),17(10),25(30),26(25),27(20),28(15)
      Hitter replacement = highest bench hitter after flex = 25(OF, score=30)
      Pitcher replacement = 4(P, score=15)
    """
    ps = [make_player(i, "P", (6 - j) * 5) for j, i in enumerate(range(1, 6))]
    ifs = [make_player(i, "IF", (8 - j) * 5) for j, i in enumerate(range(11, 18))]
    ofs = [make_player(i, "OF", (10 - j) * 5) for j, i in enumerate(range(21, 29))]
    return ps + ifs + ofs


# ---------------------------------------------------------------------------
# Weekly BPCOR
# ---------------------------------------------------------------------------

class TestComputeWeekBpcor:
    def test_returns_one_entry_per_player(self):
        roster = standard_roster()
        results = compute_week_bpcor("draft_1", week_number=1, players=roster)
        assert len(results) == len(roster)

    def test_starter_bpcor_is_contributed_minus_replacement(self):
        roster = standard_roster()
        results = compute_week_bpcor("draft_1", week_number=1, players=roster)
        by_id = {r.player_id: r for r in results}

        # P starter: player 1 (score=30), pitcher replacement = 15
        p1 = by_id[1]
        assert p1.is_starter
        assert p1.contributed_score == 30.0
        assert p1.replacement_score == 15.0
        assert p1.bpcor == pytest.approx(15.0)

    def test_bench_bpcor_is_zero(self):
        roster = standard_roster()
        results = compute_week_bpcor("draft_1", week_number=1, players=roster)
        by_id = {r.player_id: r for r in results}

        # P bench player: player 5 (score=10, bench)
        p5 = by_id[5]
        assert p5.is_bench
        assert p5.contributed_score == 0.0
        assert p5.bpcor == 0.0

    def test_bpcor_never_negative(self):
        # Starter whose score is below replacement level → clamped to 0
        players = (
            [make_player(1, "P", 5), make_player(2, "P", 4), make_player(3, "P", 3)]
            + [make_player(4, "P", 100)]  # bench pitcher with monster score → high replacement
            + [make_player(11, "IF", 20), make_player(12, "IF", 18), make_player(13, "IF", 15)]
            + [make_player(21, "OF", 25), make_player(22, "OF", 22), make_player(23, "OF", 19)]
            + [make_player(14, "IF", 5)]  # flex
        )
        results = compute_week_bpcor("draft_1", 1, players)
        for r in results:
            assert r.bpcor >= 0.0, f"Negative BPCOR for player {r.player_id}: {r.bpcor}"

    def test_flex_player_uses_hitter_replacement(self):
        roster = standard_roster()
        results = compute_week_bpcor("draft_1", week_number=1, players=roster)
        by_id = {r.player_id: r for r in results}

        flex = by_id[24]
        assert flex.is_flex
        assert flex.position == "OF"
        assert flex.contributed_score == 35.0
        # hitter replacement = 30 (player 25, highest non-flex bench hitter)
        assert flex.replacement_score == 30.0
        assert flex.bpcor == pytest.approx(5.0)

    def test_pitcher_uses_pitcher_replacement_not_hitter(self):
        roster = standard_roster()
        results = compute_week_bpcor("draft_1", week_number=1, players=roster)
        by_id = {r.player_id: r for r in results}

        # Bench pitcher player 4 (score=15) uses pitcher replacement = 15 (itself), BPCOR=0
        p4 = by_id[4]
        assert p4.is_bench
        assert p4.replacement_score == 15.0  # pitcher replacement level

    def test_draft_id_propagated(self):
        results = compute_week_bpcor("my_draft", week_number=3, players=standard_roster())
        assert all(r.draft_id == "my_draft" for r in results)

    def test_week_number_propagated(self):
        results = compute_week_bpcor("d", week_number=7, players=standard_roster())
        assert all(r.week_number == 7 for r in results)


# ---------------------------------------------------------------------------
# Season BPCOR
# ---------------------------------------------------------------------------

class TestComputeSeasonBpcor:
    def make_week(self, week: int) -> list[RosterPlayer]:
        """Minimal valid roster for a week."""
        return (
            [make_player(i, "P", 10 + i) for i in range(1, 6)]
            + [make_player(i, "IF", 20 + i) for i in range(11, 18)]
            + [make_player(i, "OF", 30 + i) for i in range(21, 29)]
        )

    def test_season_bpcor_sums_weekly(self):
        weekly = {w: self.make_week(w) for w in range(1, 4)}
        season = compute_season_bpcor("d1", 2026, weekly)

        for player_id, s in season.items():
            assert s.season_bpcor == pytest.approx(
                sum(w.bpcor for w in s.weekly_bpcors), rel=1e-5
            )

    def test_three_weeks_of_data(self):
        weekly = {w: self.make_week(w) for w in range(1, 4)}
        season = compute_season_bpcor("d1", 2026, weekly)
        player_1 = season[1]
        assert len(player_1.weekly_bpcors) == 3

    def test_weeks_started_counter(self):
        weekly = {w: self.make_week(w) for w in range(1, 5)}
        season = compute_season_bpcor("d1", 2026, weekly)
        # Player 1 (P, score 11) — is in top 3 P? Depends on other P scores.
        # Just verify counter == 4 if they start every week
        for p_id, s in season.items():
            assert s.weeks_started + s.weeks_on_bench == len(s.weekly_bpcors)

    def test_consecutive_zero_bpcor_streak(self):
        """Simulate a player on bench for last 3 weeks (triggers Below Replacement flag)."""
        from backend.services.bpcor import PlayerWeekBPCOR, PlayerSeasonBPCOR

        mock_weeks = [
            PlayerWeekBPCOR(1, 1, "d", "IF", 20, 20, 5, 15.0, True, False, False),
            PlayerWeekBPCOR(1, 2, "d", "IF", 3,  0, 5, 0.0, False, False, True),
            PlayerWeekBPCOR(1, 3, "d", "IF", 2,  0, 5, 0.0, False, False, True),
            PlayerWeekBPCOR(1, 4, "d", "IF", 1,  0, 5, 0.0, False, False, True),
        ]
        season = PlayerSeasonBPCOR(player_id=1, draft_id="d", season=2026,
                                   weekly_bpcors=mock_weeks)
        assert season.consecutive_zero_bpcor_streak == 3

    def test_consecutive_zero_streak_resets_on_nonzero(self):
        from backend.services.bpcor import PlayerWeekBPCOR, PlayerSeasonBPCOR

        mock_weeks = [
            PlayerWeekBPCOR(1, 1, "d", "IF", 1, 0, 5, 0.0, False, False, True),
            PlayerWeekBPCOR(1, 2, "d", "IF", 20, 20, 5, 15.0, True, False, False),  # non-zero
            PlayerWeekBPCOR(1, 3, "d", "IF", 0, 0, 5, 0.0, False, False, True),
        ]
        season = PlayerSeasonBPCOR(player_id=1, draft_id="d", season=2026,
                                   weekly_bpcors=mock_weeks)
        assert season.consecutive_zero_bpcor_streak == 1


# ---------------------------------------------------------------------------
# Tournament-level BPCOR
# ---------------------------------------------------------------------------

class TestComputeTournamentBpcor:
    def _make_season_dict(self, player_id: int, draft_id: str, bpcor_val: float):
        """Create a single-player season BPCOR dict with a given total BPCOR."""
        from backend.services.bpcor import PlayerSeasonBPCOR, PlayerWeekBPCOR
        week = PlayerWeekBPCOR(
            player_id=player_id, week_number=1, draft_id=draft_id,
            position="IF", weekly_score=bpcor_val, contributed_score=bpcor_val,
            replacement_score=0.0, bpcor=bpcor_val,
            is_starter=True, is_flex=False, is_bench=False,
        )
        s = PlayerSeasonBPCOR(player_id=player_id, draft_id=draft_id, season=2026)
        s.weekly_bpcors = [week]
        return {player_id: s}

    def test_single_roster(self):
        roster = self._make_season_dict(player_id=42, draft_id="d1", bpcor_val=50.0)
        result = compute_tournament_bpcor(2026, [roster])
        assert 42 in result
        assert result[42].team_count == 1
        assert result[42].avg_bpcor_per_roster == pytest.approx(50.0)

    def test_multiple_rosters_averages_correctly(self):
        r1 = self._make_season_dict(42, "d1", 60.0)
        r2 = self._make_season_dict(42, "d2", 40.0)
        r3 = self._make_season_dict(42, "d3", 50.0)
        result = compute_tournament_bpcor(2026, [r1, r2, r3])
        assert result[42].team_count == 3
        assert result[42].total_bpcor == pytest.approx(150.0)
        assert result[42].avg_bpcor_per_roster == pytest.approx(50.0)

    def test_separate_players_tracked_independently(self):
        r1 = self._make_season_dict(1, "d1", 30.0)
        r2 = self._make_season_dict(2, "d2", 20.0)
        result = compute_tournament_bpcor(2026, [r1, r2])
        assert result[1].team_count == 1
        assert result[2].team_count == 1
        assert result[1].avg_bpcor_per_roster == pytest.approx(30.0)
        assert result[2].avg_bpcor_per_roster == pytest.approx(20.0)

    def test_empty_input(self):
        result = compute_tournament_bpcor(2026, [])
        assert result == {}
