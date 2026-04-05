"""
Fangraphs projection ingestion (Steamer + ATC).

Downloads preseason and rest-of-season (RoS) projection CSVs from Fangraphs
and stores them in the projections table.

Projection sources:
  - steamer     : preseason Steamer projections
  - steamer_ros : Steamer rest-of-season (in-season updates)
  - atc         : preseason ATC projections
  - atc_ros     : ATC rest-of-season

The final snapshot captured on/before Opening Day is tagged is_canonical=True
and used for all ADP value calculations (projected BPCOR at ADP slot).

In-season RoS projections are updated nightly to power the "rest of season
outlook" on player pages and the mid-season BPCOR value blend.
"""

from __future__ import annotations

import logging
from datetime import date
from io import StringIO
from pathlib import Path
from typing import Optional

import httpx
import pandas as pd
from sqlmodel import Session, select

from backend.db.models import Player, Projection

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Fangraphs CSV download URLs
# Fangraphs allows direct CSV export from their projections pages.
# These are the standard export URLs — they return CSVs directly.
# ---------------------------------------------------------------------------

FANGRAPHS_URLS = {
    "steamer_hitters": "https://www.fangraphs.com/api/projections?type=steamer&stats=bat&pos=all&team=0&players=0&lg=all&z=1&csv=1",
    "steamer_pitchers": "https://www.fangraphs.com/api/projections?type=steamer&stats=pit&pos=all&team=0&players=0&lg=all&z=1&csv=1",
    "steamer_ros_hitters": "https://www.fangraphs.com/api/projections?type=steamerr&stats=bat&pos=all&team=0&players=0&lg=all&z=1&csv=1",
    "steamer_ros_pitchers": "https://www.fangraphs.com/api/projections?type=steamerr&stats=pit&pos=all&team=0&players=0&lg=all&z=1&csv=1",
    "atc_hitters": "https://www.fangraphs.com/api/projections?type=atc&stats=bat&pos=all&team=0&players=0&lg=all&z=1&csv=1",
    "atc_pitchers": "https://www.fangraphs.com/api/projections?type=atc&stats=pit&pos=all&team=0&players=0&lg=all&z=1&csv=1",
}

# Fangraphs column names we care about
HITTER_PROJ_COLS = {"playerid", "Name", "PA", "G"}
PITCHER_PROJ_COLS = {"playerid", "Name", "IP", "G", "GS"}

# Opening Day 2026 — projections captured on or before this date are canonical
OPENING_DAY_2026 = date(2026, 3, 25)


# ---------------------------------------------------------------------------
# Download helper
# ---------------------------------------------------------------------------

def download_fangraphs_csv(url: str, timeout: int = 30) -> Optional[pd.DataFrame]:
    """Download a Fangraphs projection CSV and return as DataFrame."""
    try:
        response = httpx.get(url, timeout=timeout, follow_redirects=True)
        response.raise_for_status()
        return pd.read_csv(StringIO(response.text))
    except Exception as e:
        logger.error(f"Failed to download Fangraphs projection from {url}: {e}")
        return None


# ---------------------------------------------------------------------------
# Projected points calculation from projection stats
# ---------------------------------------------------------------------------

def project_hitter_points(row: dict) -> float:
    """
    Estimate best ball points from projected counting stats.
    Uses the same scoring weights as actual scoring.
    """
    from backend.services.scoring import score_hitter_row

    # Fangraphs gives H, 2B, 3B, HR directly
    proj_row = {
        "h": float(row.get("H", 0)),
        "doubles": float(row.get("2B", 0)),
        "triples": float(row.get("3B", 0)),
        "home_runs": float(row.get("HR", 0)),
        "rbi": float(row.get("RBI", 0)),
        "runs": float(row.get("R", 0)),
        "stolen_bases": float(row.get("SB", 0)),
        "walks": float(row.get("BB", 0)),
        "hit_by_pitch": float(row.get("HBP", 0)),
    }
    return score_hitter_row(proj_row)


def project_pitcher_points(row: dict) -> float:
    """
    Estimate best ball points from projected pitching stats.
    QS is not directly projected — estimate from GS, IP/GS, and ERA/ER.
    """
    ip = float(row.get("IP", 0))
    er = float(row.get("ER", 0))
    k = float(row.get("SO", row.get("K", 0)))
    w = float(row.get("W", 0))

    # Estimate QS: starts where projected IP/GS >= 6 and ER/GS <= 3
    gs = float(row.get("GS", 1)) or 1
    ip_per_gs = ip / gs
    er_per_gs = er / gs
    # Fraction of starts expected to qualify as QS
    qs_rate = 1.0 if (ip_per_gs >= 6.0 and er_per_gs <= 3.0) else (
        0.5 if ip_per_gs >= 5.5 else 0.0
    )
    projected_qs = gs * qs_rate

    from backend.constants import PITCHER_SCORING
    from backend.services.scoring import ip_to_true_innings

    return round(
        ip_to_true_innings(ip) * PITCHER_SCORING["inning_pitched"]
        + k * PITCHER_SCORING["strikeout"]
        + w * PITCHER_SCORING["win"]
        + projected_qs * PITCHER_SCORING["quality_start"]
        + er * PITCHER_SCORING["earned_run"],
        2,
    )


# ---------------------------------------------------------------------------
# Ingest one projection set
# ---------------------------------------------------------------------------

def ingest_projection_csv(
    df: pd.DataFrame,
    source: str,          # "steamer", "steamer_ros", "atc", "atc_ros"
    stat_type: str,       # "hitting" or "pitching"
    season: int,
    captured_date: date,
    session: Session,
    player_fangraphs_to_underdog: dict[str, int],  # {fangraphs_playerid: internal player_id}
    opening_day: date = OPENING_DAY_2026,
) -> dict:
    """
    Parse a Fangraphs projection DataFrame and insert/update projection rows.
    """
    is_canonical = captured_date <= opening_day and "ros" not in source
    inserted = 0
    skipped = 0

    for _, row in df.iterrows():
        fg_id = str(row.get("playerid", ""))
        internal_id = player_fangraphs_to_underdog.get(fg_id)
        if internal_id is None:
            skipped += 1
            continue

        if stat_type == "hitting":
            proj_points = project_hitter_points(row.to_dict())
            proj_pa = float(row.get("PA", 0))
            proj_ip = None
        else:
            proj_points = project_pitcher_points(row.to_dict())
            proj_pa = None
            proj_ip = float(row.get("IP", 0))

        # Delete existing entry for same player/season/source/date before inserting
        stmt = (
            select(Projection)
            .where(Projection.player_id == internal_id)
            .where(Projection.season == season)
            .where(Projection.source == source)
            .where(Projection.captured_date == captured_date)
        )
        existing = session.exec(stmt).first()
        if existing:
            session.delete(existing)

        proj = Projection(
            player_id=internal_id,
            season=season,
            source=source,
            captured_date=captured_date,
            is_canonical=is_canonical,
            projected_points=proj_points,
            projected_pa=proj_pa,
            projected_ip=proj_ip,
        )
        session.add(proj)
        inserted += 1

    session.commit()
    return {"source": source, "inserted": inserted, "skipped_no_mapping": skipped}


# ---------------------------------------------------------------------------
# Full nightly projection refresh
# ---------------------------------------------------------------------------

def refresh_projections(
    season: int,
    session: Session,
    player_fangraphs_to_underdog: dict[str, int],
    is_preseason: bool = False,
) -> list[dict]:
    """
    Download and ingest all projection sources for a given day.
    Call nightly during preseason (all 4 sources) and in-season (RoS only).
    """
    today = date.today()
    results = []

    sources_to_fetch = [
        ("steamer_hitters", "steamer", "hitting"),
        ("steamer_pitchers", "steamer", "pitching"),
        ("atc_hitters", "atc", "hitting"),
        ("atc_pitchers", "atc", "pitching"),
    ] if is_preseason else [
        ("steamer_ros_hitters", "steamer_ros", "hitting"),
        ("steamer_ros_pitchers", "steamer_ros", "pitching"),
    ]

    for url_key, source, stat_type in sources_to_fetch:
        url = FANGRAPHS_URLS[url_key]
        df = download_fangraphs_csv(url)
        if df is None:
            logger.warning(f"Skipping {source} ({stat_type}) — download failed")
            continue

        result = ingest_projection_csv(
            df, source, stat_type, season, today, session, player_fangraphs_to_underdog
        )
        results.append(result)
        logger.info(f"Projection ingest: {result}")

    return results
