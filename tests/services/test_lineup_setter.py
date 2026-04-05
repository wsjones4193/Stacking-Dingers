"""
Tests for backend/services/lineup_setter.py

Covers:
- Basic optimal lineup selection
- FLEX selection (IF/OF only, never P)
- Correct bench assignment
- Replacement level calculation
- Edge cases: undersized rosters, ties, all-zero scores
- Total score accuracy
"""

import pytest

from backend.services.lineup_setter import (
    LineupResult,
    RosterPlayer,
    compute_weekly_score,
    set_lineup,
)


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def make_player(player_id: int, position: str, score: float, name: str = "") -> RosterPlayer:
    return RosterPlayer(player_id=player_id, position=position, weekly_score=score, name=name)


def make_full_roster() -> list[RosterPlayer]:
    """
    Standard 20-player roster:
    - P: IDs 1-5 (scores 30, 25, 20, 15, 10)
    - IF: IDs 11-17 (scores 40, 35, 30, 25, 20, 15, 10)
    - OF: IDs 21-28 (scores 50, 45, 40, 35, 30, 25, 20, 15)
    """
    pitchers = [make_player(i, "P", (6 - j) * 5) for j, i in enumerate(range(1, 6))]
    infielders = [make_player(i, "IF", (8 - j) * 5) for j, i in enumerate(range(11, 18))]
    outfielders = [make_player(i, "OF", (10 - j) * 5) for j, i in enumerate(range(21, 29))]
    return pitchers + infielders + outfielders


# ---------------------------------------------------------------------------
# Basic lineup construction
# ---------------------------------------------------------------------------

class TestSetLineup:
    def test_starter_count(self):
        result = set_lineup(make_full_roster())
        assert len(result.starters) == 9

    def test_flex_exists(self):
        result = set_lineup(make_full_roster())
        assert result.flex is not None

    def test_bench_count(self):
        result = set_lineup(make_full_roster())
        # 20 total - 9 starters - 1 flex = 10 bench
        assert len(result.bench) == 10

    def test_total_player_count(self):
        roster = make_full_roster()
        result = set_lineup(roster)
        all_ids = (
            [p.player_id for p in result.starters]
            + ([result.flex.player_id] if result.flex else [])
            + [p.player_id for p in result.bench]
        )
        assert len(all_ids) == len(roster)
        assert set(all_ids) == {p.player_id for p in roster}

    def test_top_3_pitchers_start(self):
        result = set_lineup(make_full_roster())
        starter_ids = {p.player_id for p in result.starters if p.position == "P"}
        assert starter_ids == {1, 2, 3}  # scores 30, 25, 20

    def test_top_3_infielders_start(self):
        result = set_lineup(make_full_roster())
        starter_ids = {p.player_id for p in result.starters if p.position == "IF"}
        assert starter_ids == {11, 12, 13}  # scores 40, 35, 30

    def test_top_3_outfielders_start(self):
        result = set_lineup(make_full_roster())
        starter_ids = {p.player_id for p in result.starters if p.position == "OF"}
        assert starter_ids == {21, 22, 23}  # scores 50, 45, 40

    def test_flex_is_highest_remaining_hitter(self):
        result = set_lineup(make_full_roster())
        # After 3 IF starters (11,12,13) and 3 OF starters (21,22,23),
        # remaining hitters: IF14(25), IF15(20), IF16(15), IF17(10),
        #                    OF24(35), OF25(30), OF26(25), OF27(20), OF28(15)
        # Highest: OF24 at 35
        assert result.flex is not None
        assert result.flex.player_id == 24
        assert result.flex.weekly_score == 35

    def test_pitcher_never_flex(self):
        # Even if a pitcher has a higher score than all hitters, P never goes to FLEX
        players = [
            make_player(1, "P", 100),
            make_player(2, "P", 90),
            make_player(3, "P", 80),
            make_player(4, "P", 70),   # bench pitcher with high score
            make_player(11, "IF", 10),
            make_player(12, "IF", 9),
            make_player(13, "IF", 8),
            make_player(14, "IF", 7),  # should be FLEX, not pitcher 4
            make_player(21, "OF", 6),
            make_player(22, "OF", 5),
            make_player(23, "OF", 4),
        ]
        result = set_lineup(players)
        assert result.flex is not None
        assert result.flex.position in {"IF", "OF"}
        assert result.flex.player_id == 14  # IF at score 7

    def test_total_score_is_correct(self):
        roster = make_full_roster()
        result = set_lineup(roster)
        # Starters: P(30+25+20) + IF(40+35+30) + OF(50+45+40) + FLEX(OF24=35)
        expected = (30 + 25 + 20) + (40 + 35 + 30) + (50 + 45 + 40) + 35
        assert result.total_score == pytest.approx(expected)

    def test_bench_players_not_in_starting_lineup(self):
        result = set_lineup(make_full_roster())
        starter_ids = {p.player_id for p in result.starters}
        flex_id = result.flex.player_id if result.flex else None
        bench_ids = {p.player_id for p in result.bench}
        assert not bench_ids & starter_ids
        if flex_id:
            assert flex_id not in bench_ids


# ---------------------------------------------------------------------------
# Replacement level
# ---------------------------------------------------------------------------

class TestReplacementLevel:
    def test_pitcher_replacement_is_4th_best_p(self):
        result = set_lineup(make_full_roster())
        # Top 3 P starters are 30,25,20. Bench Ps: 15,10. Highest = 15.
        assert result.pitcher_replacement_score == 15.0

    def test_hitter_replacement_is_best_bench_hitter_after_flex(self):
        result = set_lineup(make_full_roster())
        # FLEX = OF24 at 35. Non-flex bench hitters:
        # IF14(25), IF15(20), IF16(15), IF17(10), OF25(30), OF26(25), OF27(20), OF28(15)
        # Highest non-flex bench hitter = OF25 at 30
        assert result.hitter_replacement_score == 30.0

    def test_replacement_zero_when_no_bench(self):
        # Minimal roster: exactly 3P, 3IF, 3OF, 1 FLEX — no bench
        players = (
            [make_player(i, "P", 10) for i in range(1, 4)]
            + [make_player(i, "IF", 10) for i in range(11, 14)]
            + [make_player(i, "OF", 10) for i in range(21, 25)]  # 4 OFs → 3 start + 1 FLEX
        )
        result = set_lineup(players)
        assert result.pitcher_replacement_score == 0.0
        assert result.hitter_replacement_score == 0.0


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_undersized_roster_fewer_than_3_pitchers(self):
        players = [
            make_player(1, "P", 20),
            make_player(2, "P", 10),
            # Only 2 pitchers — fills 2 P slots
            make_player(11, "IF", 30),
            make_player(12, "IF", 25),
            make_player(13, "IF", 20),
            make_player(21, "OF", 40),
            make_player(22, "OF", 35),
            make_player(23, "OF", 30),
        ]
        result = set_lineup(players)
        p_starters = [p for p in result.starters if p.position == "P"]
        assert len(p_starters) == 2

    def test_no_flex_when_not_enough_hitters(self):
        # Only exactly 3 IF and 3 OF — all go to starters, no FLEX
        players = (
            [make_player(i, "P", 10) for i in range(1, 4)]
            + [make_player(i, "IF", 10) for i in range(11, 14)]
            + [make_player(i, "OF", 10) for i in range(21, 24)]
        )
        result = set_lineup(players)
        assert result.flex is None

    def test_all_zero_scores(self):
        players = [make_player(i, "IF" if i < 4 else "P", 0.0) for i in range(1, 8)]
        result = set_lineup(players)
        assert result.total_score == 0.0

    def test_flex_prefers_highest_scorer_across_positions(self):
        # IF scores [40,35,30,50] → sorted starters: 14(50),11(40),12(35); flex candidate: 13(30)
        # OF scores [45,38,32,20] → sorted starters: 21(45),22(38),23(32); flex candidate: 24(20)
        # FLEX = IF13 at 30 (beats OF24 at 20)
        players = (
            [make_player(i, "P", 10) for i in range(1, 4)]
            + [make_player(10 + i, "IF", [40, 35, 30, 50][i - 1]) for i in range(1, 5)]
            + [make_player(20 + i, "OF", [45, 38, 32, 20][i - 1]) for i in range(1, 5)]
        )
        result = set_lineup(players)
        assert result.flex is not None
        assert result.flex.position == "IF"
        assert result.flex.weekly_score == 30.0

    def test_empty_roster(self):
        result = set_lineup([])
        assert result.total_score == 0.0
        assert result.flex is None
        assert len(result.starters) == 0


# ---------------------------------------------------------------------------
# compute_weekly_score convenience wrapper
# ---------------------------------------------------------------------------

class TestComputeWeeklyScore:
    def test_basic_dict_input(self):
        scores = {
            1: ("P", 20.0), 2: ("P", 18.0), 3: ("P", 15.0),
            11: ("IF", 30.0), 12: ("IF", 25.0), 13: ("IF", 22.0), 14: ("IF", 10.0),
            21: ("OF", 35.0), 22: ("OF", 28.0), 23: ("OF", 20.0),
        }
        result = compute_weekly_score(scores)
        # Starters: P(20+18+15) + IF(30+25+22) + OF(35+28+20) + FLEX(IF14=10)
        expected = (20 + 18 + 15) + (30 + 25 + 22) + (35 + 28 + 20) + 10
        assert result.total_score == pytest.approx(expected)
