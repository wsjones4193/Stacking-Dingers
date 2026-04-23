"""
/api/soccer/rankings — CRUD for user-saved player ranking lists.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import Session, select

from backend.db.deps import get_session
from backend.schemas import DataResponse
from backend.soccer.db_models import SoccerAdpSnapshot, SoccerPlayer, SoccerRanking
from backend.soccer.schemas import RankingEntry, RankingList, RankingListSummary

router = APIRouter()
SessionDep = Annotated[Session, Depends(get_session)]


# ---------------------------------------------------------------------------
# Request body schemas
# ---------------------------------------------------------------------------

class RankingEntryInput(BaseModel):
    player_id: int
    tier: Optional[int] = None
    notes: Optional[str] = None


class CreateRankingRequest(BaseModel):
    name: str
    description: Optional[str] = None
    position_filter: Optional[str] = None  # "ALL", "GK", "DEF", "MID", "FWD"
    entries: list[RankingEntryInput] = []


class UpdateRankingRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    position_filter: Optional[str] = None
    entries: Optional[list[RankingEntryInput]] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_ranking_list(ranking: SoccerRanking, session: Session) -> RankingList:
    raw_entries = json.loads(ranking.rankings_json)
    entries = []
    for e in raw_entries:
        player = session.get(SoccerPlayer, e["player_id"])
        if not player:
            continue
        latest_adp = session.exec(
            select(SoccerAdpSnapshot)
            .where(SoccerAdpSnapshot.player_id == player.player_id)
            .order_by(SoccerAdpSnapshot.snapshot_date.desc())
            .limit(1)
        ).first()
        entries.append(RankingEntry(
            player_id=player.player_id,
            name=player.name,
            position=player.position,
            nationality=player.nationality,
            current_adp=latest_adp.adp if latest_adp else None,
            tier=e.get("tier"),
            notes=e.get("notes"),
        ))
    return RankingList(
        ranking_id=ranking.ranking_id,
        name=ranking.name,
        description=ranking.description,
        position_filter=ranking.position_filter,
        entries=entries,
        created_at=ranking.created_at.isoformat(),
        updated_at=ranking.updated_at.isoformat(),
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/", response_model=DataResponse)
def list_rankings(session: SessionDep):
    """List all saved rankings (summary only, no entries)."""
    rankings = session.exec(select(SoccerRanking)).all()
    summaries = [
        RankingListSummary(
            ranking_id=r.ranking_id,
            name=r.name,
            description=r.description,
            position_filter=r.position_filter,
            entry_count=len(json.loads(r.rankings_json)),
            updated_at=r.updated_at.isoformat(),
        )
        for r in rankings
    ]
    return DataResponse(data=summaries, data_as_of=date.today().isoformat())


@router.post("/", response_model=DataResponse)
def create_ranking(body: CreateRankingRequest, session: SessionDep):
    """Create a new ranking list."""
    ranking = SoccerRanking(
        name=body.name,
        description=body.description,
        position_filter=body.position_filter,
        rankings_json=json.dumps([e.model_dump() for e in body.entries]),
    )
    session.add(ranking)
    session.commit()
    session.refresh(ranking)
    return DataResponse(data=_build_ranking_list(ranking, session), data_as_of=date.today().isoformat())


@router.get("/{ranking_id}", response_model=DataResponse)
def get_ranking(ranking_id: int, session: SessionDep):
    """Get a ranking list with full player details."""
    ranking = session.get(SoccerRanking, ranking_id)
    if not ranking:
        raise HTTPException(status_code=404, detail="Ranking not found")
    return DataResponse(data=_build_ranking_list(ranking, session), data_as_of=date.today().isoformat())


@router.patch("/{ranking_id}", response_model=DataResponse)
def update_ranking(ranking_id: int, body: UpdateRankingRequest, session: SessionDep):
    """Update a ranking's metadata or entries."""
    ranking = session.get(SoccerRanking, ranking_id)
    if not ranking:
        raise HTTPException(status_code=404, detail="Ranking not found")

    if body.name is not None:
        ranking.name = body.name
    if body.description is not None:
        ranking.description = body.description
    if body.position_filter is not None:
        ranking.position_filter = body.position_filter
    if body.entries is not None:
        ranking.rankings_json = json.dumps([e.model_dump() for e in body.entries])

    ranking.updated_at = datetime.utcnow()
    session.add(ranking)
    session.commit()
    session.refresh(ranking)
    return DataResponse(data=_build_ranking_list(ranking, session), data_as_of=date.today().isoformat())


@router.delete("/{ranking_id}", response_model=DataResponse)
def delete_ranking(ranking_id: int, session: SessionDep):
    """Delete a ranking list."""
    ranking = session.get(SoccerRanking, ranking_id)
    if not ranking:
        raise HTTPException(status_code=404, detail="Ranking not found")
    session.delete(ranking)
    session.commit()
    return DataResponse(data={"deleted": ranking_id}, data_as_of=date.today().isoformat())
