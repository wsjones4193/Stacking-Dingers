"""
SQLModel table definitions for bestball.db.
All tables use integer primary keys. JSON columns stored as TEXT in SQLite.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Optional

from sqlalchemy import UniqueConstraint
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
    pick_number: int                        # overall pick number 1–240
    round_number: int                       # draft round 1–20
    player_id: int = Field(foreign_key="players.player_id", index=True)
    username: str
    projection_adp: Optional[float] = None  # Underdog's ADP at time of draft


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
    replacement_score: Optional[float] = None  # bench replacement level for this position group
    bpcor: Optional[float] = None              # max(0, score - replacement) if starter/flex, else 0


# ---------------------------------------------------------------------------
# Player-level weekly scores (MLB-wide, independent of drafts)
# ---------------------------------------------------------------------------

class PlayerWeeklyScore(SQLModel, table=True):
    __tablename__ = "player_weekly_scores"
    __table_args__ = (
        UniqueConstraint("mlb_id", "season", "week_number", "stat_type"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    mlb_id: int = Field(index=True)
    player_name: str
    season: int = Field(index=True)
    week_number: int
    stat_type: str              # "hitting" or "pitching"
    calculated_points: float = Field(default=0.0)


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
# Articles (admin-authored written content)
# ---------------------------------------------------------------------------

class Article(SQLModel, table=True):
    __tablename__ = "articles"

    article_id: Optional[int] = Field(default=None, primary_key=True)
    title: str = Field(index=True)
    author: str
    published_date: date
    content_html: str           # rich-text stored as HTML (TipTap output)
    excerpt: str                # plain-text blurb for card view
    thumbnail_url: Optional[str] = None
    slug: str = Field(unique=True, index=True)   # URL-friendly identifier
    category: Optional[str] = None   # "data analysis" | "strategy" | "adp" | "other"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# Podcast episodes (manually added via admin)
# ---------------------------------------------------------------------------

class PodcastEpisode(SQLModel, table=True):
    __tablename__ = "podcast_episodes"

    episode_id: Optional[int] = Field(default=None, primary_key=True)
    youtube_id: str = Field(unique=True, index=True)   # e.g. "dQw4w9WgXcQ"
    title: str
    published_date: date
    description: str
    thumbnail_url: Optional[str] = None
    duration_seconds: Optional[int] = None
    series: Optional[str] = None   # user-defined tag e.g. "Draft Season 2026"


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
# Pre-computed ADP tables (populated by scripts/precompute_adp.py)
# ---------------------------------------------------------------------------

class AdpPlayerSummary(SQLModel, table=True):
    __tablename__ = "adp_player_summary"
    __table_args__ = (
        UniqueConstraint("player_id", "season"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    player_id: int = Field(foreign_key="players.player_id", index=True)
    season: int = Field(index=True)
    player_name: str
    position: str
    avg_pick: float
    pick_std: Optional[float] = None
    ownership_pct: float        # % of season drafts that drafted this player
    draft_count: int            # times drafted
    total_season_drafts: int    # total drafts in season (denominator)


class AdpScarcityCache(SQLModel, table=True):
    __tablename__ = "adp_scarcity_cache"
    __table_args__ = (
        UniqueConstraint("season", "position", "pick_number"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    season: int = Field(index=True)
    position: str
    pick_number: int
    cumulative_pct: float       # % of that position's total picks made by this pick number
    avg_per_draft: float = Field(default=0.0)  # avg count of this position selected per draft by this pick


class AdpRoundComposition(SQLModel, table=True):
    __tablename__ = "adp_round_composition"
    __table_args__ = (
        UniqueConstraint("season", "round_number", "position"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    season: int = Field(index=True)
    round_number: int
    position: str
    count: int
    pct_of_round: float         # % of all picks in this round taken at this position


# ---------------------------------------------------------------------------
# Database initialization helper
# ---------------------------------------------------------------------------

def create_db_and_tables(db_path: str = "data/bestball.db") -> None:
    """Create all tables in the SQLite database if they don't exist."""
    from sqlmodel import create_engine
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    SQLModel.metadata.create_all(engine)
    return engine
