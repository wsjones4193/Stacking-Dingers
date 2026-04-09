"""
/api/adp — ADP Explorer endpoints.

Three views:
  GET /api/adp/scatter   — ADP rank vs. BPCOR rank scatter data
  GET /api/adp/movement  — ADP movement over draft window
  GET /api/adp/scarcity  — positional scarcity curves
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session, select

from backend.constants import LOW_CONFIDENCE_THRESHOLD
from backend.db.deps import get_session
import sqlite3
from pathlib import Path

from backend.db.models import AdpSnapshot, Player, WeeklyScore

# Path to the tiny pre-computed cache DB shipped with each deployment
_ADP_CACHE_DB = Path(__file__).resolve().parent.parent.parent / "data" / "adp_cache.db"


def _cache_conn():
    """Return a read-only-friendly connection to adp_cache.db."""
    return sqlite3.connect(str(_ADP_CACHE_DB))
from backend.schemas import (
    AdpMovementPoint,
    AdpScatterPoint,
    DataResponse,
    PositionalScarcityCurve,
)

router = APIRouter()

SessionDep = Annotated[Session, Depends(get_session)]


# ---------------------------------------------------------------------------
# GET /api/adp/scatter?season=2026&position=P
# ---------------------------------------------------------------------------

@router.get("/scatter", response_model=DataResponse)
def adp_scatter(
    session: SessionDep,
    season: int = Query(default=2026),
    position: Optional[str] = Query(default=None, description="P | IF | OF"),
):
    """ADP vs. production rank scatter data. Top 10 value/bust highlighted."""
    # Get all players with ADP data this season
    stmt = select(Player).where(Player.active == True)  # noqa: E712
    if position:
        stmt = stmt.where(Player.position == position.upper())
    players = session.exec(stmt).all()

    points: list[AdpScatterPoint] = []

    for p in players:
        latest_adp_row = session.exec(
            select(AdpSnapshot)
            .where(AdpSnapshot.player_id == p.player_id)
            .where(AdpSnapshot.season == season)
            .order_by(AdpSnapshot.snapshot_date.desc())
            .limit(1)
        ).first()
        if not latest_adp_row or not latest_adp_row.adp:
            continue

        # Season BPCOR = sum of started/flex scores across all drafts
        all_ws = session.exec(
            select(WeeklyScore)
            .where(WeeklyScore.player_id == p.player_id)
            .where(WeeklyScore.season == season)
        ).all()
        started = [w.calculated_score for w in all_ws if w.is_starter or w.is_flex]
        bpcor = sum(started) / len(set(w.draft_id for w in all_ws)) if all_ws else 0.0

        points.append(AdpScatterPoint(
            player_id=p.player_id,
            name=p.name,
            position=p.position,
            adp_rank=0,         # filled after sort
            bpcor_rank=None,
            adp=latest_adp_row.adp,
            season_bpcor=round(bpcor, 2),
            value_label=None,
        ))

    # Rank by ADP (ascending = earlier pick = higher rank)
    points.sort(key=lambda x: x.adp or 9999)
    for rank, pt in enumerate(points, start=1):
        pt.adp_rank = rank

    # Rank by BPCOR (descending = higher production = better rank)
    bpcor_sorted = sorted(
        [p for p in points if p.season_bpcor],
        key=lambda x: x.season_bpcor,
        reverse=True,
    )
    bpcor_rank_map = {p.player_id: rank for rank, p in enumerate(bpcor_sorted, start=1)}
    for pt in points:
        pt.bpcor_rank = bpcor_rank_map.get(pt.player_id)

    # Value/bust labels: top 10 discrepancy (ADP rank >> BPCOR rank = value, opposite = bust)
    ranked = [p for p in points if p.bpcor_rank]
    ranked_by_diff = sorted(
        ranked, key=lambda x: (x.adp_rank - x.bpcor_rank), reverse=True
    )
    for pt in ranked_by_diff[:10]:
        pt.value_label = "value"
    for pt in ranked_by_diff[-10:]:
        pt.value_label = "bust"

    return DataResponse(
        data=points,
        sample_size=len(points),
        low_confidence=len(points) < LOW_CONFIDENCE_THRESHOLD,
        data_as_of=date.today().isoformat(),
    )


# ---------------------------------------------------------------------------
# GET /api/adp/movement?season=2026&player_id=123&position=P&start=2026-03-01&end=2026-04-01
# ---------------------------------------------------------------------------

@router.get("/movement", response_model=DataResponse)
def adp_movement(
    session: SessionDep,
    season: int = Query(default=2026),
    player_id: Optional[int] = Query(default=None),
    position: Optional[str] = Query(default=None),
    start: Optional[date] = Query(default=None),
    end: Optional[date] = Query(default=None),
    limit: int = Query(default=20, le=50),
):
    """ADP movement over the draft window — per-player or position-filtered."""
    stmt = (
        select(AdpSnapshot, Player)
        .join(Player, AdpSnapshot.player_id == Player.player_id)
        .where(AdpSnapshot.season == season)
    )
    if player_id:
        stmt = stmt.where(AdpSnapshot.player_id == player_id)
    if position:
        stmt = stmt.where(Player.position == position.upper())
    if start:
        stmt = stmt.where(AdpSnapshot.snapshot_date >= start)
    if end:
        stmt = stmt.where(AdpSnapshot.snapshot_date <= end)

    stmt = stmt.order_by(AdpSnapshot.snapshot_date)
    rows = session.exec(stmt).all()

    result = [
        AdpMovementPoint(
            snapshot_date=str(snap.snapshot_date),
            player_id=p.player_id,
            name=p.name,
            adp=snap.adp,
            draft_rate=snap.draft_rate,
        )
        for snap, p in rows
    ]
    return DataResponse(
        data=result,
        sample_size=len(result),
        data_as_of=date.today().isoformat(),
    )


# ---------------------------------------------------------------------------
# GET /api/adp/scarcity?season=2026&prior_season=2025
# ---------------------------------------------------------------------------

@router.get("/scarcity", response_model=DataResponse)
def adp_scarcity(
    session: SessionDep,
    season: int = Query(default=2026),
    prior_season: Optional[int] = Query(default=None),
):
    """
    Positional scarcity curves: for each position, cumulative % of position
    drafted by ADP rank, with optional prior-season overlay.
    """
    seasons_to_fetch = [season]
    if prior_season:
        seasons_to_fetch.append(prior_season)

    curves: list[PositionalScarcityCurve] = []

    for s in seasons_to_fetch:
        # Get all ADP data for the most recent snapshot date of this season
        latest_date_row = session.exec(
            select(AdpSnapshot.snapshot_date)
            .where(AdpSnapshot.season == s)
            .order_by(AdpSnapshot.snapshot_date.desc())
            .limit(1)
        ).first()
        if not latest_date_row:
            continue

        rows = session.exec(
            select(AdpSnapshot, Player)
            .join(Player, AdpSnapshot.player_id == Player.player_id)
            .where(AdpSnapshot.season == s)
            .where(AdpSnapshot.snapshot_date == latest_date_row)
            .where(AdpSnapshot.adp.is_not(None))
            .order_by(AdpSnapshot.adp)
        ).all()

        by_position: dict[str, list[dict]] = {}
        for rank, (snap, p) in enumerate(rows, start=1):
            by_position.setdefault(p.position, []).append({
                "adp_rank": rank,
                "adp": snap.adp,
            })

        for pos, picks in by_position.items():
            total = len(picks)
            for i, pick in enumerate(picks):
                pick["cumulative_pct"] = round((i + 1) / total * 100, 1)
            curves.append(PositionalScarcityCurve(position=pos, season=s, picks=picks))

    return DataResponse(data=curves, data_as_of=date.today().isoformat())


# ---------------------------------------------------------------------------
# GET /api/adp/leaderboard?season=2025&position=P
# Reads from adp_cache.db (ships with each Railway deployment)
# ---------------------------------------------------------------------------

@router.get("/leaderboard", response_model=DataResponse)
def adp_leaderboard(
    season: int = Query(default=2025),
    position: Optional[str] = Query(default=None, description="P | IF | OF"),
):
    """Per-player ADP summary derived from actual draft picks."""
    conn = _cache_conn()
    sql = "SELECT player_id, player_name, position, avg_pick, pick_std, ownership_pct, draft_count, total_season_drafts FROM adp_player_summary WHERE season=?"
    params: list = [season]
    if position:
        sql += " AND position=?"
        params.append(position.upper())
    sql += " ORDER BY avg_pick"
    rows = conn.execute(sql, params).fetchall()
    conn.close()

    data = [
        {
            "player_id": r[0], "player_name": r[1], "position": r[2],
            "avg_pick": r[3], "pick_std": r[4],
            "ownership_pct": r[5], "draft_count": r[6], "total_season_drafts": r[7],
        }
        for r in rows
    ]
    return DataResponse(data=data, sample_size=len(data), data_as_of=date.today().isoformat())


# ---------------------------------------------------------------------------
# GET /api/adp/scarcity-cache?season=2025
# ---------------------------------------------------------------------------

@router.get("/scarcity-cache", response_model=DataResponse)
def adp_scarcity_cache(
    season: int = Query(default=2025),
):
    """Pre-computed positional scarcity curves for a given season."""
    conn = _cache_conn()
    rows = conn.execute(
        "SELECT season, position, pick_number, cumulative_pct FROM adp_scarcity_cache WHERE season=? ORDER BY position, pick_number",
        [season],
    ).fetchall()
    conn.close()

    data = [
        {"season": r[0], "position": r[1], "pick_number": r[2], "cumulative_pct": r[3]}
        for r in rows
    ]
    return DataResponse(data=data, sample_size=len(data), data_as_of=date.today().isoformat())


# ---------------------------------------------------------------------------
# GET /api/adp/round-composition?season=2025
# ---------------------------------------------------------------------------

@router.get("/round-composition", response_model=DataResponse)
def adp_round_composition(
    season: int = Query(default=2025),
):
    """Pre-computed position breakdown per round for a given season."""
    conn = _cache_conn()
    rows = conn.execute(
        "SELECT season, round_number, position, count, pct_of_round FROM adp_round_composition WHERE season=? ORDER BY round_number, position",
        [season],
    ).fetchall()
    conn.close()

    data = [
        {"season": r[0], "round_number": r[1], "position": r[2], "count": r[3], "pct_of_round": r[4]}
        for r in rows
    ]
    return DataResponse(data=data, sample_size=len(data), data_as_of=date.today().isoformat())
