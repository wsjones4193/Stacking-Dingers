"""
/api/players/* — player search and detail endpoints.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from backend.constants import LOW_CONFIDENCE_THRESHOLD, WEEK_MAP_2026
from backend.db.deps import get_session
from backend.db.models import (
    AdpSnapshot,
    Draft,
    Pick,
    Player,
    Projection,
    RosterFlag,
    WeeklyScore,
)
from backend.db.parquet_helpers import load_gamelogs_for_player
from backend.schemas import DataResponse, PlayerDetail, PlayerSearchResult, PlayerSummary

router = APIRouter()

SessionDep = Annotated[Session, Depends(get_session)]


# ---------------------------------------------------------------------------
# GET /api/players/search?q=name&season=2026
# ---------------------------------------------------------------------------

@router.get("/search", response_model=DataResponse)
def search_players(
    session: SessionDep,
    q: str = Query(..., min_length=1, description="Player name query"),
    season: int = Query(default=2026),
    limit: int = Query(default=10, le=50),
):
    """Autocomplete player search — returns top matches with position, team, current ADP."""
    players = session.exec(
        select(Player)
        .where(Player.name.icontains(q))
        .where(Player.active == True)
        .limit(limit)
    ).all()

    # Fetch most recent ADP for each player
    results = []
    for p in players:
        latest_adp = session.exec(
            select(AdpSnapshot)
            .where(AdpSnapshot.player_id == p.player_id)
            .where(AdpSnapshot.season == season)
            .order_by(AdpSnapshot.snapshot_date.desc())
            .limit(1)
        ).first()

        results.append(PlayerSearchResult(
            player_id=p.player_id,
            name=p.name,
            position=p.position,
            mlb_team=p.mlb_team,
            current_adp=latest_adp.adp if latest_adp else None,
        ))

    results.sort(key=lambda x: (x.current_adp or 9999, x.name))
    return DataResponse(data=results, data_as_of=date.today().isoformat())


# ---------------------------------------------------------------------------
# GET /api/players/{player_id}?season=2026
# ---------------------------------------------------------------------------

@router.get("/{player_id}", response_model=DataResponse)
def get_player(
    player_id: int,
    session: SessionDep,
    season: int = Query(default=2026),
    proj: str = Query(default="blended", description="steamer | atc | blended"),
):
    """Full player detail: scoring trajectory, ADP trend, BPCOR, ownership, roster context."""
    player = session.get(Player, player_id)
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    # --- Scoring trajectory from Parquet ---
    gamelogs_df = load_gamelogs_for_player(season, player_id)
    scoring_trajectory = []
    weekly_scores_map: dict[int, float] = {}

    if not gamelogs_df.empty:
        for _, row in gamelogs_df.sort_values("game_date").iterrows():
            scoring_trajectory.append({
                "date": str(row["game_date"]),
                "points": float(row["calculated_points"]),
            })
        # Aggregate weekly scores for weekly_scores list
        for week_num, (wstart, wend, _) in WEEK_MAP_2026.items():
            mask = (gamelogs_df["game_date"] >= str(wstart)) & (gamelogs_df["game_date"] <= str(wend))
            week_pts = float(gamelogs_df.loc[mask, "calculated_points"].sum())
            if week_pts > 0:
                weekly_scores_map[week_num] = week_pts

    last_game_date = (
        str(gamelogs_df["game_date"].max())
        if not gamelogs_df.empty
        else None
    )

    # --- ADP trend ---
    adp_snapshots = session.exec(
        select(AdpSnapshot)
        .where(AdpSnapshot.player_id == player_id)
        .where(AdpSnapshot.season == season)
        .order_by(AdpSnapshot.snapshot_date)
    ).all()

    current_adp = adp_snapshots[-1].adp if adp_snapshots else None
    draft_rate = adp_snapshots[-1].draft_rate if adp_snapshots else None

    # --- Season BPCOR (sum of started/flex scores) ---
    all_ws = session.exec(
        select(WeeklyScore)
        .where(WeeklyScore.player_id == player_id)
        .where(WeeklyScore.season == season)
        .where(WeeklyScore.is_starter == True)  # noqa: E712
    ).all()
    flex_ws = session.exec(
        select(WeeklyScore)
        .where(WeeklyScore.player_id == player_id)
        .where(WeeklyScore.season == season)
        .where(WeeklyScore.is_flex == True)  # noqa: E712
    ).all()
    season_bpcor = sum(w.calculated_score for w in all_ws + flex_ws)

    # --- Roster count and ownership ---
    pick_count = session.exec(
        select(Pick)
        .join(Draft, Pick.draft_id == Draft.draft_id)
        .where(Pick.player_id == player_id)
        .where(Draft.season == season)
    ).all()
    roster_count = len(pick_count)

    total_drafts_count = session.exec(
        select(Draft).where(Draft.season == season)
    ).all()
    total_drafts = len(total_drafts_count)
    ownership_pct = (roster_count / total_drafts * 100) if total_drafts > 0 else None

    # --- IL status (latest roster flag) ---
    il_flag = session.exec(
        select(RosterFlag)
        .where(RosterFlag.player_id == player_id)
        .where(RosterFlag.flag_type == "il_status")
        .order_by(RosterFlag.created_at.desc())
        .limit(1)
    ).first()
    il_status = il_flag is not None

    detail = PlayerDetail(
        player_id=player.player_id,
        name=player.name,
        position=player.position,
        mlb_team=player.mlb_team,
        underdog_id=player.underdog_id,
        mlb_id=player.mlb_id,
        active=player.active,
        current_adp=current_adp,
        draft_rate=draft_rate,
        season_bpcor=round(season_bpcor, 2),
        ownership_pct=round(ownership_pct, 2) if ownership_pct is not None else None,
        roster_count=roster_count,
        last_game_date=last_game_date,
        il_status=il_status,
        scoring_trajectory=scoring_trajectory,
        weekly_scores=[
            {"week": w, "score": s} for w, s in sorted(weekly_scores_map.items())
        ],
    )
    return DataResponse(data=detail, data_as_of=date.today().isoformat())


# ---------------------------------------------------------------------------
# GET /api/players/{player_id}/history?season=2026
# Returns historical (multi-season) performance for History Browser Module 6
# ---------------------------------------------------------------------------

@router.get("/{player_id}/history", response_model=DataResponse)
def get_player_history(
    player_id: int,
    session: SessionDep,
    seasons: str = Query(
        default="2022,2023,2024,2025,2026",
        description="Comma-separated list of seasons",
    ),
):
    """Historical season-by-season stats for a player (Module 6)."""
    player = session.get(Player, player_id)
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    season_list = [int(s.strip()) for s in seasons.split(",")]
    history = []

    for season in season_list:
        # Weekly scores for this season
        ws_rows = session.exec(
            select(WeeklyScore)
            .where(WeeklyScore.player_id == player_id)
            .where(WeeklyScore.season == season)
        ).all()

        if not ws_rows:
            continue

        started_scores = [w.calculated_score for w in ws_rows if w.is_starter or w.is_flex]
        total_bpcor = sum(started_scores)
        weeks_started = len(started_scores)

        # ADP for this season (opening day canonical snapshot if available)
        canonical_adp = session.exec(
            select(AdpSnapshot)
            .where(AdpSnapshot.player_id == player_id)
            .where(AdpSnapshot.season == season)
            .order_by(AdpSnapshot.snapshot_date)
            .limit(1)
        ).first()

        history.append({
            "season": season,
            "total_bpcor": round(total_bpcor, 2),
            "weeks_started": weeks_started,
            "opening_adp": canonical_adp.adp if canonical_adp else None,
        })

    sample = len(history)
    return DataResponse(
        data={"player": PlayerSummary.model_validate(player), "seasons": history},
        sample_size=sample,
        low_confidence=sample < LOW_CONFIDENCE_THRESHOLD,
        data_as_of=date.today().isoformat(),
    )
