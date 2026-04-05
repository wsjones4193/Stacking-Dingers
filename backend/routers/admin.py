"""
/api/admin/* — admin-only endpoints (no auth, obscure route).

GET  /api/admin/player-mapping         — list unconfirmed mappings
PATCH /api/admin/player-mapping/{map_id} — confirm or correct a mapping
POST  /api/admin/player-mapping        — manually add a mapping

GET  /api/admin/score-audit            — score discrepancies
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import Session, select

from backend.db.deps import get_session
from backend.db.models import Player, PlayerIdMap, ScoreAudit
from backend.schemas import DataResponse, PlayerMappingEntry, ScoreAuditEntry

router = APIRouter()

SessionDep = Annotated[Session, Depends(get_session)]


# ---------------------------------------------------------------------------
# GET /api/admin/player-mapping
# ---------------------------------------------------------------------------

@router.get("/player-mapping", response_model=DataResponse)
def list_player_mappings(
    session: SessionDep,
    season: int = Query(default=2026),
    confirmed: Optional[bool] = Query(default=None, description="Filter by confirmed status"),
    unmatched_only: bool = Query(default=False, description="Only show entries with no mlb_id"),
    limit: int = Query(default=100, le=500),
):
    """List player ID mappings, optionally filtered to unconfirmed or unmatched."""
    stmt = select(PlayerIdMap).where(PlayerIdMap.season == season)
    if confirmed is not None:
        stmt = stmt.where(PlayerIdMap.confirmed == confirmed)
    if unmatched_only:
        stmt = stmt.where(PlayerIdMap.mlb_id == None)  # noqa: E711
    stmt = stmt.order_by(PlayerIdMap.match_score).limit(limit)
    rows = session.exec(stmt).all()

    entries = [
        PlayerMappingEntry(
            map_id=r.map_id,
            underdog_id=r.underdog_id,
            underdog_name=r.underdog_name,
            mlb_id=r.mlb_id,
            mlb_name=r.mlb_name,
            confirmed=r.confirmed,
            match_score=r.match_score,
            season=r.season,
            notes=r.notes,
        )
        for r in rows
    ]
    return DataResponse(data=entries, data_as_of=date.today().isoformat())


# ---------------------------------------------------------------------------
# PATCH /api/admin/player-mapping/{map_id}
# ---------------------------------------------------------------------------

class MappingUpdate(BaseModel):
    mlb_id: Optional[int] = None
    mlb_name: Optional[str] = None
    confirmed: Optional[bool] = None
    notes: Optional[str] = None


@router.patch("/player-mapping/{map_id}", response_model=DataResponse)
def update_player_mapping(
    map_id: int,
    update: MappingUpdate,
    session: SessionDep,
):
    """Confirm, correct, or annotate a player ID mapping."""
    mapping = session.get(PlayerIdMap, map_id)
    if not mapping:
        raise HTTPException(status_code=404, detail="Mapping not found")

    if update.mlb_id is not None:
        mapping.mlb_id = update.mlb_id
    if update.mlb_name is not None:
        mapping.mlb_name = update.mlb_name
    if update.confirmed is not None:
        mapping.confirmed = update.confirmed
    if update.notes is not None:
        mapping.notes = update.notes

    session.add(mapping)
    session.commit()
    session.refresh(mapping)

    return DataResponse(
        data=PlayerMappingEntry(
            map_id=mapping.map_id,
            underdog_id=mapping.underdog_id,
            underdog_name=mapping.underdog_name,
            mlb_id=mapping.mlb_id,
            mlb_name=mapping.mlb_name,
            confirmed=mapping.confirmed,
            match_score=mapping.match_score,
            season=mapping.season,
            notes=mapping.notes,
        ),
        data_as_of=date.today().isoformat(),
    )


# ---------------------------------------------------------------------------
# POST /api/admin/player-mapping
# ---------------------------------------------------------------------------

class MappingCreate(BaseModel):
    underdog_id: str
    underdog_name: str
    mlb_id: Optional[int] = None
    mlb_name: Optional[str] = None
    season: int = 2026
    notes: Optional[str] = None


@router.post("/player-mapping", response_model=DataResponse)
def create_player_mapping(
    body: MappingCreate,
    session: SessionDep,
):
    """Manually add a player ID mapping."""
    mapping = PlayerIdMap(
        underdog_id=body.underdog_id,
        underdog_name=body.underdog_name,
        mlb_id=body.mlb_id,
        mlb_name=body.mlb_name,
        confirmed=True,   # manual additions are auto-confirmed
        match_score=None,
        season=body.season,
        notes=body.notes,
    )
    session.add(mapping)
    session.commit()
    session.refresh(mapping)

    return DataResponse(
        data=PlayerMappingEntry(
            map_id=mapping.map_id,
            underdog_id=mapping.underdog_id,
            underdog_name=mapping.underdog_name,
            mlb_id=mapping.mlb_id,
            mlb_name=mapping.mlb_name,
            confirmed=mapping.confirmed,
            match_score=mapping.match_score,
            season=mapping.season,
            notes=mapping.notes,
        ),
        data_as_of=date.today().isoformat(),
    )


# ---------------------------------------------------------------------------
# GET /api/admin/score-audit
# ---------------------------------------------------------------------------

@router.get("/score-audit", response_model=DataResponse)
def get_score_audit(
    session: SessionDep,
    season: int = Query(default=2026),
    week_number: Optional[int] = Query(default=None),
    min_delta: float = Query(default=0.5, description="Minimum absolute delta to include"),
    sort_by: str = Query(default="delta", description="delta | week_number | player_id"),
    limit: int = Query(default=100, le=500),
):
    """
    Score audit discrepancies (calculated vs. Underdog-reported scores).
    Sorted by delta magnitude descending.
    """
    stmt = (
        select(ScoreAudit, Player)
        .join(Player, ScoreAudit.player_id == Player.player_id)
        .where(ScoreAudit.season == season)
    )
    if week_number:
        stmt = stmt.where(ScoreAudit.week_number == week_number)
    rows = session.exec(stmt).all()

    entries = []
    for audit, player in rows:
        if abs(audit.delta) < min_delta:
            continue
        entries.append(ScoreAuditEntry(
            audit_id=audit.audit_id,
            player_id=audit.player_id,
            player_name=player.name,
            draft_id=audit.draft_id,
            week_number=audit.week_number,
            season=audit.season,
            calculated_score=audit.calculated_score,
            underdog_score=audit.underdog_score,
            delta=audit.delta,
            flagged_date=audit.flagged_date.isoformat(),
        ))

    sort_key = {
        "delta": lambda e: abs(e.delta),
        "week_number": lambda e: e.week_number,
        "player_id": lambda e: e.player_id,
    }.get(sort_by, lambda e: abs(e.delta))

    entries.sort(key=sort_key, reverse=True)
    entries = entries[:limit]

    return DataResponse(
        data=entries,
        sample_size=len(entries),
        data_as_of=date.today().isoformat(),
    )
