"""
Scoring calculator: raw MLB Stats API stats → Underdog best ball points.

Hitters: 1B(3) 2B(6) 3B(8) HR(10) RBI(2) R(2) SB(4) BB(3) HBP(3)
Pitchers: IP(3) K(3) W(5) QS(5) ER(-3)

QS = quality start: >= 6.0 IP and <= 3 ER in the same game appearance.
1B is derived: H - 2B - 3B - HR (singles not a direct API field).

IP is stored as a float where 0.1 = 1/3 of an inning.
Example: 6.2 IP = 6 full innings + 2 outs = 6.667 innings scored as 6.667 * 3.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from backend.constants import (
    HITTER_SCORING,
    PITCHER_SCORING,
    QS_MAX_ER,
    QS_MIN_IP,
)


# ---------------------------------------------------------------------------
# Input dataclasses (one per game appearance)
# ---------------------------------------------------------------------------

@dataclass
class HitterGameLog:
    player_id: int
    game_date: str       # YYYY-MM-DD
    season: int
    position: str        # "IF" or "OF"
    pa: int = 0
    ab: int = 0
    h: int = 0
    doubles: int = 0
    triples: int = 0
    home_runs: int = 0
    runs: int = 0
    rbi: int = 0
    stolen_bases: int = 0
    walks: int = 0
    hit_by_pitch: int = 0


@dataclass
class PitcherGameLog:
    player_id: int
    game_date: str
    season: int
    position: str = "P"
    ip: float = 0.0       # e.g. 6.2 means 6 innings + 2 outs
    earned_runs: int = 0
    strikeouts: int = 0
    wins: int = 0         # 1 if pitcher received the win, else 0


# ---------------------------------------------------------------------------
# Output dataclass
# ---------------------------------------------------------------------------

@dataclass
class ScoredGameLog:
    player_id: int
    game_date: str
    season: int
    position: str
    calculated_points: float

    # Hitting stat breakdown
    singles: int = 0
    doubles: int = 0
    triples: int = 0
    home_runs: int = 0
    runs: int = 0
    rbi: int = 0
    stolen_bases: int = 0
    walks: int = 0
    hit_by_pitch: int = 0
    pa: int = 0
    ab: int = 0
    h: int = 0

    # Pitching stat breakdown
    ip: float = 0.0
    ip_true: float = 0.0   # actual innings (6.2 → 6.667)
    earned_runs: int = 0
    strikeouts: int = 0
    wins: int = 0
    qs_flag: int = 0


# ---------------------------------------------------------------------------
# IP conversion
# ---------------------------------------------------------------------------

def ip_to_true_innings(ip: float) -> float:
    """
    Convert Underdog/MLB Stats API IP notation to true decimal innings.
    6.2 IP = 6 full innings + 2/3 inning = 6.667
    """
    full_innings = int(ip)
    partial_outs = round((ip - full_innings) * 10)  # 0, 1, or 2 outs
    return full_innings + partial_outs / 3.0


# ---------------------------------------------------------------------------
# Scoring functions
# ---------------------------------------------------------------------------

def score_hitter_game(log: HitterGameLog) -> ScoredGameLog:
    """Calculate best ball points for a single hitter game appearance."""
    singles = log.h - log.doubles - log.triples - log.home_runs
    singles = max(0, singles)  # guard against any data oddities

    points = (
        singles * HITTER_SCORING["single"]
        + log.doubles * HITTER_SCORING["double"]
        + log.triples * HITTER_SCORING["triple"]
        + log.home_runs * HITTER_SCORING["home_run"]
        + log.rbi * HITTER_SCORING["rbi"]
        + log.runs * HITTER_SCORING["run"]
        + log.stolen_bases * HITTER_SCORING["stolen_base"]
        + log.walks * HITTER_SCORING["walk"]
        + log.hit_by_pitch * HITTER_SCORING["hit_by_pitch"]
    )

    return ScoredGameLog(
        player_id=log.player_id,
        game_date=log.game_date,
        season=log.season,
        position=log.position,
        calculated_points=round(points, 2),
        singles=singles,
        doubles=log.doubles,
        triples=log.triples,
        home_runs=log.home_runs,
        runs=log.runs,
        rbi=log.rbi,
        stolen_bases=log.stolen_bases,
        walks=log.walks,
        hit_by_pitch=log.hit_by_pitch,
        pa=log.pa,
        ab=log.ab,
        h=log.h,
    )


def score_pitcher_game(log: PitcherGameLog) -> ScoredGameLog:
    """Calculate best ball points for a single pitcher game appearance."""
    ip_true = ip_to_true_innings(log.ip)
    qs_flag = 1 if ip_true >= QS_MIN_IP and log.earned_runs <= QS_MAX_ER else 0

    points = (
        ip_true * PITCHER_SCORING["inning_pitched"]
        + log.strikeouts * PITCHER_SCORING["strikeout"]
        + log.wins * PITCHER_SCORING["win"]
        + qs_flag * PITCHER_SCORING["quality_start"]
        + log.earned_runs * PITCHER_SCORING["earned_run"]
    )

    return ScoredGameLog(
        player_id=log.player_id,
        game_date=log.game_date,
        season=log.season,
        position="P",
        calculated_points=round(points, 2),
        ip=log.ip,
        ip_true=ip_true,
        earned_runs=log.earned_runs,
        strikeouts=log.strikeouts,
        wins=log.wins,
        qs_flag=qs_flag,
    )


# ---------------------------------------------------------------------------
# Batch scoring (DataFrame interface for ETL)
# ---------------------------------------------------------------------------

def score_hitter_row(row: dict) -> float:
    """Score a single row dict (from a DataFrame). Returns calculated_points."""
    h = int(row.get("h", 0))
    doubles = int(row.get("doubles", 0))
    triples = int(row.get("triples", 0))
    home_runs = int(row.get("home_runs", 0))
    singles = max(0, h - doubles - triples - home_runs)

    return round(
        singles * HITTER_SCORING["single"]
        + doubles * HITTER_SCORING["double"]
        + triples * HITTER_SCORING["triple"]
        + home_runs * HITTER_SCORING["home_run"]
        + int(row.get("rbi", 0)) * HITTER_SCORING["rbi"]
        + int(row.get("runs", 0)) * HITTER_SCORING["run"]
        + int(row.get("stolen_bases", 0)) * HITTER_SCORING["stolen_base"]
        + int(row.get("walks", 0)) * HITTER_SCORING["walk"]
        + int(row.get("hit_by_pitch", 0)) * HITTER_SCORING["hit_by_pitch"],
        2,
    )


def score_pitcher_row(row: dict) -> tuple[float, int]:
    """
    Score a single pitcher row dict.
    Returns (calculated_points, qs_flag).
    """
    ip_true = ip_to_true_innings(float(row.get("ip", 0.0)))
    earned_runs = int(row.get("earned_runs", 0))
    qs_flag = 1 if ip_true >= QS_MIN_IP and earned_runs <= QS_MAX_ER else 0

    points = round(
        ip_true * PITCHER_SCORING["inning_pitched"]
        + int(row.get("strikeouts", 0)) * PITCHER_SCORING["strikeout"]
        + int(row.get("wins", 0)) * PITCHER_SCORING["win"]
        + qs_flag * PITCHER_SCORING["quality_start"]
        + earned_runs * PITCHER_SCORING["earned_run"],
        2,
    )
    return points, qs_flag
