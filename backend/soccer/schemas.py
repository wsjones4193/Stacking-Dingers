"""
Pydantic response schemas for The World Pup soccer API.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel

from backend.schemas import DataResponse  # reuse the shared envelope


# ---------------------------------------------------------------------------
# Player
# ---------------------------------------------------------------------------

class SoccerPlayerSearchResult(BaseModel):
    player_id: int
    name: str
    position: str
    nationality: Optional[str]
    current_club: Optional[str]
    current_adp: Optional[float]
    draft_rate: Optional[float]


class SoccerPlayerStats(BaseModel):
    season: int
    club: Optional[str]
    competition: Optional[str]
    matches_played: int
    minutes_played: int
    goals: int
    assists: int
    shots_on_target: int
    shots_off_target: int
    chances_created: int
    crosses: int
    tackles_successful: int
    passes_successful: int
    saves: int
    penalty_saves: int
    goals_conceded: int
    wins: int
    clean_sheets: int
    calculated_points: float
    points_per_90: Optional[float]


class SoccerPlayerDetail(BaseModel):
    player_id: int
    name: str
    position: str
    nationality: Optional[str]
    current_club: Optional[str]
    underdog_id: Optional[str]
    active: bool
    current_adp: Optional[float]
    draft_rate: Optional[float]
    adp_history: list[dict] = []    # [{date, adp}, ...]
    stats: list[SoccerPlayerStats] = []


# ---------------------------------------------------------------------------
# ADP
# ---------------------------------------------------------------------------

class SoccerAdpScatterPoint(BaseModel):
    player_id: int
    name: str
    position: str
    nationality: Optional[str]
    current_club: Optional[str]
    adp: float
    draft_rate: Optional[float]
    points_per_90: Optional[float]   # club season proxy for value


class SoccerAdpMovement(BaseModel):
    player_id: int
    name: str
    position: str
    adp_7d_ago: Optional[float]
    adp_today: Optional[float]
    movement: Optional[float]        # positive = rising (ADP number dropping)


class SoccerAdpScarcity(BaseModel):
    position: str
    pick_number: int
    cumulative_pct: float            # % of that position drafted by this pick


# ---------------------------------------------------------------------------
# Team Odds
# ---------------------------------------------------------------------------

class TeamOddsRow(BaseModel):
    team_name: str
    r32_prob: Optional[float]
    r16_prob: Optional[float]
    qf_prob: Optional[float]
    sf_prob: Optional[float]
    final_prob: Optional[float]
    winner_prob: Optional[float]
    updated_at: Optional[str]


# ---------------------------------------------------------------------------
# Projected XI
# ---------------------------------------------------------------------------

class XIPlayer(BaseModel):
    player_id: int
    name: str
    position: str
    position_slot: str
    current_adp: Optional[float]
    is_starter: bool


class ProjectedXI(BaseModel):
    team_name: str
    formation: str
    starters: list[XIPlayer]
    bench: list[XIPlayer]
    updated_at: Optional[str]


# ---------------------------------------------------------------------------
# Rankings
# ---------------------------------------------------------------------------

class RankingEntry(BaseModel):
    player_id: int
    name: str
    position: str
    nationality: Optional[str]
    current_adp: Optional[float]
    tier: Optional[int]
    notes: Optional[str]


class RankingList(BaseModel):
    ranking_id: int
    name: str
    description: Optional[str]
    position_filter: Optional[str]
    entries: list[RankingEntry]
    created_at: str
    updated_at: str


class RankingListSummary(BaseModel):
    ranking_id: int
    name: str
    description: Optional[str]
    position_filter: Optional[str]
    entry_count: int
    updated_at: str
