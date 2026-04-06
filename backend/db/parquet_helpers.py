"""
DuckDB-based helpers for reading and writing Parquet game log files.
One Parquet file per season: data/gamelogs/{season}.parquet
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import duckdb
import pandas as pd


GAMELOGS_DIR = Path("data/gamelogs")
ADP_HISTORY_DIR = Path("data/adp_history")


# ---------------------------------------------------------------------------
# Game log helpers
# ---------------------------------------------------------------------------

def gamelog_path(season: int) -> Path:
    return GAMELOGS_DIR / f"{season}.parquet"


def load_gamelogs(season: int) -> pd.DataFrame:
    """Load the full game log Parquet for a season into a DataFrame."""
    path = gamelog_path(season)
    if not path.exists():
        return pd.DataFrame()
    return duckdb.query(f"SELECT * FROM read_parquet('{path}')").df()


def load_gamelogs_for_player(season: int, player_id: int) -> pd.DataFrame:
    path = gamelog_path(season)
    if not path.exists():
        return pd.DataFrame()
    return duckdb.query(
        f"SELECT * FROM read_parquet('{path}') WHERE player_id = {player_id}"
    ).df()


def load_gamelogs_date_range(
    season: int, start_date: str, end_date: str
) -> pd.DataFrame:
    """Load game logs for a specific date range (YYYY-MM-DD strings)."""
    path = gamelog_path(season)
    if not path.exists():
        return pd.DataFrame()
    return duckdb.query(
        f"""
        SELECT * FROM read_parquet('{path}')
        WHERE game_date >= '{start_date}' AND game_date <= '{end_date}'
        """
    ).df()


def load_gamelogs_week(season: int, week_start: str, week_end: str) -> pd.DataFrame:
    """Load game logs for a single tournament week."""
    return load_gamelogs_date_range(season, week_start, week_end)


def append_gamelogs(season: int, new_rows: pd.DataFrame) -> None:
    """
    Append new game log rows to the season Parquet file.
    Deduplicates on (mlb_id, game_date, stat_type) if those columns exist,
    otherwise falls back to (player_id, game_date) for legacy compatibility.
    """
    path = gamelog_path(season)
    GAMELOGS_DIR.mkdir(parents=True, exist_ok=True)

    if path.exists():
        existing = load_gamelogs(season)
        combined = pd.concat([existing, new_rows], ignore_index=True)
    else:
        combined = new_rows.copy()

    if "mlb_id" in combined.columns and "stat_type" in combined.columns:
        dedup_keys = ["mlb_id", "game_date", "stat_type"]
    else:
        dedup_keys = ["player_id", "game_date"]

    combined = combined.drop_duplicates(subset=dedup_keys, keep="last")
    combined = combined.sort_values(dedup_keys[:2]).reset_index(drop=True)
    combined.to_parquet(path, index=False)


def load_gamelogs_for_mlb_id(season: int, mlb_id: int) -> pd.DataFrame:
    """Load game logs for a single player by mlb_id."""
    path = gamelog_path(season)
    if not path.exists():
        return pd.DataFrame()
    return duckdb.query(
        f"SELECT * FROM read_parquet('{path}') WHERE mlb_id = {mlb_id}"
    ).df()


def load_gamelogs_by_mlb_ids(season: int, mlb_ids: list[int]) -> pd.DataFrame:
    """Load game logs for a list of mlb_ids."""
    path = gamelog_path(season)
    if not path.exists():
        return pd.DataFrame()
    ids = ", ".join(str(i) for i in mlb_ids)
    return duckdb.query(
        f"SELECT * FROM read_parquet('{path}') WHERE mlb_id IN ({ids})"
    ).df()


def get_last_gamelog_date(season: int) -> Optional[str]:
    """Return the most recent game_date in the season's Parquet, or None."""
    path = gamelog_path(season)
    if not path.exists():
        return None
    result = duckdb.query(
        f"SELECT MAX(game_date) AS last_date FROM read_parquet('{path}')"
    ).df()
    val = result["last_date"].iloc[0]
    return str(val) if pd.notna(val) else None


# ---------------------------------------------------------------------------
# ADP history helpers
# ---------------------------------------------------------------------------

def adp_history_path(season: int) -> Path:
    return ADP_HISTORY_DIR / f"{season}.parquet"


def load_adp_history(season: int) -> pd.DataFrame:
    path = adp_history_path(season)
    if not path.exists():
        return pd.DataFrame()
    return duckdb.query(f"SELECT * FROM read_parquet('{path}')").df()


def append_adp_snapshot(season: int, snapshot_rows: pd.DataFrame) -> None:
    """Append daily ADP snapshot rows. Deduplicates on (player_id, snapshot_date)."""
    path = adp_history_path(season)
    ADP_HISTORY_DIR.mkdir(parents=True, exist_ok=True)

    if path.exists():
        existing = load_adp_history(season)
        combined = pd.concat([existing, snapshot_rows], ignore_index=True)
    else:
        combined = snapshot_rows.copy()

    combined = combined.drop_duplicates(
        subset=["player_id", "snapshot_date"], keep="last"
    )
    combined = combined.sort_values(["snapshot_date", "player_id"]).reset_index(
        drop=True
    )
    combined.to_parquet(path, index=False)


# ---------------------------------------------------------------------------
# Expected Parquet schema documentation (not enforced here — enforced at ETL)
# ---------------------------------------------------------------------------

GAMELOG_COLUMNS = [
    "game_date",          # str YYYY-MM-DD
    "player_id",          # int (Underdog player_id)
    "mlb_id",             # int
    "position",           # "P", "IF", "OF"
    "season",             # int
    # Raw hitting stats
    "pa", "ab", "h", "doubles", "triples", "home_runs",
    "runs", "rbi", "stolen_bases", "walks", "hit_by_pitch",
    # Derived hitting
    "singles",            # h - doubles - triples - home_runs
    # Raw pitching stats
    "ip", "earned_runs", "strikeouts", "wins",
    # Derived pitching
    "qs_flag",            # 0 or 1
    # Calculated best ball points
    "calculated_points",
]

ADP_HISTORY_COLUMNS = [
    "snapshot_date",      # str YYYY-MM-DD
    "player_id",          # int
    "season",             # int
    "adp",                # float
    "draft_rate",         # float (actual % of drafts)
    "projected_draft_rate",
    "projected_daily_picks",
]
