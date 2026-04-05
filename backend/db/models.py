"""
SQLModel table definitions for bestball.db.
All tables use integer primary keys. JSON columns stored as TEXT in SQLite.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Optional

from sqlmodel import Field, SQLModel


# ---------------------------------------------------------------------------
# Player master table
# ---------------------------------------------------------------------------

class Player(SQLModel, table=True):
    __tablename__ = "players"

    player_id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    position: str              # "P", "IF", or "OF" — Underdog designation is authoritative
    mlb_team: Optional[str] = None
    underdog_id: Optional[str] = Field(default=None, index=True)
    mlb_id: Optional[int] = Field(default=None, index=True)
    active: bool = Field(default=True)


# ---------------------------------------------------------------------------
# Player ID mapping (Underdog ↔ MLB Stats API)
# ---------------------------------------------------------------------------

class PlayerIdMap(SQLModel, table=True):
    __tablename__ = "player_id_map"

    map_id: Optional[int] = Field(default=None, primary_key=True)
    underdog_id: str = Field(index=True)
    underdog_name: str
    mlb_id: Optional[int] = Field(default=None, index=True)
    mlb_name: Optional[str] = None
    confirmed: bool = Field(default=False)
    match_score: Optional[float] = None   # rapidfuzz ratio (0–100)
    season: int
    notes: Optional[str] = None


# ---------------------------------------------------------------------------
# Drafts and picks
# ---------------------------------------------------------------------------

class Draft(SQLModel, table=True):
    __tablename__ = "drafts"

    draft_id: str = Field(primary_key=True)   # Underdog's draft ID
    season: int = Field(index=True)
    draft_date: date
    entry_type: Optional[str] = None          # e.g. "the_dinger"
    username: str = Field(index=True)
    draft_position: int                        # seat 1–12


class Pick(SQLModel, table=True):
    __tablename__ = "picks"

    pick_id: Optional[int] = Field(default=None, primary_key=True)
    draft_id: str = Field(foreign_key="drafts.draft_id", index=True)
    pick_number: int           # overall pick number 1–240
    round_number: int          # draft round 1–20
    player_id: int = Field(foreign_key="players.player_id", index=True)
    username: str


# ---------------------------------------------------------------------------
# Weekly scores
# ---------------------------------------------------------------------------

class WeeklyScore(SQLModel, table=True):
    __tablename__ = "weekly_scores"

    score_id: Optional[int] = Field(default=None, primary_key=True)
    draft_id: str = Field(foreign_key="drafts.draft_id", index=True)
    week_number: int
    season: int
    player_id: int = Field(foreign_key="players.player_id", index=True)
    calculated_score: float = Field(default=0.0)
    underdog_score: Optional[float] = None    # from CSV for audit
    is_starter: bool = Field(default=False)
    is_flex: bool = Field(default=False)
    is_bench: bool = Field(default=True)


# ---------------------------------------------------------------------------
# ADP snapshots
# ---------------------------------------------------------------------------

class AdpSnapshot(SQLModel, table=True):
    __tablename__ = "adp_snapshots"

    snapshot_id: Optional[int] = Field(default=None, primary_key=True)
    player_id: int = Field(foreign_key="players.player_id", index=True)
    snapshot_date: date = Field(index=True)
    season: int
    adp: Optional[float] = None
    draft_rate: Optional[float] = None                # actual % of drafts
    projected_draft_rate: Optional[float] = None      # weighted historical projection
    projected_daily_picks: Optional[float] = None     # expected picks today


# ---------------------------------------------------------------------------
# Projections (Steamer / ATC — preseason and RoS)
# ---------------------------------------------------------------------------

class Projection(SQLModel, table=True):
    __tablename__ = "projections"

    projection_id: Optional[int] = Field(default=None, primary_key=True)
    player_id: int = Field(foreign_key="players.player_id", index=True)
    season: int
    source: str        # "steamer", "steamer_ros", "atc", "atc_ros"
    captured_date: date
    is_canonical: bool = Field(default=False)   # True = Opening Day snapshot
    projected_points: Optional[float] = None
    projected_pa: Optional[float] = None        # hitters
    projected_ip: Optional[float] = None        # pitchers


# ---------------------------------------------------------------------------
# Groups and standings
# ---------------------------------------------------------------------------

class Group(SQLModel, table=True):
    __tablename__ = "groups"

    group_id: Optional[int] = Field(default=None, primary_key=True)
    season: int = Field(index=True)
    round_number: int
    team_ids_json: str = Field(default="[]")   # JSON array of draft_ids

    @property
    def team_ids(self) -> list[str]:
        return json.loads(self.team_ids_json)

    @team_ids.setter
    def team_ids(self, value: list[str]) -> None:
        self.team_ids_json = json.dumps(value)


class GroupStanding(SQLModel, table=True):
    __tablename__ = "group_standings"

    standing_id: Optional[int] = Field(default=None, primary_key=True)
    group_id: int = Field(foreign_key="groups.group_id", index=True)
    draft_id: str = Field(foreign_key="drafts.draft_id", index=True)
    round_number: int
    season: int
    total_points: float = Field(default=0.0)
    rank: Optional[int] = None
    advanced: bool = Field(default=False)


# ---------------------------------------------------------------------------
# Score audit (discrepancy tracking — admin only)
# ---------------------------------------------------------------------------

class ScoreAudit(SQLModel, table=True):
    __tablename__ = "score_audit"

    audit_id: Optional[int] = Field(default=None, primary_key=True)
    player_id: int = Field(foreign_key="players.player_id", index=True)
    draft_id: str
    week_number: int
    season: int
    calculated_score: float
    underdog_score: float
    delta: float                    # calculated - underdog
    flagged_date: datetime = Field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# Team season profiles (peak window, consistency, ceiling tier)
# ---------------------------------------------------------------------------

class TeamSeasonProfile(SQLModel, table=True):
    __tablename__ = "team_season_profiles"

    profile_id: Optional[int] = Field(default=None, primary_key=True)
    draft_id: str = Field(foreign_key="drafts.draft_id", index=True)
    season: int = Field(index=True)
    peak_2wk_score: Optional[float] = None
    peak_window_weeks_json: Optional[str] = None   # JSON [week_a, week_b]
    consistency_score: Optional[float] = None       # std dev of weekly scores
    ceiling_tier: Optional[str] = None              # "top1", "top10", "advancing", None
    round_reached: Optional[int] = None
    r2_score: Optional[float] = None
    r3_score: Optional[float] = None
    r4_score: Optional[float] = None


# ---------------------------------------------------------------------------
# Draft sequences (pick-by-pick positional sequence + archetype tag)
# ---------------------------------------------------------------------------

class DraftSequence(SQLModel, table=True):
    __tablename__ = "draft_sequences"

    sequence_id: Optional[int] = Field(default=None, primary_key=True)
    draft_id: str = Field(foreign_key="drafts.draft_id", unique=True)
    season: int
    pick_sequence_json: str = Field(default="[]")   # JSON ["IF","P","OF",...]
    archetype_tag: Optional[str] = None              # "p_heavy", "if_heavy", etc.
    advance_round: Optional[int] = None              # highest round reached (1–4)

    @property
    def pick_sequence(self) -> list[str]:
        return json.loads(self.pick_sequence_json)

    @pick_sequence.setter
    def pick_sequence(self, value: list[str]) -> None:
        self.pick_sequence_json = json.dumps(value)


# ---------------------------------------------------------------------------
# Roster flags
# ---------------------------------------------------------------------------

class RosterFlag(SQLModel, table=True):
    __tablename__ = "roster_flags"

    flag_id: Optional[int] = Field(default=None, primary_key=True)
    draft_id: str = Field(foreign_key="drafts.draft_id", index=True)
    week_number: int
    season: int
    player_id: Optional[int] = Field(default=None, foreign_key="players.player_id")
    position_group: Optional[str] = None    # "P", "IF", "OF" — for position-level flags
    flag_type: str    # "position_wiped", "ghost_player", "below_replacement",
                      # "pitcher_trending_wrong", "hitter_usage_decline"
    flag_reason: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# Combo projections (association rule mining — combinatorial ownership)
# ---------------------------------------------------------------------------

class ComboProjection(SQLModel, table=True):
    __tablename__ = "combo_projections"

    combo_id: Optional[int] = Field(default=None, primary_key=True)
    season: int = Field(index=True)
    player_a_id: int = Field(foreign_key="players.player_id", index=True)
    player_b_id: int = Field(foreign_key="players.player_id", index=True)
    player_c_id: Optional[int] = Field(default=None, foreign_key="players.player_id")
    support: Optional[float] = None            # % of all rosters with all players
    confidence: Optional[float] = None         # P(C | A and B)
    lift: Optional[float] = None               # confidence / expected independent rate
    projected_pair_count: Optional[float] = None
    pair_rate: Optional[float] = None          # % of A's rosters that also have B


# ---------------------------------------------------------------------------
# Database initialization helper
# ---------------------------------------------------------------------------

def create_db_and_tables(db_path: str = "data/bestball.db") -> None:
    """Create all tables in the SQLite database if they don't exist."""
    from sqlmodel import create_engine
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    SQLModel.metadata.create_all(engine)
    return engine
