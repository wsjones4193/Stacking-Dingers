"""
Underdog CSV ingestion.

Loads pick-by-pick draft data from Underdog CSV exports into SQLite.
One-time load per season (CSVs are published once per tournament by Underdog).

Expected CSV columns (Underdog may vary slightly by year — normalized here):
  draft_id, pick_number, round_number, player_id (underdog), player_name,
  username, draft_date, entry_type, draft_position (seat 1–12)

Historical data integrity: advance rates are recalculated independently
as top-2-of-12 for all seasons, ignoring any wildcard logic in original data.
"""

from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Optional

import pandas as pd
from sqlmodel import Session, select

from backend.db.models import Draft, Pick, Player, create_db_and_tables
from backend.db.player_mapping import build_mappings_for_season

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Column name normalization (handles variation across Underdog CSV formats)
# ---------------------------------------------------------------------------

# Maps possible CSV column names → canonical internal names
COLUMN_ALIASES = {
    # draft_id
    "draft_id": "draft_id",
    "draftId": "draft_id",

    # pick_number
    "pick_number": "pick_number",
    "pickNumber": "pick_number",
    "pick": "pick_number",

    # round_number
    "round_number": "round_number",
    "roundNumber": "round_number",
    "round": "round_number",

    # player underdog ID
    "player_id": "underdog_player_id",
    "playerId": "underdog_player_id",
    "underdog_player_id": "underdog_player_id",

    # player name
    "player_name": "player_name",
    "playerName": "player_name",
    "name": "player_name",

    # username
    "username": "username",
    "user_name": "username",
    "userName": "username",

    # draft date
    "draft_date": "draft_date",
    "draftDate": "draft_date",
    "date": "draft_date",

    # entry / contest type
    "entry_type": "entry_type",
    "entryType": "entry_type",
    "contest": "entry_type",
    "tournament": "entry_type",

    # draft seat position
    "draft_position": "draft_position",
    "draftPosition": "draft_position",
    "pick_position": "draft_position",
    "seat": "draft_position",

    # position (P/IF/OF)
    "position": "position",

    # Underdog's ADP at time of draft (preserved for time-series ADP calculation)
    "projection_adp": "projection_adp",
    "projectionAdp": "projection_adp",
    "adp": "projection_adp",
}


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Rename CSV columns to canonical internal names."""
    rename_map = {}
    for col in df.columns:
        canonical = COLUMN_ALIASES.get(col) or COLUMN_ALIASES.get(col.lower())
        if canonical:
            rename_map[col] = canonical
    return df.rename(columns=rename_map)


# ---------------------------------------------------------------------------
# CSV loading
# ---------------------------------------------------------------------------

def load_underdog_csv(csv_path: str | Path, season: int) -> pd.DataFrame:
    """
    Load and normalize a single Underdog draft CSV.
    Returns a cleaned DataFrame with canonical column names.
    """
    df = pd.read_csv(csv_path, dtype=str)
    df = normalize_columns(df)
    df["season"] = season

    required = ["draft_id", "pick_number", "underdog_player_id", "player_name", "username"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"CSV at {csv_path} is missing required columns: {missing}")

    # Coerce types
    df["pick_number"] = pd.to_numeric(df["pick_number"], errors="coerce").fillna(0).astype(int)
    df["round_number"] = pd.to_numeric(df.get("round_number", 0), errors="coerce").fillna(0).astype(int)
    df["draft_position"] = pd.to_numeric(df.get("draft_position", 1), errors="coerce").fillna(1).astype(int)
    df["draft_date"] = pd.to_datetime(df.get("draft_date", pd.NaT), errors="coerce").dt.date

    return df


# ---------------------------------------------------------------------------
# Player upsert
# ---------------------------------------------------------------------------

def upsert_players_from_csv(
    df: pd.DataFrame,
    session: Session,
) -> dict[str, int]:
    """
    Ensure all players in the CSV exist in the players table.
    Returns a mapping of {underdog_player_id: player_id}.
    """
    id_map: dict[str, int] = {}

    for _, row in df.drop_duplicates("underdog_player_id").iterrows():
        underdog_id = str(row["underdog_player_id"])
        name = str(row.get("player_name", ""))
        position = str(row.get("position", "")).upper() if "position" in row else None

        stmt = select(Player).where(Player.underdog_id == underdog_id)
        player = session.exec(stmt).first()

        if player is None:
            player = Player(
                name=name,
                position=position or "IF",   # default; corrected by mapping or manual review
                underdog_id=underdog_id,
            )
            session.add(player)
            session.flush()  # get the auto-assigned player_id

        id_map[underdog_id] = player.player_id

    session.commit()
    return id_map


# ---------------------------------------------------------------------------
# Draft and pick ingestion
# ---------------------------------------------------------------------------

def ingest_season_csv(
    csv_path: str | Path,
    season: int,
    session: Session,
    mlb_player_list: Optional[list[tuple[int, str]]] = None,
    skip_existing: bool = True,
) -> dict:
    """
    Full ingestion pipeline for one season's Underdog CSV:
    1. Load + normalize CSV
    2. Upsert players
    3. Run player ID auto-matching (if mlb_player_list provided)
    4. Insert drafts and picks (skip if already present and skip_existing=True)

    Returns a summary dict.
    """
    df = load_underdog_csv(csv_path, season)
    logger.info(f"Loaded {len(df)} rows from {csv_path}")

    # Upsert players
    player_id_map = upsert_players_from_csv(df, session)

    # Auto-match player IDs if MLB player list provided
    mapping_summary = {"matched": [], "unmatched": []}
    if mlb_player_list:
        underdog_players = [
            (str(row["underdog_player_id"]), str(row.get("player_name", "")))
            for _, row in df.drop_duplicates("underdog_player_id").iterrows()
        ]
        mapping_summary = build_mappings_for_season(
            session, underdog_players, mlb_player_list, season
        )

    # Group by draft
    drafts_inserted = 0
    picks_inserted = 0
    drafts_skipped = 0

    for draft_id, draft_df in df.groupby("draft_id"):
        draft_id = str(draft_id)

        if skip_existing:
            existing = session.exec(select(Draft).where(Draft.draft_id == draft_id)).first()
            if existing:
                drafts_skipped += 1
                continue

        first_row = draft_df.iloc[0]

        draft = Draft(
            draft_id=draft_id,
            season=season,
            draft_date=first_row.get("draft_date"),
            entry_type=str(first_row.get("entry_type", "")) or None,
            username=str(first_row.get("username", "")),
            draft_position=int(first_row.get("draft_position", 1)),
        )
        session.add(draft)

        for _, pick_row in draft_df.iterrows():
            underdog_player_id = str(pick_row["underdog_player_id"])
            internal_player_id = player_id_map.get(underdog_player_id)
            if internal_player_id is None:
                logger.warning(f"No internal player_id for underdog_id={underdog_player_id}")
                continue

            proj_adp_raw = pick_row.get("projection_adp")
            try:
                proj_adp = float(proj_adp_raw) if proj_adp_raw not in (None, "", "nan") else None
            except (ValueError, TypeError):
                proj_adp = None

            pick = Pick(
                draft_id=draft_id,
                pick_number=int(pick_row["pick_number"]),
                round_number=int(pick_row.get("round_number", 0)),
                player_id=internal_player_id,
                username=str(pick_row.get("username", "")),
                projection_adp=proj_adp,
            )
            session.add(pick)
            picks_inserted += 1

        drafts_inserted += 1

    session.commit()

    return {
        "season": season,
        "rows_in_csv": len(df),
        "drafts_inserted": drafts_inserted,
        "drafts_skipped": drafts_skipped,
        "picks_inserted": picks_inserted,
        "players_auto_matched": len(mapping_summary["matched"]),
        "players_unmatched": len(mapping_summary["unmatched"]),
    }


# ---------------------------------------------------------------------------
# Historical seasons bulk load
# ---------------------------------------------------------------------------

HISTORICAL_SEASON_URLS = {
    2025: "https://underdognetwork.com/baseball/analysis/mlb-best-ball-downloadable-pick-by-pick-data",
    2024: "https://underdognetwork.com/baseball/analysis/the-dinger-2024-downloadable-pick-by-pick-data",
    2023: "https://underdognetwork.com/baseball/analysis/downloadable-fantasy-baseball-pick-by-pick-data-the-dinger-2023",
    2022: "https://underdognetwork.com/baseball/news-and-lineups/downloadable-fantasy-baseball-pick-by-pick-data-the-dinger-2022",
}


def ingest_all_historical(
    csv_dir: str | Path,
    session: Session,
    mlb_player_list: Optional[list[tuple[int, str]]] = None,
) -> list[dict]:
    """
    Load all historical CSVs from a directory.
    Files should be named {season}.csv (e.g., 2022.csv, 2023.csv).
    """
    csv_dir = Path(csv_dir)
    results = []

    for season in [2022, 2023, 2024, 2025]:
        csv_path = csv_dir / f"{season}.csv"
        if not csv_path.exists():
            logger.warning(f"No CSV found for season {season} at {csv_path}")
            continue
        summary = ingest_season_csv(csv_path, season, session, mlb_player_list)
        results.append(summary)
        logger.info(f"Season {season}: {summary}")

    return results
