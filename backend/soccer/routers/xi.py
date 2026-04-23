"""
/api/soccer/xi — projected starting XIs per national team.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from backend.db.deps import get_session
from backend.schemas import DataResponse
from backend.soccer.constants import WORLD_CUP_TEAMS
from backend.soccer.db_models import SoccerAdpSnapshot, SoccerPlayer, SoccerProjectedXI
from backend.soccer.schemas import ProjectedXI, XIPlayer

router = APIRouter()
SessionDep = Annotated[Session, Depends(get_session)]


def _build_xi(team_name: str, rows: list, session: Session) -> ProjectedXI:
    starters, bench = [], []
    latest_updated = None

    for row in rows:
        player = session.get(SoccerPlayer, row.player_id)
        if not player:
            continue

        latest_adp = session.exec(
            select(SoccerAdpSnapshot)
            .where(SoccerAdpSnapshot.player_id == player.player_id)
            .order_by(SoccerAdpSnapshot.snapshot_date.desc())
            .limit(1)
        ).first()

        xi_player = XIPlayer(
            player_id=player.player_id,
            name=player.name,
            position=player.position,
            position_slot=row.position_slot,
            current_adp=latest_adp.adp if latest_adp else None,
            is_starter=row.is_starter,
        )
        if row.is_starter:
            starters.append(xi_player)
        else:
            bench.append(xi_player)

        if latest_updated is None or row.updated_at > latest_updated:
            latest_updated = row.updated_at

    # Try to get formation from first starter row
    formation = rows[0].formation if rows else "4-3-3"

    return ProjectedXI(
        team_name=team_name,
        formation=formation,
        starters=starters,
        bench=bench,
        updated_at=latest_updated.isoformat() if latest_updated else None,
    )


@router.get("/teams", response_model=DataResponse)
def list_teams(session: SessionDep):
    """List all national teams that have a projected XI entered."""
    teams = session.exec(
        select(SoccerProjectedXI.team_name).distinct()
    ).all()
    return DataResponse(data=sorted(teams), data_as_of=date.today().isoformat())


@router.get("/all-teams", response_model=DataResponse)
def all_wc_teams(session: SessionDep):
    """Full list of 2026 World Cup teams (whether or not they have an XI entered)."""
    return DataResponse(data=sorted(WORLD_CUP_TEAMS), data_as_of=date.today().isoformat())


@router.get("/{team_name}", response_model=DataResponse)
def get_xi(team_name: str, session: SessionDep):
    """Projected starting XI for a national team."""
    rows = session.exec(
        select(SoccerProjectedXI)
        .where(SoccerProjectedXI.team_name.icontains(team_name))
        .order_by(SoccerProjectedXI.is_starter.desc())
    ).all()

    if not rows:
        raise HTTPException(status_code=404, detail=f"No XI found for {team_name}")

    actual_team = rows[0].team_name
    xi = _build_xi(actual_team, rows, session)
    return DataResponse(data=xi, data_as_of=date.today().isoformat())


# ---------------------------------------------------------------------------
# Admin write endpoints (update projected XIs)
# ---------------------------------------------------------------------------

class XIEntryInput(BaseModel):
    player_id: int
    position_slot: str    # e.g. "GK", "CB1", "CB2", "LB", "RB", "CM1"
    is_starter: bool = True


class SetXIRequest(BaseModel):
    formation: str = "4-3-3"
    players: list[XIEntryInput]


@router.post("/{team_name}", response_model=DataResponse)
def set_xi(team_name: str, body: SetXIRequest, session: SessionDep):
    """Replace the entire projected XI for a team (admin use)."""
    # Delete existing
    existing = session.exec(
        select(SoccerProjectedXI).where(SoccerProjectedXI.team_name == team_name)
    ).all()
    for row in existing:
        session.delete(row)

    # Insert new
    for entry in body.players:
        session.add(SoccerProjectedXI(
            team_name=team_name,
            formation=body.formation,
            player_id=entry.player_id,
            position_slot=entry.position_slot,
            is_starter=entry.is_starter,
        ))

    session.commit()

    rows = session.exec(
        select(SoccerProjectedXI).where(SoccerProjectedXI.team_name == team_name)
    ).all()
    xi = _build_xi(team_name, rows, session)
    return DataResponse(data=xi, data_as_of=date.today().isoformat())
