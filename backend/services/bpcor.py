"""
BPCOR — Best Ball Points Contributed Over Replacement.

Two levels:
1. Team-level BPCOR: per roster, per week. Uses that team's specific bench
   as the replacement bar. This is the primary calculation.
2. Tournament-level BPCOR: for a given player across a season, average
   their team-level BPCOR contributions across all rosters that drafted them.

weekly_BPCOR = max(0, contributed_score - replacement_score)
  where:
    contributed_score = player's score if they started or played FLEX, else 0
    replacement_score = that week's replacement level for their position group
                        (highest bench IF/OF score for hitters,
                         highest bench P score for pitchers)

Season BPCOR = sum of weekly_BPCOR across all weeks on that roster.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from backend.services.lineup_setter import LineupResult, RosterPlayer, set_lineup


# ---------------------------------------------------------------------------
# Output types
# ---------------------------------------------------------------------------

@dataclass
class PlayerWeekBPCOR:
    player_id: int
    week_number: int
    draft_id: str
    position: str
    weekly_score: float
    contributed_score: float    # score if started/flex, else 0
    replacement_score: float    # replacement level for this position group this week
    bpcor: float                # max(0, contributed - replacement)
    is_starter: bool
    is_flex: bool
    is_bench: bool


@dataclass
class PlayerSeasonBPCOR:
    """Team-level season BPCOR for one player on one roster."""
    player_id: int
    draft_id: str
    season: int
    weekly_bpcors: list[PlayerWeekBPCOR] = field(default_factory=list)

    @property
    def season_bpcor(self) -> float:
        return sum(w.bpcor for w in self.weekly_bpcors)

    @property
    def weeks_started(self) -> int:
        return sum(1 for w in self.weekly_bpcors if w.is_starter or w.is_flex)

    @property
    def weeks_on_bench(self) -> int:
        return sum(1 for w in self.weekly_bpcors if w.is_bench)

    @property
    def consecutive_zero_bpcor_streak(self) -> int:
        """Number of consecutive most-recent weeks with zero BPCOR (for Below Replacement flag)."""
        streak = 0
        for week in reversed(self.weekly_bpcors):
            if week.bpcor == 0.0:
                streak += 1
            else:
                break
        return streak


@dataclass
class TournamentPlayerBPCOR:
    """Tournament-level BPCOR: aggregated across all rosters that drafted a player."""
    player_id: int
    season: int
    team_count: int                            # number of rosters that drafted this player
    total_bpcor: float                         # sum across all rosters
    avg_bpcor_per_roster: float               # total / team_count
    roster_season_bpcors: list[PlayerSeasonBPCOR] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Team-level BPCOR: one week
# ---------------------------------------------------------------------------

def compute_week_bpcor(
    draft_id: str,
    week_number: int,
    players: list[RosterPlayer],
) -> list[PlayerWeekBPCOR]:
    """
    Compute BPCOR for every player on a roster for a single week.

    Returns one PlayerWeekBPCOR per player.
    """
    result_lineup = set_lineup(players)

    starter_ids = {p.player_id for p in result_lineup.starters}
    flex_id = result_lineup.flex.player_id if result_lineup.flex else None

    hitter_replacement = result_lineup.hitter_replacement_score
    pitcher_replacement = result_lineup.pitcher_replacement_score

    weekly_bpcors: list[PlayerWeekBPCOR] = []

    for player in players:
        is_starter = player.player_id in starter_ids
        is_flex = player.player_id == flex_id
        is_bench = not (is_starter or is_flex)

        contributed = player.weekly_score if (is_starter or is_flex) else 0.0

        if player.position == "P":
            replacement = pitcher_replacement
        else:
            replacement = hitter_replacement

        bpcor = max(0.0, contributed - replacement)

        weekly_bpcors.append(PlayerWeekBPCOR(
            player_id=player.player_id,
            week_number=week_number,
            draft_id=draft_id,
            position=player.position,
            weekly_score=player.weekly_score,
            contributed_score=contributed,
            replacement_score=replacement,
            bpcor=round(bpcor, 3),
            is_starter=is_starter,
            is_flex=is_flex,
            is_bench=is_bench,
        ))

    return weekly_bpcors


# ---------------------------------------------------------------------------
# Team-level BPCOR: full season
# ---------------------------------------------------------------------------

def compute_season_bpcor(
    draft_id: str,
    season: int,
    weekly_rosters: dict[int, list[RosterPlayer]],  # {week_number: [RosterPlayer, ...]}
) -> dict[int, PlayerSeasonBPCOR]:
    """
    Compute season BPCOR for all players on a roster across all weeks.

    weekly_rosters maps week_number → list of RosterPlayer objects for that week.
    A player may not appear every week (IL, not drafted yet, etc.).

    Returns {player_id: PlayerSeasonBPCOR}.
    """
    player_seasons: dict[int, PlayerSeasonBPCOR] = {}

    for week_number, roster in sorted(weekly_rosters.items()):
        week_bpcors = compute_week_bpcor(draft_id, week_number, roster)
        for wb in week_bpcors:
            if wb.player_id not in player_seasons:
                player_seasons[wb.player_id] = PlayerSeasonBPCOR(
                    player_id=wb.player_id,
                    draft_id=draft_id,
                    season=season,
                )
            player_seasons[wb.player_id].weekly_bpcors.append(wb)

    return player_seasons


# ---------------------------------------------------------------------------
# Tournament-level BPCOR: aggregate across all rosters
# ---------------------------------------------------------------------------

def compute_tournament_bpcor(
    season: int,
    all_roster_seasons: list[dict[int, PlayerSeasonBPCOR]],
    # Each element = output of compute_season_bpcor for one roster
) -> dict[int, TournamentPlayerBPCOR]:
    """
    Aggregate team-level BPCOR for all players across the full tournament.

    Returns {player_id: TournamentPlayerBPCOR}.
    """
    aggregated: dict[int, TournamentPlayerBPCOR] = {}

    for roster_dict in all_roster_seasons:
        for player_id, season_bpcor in roster_dict.items():
            if player_id not in aggregated:
                aggregated[player_id] = TournamentPlayerBPCOR(
                    player_id=player_id,
                    season=season,
                    team_count=0,
                    total_bpcor=0.0,
                    avg_bpcor_per_roster=0.0,
                )
            agg = aggregated[player_id]
            agg.team_count += 1
            agg.total_bpcor += season_bpcor.season_bpcor
            agg.roster_season_bpcors.append(season_bpcor)

    for agg in aggregated.values():
        agg.avg_bpcor_per_roster = (
            round(agg.total_bpcor / agg.team_count, 3) if agg.team_count > 0 else 0.0
        )

    return aggregated
