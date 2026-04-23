"""
SQLModel table definitions for The World Pup soccer bestball app.
All tables prefixed with 'soccer_' to avoid conflicts with MLB tables.
Stored in the same bestball.db.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


# ---------------------------------------------------------------------------
# Player registry
# ---------------------------------------------------------------------------

class SoccerPlayer(SQLModel, table=True):
    __tablename__ = "soccer_players"

    player_id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    position: str               # "GK", "DEF", "MID", "FWD"
    nationality: Optional[str] = Field(default=None, index=True)  # national team
    current_club: Optional[str] = None
    underdog_id: Optional[str] = Field(default=None, index=True)
    fbref_id: Optional[str] = Field(default=None, index=True)     # FBref player key
    sofascore_id: Optional[int] = None
    active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# Player ID mapping (Underdog name → FBref ID)
# ---------------------------------------------------------------------------

class SoccerPlayerIdMap(SQLModel, table=True):
    __tablename__ = "soccer_player_id_map"

    map_id: Optional[int] = Field(default=None, primary_key=True)
    underdog_id: str = Field(index=True)
    underdog_name: str
    fbref_id: Optional[str] = None
    fbref_name: Optional[str] = None
    confirmed: bool = Field(default=False)
    match_score: Optional[float] = None   # fuzzy match confidence 0–100
    notes: Optional[str] = None


# ---------------------------------------------------------------------------
# ADP snapshots (one row per player per day)
# ---------------------------------------------------------------------------

class SoccerAdpSnapshot(SQLModel, table=True):
    __tablename__ = "soccer_adp_snapshots"
    __table_args__ = (
        UniqueConstraint("player_id", "snapshot_date"),
    )

    snapshot_id: Optional[int] = Field(default=None, primary_key=True)
    player_id: int = Field(foreign_key="soccer_players.player_id", index=True)
    snapshot_date: date = Field(index=True)
    adp: Optional[float] = None
    draft_rate: Optional[float] = None    # % of drafts that include this player
    pick_count: Optional[int] = None      # raw count of times drafted
    total_drafts: Optional[int] = None    # total drafts in sample


# ---------------------------------------------------------------------------
# Player stats (per season, from FBref club data)
# ---------------------------------------------------------------------------

class SoccerPlayerStats(SQLModel, table=True):
    __tablename__ = "soccer_player_stats"
    __table_args__ = (
        UniqueConstraint("player_id", "season", "club"),
    )

    stat_id: Optional[int] = Field(default=None, primary_key=True)
    player_id: int = Field(foreign_key="soccer_players.player_id", index=True)
    season: int = Field(index=True)
    club: Optional[str] = None
    competition: Optional[str] = None   # e.g. "Premier League", "La Liga"
    matches_played: int = Field(default=0)
    minutes_played: int = Field(default=0)

    # Scoring-relevant stats
    goals: int = Field(default=0)
    assists: int = Field(default=0)
    shots_on_target: int = Field(default=0)
    shots_off_target: int = Field(default=0)
    chances_created: int = Field(default=0)
    crosses: int = Field(default=0)
    tackles_successful: int = Field(default=0)
    passes_successful: int = Field(default=0)

    # GK-only
    saves: int = Field(default=0)
    penalty_saves: int = Field(default=0)
    goals_conceded: int = Field(default=0)
    wins: int = Field(default=0)
    clean_sheets: int = Field(default=0)

    # Derived: calculated fantasy points over the season
    calculated_points: float = Field(default=0.0)
    points_per_90: Optional[float] = None

    updated_at: datetime = Field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# Team odds (advancement probability per World Cup stage)
# ---------------------------------------------------------------------------

class SoccerTeamOdds(SQLModel, table=True):
    __tablename__ = "soccer_team_odds"
    __table_args__ = (
        UniqueConstraint("team_name", "stage"),
    )

    odds_id: Optional[int] = Field(default=None, primary_key=True)
    team_name: str = Field(index=True)
    stage: str       # "r32", "r16", "qf", "sf", "final", "winner"
    odds: Optional[float] = None          # American odds (e.g. +150, -110)
    implied_prob: Optional[float] = None  # 0.0 – 1.0
    source: Optional[str] = None          # e.g. "theOddsApi", "manual"
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# Projected starting XIs
# ---------------------------------------------------------------------------

class SoccerProjectedXI(SQLModel, table=True):
    __tablename__ = "soccer_projected_xi"

    xi_id: Optional[int] = Field(default=None, primary_key=True)
    team_name: str = Field(index=True)
    formation: str = Field(default="4-3-3")   # e.g. "4-3-3", "4-2-3-1"
    player_id: int = Field(foreign_key="soccer_players.player_id", index=True)
    position_slot: str    # "GK", "CB1", "CB2", "LB", "RB", "CM1", etc.
    is_starter: bool = Field(default=True)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# User-saved rankings
# ---------------------------------------------------------------------------

class SoccerRanking(SQLModel, table=True):
    __tablename__ = "soccer_rankings"

    ranking_id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    description: Optional[str] = None
    position_filter: Optional[str] = None   # "ALL", "GK", "DEF", "MID", "FWD"
    rankings_json: str = Field(default="[]")  # JSON: [{player_id, tier, notes}, ...]
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
