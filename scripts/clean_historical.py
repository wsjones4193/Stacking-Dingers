"""
Clean and normalize the raw Underdog historical CSV files for ingestion.

Reads from:
  Historical Dinger Data/
    2022/The_Dinger_2022_Pick_Dump.csv          (single file, all rounds)
    2023/The_Dinger_2023.csv                     (single file, all rounds)
    2024/the_dinger_2024_r{1..4}_results_pick_by_pick.csv
    2025/the_dinger_rd{1..4}.csv

Writes to:
  data/csv/2022.csv, 2023.csv, 2024.csv, 2025.csv

Structure (consistent across all years):
  - draft_id           = 12-team group pod (used for ranking within groups)
  - tournament_entry_id = per-team unique ID (becomes our draft_id)
  - Only R1 data is kept (R2/R3 are separate re-drafts by the same users)
  - made_playoffs derived by checking if tournament_entry_id appears in R2 data

Transformations:
  - tournament_entry_id -> draft_id  (per-team key)
  - draft_id            -> group_id  (group pod key)
  - Positions mapped: SP/RP->P, 1B/2B/3B/SS/C->IF, LF/CF/RF/DH->OF
  - draft_date from draft_completed_time
  - Redundant columns dropped (~50-65% file size reduction)

Usage:
  python scripts/clean_historical.py
  python scripts/clean_historical.py --raw-dir "path/to/raw" --out-dir "data/csv"
  python scripts/clean_historical.py --seasons 2024 2025
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("clean_historical")


# ---------------------------------------------------------------------------
# Position mapping
# ---------------------------------------------------------------------------

POSITION_MAP = {
    "SP": "P", "RP": "P",
    "1B": "IF", "2B": "IF", "3B": "IF", "SS": "IF", "C": "IF",
    "LF": "OF", "CF": "OF", "RF": "OF", "DH": "OF",
}


def map_position(pos: str) -> str:
    return POSITION_MAP.get(str(pos).strip().upper(), "OF")


# ---------------------------------------------------------------------------
# Output columns
# ---------------------------------------------------------------------------

OUTPUT_COLUMNS = [
    "draft_id",           # tournament_entry_id (per-team key)
    "group_id",           # original draft_id (12-team pod key)
    "season",
    "username",
    "draft_position",     # seat 1-12 (pick_order)
    "draft_date",
    "player_name",
    "underdog_player_id", # Underdog UUID (blank for 2022)
    "position",           # P / IF / OF
    "pick_number",        # overall pick 1-240
    "round_number",       # team pick number 1-20 (draft round)
    "pick_points",        # Underdog's player season points (for audit)
    "roster_points",      # Underdog's team total points
    "made_playoffs",      # 1 = advanced to R2
]


def extract_date(df: pd.DataFrame) -> pd.Series:
    """Extract date from the best available timestamp column."""
    for col in ["draft_completed_time", "draft_time", "pick_created_time"]:
        if col in df.columns:
            try:
                return pd.to_datetime(df[col], errors="coerce", utc=True).dt.date
            except Exception:
                continue
    return pd.Series([None] * len(df))


def build_r1_frame(df_r1: pd.DataFrame, r2_entry_ids: set[str], season: int) -> pd.DataFrame:
    """
    Common transformation applied to R1 data regardless of source year.
    - df_r1: raw R1 DataFrame (already filtered to tournament_round_number==1 if needed)
    - r2_entry_ids: set of tournament_entry_ids that appear in the R2 file
    """
    out = pd.DataFrame()
    out["draft_id"]           = df_r1["tournament_entry_id"]
    out["group_id"]           = df_r1["draft_id"]
    out["season"]             = season
    out["username"]           = df_r1.get("username", pd.Series(dtype=str))
    out["draft_position"]     = pd.to_numeric(df_r1.get("pick_order", pd.Series(dtype=str)), errors="coerce")
    out["draft_date"]         = extract_date(df_r1)
    out["player_name"]        = df_r1["player_name"].str.strip()
    out["underdog_player_id"] = df_r1.get("player_id", pd.Series(dtype=str))
    out["position"]           = df_r1["position_name"].apply(map_position)
    out["pick_number"]        = pd.to_numeric(df_r1["overall_pick_number"], errors="coerce").fillna(0).astype(int)
    out["round_number"]       = pd.to_numeric(df_r1["team_pick_number"], errors="coerce").fillna(0).astype(int)
    out["pick_points"]        = pd.to_numeric(df_r1.get("pick_points", pd.Series(dtype=str)), errors="coerce").fillna(0)
    out["roster_points"]      = pd.to_numeric(df_r1.get("roster_points", pd.Series(dtype=str)), errors="coerce").fillna(0)
    # Derive made_playoffs from R2 participation (same logic as user's R code)
    out["made_playoffs"]      = df_r1["tournament_entry_id"].isin(r2_entry_ids).astype(int)
    return out


# ---------------------------------------------------------------------------
# Per-season cleaners
# ---------------------------------------------------------------------------

def clean_2022(raw_dir: Path, season: int = 2022) -> pd.DataFrame:
    path = raw_dir / "2022" / "The_Dinger_2022_Pick_Dump.csv"
    logger.info(f"  Reading {path.name} ...")
    df = pd.read_csv(path, dtype=str, low_memory=False)
    logger.info(f"  {len(df):,} rows total")

    df_r1 = df[df["tournament_round_number"] == "1"].copy()
    df_r2 = df[df["tournament_round_number"] == "2"]
    r2_ids = set(df_r2["tournament_entry_id"].dropna())

    logger.info(f"  R1: {len(df_r1):,} rows | R2 participants: {len(r2_ids):,}")
    return build_r1_frame(df_r1, r2_ids, season)


def clean_2023(raw_dir: Path, season: int = 2023) -> pd.DataFrame:
    path = raw_dir / "2023" / "The_Dinger_2023.csv"
    logger.info(f"  Reading {path.name} ...")
    df = pd.read_csv(path, dtype=str, low_memory=False)
    logger.info(f"  {len(df):,} rows total")

    df_r1 = df[df["tournament_round_number"] == "1"].copy()
    df_r2 = df[df["tournament_round_number"] == "2"]
    r2_ids = set(df_r2["tournament_entry_id"].dropna())

    logger.info(f"  R1: {len(df_r1):,} rows | R2 participants: {len(r2_ids):,}")
    return build_r1_frame(df_r1, r2_ids, season)


def clean_2024(raw_dir: Path, season: int = 2024) -> pd.DataFrame:
    r1_path = raw_dir / "2024" / "the_dinger_2024_r1_results_pick_by_pick.csv"
    r2_path = raw_dir / "2024" / "the_dinger_2024_r2_results_pick_by_pick.csv"

    logger.info(f"  Reading {r1_path.name} ...")
    df_r1 = pd.read_csv(r1_path, dtype=str, low_memory=False)
    logger.info(f"  R1: {len(df_r1):,} rows")

    logger.info(f"  Reading {r2_path.name} (for advancement derivation) ...")
    df_r2 = pd.read_csv(r2_path, usecols=["tournament_entry_id"], dtype=str)
    r2_ids = set(df_r2["tournament_entry_id"].dropna())
    logger.info(f"  R2 participants: {len(r2_ids):,}")

    return build_r1_frame(df_r1, r2_ids, season)


def clean_2025(raw_dir: Path, season: int = 2025) -> pd.DataFrame:
    r1_path = raw_dir / "2025" / "the_dinger_rd1.csv"
    r2_path = raw_dir / "2025" / "the_dinger_rd2.csv"

    logger.info(f"  Reading {r1_path.name} ...")
    df_r1 = pd.read_csv(r1_path, dtype=str, low_memory=False)
    logger.info(f"  R1: {len(df_r1):,} rows")

    logger.info(f"  Reading {r2_path.name} (for advancement derivation) ...")
    df_r2 = pd.read_csv(r2_path, usecols=["tournament_entry_id"], dtype=str)
    r2_ids = set(df_r2["tournament_entry_id"].dropna())
    logger.info(f"  R2 participants: {len(r2_ids):,}")

    return build_r1_frame(df_r1, r2_ids, season)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

DEFAULT_RAW_DIR = Path("C:/Users/wsjon/OneDrive/Stacking Dingers/Historical Dinger Data")
DEFAULT_OUT_DIR = Path("data/csv")

CLEANERS = {
    2022: clean_2022,
    2023: clean_2023,
    2024: clean_2024,
    2025: clean_2025,
}


def run(raw_dir: Path, out_dir: Path, seasons: list[int]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    for season in seasons:
        logger.info(f"\n=== Season {season} ===")
        cleaner = CLEANERS.get(season)
        if cleaner is None:
            logger.warning(f"  No cleaner defined for season {season} -- skipping")
            continue

        df = cleaner(raw_dir, season)

        for col in OUTPUT_COLUMNS:
            if col not in df.columns:
                df[col] = None
        df = df[OUTPUT_COLUMNS]

        # Fill draft_date per team entry
        df["draft_date"] = df.groupby("draft_id")["draft_date"].transform(
            lambda x: x.ffill().bfill()
        )

        out_path = out_dir / f"{season}.csv"
        df.to_csv(out_path, index=False)

        # Size stats
        raw_bytes = sum(
            f.stat().st_size for f in (raw_dir / str(season)).glob("*.csv")
        )
        raw_mb = raw_bytes / 1_048_576
        out_mb = out_path.stat().st_size / 1_048_576
        pct = int(100 * (1 - out_mb / raw_mb)) if raw_mb else 0

        teams = df["draft_id"].nunique()
        groups = df["group_id"].nunique()
        players = df["player_name"].nunique()
        adv_rate = df.groupby("draft_id")["made_playoffs"].first().mean()

        logger.info(f"  Wrote {len(df):,} rows to {out_path}")
        logger.info(f"  Size: {raw_mb:.1f} MB raw -> {out_mb:.1f} MB cleaned ({pct}% reduction)")
        logger.info(f"  Teams: {teams:,} | Groups: {groups:,} | Players: {players:,} | "
                    f"Advance rate: {adv_rate:.1%}")

    logger.info("\nDone. Run load_historical.py next:")
    logger.info(f"  python scripts/load_historical.py --csv-dir {out_dir}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Clean raw Underdog historical CSVs")
    parser.add_argument("--raw-dir", default=str(DEFAULT_RAW_DIR))
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.add_argument("--seasons", type=int, nargs="+", default=[2022, 2023, 2024, 2025])
    args = parser.parse_args()
    run(Path(args.raw_dir), Path(args.out_dir), args.seasons)
