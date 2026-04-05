"""
Player ID mapping: Underdog player IDs ↔ MLB Stats API player IDs.

Underdog is the authoritative player pool. This module:
1. Fuzzy-matches Underdog names against MLB Stats API names at ingest time
2. Stores results in the player_id_map table (confirmed=False for auto-matches)
3. Exposes helpers for the admin review page to confirm/correct mappings

Unmatched Underdog players are left in all draft data but show N/A
for any field that requires MLB game log data.
"""

from __future__ import annotations

from typing import Optional

from rapidfuzz import fuzz, process
from sqlmodel import Session, select

from backend.db.models import PlayerIdMap


# ---------------------------------------------------------------------------
# Auto-match logic
# ---------------------------------------------------------------------------

def fuzzy_match_name(
    underdog_name: str,
    mlb_candidates: list[tuple[int, str]],  # list of (mlb_id, mlb_name)
    score_cutoff: float = 85.0,
) -> Optional[tuple[int, str, float]]:
    """
    Attempt to match an Underdog player name to an MLB Stats API name.

    Returns (mlb_id, mlb_name, match_score) if a match is found above the
    cutoff, otherwise None.

    Uses token_sort_ratio to handle name order variations (e.g. "Shohei Ohtani"
    vs "Ohtani, Shohei").
    """
    if not mlb_candidates:
        return None

    names_only = [name for _, name in mlb_candidates]
    result = process.extractOne(
        underdog_name,
        names_only,
        scorer=fuzz.token_sort_ratio,
        score_cutoff=score_cutoff,
    )
    if result is None:
        return None

    matched_name, score, idx = result
    mlb_id = mlb_candidates[idx][0]
    return mlb_id, matched_name, float(score)


def build_mappings_for_season(
    session: Session,
    underdog_players: list[tuple[str, str]],   # [(underdog_id, underdog_name), ...]
    mlb_players: list[tuple[int, str]],         # [(mlb_id, mlb_name), ...]
    season: int,
    score_cutoff: float = 85.0,
) -> dict[str, list[str]]:
    """
    Attempt to auto-match all Underdog players for a season.
    Writes results to player_id_map. Skips players already mapped for this season.

    Returns a summary: {"matched": [...names], "unmatched": [...names]}
    """
    existing_stmt = select(PlayerIdMap).where(PlayerIdMap.season == season)
    existing = {row.underdog_id for row in session.exec(existing_stmt).all()}

    matched: list[str] = []
    unmatched: list[str] = []

    for underdog_id, underdog_name in underdog_players:
        if underdog_id in existing:
            continue

        result = fuzzy_match_name(underdog_name, mlb_players, score_cutoff)

        if result:
            mlb_id, mlb_name, score = result
            mapping = PlayerIdMap(
                underdog_id=underdog_id,
                underdog_name=underdog_name,
                mlb_id=mlb_id,
                mlb_name=mlb_name,
                confirmed=False,
                match_score=score,
                season=season,
            )
            matched.append(underdog_name)
        else:
            mapping = PlayerIdMap(
                underdog_id=underdog_id,
                underdog_name=underdog_name,
                mlb_id=None,
                mlb_name=None,
                confirmed=False,
                match_score=None,
                season=season,
                notes="No match found — needs manual review",
            )
            unmatched.append(underdog_name)

        session.add(mapping)

    session.commit()
    return {"matched": matched, "unmatched": unmatched}


# ---------------------------------------------------------------------------
# Lookup helpers
# ---------------------------------------------------------------------------

def get_mlb_id(session: Session, underdog_id: str, season: int) -> Optional[int]:
    """
    Return the confirmed (or best auto-matched) MLB ID for an Underdog player.
    Returns None if no mapping exists or player is unmatched.
    """
    stmt = (
        select(PlayerIdMap)
        .where(PlayerIdMap.underdog_id == underdog_id)
        .where(PlayerIdMap.season == season)
        .where(PlayerIdMap.mlb_id.is_not(None))
        .order_by(PlayerIdMap.confirmed.desc(), PlayerIdMap.match_score.desc())
    )
    result = session.exec(stmt).first()
    return result.mlb_id if result else None


def get_unconfirmed_mappings(
    session: Session, season: Optional[int] = None
) -> list[PlayerIdMap]:
    """Return all auto-matched (unconfirmed) mappings, optionally filtered by season."""
    stmt = select(PlayerIdMap).where(PlayerIdMap.confirmed == False)  # noqa: E712
    if season is not None:
        stmt = stmt.where(PlayerIdMap.season == season)
    stmt = stmt.order_by(PlayerIdMap.match_score.asc())   # lowest confidence first
    return list(session.exec(stmt).all())


def get_unmatched_players(
    session: Session, season: Optional[int] = None
) -> list[PlayerIdMap]:
    """Return all Underdog players with no MLB match found."""
    stmt = select(PlayerIdMap).where(PlayerIdMap.mlb_id.is_(None))
    if season is not None:
        stmt = stmt.where(PlayerIdMap.season == season)
    return list(session.exec(stmt).all())


def confirm_mapping(
    session: Session,
    underdog_id: str,
    season: int,
    mlb_id: int,
    mlb_name: str,
) -> PlayerIdMap:
    """Admin action: confirm or correct a mapping."""
    stmt = (
        select(PlayerIdMap)
        .where(PlayerIdMap.underdog_id == underdog_id)
        .where(PlayerIdMap.season == season)
    )
    mapping = session.exec(stmt).first()
    if mapping is None:
        raise ValueError(f"No mapping found for underdog_id={underdog_id} season={season}")

    mapping.mlb_id = mlb_id
    mapping.mlb_name = mlb_name
    mapping.confirmed = True
    mapping.notes = None
    session.add(mapping)
    session.commit()
    session.refresh(mapping)
    return mapping


def add_manual_mapping(
    session: Session,
    underdog_id: str,
    underdog_name: str,
    mlb_id: int,
    mlb_name: str,
    season: int,
) -> PlayerIdMap:
    """Admin action: manually add a mapping that auto-match missed."""
    mapping = PlayerIdMap(
        underdog_id=underdog_id,
        underdog_name=underdog_name,
        mlb_id=mlb_id,
        mlb_name=mlb_name,
        confirmed=True,
        match_score=100.0,
        season=season,
        notes="Manually added",
    )
    session.add(mapping)
    session.commit()
    session.refresh(mapping)
    return mapping
