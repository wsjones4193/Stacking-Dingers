"""
/api/history/modules/* — History Browser module endpoints.

Module 1: Ceiling analysis (peak windows, grinder/peaker quadrants)
Module 2: Stacking analysis (MLB team stacks, positional stacks)
Module 3: Draft structure (first-address, pick sequencing, archetypes)
Module 4: Player combos (2-player and 3-player co-ownership + outcomes)
Module 5: ADP accuracy (projected vs. actual BPCOR)
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session, select

from backend.constants import LOW_CONFIDENCE_THRESHOLD, MIN_SAMPLE_SIZE
from backend.db.deps import get_session
from backend.db.models import (
    AdpSnapshot,
    Draft,
    DraftSequence,
    GroupStanding,
    Pick,
    Player,
    Projection,
    TeamSeasonProfile,
    WeeklyScore,
)
from backend.schemas import (
    AdpAccuracyData,
    CeilingAnalysisData,
    ComboData,
    DataResponse,
    DraftStructureData,
    HistoryModuleSummary,
    StackingData,
)

router = APIRouter()

SessionDep = Annotated[Session, Depends(get_session)]

# Module metadata
MODULES: list[HistoryModuleSummary] = [
    HistoryModuleSummary(
        module_id=1,
        title="Ceiling Analysis",
        headline="Peak 2-week scores predict playoff runs",
        description="Explore peak scoring windows, grinder vs. peaker profiles, and playoff advancement windows.",
    ),
    HistoryModuleSummary(
        module_id=2,
        title="Stacking Analysis",
        headline="MLB team stacks boost ceiling significantly",
        description="How same-team and positional stacks affect tournament advancement rates.",
    ),
    HistoryModuleSummary(
        module_id=3,
        title="Draft Structure",
        headline="P-heavy drafts dominate R2+",
        description="First-address tendencies, pick heatmaps, and archetype outcomes.",
    ),
    HistoryModuleSummary(
        module_id=4,
        title="Player Combos",
        headline="Certain pairs advance at 2× the baseline rate",
        description="2-player and 3-player co-ownership advance rates vs. baseline.",
    ),
    HistoryModuleSummary(
        module_id=5,
        title="ADP Accuracy",
        headline="Top-10 picks consistently outperform ADP",
        description="Which ADP ranges and players most/least lived up to their draft cost.",
    ),
]


# ---------------------------------------------------------------------------
# GET /api/history/modules — dashboard listing
# ---------------------------------------------------------------------------

@router.get("/modules", response_model=DataResponse)
def list_modules():
    return DataResponse(data=MODULES, data_as_of=date.today().isoformat())


# ---------------------------------------------------------------------------
# Common filter extractor
# ---------------------------------------------------------------------------

def _parse_seasons(seasons_str: str) -> list[int]:
    return [int(s.strip()) for s in seasons_str.split(",") if s.strip().isdigit()]


# ---------------------------------------------------------------------------
# Module 1: Ceiling Analysis
# GET /api/history/modules/1?seasons=2022,2023,2024,2025&position=P
# ---------------------------------------------------------------------------

@router.get("/modules/1", response_model=DataResponse)
def module_ceiling(
    session: SessionDep,
    seasons: str = Query(default="2022,2023,2024,2025"),
    position: Optional[str] = Query(default=None),
):
    season_list = _parse_seasons(seasons)

    stmt = select(TeamSeasonProfile, Draft).join(
        Draft, TeamSeasonProfile.draft_id == Draft.draft_id
    ).where(Draft.season.in_(season_list))
    rows = session.exec(stmt).all()

    if not rows:
        return DataResponse(
            data=CeilingAnalysisData(
                peak_histogram=[],
                grinder_peaker_quadrants=[],
                playoff_window_distribution=[],
                sample_size=0,
                low_confidence=True,
            ),
            data_as_of=date.today().isoformat(),
        )

    # Peak histogram: bucket peak_2wk_scores into 25-pt bins
    histogram: dict[str, int] = defaultdict(int)
    quadrants: list[dict] = []

    for profile, draft in rows:
        if not profile.peak_2wk_score:
            continue
        bucket = int(profile.peak_2wk_score // 25) * 25
        histogram[f"{bucket}-{bucket+24}"] += 1

        # Grinder/peaker: high peak + low consistency = peaker; low peak + low std = grinder
        if profile.consistency_score is not None:
            quadrant = (
                "peaker" if profile.peak_2wk_score >= 300 and profile.consistency_score >= 25
                else "grinder" if profile.consistency_score < 15
                else "balanced"
            )
            quadrants.append({
                "draft_id": draft.draft_id,
                "username": draft.username,
                "season": draft.season,
                "peak_2wk_score": profile.peak_2wk_score,
                "consistency_score": profile.consistency_score,
                "ceiling_tier": profile.ceiling_tier,
                "round_reached": profile.round_reached,
                "quadrant": quadrant,
            })

    peak_histogram = [{"range": k, "count": v} for k, v in sorted(histogram.items())]

    # Playoff window distribution: which weeks did peak windows fall in?
    window_dist: dict[str, int] = defaultdict(int)
    for profile, _ in rows:
        if profile.peak_window_weeks_json:
            import json
            weeks = json.loads(profile.peak_window_weeks_json)
            if weeks:
                key = f"W{weeks[0]}-W{weeks[1]}"
                window_dist[key] += 1
    playoff_dist = [{"window": k, "count": v} for k, v in sorted(window_dist.items())]

    sample_size = len(rows)
    return DataResponse(
        data=CeilingAnalysisData(
            peak_histogram=peak_histogram,
            grinder_peaker_quadrants=quadrants,
            playoff_window_distribution=playoff_dist,
            sample_size=sample_size,
            low_confidence=sample_size < LOW_CONFIDENCE_THRESHOLD,
        ),
        sample_size=sample_size,
        low_confidence=sample_size < LOW_CONFIDENCE_THRESHOLD,
        data_as_of=date.today().isoformat(),
    )


# ---------------------------------------------------------------------------
# Module 2: Stacking Analysis
# GET /api/history/modules/2?seasons=2022,2023,2024,2025
# ---------------------------------------------------------------------------

@router.get("/modules/2", response_model=DataResponse)
def module_stacking(
    session: SessionDep,
    seasons: str = Query(default="2022,2023,2024,2025"),
):
    season_list = _parse_seasons(seasons)

    # For each draft, find which MLB teams appear 2+ times on the roster
    drafts = session.exec(
        select(Draft).where(Draft.season.in_(season_list))
    ).all()

    mlb_stack_counts: dict[str, dict] = defaultdict(lambda: {"total": 0, "advanced": 0})
    pos_stack_counts: dict[str, dict] = defaultdict(lambda: {"total": 0, "advanced": 0})

    for draft in drafts:
        standing = session.exec(
            select(GroupStanding)
            .where(GroupStanding.draft_id == draft.draft_id)
            .where(GroupStanding.round_number == 1)
        ).first()
        advanced = standing.advanced if standing else False

        picks = session.exec(
            select(Pick, Player)
            .join(Player, Pick.player_id == Player.player_id)
            .where(Pick.draft_id == draft.draft_id)
        ).all()

        # MLB team stack detection
        team_counts: dict[str, int] = defaultdict(int)
        pos_counts: dict[str, int] = defaultdict(int)
        for pick, player in picks:
            if player.mlb_team:
                team_counts[player.mlb_team] += 1
            pos_counts[player.position] += 1

        for team, cnt in team_counts.items():
            if cnt >= 2:
                key = f"{team}_stack_{cnt}+"
                mlb_stack_counts[key]["total"] += 1
                if advanced:
                    mlb_stack_counts[key]["advanced"] += 1

        # Positional stack: 5+ of a position
        for pos, cnt in pos_counts.items():
            if cnt >= 5:
                key = f"{pos}_heavy_{cnt}+"
                pos_stack_counts[key]["total"] += 1
                if advanced:
                    pos_stack_counts[key]["advanced"] += 1

    total_drafts = len(drafts)
    baseline_advance_rate = 2 / 12  # top-2-of-12

    mlb_stacks = [
        {
            "stack": k,
            "count": v["total"],
            "advance_rate": round(v["advanced"] / v["total"], 3) if v["total"] > 0 else 0,
            "advance_rate_vs_baseline": round(
                v["advanced"] / v["total"] - baseline_advance_rate, 3
            ) if v["total"] > 0 else 0,
            "low_confidence": v["total"] < LOW_CONFIDENCE_THRESHOLD,
        }
        for k, v in sorted(mlb_stack_counts.items(), key=lambda x: -x[1]["total"])
        if v["total"] >= MIN_SAMPLE_SIZE
    ]

    pos_stacks = [
        {
            "stack": k,
            "count": v["total"],
            "advance_rate": round(v["advanced"] / v["total"], 3) if v["total"] > 0 else 0,
            "low_confidence": v["total"] < LOW_CONFIDENCE_THRESHOLD,
        }
        for k, v in sorted(pos_stack_counts.items(), key=lambda x: -x[1]["total"])
        if v["total"] >= MIN_SAMPLE_SIZE
    ]

    sample_size = total_drafts
    return DataResponse(
        data=StackingData(
            mlb_team_stacks=mlb_stacks,
            positional_stacks=pos_stacks,
            combined_effects=[],
            sample_size=sample_size,
            low_confidence=sample_size < LOW_CONFIDENCE_THRESHOLD,
        ),
        sample_size=sample_size,
        low_confidence=sample_size < LOW_CONFIDENCE_THRESHOLD,
        data_as_of=date.today().isoformat(),
    )


# ---------------------------------------------------------------------------
# Module 3: Draft Structure
# GET /api/history/modules/3?seasons=2022,2023,2024,2025
# ---------------------------------------------------------------------------

@router.get("/modules/3", response_model=DataResponse)
def module_draft_structure(
    session: SessionDep,
    seasons: str = Query(default="2022,2023,2024,2025"),
):
    season_list = _parse_seasons(seasons)

    sequences = session.exec(
        select(DraftSequence, Draft)
        .join(Draft, DraftSequence.draft_id == Draft.draft_id)
        .where(Draft.season.in_(season_list))
    ).all()

    # First-address cross-tab: what position was taken first, and advance rate
    first_addr: dict[str, dict] = defaultdict(lambda: {"total": 0, "advanced": 0})
    archetype_outcomes: dict[str, dict] = defaultdict(lambda: {"total": 0, "advanced": 0})
    # Pick heatmap: position × round → count
    heatmap: dict[str, int] = defaultdict(int)

    for seq, draft in sequences:
        if not seq.pick_sequence_json:
            continue
        import json
        picks = json.loads(seq.pick_sequence_json)
        if not picks:
            continue

        advanced = seq.advance_round is not None and seq.advance_round > 1
        first_pos = picks[0]
        first_addr[first_pos]["total"] += 1
        if advanced:
            first_addr[first_pos]["advanced"] += 1

        tag = seq.archetype_tag or "unknown"
        archetype_outcomes[tag]["total"] += 1
        if advanced:
            archetype_outcomes[tag]["advanced"] += 1

        # Heatmap: round = pick_index // 12 + 1 (12-person draft)
        for i, pos in enumerate(picks):
            round_num = i // 12 + 1
            heatmap[f"{pos}_R{round_num}"] += 1

    baseline = 2 / 12

    first_addr_result = [
        {
            "first_pick": pos,
            "total": v["total"],
            "advance_rate": round(v["advanced"] / v["total"], 3) if v["total"] > 0 else 0,
            "vs_baseline": round(v["advanced"] / v["total"] - baseline, 3) if v["total"] > 0 else 0,
            "low_confidence": v["total"] < LOW_CONFIDENCE_THRESHOLD,
        }
        for pos, v in sorted(first_addr.items())
        if v["total"] >= MIN_SAMPLE_SIZE
    ]

    archetype_result = [
        {
            "archetype": tag,
            "total": v["total"],
            "advance_rate": round(v["advanced"] / v["total"], 3) if v["total"] > 0 else 0,
            "vs_baseline": round(v["advanced"] / v["total"] - baseline, 3) if v["total"] > 0 else 0,
            "low_confidence": v["total"] < LOW_CONFIDENCE_THRESHOLD,
        }
        for tag, v in sorted(archetype_outcomes.items())
        if v["total"] >= MIN_SAMPLE_SIZE
    ]

    heatmap_result = [
        {"position_round": k, "count": v}
        for k, v in sorted(heatmap.items())
    ]

    sample_size = len(sequences)
    return DataResponse(
        data=DraftStructureData(
            first_address_crosstab=first_addr_result,
            archetype_outcomes=archetype_result,
            pick_heatmap=heatmap_result,
            sample_size=sample_size,
            low_confidence=sample_size < LOW_CONFIDENCE_THRESHOLD,
        ),
        sample_size=sample_size,
        low_confidence=sample_size < LOW_CONFIDENCE_THRESHOLD,
        data_as_of=date.today().isoformat(),
    )


# ---------------------------------------------------------------------------
# Module 4: Player Combos
# GET /api/history/modules/4?seasons=2022,2023,2024,2025&player_a=123&player_b=456
# ---------------------------------------------------------------------------

@router.get("/modules/4", response_model=DataResponse)
def module_combos(
    session: SessionDep,
    seasons: str = Query(default="2022,2023,2024,2025"),
    player_a: Optional[int] = Query(default=None, description="Search mode: filter by player A"),
    player_b: Optional[int] = Query(default=None, description="Search mode: filter by player B"),
    leaderboard_mode: bool = Query(default=False, description="Return top combos by advance rate delta"),
    limit: int = Query(default=20, le=100),
):
    """
    Co-ownership combos. In leaderboard mode returns top combos.
    In search mode filters by specific player(s).
    """
    season_list = _parse_seasons(seasons)

    drafts = session.exec(
        select(Draft).where(Draft.season.in_(season_list))
    ).all()

    baseline = 2 / 12
    pair_outcomes: dict[tuple[int, int], dict] = defaultdict(
        lambda: {"total": 0, "advanced": 0, "name_a": "", "name_b": ""}
    )

    for draft in drafts:
        standing = session.exec(
            select(GroupStanding)
            .where(GroupStanding.draft_id == draft.draft_id)
            .where(GroupStanding.round_number == 1)
        ).first()
        advanced = standing.advanced if standing else False

        picks = session.exec(
            select(Pick).where(Pick.draft_id == draft.draft_id)
        ).all()
        player_ids = sorted({p.player_id for p in picks})

        # Filter: if player_a specified, only include drafts with player_a
        if player_a and player_a not in player_ids:
            continue
        if player_b and player_b not in player_ids:
            continue

        # Generate pairs
        for i in range(len(player_ids)):
            for j in range(i + 1, len(player_ids)):
                pair = (player_ids[i], player_ids[j])
                pair_outcomes[pair]["total"] += 1
                if advanced:
                    pair_outcomes[pair]["advanced"] += 1

    # Enrich with player names and filter by min sample
    combos: list[dict] = []
    for (pid_a, pid_b), v in pair_outcomes.items():
        if v["total"] < MIN_SAMPLE_SIZE:
            continue
        if player_a and player_a not in (pid_a, pid_b):
            continue
        advance_rate = v["advanced"] / v["total"]
        delta = advance_rate - baseline

        pa = session.get(Player, pid_a)
        pb = session.get(Player, pid_b)

        combos.append({
            "player_a_id": pid_a,
            "player_a_name": pa.name if pa else str(pid_a),
            "player_b_id": pid_b,
            "player_b_name": pb.name if pb else str(pid_b),
            "count": v["total"],
            "advance_rate": round(advance_rate, 3),
            "advance_rate_delta": round(delta, 3),
            "low_confidence": v["total"] < LOW_CONFIDENCE_THRESHOLD,
        })

    if leaderboard_mode:
        combos.sort(key=lambda x: x["advance_rate_delta"], reverse=True)
    else:
        combos.sort(key=lambda x: x["count"], reverse=True)

    combos = combos[:limit]
    sample_size = len(combos)

    return DataResponse(
        data=ComboData(
            combos=combos,
            sample_size=sample_size,
            low_confidence=sample_size < LOW_CONFIDENCE_THRESHOLD,
        ),
        sample_size=sample_size,
        low_confidence=sample_size < LOW_CONFIDENCE_THRESHOLD,
        data_as_of=date.today().isoformat(),
    )


# ---------------------------------------------------------------------------
# Module 5: ADP Accuracy
# GET /api/history/modules/5?seasons=2022,2023,2024,2025&position=P
# ---------------------------------------------------------------------------

@router.get("/modules/5", response_model=DataResponse)
def module_adp_accuracy(
    session: SessionDep,
    seasons: str = Query(default="2022,2023,2024,2025"),
    position: Optional[str] = Query(default=None),
):
    """ADP vs. actual BPCOR — over- and under-performers by position and ADP range."""
    season_list = _parse_seasons(seasons)

    stmt = select(Player).where(Player.active == True)  # noqa: E712
    if position:
        stmt = stmt.where(Player.position == position.upper())
    players = session.exec(stmt).all()

    results: list[dict] = []

    for p in players:
        for season in season_list:
            canonical = session.exec(
                select(AdpSnapshot)
                .where(AdpSnapshot.player_id == p.player_id)
                .where(AdpSnapshot.season == season)
                .order_by(AdpSnapshot.snapshot_date)
                .limit(1)
            ).first()
            if not canonical or not canonical.adp:
                continue

            ws_rows = session.exec(
                select(WeeklyScore)
                .where(WeeklyScore.player_id == p.player_id)
                .where(WeeklyScore.season == season)
            ).all()
            actual_bpcor = sum(
                w.calculated_score for w in ws_rows if w.is_starter or w.is_flex
            )

            proj = session.exec(
                select(Projection)
                .where(Projection.player_id == p.player_id)
                .where(Projection.season == season)
                .where(Projection.is_canonical == True)  # noqa: E712
                .limit(1)
            ).first()
            projected_points = proj.projected_points if proj else None

            if actual_bpcor > 0 or projected_points:
                results.append({
                    "player_id": p.player_id,
                    "name": p.name,
                    "position": p.position,
                    "season": season,
                    "opening_adp": canonical.adp,
                    "actual_bpcor": round(actual_bpcor, 2),
                    "projected_points": projected_points,
                    "delta": round(actual_bpcor - (projected_points or 0), 2),
                })

    overperformers = sorted(
        [r for r in results if r["delta"] > 0], key=lambda x: -x["delta"]
    )[:20]
    underperformers = sorted(
        [r for r in results if r["delta"] < 0], key=lambda x: x["delta"]
    )[:20]

    # By position summary
    by_pos: dict[str, list[float]] = defaultdict(list)
    for r in results:
        by_pos[r["position"]].append(r["delta"])
    by_position = [
        {
            "position": pos,
            "avg_delta": round(sum(deltas) / len(deltas), 2),
            "count": len(deltas),
            "low_confidence": len(deltas) < LOW_CONFIDENCE_THRESHOLD,
        }
        for pos, deltas in by_pos.items()
    ]

    sample_size = len(results)
    return DataResponse(
        data=AdpAccuracyData(
            overperformers=overperformers,
            underperformers=underperformers,
            by_position=by_position,
            sample_size=sample_size,
            low_confidence=sample_size < LOW_CONFIDENCE_THRESHOLD,
        ),
        sample_size=sample_size,
        low_confidence=sample_size < LOW_CONFIDENCE_THRESHOLD,
        data_as_of=date.today().isoformat(),
    )
