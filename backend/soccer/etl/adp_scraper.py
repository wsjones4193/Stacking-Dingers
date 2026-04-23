"""
Daily ADP scraper for The World Pup — Underdog Fantasy.

Approach: reverse-engineered Underdog internal API.
  1. POST /api/v3/user_sessions  →  get auth token
  2. GET  /api/v3/contests/<slug>/players  →  player list with ADP

Setup (one-time):
  - Open app.underdogfantasy.com in Chrome DevTools → Network tab
  - Find the XHR calls when browsing The World Pup lobby
  - Confirm the endpoint paths and response shape match below
  - Update PLAYERS_ENDPOINT and the field names in _parse_players() if needed

Credentials: set UNDERDOG_EMAIL and UNDERDOG_PASSWORD in your .env file.
Run manually: python -m backend.soccer.etl.adp_scraper
"""

from __future__ import annotations

import logging
import os
from datetime import date, datetime
from pathlib import Path

import httpx
from sqlmodel import Session, select

from backend.db.deps import get_engine
from backend.soccer.constants import UNDERDOG_API_BASE, UNDERDOG_TOURNAMENT_SLUG
from backend.soccer.db_models import SoccerAdpSnapshot, SoccerPlayer, SoccerPlayerIdMap

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Endpoint config (update these if Underdog changes their API)
# ---------------------------------------------------------------------------

LOGIN_ENDPOINT = f"{UNDERDOG_API_BASE}/api/v3/user_sessions"
PLAYERS_ENDPOINT = f"{UNDERDOG_API_BASE}/api/v3/contest_players"

HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Origin": "https://app.underdogfantasy.com",
    "Referer": "https://app.underdogfantasy.com/",
}


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def _get_auth_token(client: httpx.Client) -> str:
    email = os.environ.get("UNDERDOG_EMAIL")
    password = os.environ.get("UNDERDOG_PASSWORD")
    if not email or not password:
        raise RuntimeError("UNDERDOG_EMAIL and UNDERDOG_PASSWORD must be set in environment")

    resp = client.post(
        LOGIN_ENDPOINT,
        json={"user_session": {"email": email, "password": password}},
        headers=HEADERS,
    )
    resp.raise_for_status()
    data = resp.json()

    # Try common token locations — update key path if Underdog changes response shape
    token = (
        data.get("token")
        or data.get("user_session", {}).get("token")
        or data.get("data", {}).get("token")
    )
    if not token:
        raise RuntimeError(f"Could not find auth token in login response: {list(data.keys())}")

    logger.info("Underdog auth token obtained")
    return token


# ---------------------------------------------------------------------------
# Fetch players + ADP
# ---------------------------------------------------------------------------

def _fetch_players(client: httpx.Client, token: str) -> list[dict]:
    """
    GET the player list for the World Pup contest.
    Returns the raw list of player dicts from the Underdog API.
    """
    resp = client.get(
        PLAYERS_ENDPOINT,
        params={"contest_slug": UNDERDOG_TOURNAMENT_SLUG, "per_page": 500},
        headers={**HEADERS, "Authorization": f"Bearer {token}"},
    )
    resp.raise_for_status()
    data = resp.json()

    # Underdog typically wraps results — try common shapes
    players = (
        data.get("players")
        or data.get("contest_players")
        or data.get("data")
        or data
    )
    if not isinstance(players, list):
        raise RuntimeError(f"Unexpected player response shape: {type(players)}")

    logger.info("Fetched %d players from Underdog", len(players))
    return players


# ---------------------------------------------------------------------------
# Parse + upsert
# ---------------------------------------------------------------------------

def _parse_player(raw: dict) -> dict:
    """
    Extract relevant fields from a raw Underdog player dict.
    Field names below are guesses based on typical Underdog API responses —
    update after inspecting actual XHR response in DevTools.
    """
    return {
        "underdog_id": str(raw.get("id") or raw.get("player_id", "")),
        "name": raw.get("full_name") or raw.get("name", "Unknown"),
        "position": raw.get("position", ""),
        "nationality": raw.get("team") or raw.get("nationality"),
        "adp": raw.get("average_draft_position") or raw.get("adp"),
        "draft_rate": raw.get("draft_rate") or raw.get("ownership_pct"),
        "pick_count": raw.get("draft_count") or raw.get("total_picks"),
        "total_drafts": raw.get("total_drafts") or raw.get("draft_total"),
    }


def _upsert_players_and_snapshots(players_raw: list[dict], session: Session) -> None:
    today = date.today()
    inserted_snapshots = 0
    new_players = 0

    from backend.soccer.constants import UNDERDOG_POSITION_MAP

    for raw in players_raw:
        p = _parse_player(raw)
        if not p["underdog_id"] or not p["name"]:
            continue

        # Normalize position
        position = UNDERDOG_POSITION_MAP.get(p["position"], p["position"])

        # Find or create player record
        player = session.exec(
            select(SoccerPlayer).where(SoccerPlayer.underdog_id == p["underdog_id"])
        ).first()

        if not player:
            player = SoccerPlayer(
                name=p["name"],
                position=position,
                nationality=p["nationality"],
                underdog_id=p["underdog_id"],
                active=True,
            )
            session.add(player)
            session.flush()  # get player_id
            new_players += 1

            # Also create a pending ID map entry for admin to confirm
            id_map = SoccerPlayerIdMap(
                underdog_id=p["underdog_id"],
                underdog_name=p["name"],
                confirmed=False,
            )
            session.add(id_map)

        # Upsert today's ADP snapshot
        existing = session.exec(
            select(SoccerAdpSnapshot)
            .where(SoccerAdpSnapshot.player_id == player.player_id)
            .where(SoccerAdpSnapshot.snapshot_date == today)
        ).first()

        adp_val = float(p["adp"]) if p["adp"] is not None else None
        draft_rate = float(p["draft_rate"]) if p["draft_rate"] is not None else None
        pick_count = int(p["pick_count"]) if p["pick_count"] is not None else None
        total_drafts = int(p["total_drafts"]) if p["total_drafts"] is not None else None

        if existing:
            existing.adp = adp_val
            existing.draft_rate = draft_rate
            existing.pick_count = pick_count
            existing.total_drafts = total_drafts
        else:
            session.add(SoccerAdpSnapshot(
                player_id=player.player_id,
                snapshot_date=today,
                adp=adp_val,
                draft_rate=draft_rate,
                pick_count=pick_count,
                total_drafts=total_drafts,
            ))
            inserted_snapshots += 1

    session.commit()
    logger.info(
        "ADP scrape complete — new players: %d, new snapshots: %d",
        new_players,
        inserted_snapshots,
    )


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run_adp_scrape() -> None:
    """Fetch today's ADP from Underdog and upsert into the database."""
    logger.info("Starting World Pup ADP scrape — %s", date.today().isoformat())

    with httpx.Client(timeout=30) as client:
        token = _get_auth_token(client)
        players_raw = _fetch_players(client, token)

    engine = get_engine()
    with Session(engine) as session:
        _upsert_players_and_snapshots(players_raw, session)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_adp_scrape()
