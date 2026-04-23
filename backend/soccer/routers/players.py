"""
/api/soccer/players/* — player search and detail endpoints.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session, select

from backend.db.deps import get_session
from backend.schemas import DataResponse
from backend.soccer.db_models import SoccerAdpSnapshot, SoccerPlayer, SoccerPlayerStats
from backend.soccer.schemas import SoccerPlayerDetail, SoccerPlayerSearchResult
from backend.soccer.schemas import SoccerPlayerStats as SoccerPlayerStatsSchema

router = APIRouter()
SessionDep = Annotated[Session, Depends(get_session)]


@router.get("/search", response_model=DataResponse)
def search_players(
    session: SessionDep,
    q: str = Query(..., min_length=1),
    position: Optional[str] = Query(default=None, description="GK, DEF, MID, FWD"),
    nationality: Optional[str] = Query(default=None, description="National team filter"),
    limit: int = Query(default=15, le=50),
):
    """Autocomplete player search with optional position/nation filter."""
    stmt = (
        select(SoccerPlayer)
        .where(SoccerPlayer.name.icontains(q))
        .where(SoccerPlayer.active == True)
    )
    if position:
        stmt = stmt.where(SoccerPlayer.position == position.upper())
    if nationality:
        stmt = stmt.where(SoccerPlayer.nationality.icontains(nationality))

    players = session.exec(stmt.limit(limit)).all()

    results = []
    for p in players:
        latest_adp = session.exec(
            select(SoccerAdpSnapshot)
            .where(SoccerAdpSnapshot.player_id == p.player_id)
            .order_by(SoccerAdpSnapshot.snapshot_date.desc())
            .limit(1)
        ).first()

        results.append(SoccerPlayerSearchResult(
            player_id=p.player_id,
            name=p.name,
            position=p.position,
            nationality=p.nationality,
            current_club=p.current_club,
            current_adp=latest_adp.adp if latest_adp else None,
            draft_rate=latest_adp.draft_rate if latest_adp else None,
        ))

    results.sort(key=lambda x: (x.current_adp or 9999, x.name))
    return DataResponse(data=results, data_as_of=date.today().isoformat())


@router.get("/by-position", response_model=DataResponse)
def players_by_position(
    session: SessionDep,
    position: str = Query(..., description="GK, DEF, MID, FWD"),
    nationality: Optional[str] = Query(default=None),
    limit: int = Query(default=100, le=500),
):
    """All active players at a position, sorted by current ADP."""
    stmt = (
        select(SoccerPlayer)
        .where(SoccerPlayer.position == position.upper())
        .where(SoccerPlayer.active == True)
    )
    if nationality:
        stmt = stmt.where(SoccerPlayer.nationality.icontains(nationality))

    players = session.exec(stmt.limit(limit)).all()

    results = []
    for p in players:
        latest_adp = session.exec(
            select(SoccerAdpSnapshot)
            .where(SoccerAdpSnapshot.player_id == p.player_id)
            .order_by(SoccerAdpSnapshot.snapshot_date.desc())
            .limit(1)
        ).first()

        results.append(SoccerPlayerSearchResult(
            player_id=p.player_id,
            name=p.name,
            position=p.position,
            nationality=p.nationality,
            current_club=p.current_club,
            current_adp=latest_adp.adp if latest_adp else None,
            draft_rate=latest_adp.draft_rate if latest_adp else None,
        ))

    results.sort(key=lambda x: (x.current_adp or 9999, x.name))
    return DataResponse(data=results, data_as_of=date.today().isoformat())


@router.get("/{player_id}", response_model=DataResponse)
def get_player(
    player_id: int,
    session: SessionDep,
):
    """Full player detail: bio + ADP history + club stats."""
    player = session.get(SoccerPlayer, player_id)
    if not player:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Player not found")

    # ADP history (last 30 days)
    adp_rows = session.exec(
        select(SoccerAdpSnapshot)
        .where(SoccerAdpSnapshot.player_id == player_id)
        .order_by(SoccerAdpSnapshot.snapshot_date.desc())
        .limit(30)
    ).all()

    adp_history = [
        {"date": row.snapshot_date.isoformat(), "adp": row.adp, "draft_rate": row.draft_rate}
        for row in reversed(adp_rows)
    ]

    current_adp = adp_rows[0].adp if adp_rows else None
    current_dr = adp_rows[0].draft_rate if adp_rows else None

    # Club stats
    stats_rows = session.exec(
        select(SoccerPlayerStats)
        .where(SoccerPlayerStats.player_id == player_id)
        .order_by(SoccerPlayerStats.season.desc())
    ).all()

    stats = [
        SoccerPlayerStatsSchema(
            season=s.season,
            club=s.club,
            competition=s.competition,
            matches_played=s.matches_played,
            minutes_played=s.minutes_played,
            goals=s.goals,
            assists=s.assists,
            shots_on_target=s.shots_on_target,
            shots_off_target=s.shots_off_target,
            chances_created=s.chances_created,
            crosses=s.crosses,
            tackles_successful=s.tackles_successful,
            passes_successful=s.passes_successful,
            saves=s.saves,
            penalty_saves=s.penalty_saves,
            goals_conceded=s.goals_conceded,
            wins=s.wins,
            clean_sheets=s.clean_sheets,
            calculated_points=s.calculated_points,
            points_per_90=s.points_per_90,
        )
        for s in stats_rows
    ]

    detail = SoccerPlayerDetail(
        player_id=player.player_id,
        name=player.name,
        position=player.position,
        nationality=player.nationality,
        current_club=player.current_club,
        underdog_id=player.underdog_id,
        active=player.active,
        current_adp=current_adp,
        draft_rate=current_dr,
        adp_history=adp_history,
        stats=stats,
    )
    return DataResponse(data=detail, data_as_of=date.today().isoformat())
