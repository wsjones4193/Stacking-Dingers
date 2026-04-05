"""
Pydantic response schemas shared across routers.
These are read-only output shapes — not the SQLModel table classes.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Optional

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Shared envelope
# ---------------------------------------------------------------------------

class DataResponse(BaseModel):
    data: Any
    data_as_of: Optional[str] = None
    sample_size: Optional[int] = None
    low_confidence: Optional[bool] = None  # True if sample_size < 30


# ---------------------------------------------------------------------------
# Player
# ---------------------------------------------------------------------------

class PlayerSummary(BaseModel):
    player_id: int
    name: str
    position: str
    mlb_team: Optional[str]
    underdog_id: Optional[str]
    mlb_id: Optional[int]
    active: bool


class PlayerSearchResult(BaseModel):
    player_id: int
    name: str
    position: str
    mlb_team: Optional[str]
    current_adp: Optional[float]


class PlayerDetail(BaseModel):
    player_id: int
    name: str
    position: str
    mlb_team: Optional[str]
    underdog_id: Optional[str]
    mlb_id: Optional[int]
    active: bool
    # Enriched fields (populated from Parquet + SQLite)
    current_adp: Optional[float] = None
    draft_rate: Optional[float] = None
    season_bpcor: Optional[float] = None
    ownership_pct: Optional[float] = None
    roster_count: Optional[int] = None
    last_game_date: Optional[str] = None
    il_status: bool = False
    scoring_trajectory: list[dict] = []   # [{date, points}, ...]
    weekly_scores: list[dict] = []        # [{week, score}, ...]


# ---------------------------------------------------------------------------
# Team
# ---------------------------------------------------------------------------

class TeamSummary(BaseModel):
    draft_id: str
    username: str
    season: int
    draft_date: date
    draft_position: int
    round_reached: Optional[int]
    group_rank: Optional[int]
    total_points: float
    gap_to_advance: Optional[float]
    roster_strength_score: Optional[float]
    advancement_probability: Optional[float]
    roster_hole_badges: list[str] = []


class RosterEntry(BaseModel):
    player_id: int
    name: str
    position: str
    mlb_team: Optional[str]
    last_week_score: Optional[float]
    season_total: Optional[float]
    season_bpcor: Optional[float]
    il_status: bool
    flags: list[str] = []


class WeeklyBreakdown(BaseModel):
    week_number: int
    starters: list[dict]   # [{player_id, name, position, score, slot}, ...]
    flex: Optional[dict]
    bench: list[dict]
    total_score: float
    left_on_bench_highlight: Optional[dict]  # highest bench score


class TeamDetail(BaseModel):
    draft_id: str
    username: str
    season: int
    draft_date: date
    draft_position: int
    round_reached: Optional[int]
    total_points: float
    group_standings: list[dict]   # [{draft_id, username, total_points, rank, advanced}, ...]
    roster: list[RosterEntry]
    weekly_breakdowns: list[WeeklyBreakdown]
    roster_flags: list[dict]      # [{player_id, flag_type, flag_reason, week}, ...]
    gap_to_advance: Optional[float]
    advancement_probability: Optional[float]


# ---------------------------------------------------------------------------
# ADP
# ---------------------------------------------------------------------------

class AdpScatterPoint(BaseModel):
    player_id: int
    name: str
    position: str
    adp_rank: int
    bpcor_rank: Optional[int]
    adp: Optional[float]
    season_bpcor: Optional[float]
    value_label: Optional[str]   # "value", "bust", or None


class AdpMovementPoint(BaseModel):
    snapshot_date: str
    player_id: int
    name: str
    adp: Optional[float]
    draft_rate: Optional[float]


class PositionalScarcityCurve(BaseModel):
    position: str
    season: int
    picks: list[dict]   # [{adp_rank, adp, cumulative_pct}, ...]


# ---------------------------------------------------------------------------
# Leaderboard
# ---------------------------------------------------------------------------

class LeaderboardEntry(BaseModel):
    rank: int
    draft_id: str
    username: str
    season: int
    draft_date: date
    draft_position: int
    total_points: float
    round_reached: Optional[int]
    peak_2wk_score: Optional[float]
    peak_window_weeks: Optional[list[int]]
    ceiling_tier: Optional[str]
    archetype_tag: Optional[str]


# ---------------------------------------------------------------------------
# History modules
# ---------------------------------------------------------------------------

class HistoryModuleSummary(BaseModel):
    module_id: int
    title: str
    headline: str
    description: str


class CeilingAnalysisData(BaseModel):
    peak_histogram: list[dict]
    grinder_peaker_quadrants: list[dict]
    playoff_window_distribution: list[dict]
    sample_size: int
    low_confidence: bool


class StackingData(BaseModel):
    mlb_team_stacks: list[dict]
    positional_stacks: list[dict]
    combined_effects: list[dict]
    sample_size: int
    low_confidence: bool


class DraftStructureData(BaseModel):
    first_address_crosstab: list[dict]
    archetype_outcomes: list[dict]
    pick_heatmap: list[dict]
    sample_size: int
    low_confidence: bool


class ComboData(BaseModel):
    combos: list[dict]
    sample_size: int
    low_confidence: bool


class AdpAccuracyData(BaseModel):
    overperformers: list[dict]
    underperformers: list[dict]
    by_position: list[dict]
    sample_size: int
    low_confidence: bool


# ---------------------------------------------------------------------------
# Admin
# ---------------------------------------------------------------------------

class PlayerMappingEntry(BaseModel):
    map_id: int
    underdog_id: str
    underdog_name: str
    mlb_id: Optional[int]
    mlb_name: Optional[str]
    confirmed: bool
    match_score: Optional[float]
    season: int
    notes: Optional[str]


class ScoreAuditEntry(BaseModel):
    audit_id: int
    player_id: int
    player_name: Optional[str]
    draft_id: str
    week_number: int
    season: int
    calculated_score: float
    underdog_score: float
    delta: float
    flagged_date: str
