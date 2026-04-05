"""
/api/teams/* — team search and detail endpoints.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from backend.constants import ROUND_CONFIG, WEEK_MAP_2026
from backend.db.deps import get_session
from backend.db.models import (
    Draft,
    GroupStanding,
    Pick,
    Player,
    RosterFlag,
    TeamSeasonProfile,
    WeeklyScore,
)
from backend.schemas import (
    DataResponse,
    RosterEntry,
    TeamDetail,
    TeamSummary,
    WeeklyBreakdown,
)

router = APIRouter()

SessionDep = Annotated[Session, Depends(get_session)]

# Shared filter params
def common_filters(
    season: int = Query(default=2026),
    draft_date_from: Optional[date] = Query(default=None),
    draft_date_to: Optional[date] = Query(default=None),
    draft_position: Optional[int] = Query(default=None, ge=1, le=12),
    entry_type: Optional[str] = Query(default=None),
) -> dict:
    return {
        "season": season,
        "draft_date_from": draft_date_from,
        "draft_date_to": draft_date_to,
        "draft_position": draft_position,
        "entry_type": entry_type,
    }


def _build_team_summary(
    draft: Draft,
    profile: Optional[TeamSeasonProfile],
    standing: Optional[GroupStanding],
    group_standings: list[GroupStanding],
    flags: list[RosterFlag],
) -> TeamSummary:
    """Assemble a TeamSummary from raw DB rows."""
    total_points = standing.total_points if standing else 0.0
    rank = standing.rank if standing else None
    round_reached = profile.round_reached if profile else None

    # Gap to advance: points needed to reach the next advance cutoff
    gap_to_advance = None
    if standing and group_standings and rank and rank > 2:
        sorted_pts = sorted(
            [gs.total_points for gs in group_standings], reverse=True
        )
        cutoff_idx = ROUND_CONFIG[1]["advance"] - 1  # 0-based index of last advancer
        if cutoff_idx < len(sorted_pts):
            gap_to_advance = round(sorted_pts[cutoff_idx] - total_points, 2)

    # Roster hole badges from flags
    badge_map = {
        "position_wiped": "Position wiped",
        "ghost_player": "Ghost player",
        "below_replacement": "Below replacement",
        "pitcher_trending_wrong": "Pitcher struggling",
        "hitter_usage_decline": "Hitter usage drop",
    }
    hole_badges = list({badge_map.get(f.flag_type, f.flag_type) for f in flags})

    return TeamSummary(
        draft_id=draft.draft_id,
        username=draft.username,
        season=draft.season,
        draft_date=draft.draft_date,
        draft_position=draft.draft_position,
        round_reached=round_reached,
        group_rank=rank,
        total_points=total_points,
        gap_to_advance=gap_to_advance,
        roster_strength_score=None,      # computed separately if needed
        advancement_probability=None,    # placeholder — use advancement service
        roster_hole_badges=hole_badges,
    )


# ---------------------------------------------------------------------------
# GET /api/teams/search?username=foo&season=2026&page=1
# ---------------------------------------------------------------------------

@router.get("/search", response_model=DataResponse)
def search_teams(
    session: SessionDep,
    username: str = Query(..., min_length=1),
    season: int = Query(default=2026),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, le=50),
):
    """Return paginated list of teams for a given Underdog username."""
    drafts = session.exec(
        select(Draft)
        .where(Draft.username == username)
        .where(Draft.season == season)
        .order_by(Draft.draft_date.desc())
    ).all()

    if not drafts:
        return DataResponse(data=[], data_as_of=date.today().isoformat())

    # Paginate
    start = (page - 1) * page_size
    page_drafts = drafts[start : start + page_size]

    summaries = []
    for draft in page_drafts:
        profile = session.exec(
            select(TeamSeasonProfile)
            .where(TeamSeasonProfile.draft_id == draft.draft_id)
        ).first()
        standing = session.exec(
            select(GroupStanding)
            .where(GroupStanding.draft_id == draft.draft_id)
            .where(GroupStanding.round_number == 1)
        ).first()
        group_standings = []
        if standing:
            group_standings = session.exec(
                select(GroupStanding)
                .where(GroupStanding.group_id == standing.group_id)
                .where(GroupStanding.round_number == 1)
            ).all()

        active_flags = session.exec(
            select(RosterFlag)
            .where(RosterFlag.draft_id == draft.draft_id)
            .where(RosterFlag.season == season)
        ).all()
        summaries.append(
            _build_team_summary(draft, profile, standing, group_standings, active_flags)
        )

    return DataResponse(
        data={
            "teams": summaries,
            "total": len(drafts),
            "page": page,
            "page_size": page_size,
        },
        data_as_of=date.today().isoformat(),
    )


# ---------------------------------------------------------------------------
# GET /api/teams/{draft_id}
# ---------------------------------------------------------------------------

@router.get("/{draft_id}", response_model=DataResponse)
def get_team(
    draft_id: str,
    session: SessionDep,
    season: int = Query(default=2026),
):
    """Full team detail: roster, weekly scores, group standings, flags."""
    draft = session.get(Draft, draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Team not found")

    profile = session.exec(
        select(TeamSeasonProfile).where(TeamSeasonProfile.draft_id == draft_id)
    ).first()

    # Group standings
    standing = session.exec(
        select(GroupStanding)
        .where(GroupStanding.draft_id == draft_id)
        .where(GroupStanding.round_number == 1)
    ).first()

    group_standings_rows: list[dict] = []
    if standing:
        gs_all = session.exec(
            select(GroupStanding, Draft)
            .join(Draft, GroupStanding.draft_id == Draft.draft_id)
            .where(GroupStanding.group_id == standing.group_id)
            .where(GroupStanding.round_number == 1)
            .order_by(GroupStanding.rank)
        ).all()
        for gs, d in gs_all:
            group_standings_rows.append({
                "draft_id": gs.draft_id,
                "username": d.username,
                "total_points": gs.total_points,
                "rank": gs.rank,
                "advanced": gs.advanced,
            })

    # Roster
    picks = session.exec(
        select(Pick).where(Pick.draft_id == draft_id)
    ).all()

    roster_flags = session.exec(
        select(RosterFlag)
        .where(RosterFlag.draft_id == draft_id)
        .where(RosterFlag.season == season)
    ).all()

    flags_by_player: dict[int, list[str]] = {}
    for f in roster_flags:
        if f.player_id:
            flags_by_player.setdefault(f.player_id, []).append(f.flag_type)

    roster: list[RosterEntry] = []
    for pick in picks:
        player = session.get(Player, pick.player_id)
        if not player:
            continue

        # Last week score
        all_player_ws = session.exec(
            select(WeeklyScore)
            .where(WeeklyScore.draft_id == draft_id)
            .where(WeeklyScore.player_id == pick.player_id)
            .where(WeeklyScore.season == season)
        ).all()
        season_total = sum(
            w.calculated_score for w in all_player_ws if w.is_starter or w.is_flex
        )
        latest_week = max((w.week_number for w in all_player_ws), default=None)
        last_week_score = next(
            (w.calculated_score for w in all_player_ws if w.week_number == latest_week),
            None,
        )

        roster.append(RosterEntry(
            player_id=player.player_id,
            name=player.name,
            position=player.position,
            mlb_team=player.mlb_team,
            last_week_score=last_week_score,
            season_total=round(season_total, 2),
            season_bpcor=None,
            il_status=False,
            flags=flags_by_player.get(pick.player_id, []),
        ))

    # Weekly breakdowns
    weekly_breakdowns: list[WeeklyBreakdown] = []
    completed_weeks = [
        w for w, (_, end_date, _) in WEEK_MAP_2026.items() if end_date < date.today()
    ]

    for week_num in sorted(completed_weeks):
        week_ws = session.exec(
            select(WeeklyScore, Player)
            .join(Player, WeeklyScore.player_id == Player.player_id)
            .where(WeeklyScore.draft_id == draft_id)
            .where(WeeklyScore.week_number == week_num)
            .where(WeeklyScore.season == season)
        ).all()

        if not week_ws:
            continue

        starters, flex_entry, bench_list = [], None, []
        total_score = 0.0

        for ws, p in week_ws:
            entry = {
                "player_id": p.player_id,
                "name": p.name,
                "position": p.position,
                "score": ws.calculated_score,
                "slot": "starter" if ws.is_starter else ("flex" if ws.is_flex else "bench"),
            }
            if ws.is_starter:
                starters.append(entry)
                total_score += ws.calculated_score
            elif ws.is_flex:
                flex_entry = entry
                total_score += ws.calculated_score
            else:
                bench_list.append(entry)

        bench_list.sort(key=lambda x: x["score"], reverse=True)
        highlight = bench_list[0] if bench_list else None

        weekly_breakdowns.append(WeeklyBreakdown(
            week_number=week_num,
            starters=starters,
            flex=flex_entry,
            bench=bench_list,
            total_score=round(total_score, 2),
            left_on_bench_highlight=highlight,
        ))

    total_pts = sum(wb.total_score for wb in weekly_breakdowns)

    flags_for_response = [
        {
            "player_id": f.player_id,
            "flag_type": f.flag_type,
            "flag_reason": f.flag_reason,
            "week": f.week_number,
        }
        for f in roster_flags
    ]

    team_detail = TeamDetail(
        draft_id=draft.draft_id,
        username=draft.username,
        season=draft.season,
        draft_date=draft.draft_date,
        draft_position=draft.draft_position,
        round_reached=profile.round_reached if profile else None,
        total_points=round(total_pts, 2),
        group_standings=group_standings_rows,
        roster=roster,
        weekly_breakdowns=weekly_breakdowns,
        roster_flags=flags_for_response,
        gap_to_advance=None,
        advancement_probability=None,
    )

    return DataResponse(data=team_detail, data_as_of=date.today().isoformat())
