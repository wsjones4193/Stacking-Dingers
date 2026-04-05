"""
/api/leaderboard — all teams, sortable + filterable + paginated.
"""

from __future__ import annotations

import json
from datetime import date
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session, select

from backend.db.deps import get_session
from backend.db.models import Draft, DraftSequence, GroupStanding, TeamSeasonProfile
from backend.schemas import DataResponse, LeaderboardEntry

router = APIRouter()

SessionDep = Annotated[Session, Depends(get_session)]


@router.get("", response_model=DataResponse)
def get_leaderboard(
    session: SessionDep,
    season: int = Query(default=2026),
    draft_date_from: Optional[date] = Query(default=None),
    draft_date_to: Optional[date] = Query(default=None),
    draft_position: Optional[int] = Query(default=None, ge=1, le=12),
    position: Optional[str] = Query(default=None, description="Filter by first-round position group drafted"),
    entry_type: Optional[str] = Query(default=None),
    sort_by: str = Query(default="total_points", description="total_points | peak_2wk_score | round_reached"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, le=200),
):
    """
    All teams for a season, sorted and filtered. Supports pagination.
    Each entry includes total points, round reached, ceiling tier, and archetype.
    """
    # Base query: join Draft + GroupStanding (R1) + TeamSeasonProfile
    stmt = (
        select(Draft, GroupStanding, TeamSeasonProfile, DraftSequence)
        .join(GroupStanding,
              (GroupStanding.draft_id == Draft.draft_id) &
              (GroupStanding.round_number == 1) &
              (GroupStanding.season == season),
              isouter=True)
        .join(TeamSeasonProfile,
              TeamSeasonProfile.draft_id == Draft.draft_id,
              isouter=True)
        .join(DraftSequence,
              DraftSequence.draft_id == Draft.draft_id,
              isouter=True)
        .where(Draft.season == season)
    )

    if draft_date_from:
        stmt = stmt.where(Draft.draft_date >= draft_date_from)
    if draft_date_to:
        stmt = stmt.where(Draft.draft_date <= draft_date_to)
    if draft_position:
        stmt = stmt.where(Draft.draft_position == draft_position)
    if entry_type:
        stmt = stmt.where(Draft.entry_type == entry_type)

    rows = session.exec(stmt).all()

    # Build entries
    entries: list[LeaderboardEntry] = []
    for draft, standing, profile, seq in rows:
        total_points = standing.total_points if standing else 0.0
        round_reached = profile.round_reached if profile else None
        peak_2wk = profile.peak_2wk_score if profile else None
        peak_weeks = (
            json.loads(profile.peak_window_weeks_json)
            if profile and profile.peak_window_weeks_json
            else None
        )
        ceiling_tier = profile.ceiling_tier if profile else None
        archetype = seq.archetype_tag if seq else None

        entries.append(LeaderboardEntry(
            rank=0,
            draft_id=draft.draft_id,
            username=draft.username,
            season=draft.season,
            draft_date=draft.draft_date,
            draft_position=draft.draft_position,
            total_points=total_points,
            round_reached=round_reached,
            peak_2wk_score=peak_2wk,
            peak_window_weeks=peak_weeks,
            ceiling_tier=ceiling_tier,
            archetype_tag=archetype,
        ))

    # Sort
    sort_key = {
        "total_points": lambda e: e.total_points,
        "peak_2wk_score": lambda e: e.peak_2wk_score or 0.0,
        "round_reached": lambda e: e.round_reached or 0,
    }.get(sort_by, lambda e: e.total_points)

    entries.sort(key=sort_key, reverse=True)
    for rank, entry in enumerate(entries, start=1):
        entry.rank = rank

    # Paginate
    total = len(entries)
    start = (page - 1) * page_size
    page_entries = entries[start : start + page_size]

    return DataResponse(
        data={
            "entries": page_entries,
            "total": total,
            "page": page,
            "page_size": page_size,
        },
        data_as_of=date.today().isoformat(),
    )
