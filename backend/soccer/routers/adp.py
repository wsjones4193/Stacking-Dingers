"""
/api/soccer/adp/* — ADP scatter, movement trends, positional scarcity.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session, func, select

from backend.db.deps import get_session
from backend.schemas import DataResponse
from backend.soccer.db_models import SoccerAdpSnapshot, SoccerPlayer, SoccerPlayerStats
from backend.soccer.schemas import SoccerAdpMovement, SoccerAdpScatterPoint, SoccerAdpScarcity

router = APIRouter()
SessionDep = Annotated[Session, Depends(get_session)]


@router.get("/scatter", response_model=DataResponse)
def adp_scatter(
    session: SessionDep,
    position: Optional[str] = Query(default=None, description="GK, DEF, MID, FWD"),
    nationality: Optional[str] = Query(default=None),
    limit: int = Query(default=200, le=500),
):
    """
    ADP vs. club stats scatter — each dot is a draftable player.
    X-axis: current ADP. Y-axis: points_per_90 (club season proxy for value).
    """
    today = date.today()

    # Get latest ADP per player (subquery: max snapshot_date per player)
    stmt = (
        select(SoccerAdpSnapshot, SoccerPlayer, SoccerPlayerStats)
        .join(SoccerPlayer, SoccerPlayer.player_id == SoccerAdpSnapshot.player_id)
        .outerjoin(
            SoccerPlayerStats,
            (SoccerPlayerStats.player_id == SoccerAdpSnapshot.player_id)
            & (SoccerPlayerStats.season == 2025),  # current club season
        )
        .where(SoccerAdpSnapshot.snapshot_date == today)
        .where(SoccerPlayer.active == True)
        .where(SoccerAdpSnapshot.adp != None)
    )

    if position:
        stmt = stmt.where(SoccerPlayer.position == position.upper())
    if nationality:
        stmt = stmt.where(SoccerPlayer.nationality.icontains(nationality))

    rows = session.exec(stmt.limit(limit)).all()

    points = []
    for snap, player, stats in rows:
        points.append(SoccerAdpScatterPoint(
            player_id=player.player_id,
            name=player.name,
            position=player.position,
            nationality=player.nationality,
            current_club=player.current_club,
            adp=snap.adp,
            draft_rate=snap.draft_rate,
            points_per_90=stats.points_per_90 if stats else None,
        ))

    points.sort(key=lambda x: x.adp)
    return DataResponse(data=points, data_as_of=today.isoformat())


@router.get("/movement", response_model=DataResponse)
def adp_movement(
    session: SessionDep,
    days: int = Query(default=7, ge=1, le=30),
    position: Optional[str] = Query(default=None),
    limit: int = Query(default=50, le=200),
):
    """
    ADP movement over the last N days.
    Returns players sorted by biggest rise (ADP number dropped = rising value).
    """
    today = date.today()
    past = today - timedelta(days=days)

    # Get today's ADP
    today_snaps = {
        row.player_id: row
        for row in session.exec(
            select(SoccerAdpSnapshot).where(SoccerAdpSnapshot.snapshot_date == today)
        ).all()
    }

    # Get past ADP (closest snapshot at or before `past`)
    past_snaps = {}
    for pid in today_snaps:
        snap = session.exec(
            select(SoccerAdpSnapshot)
            .where(SoccerAdpSnapshot.player_id == pid)
            .where(SoccerAdpSnapshot.snapshot_date <= past)
            .order_by(SoccerAdpSnapshot.snapshot_date.desc())
            .limit(1)
        ).first()
        if snap:
            past_snaps[pid] = snap

    results = []
    for pid, today_snap in today_snaps.items():
        if today_snap.adp is None:
            continue
        player = session.get(SoccerPlayer, pid)
        if not player or not player.active:
            continue
        if position and player.position != position.upper():
            continue

        past_adp = past_snaps.get(pid)
        movement = None
        if past_adp and past_adp.adp is not None:
            # Positive movement = ADP number dropped = player rising
            movement = round(past_adp.adp - today_snap.adp, 1)

        results.append(SoccerAdpMovement(
            player_id=player.player_id,
            name=player.name,
            position=player.position,
            adp_7d_ago=past_adp.adp if past_adp else None,
            adp_today=today_snap.adp,
            movement=movement,
        ))

    results.sort(key=lambda x: (-(x.movement or 0), x.adp_today or 9999))
    return DataResponse(data=results[:limit], data_as_of=today.isoformat())


@router.get("/scarcity", response_model=DataResponse)
def adp_scarcity(
    session: SessionDep,
):
    """
    Positional scarcity curves — cumulative % of each position drafted by pick number.
    Uses today's ADP data to estimate how quickly each position is typically gone.
    """
    today = date.today()

    snaps = session.exec(
        select(SoccerAdpSnapshot, SoccerPlayer)
        .join(SoccerPlayer, SoccerPlayer.player_id == SoccerAdpSnapshot.player_id)
        .where(SoccerAdpSnapshot.snapshot_date == today)
        .where(SoccerAdpSnapshot.adp != None)
        .where(SoccerPlayer.active == True)
    ).all()

    # Group by position, sort by ADP
    by_position: dict[str, list[float]] = defaultdict(list)
    for snap, player in snaps:
        by_position[player.position].append(snap.adp)

    results = []
    for pos, adps in by_position.items():
        adps.sort()
        total = len(adps)
        for i, adp_val in enumerate(adps):
            results.append(SoccerAdpScarcity(
                position=pos,
                pick_number=round(adp_val),
                cumulative_pct=round((i + 1) / total, 3),
            ))

    return DataResponse(data=results, data_as_of=today.isoformat())


@router.get("/history/{player_id}", response_model=DataResponse)
def adp_history(
    player_id: int,
    session: SessionDep,
    days: int = Query(default=30, ge=7, le=90),
):
    """ADP timeseries for a single player (for trend chart on player detail page)."""
    cutoff = date.today() - timedelta(days=days)
    rows = session.exec(
        select(SoccerAdpSnapshot)
        .where(SoccerAdpSnapshot.player_id == player_id)
        .where(SoccerAdpSnapshot.snapshot_date >= cutoff)
        .order_by(SoccerAdpSnapshot.snapshot_date.asc())
    ).all()

    data = [
        {"date": r.snapshot_date.isoformat(), "adp": r.adp, "draft_rate": r.draft_rate}
        for r in rows
    ]
    return DataResponse(data=data, data_as_of=date.today().isoformat())
