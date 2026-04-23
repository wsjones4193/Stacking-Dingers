"""
Scoring calculator for The World Pup — Underdog Fantasy soccer bestball.

Scoring rules:
  All players:  Goals(8), Assists(4), ShotsOnTarget(2), ShotsOffTarget(1),
                ChancesCreated(1), Crosses(0.75), TacklesSuccessful(0.5),
                PassesSuccessful(0.05)
  GK only:      Saves(2), PenaltySaves(3), GoalsConceded(-2), Win(5)
  GK + DEF:     CleanSheet(5)
"""

from __future__ import annotations

from dataclasses import dataclass, field

from backend.soccer.constants import ALL_PLAYER_SCORING, GK_DEF_SCORING, GK_SCORING


@dataclass
class SoccerMatchLog:
    player_id: int
    position: str            # "GK", "DEF", "MID", "FWD"
    game_date: str           # YYYY-MM-DD
    minutes_played: int = 0

    # All-player stats
    goals: int = 0
    assists: int = 0
    shots_on_target: int = 0
    shots_off_target: int = 0
    chances_created: int = 0
    crosses: int = 0
    tackles_successful: int = 0
    passes_successful: int = 0

    # GK-only
    saves: int = 0
    penalty_saves: int = 0
    goals_conceded: int = 0
    win: int = 0             # 1 if team won, else 0

    # GK + DEF
    clean_sheet: int = 0     # 1 if team kept clean sheet, else 0


def score_match(log: SoccerMatchLog) -> float:
    """Calculate fantasy points for a single player match appearance."""
    pts = (
        log.goals              * ALL_PLAYER_SCORING["goals"]
        + log.assists          * ALL_PLAYER_SCORING["assists"]
        + log.shots_on_target  * ALL_PLAYER_SCORING["shots_on_target"]
        + log.shots_off_target * ALL_PLAYER_SCORING["shots_off_target"]
        + log.chances_created  * ALL_PLAYER_SCORING["chances_created"]
        + log.crosses          * ALL_PLAYER_SCORING["crosses"]
        + log.tackles_successful * ALL_PLAYER_SCORING["tackles_successful"]
        + log.passes_successful  * ALL_PLAYER_SCORING["passes_successful"]
    )

    if log.position == "GK":
        pts += (
            log.saves          * GK_SCORING["saves"]
            + log.penalty_saves * GK_SCORING["penalty_saves"]
            + log.goals_conceded * GK_SCORING["goals_conceded"]
            + log.win          * GK_SCORING["win"]
        )

    if log.position in ("GK", "DEF"):
        pts += log.clean_sheet * GK_DEF_SCORING["clean_sheet"]

    return round(pts, 2)


def score_row(row: dict, position: str) -> float:
    """Score a raw stat dict (e.g. from FBref row). Returns calculated_points."""
    log = SoccerMatchLog(
        player_id=0,
        position=position,
        game_date="",
        minutes_played=int(row.get("minutes_played", 0)),
        goals=int(row.get("goals", 0)),
        assists=int(row.get("assists", 0)),
        shots_on_target=int(row.get("shots_on_target", 0)),
        shots_off_target=int(row.get("shots_off_target", 0)),
        chances_created=int(row.get("chances_created", 0)),
        crosses=int(row.get("crosses", 0)),
        tackles_successful=int(row.get("tackles_successful", 0)),
        passes_successful=int(row.get("passes_successful", 0)),
        saves=int(row.get("saves", 0)),
        penalty_saves=int(row.get("penalty_saves", 0)),
        goals_conceded=int(row.get("goals_conceded", 0)),
        win=int(row.get("wins", 0)),
        clean_sheet=int(row.get("clean_sheets", 0)),
    )
    return score_match(log)


def points_per_90(total_points: float, minutes_played: int) -> float | None:
    """Normalize total points to a per-90-minutes rate."""
    if minutes_played < 90:
        return None
    return round(total_points / minutes_played * 90, 2)
