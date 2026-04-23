"""
/api/soccer/odds — team advancement odds per World Cup stage.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from backend.db.deps import get_session
from backend.schemas import DataResponse
from backend.soccer.db_models import SoccerTeamOdds
from backend.soccer.schemas import TeamOddsRow

router = APIRouter()
SessionDep = Annotated[Session, Depends(get_session)]

STAGES = ["r32", "r16", "qf", "sf", "final", "winner"]


@router.get("/", response_model=DataResponse)
def get_odds(session: SessionDep):
    """
    Return all team odds pivoted into one row per team.
    Columns: team_name, r32_prob, r16_prob, qf_prob, sf_prob, final_prob, winner_prob.
    """
    rows = session.exec(select(SoccerTeamOdds)).all()

    # Pivot: team → stage → prob
    teams: dict[str, dict] = {}
    latest_update = None
    for row in rows:
        if row.team_name not in teams:
            teams[row.team_name] = {s: None for s in STAGES}
            teams[row.team_name]["updated_at"] = None
        teams[row.team_name][row.stage] = row.implied_prob
        if row.updated_at:
            teams[row.team_name]["updated_at"] = row.updated_at.isoformat()

    result = [
        TeamOddsRow(
            team_name=team,
            r32_prob=data.get("r32"),
            r16_prob=data.get("r16"),
            qf_prob=data.get("qf"),
            sf_prob=data.get("sf"),
            final_prob=data.get("final"),
            winner_prob=data.get("winner"),
            updated_at=data.get("updated_at"),
        )
        for team, data in sorted(teams.items(), key=lambda x: -(x[1].get("winner") or 0))
    ]

    return DataResponse(
        data=result,
        data_as_of=date.today().isoformat(),
        sample_size=len(result),
    )


@router.get("/{team_name}", response_model=DataResponse)
def get_team_odds(team_name: str, session: SessionDep):
    """Odds for a single national team across all stages."""
    rows = session.exec(
        select(SoccerTeamOdds).where(SoccerTeamOdds.team_name.icontains(team_name))
    ).all()

    data = {r.stage: {"implied_prob": r.implied_prob, "odds": r.odds} for r in rows}
    return DataResponse(data={"team_name": team_name, "odds_by_stage": data}, data_as_of=date.today().isoformat())
