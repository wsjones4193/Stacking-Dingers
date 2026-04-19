"""
/api/combos — pre-computed player combo co-ownership.

GET /api/combos/leaderboard?season=2026&combo_size=2&limit=100
"""

from __future__ import annotations

from datetime import date
from typing import Optional
import sqlite3
from pathlib import Path

from fastapi import APIRouter, Query

from backend.schemas import DataResponse

router = APIRouter()

_COMBOS_DB = Path(__file__).resolve().parent.parent.parent / "data" / "adp_cache.db"


def _conn():
    return sqlite3.connect(str(_COMBOS_DB))


@router.get("/leaderboard", response_model=DataResponse)
def combos_leaderboard(
    season: int = Query(default=2026),
    combo_size: int = Query(default=2, ge=2, le=4),
    limit: int = Query(default=500, le=2000),
    position: Optional[str] = Query(default=None, description="P | IF | OF — filter by p1 position"),
):
    """Top combos by pair_rate for a given season and combo size."""
    conn = _conn()

    pos_join = ""
    pos_filter = ""
    params: list = [season, combo_size]

    if position:
        pos_join = "JOIN players pl ON c.p1_id = pl.player_id"
        pos_filter = "AND pl.position = ?"
        params.append(position.upper())

    sql = f"""
        SELECT
            c.p1_id, c.p1_name, c.p1_total,
            c.p2_id, c.p2_name, c.p2_total,
            c.p3_id, c.p3_name,
            c.p4_id, c.p4_name,
            c.pair_count, c.support, c.confidence, c.lift, c.conviction
        FROM combo_pairs c
        {pos_join}
        WHERE c.season = ? AND c.combo_size = ?
        {pos_filter}
        ORDER BY c.pair_count DESC
        LIMIT ?
    """
    params.append(limit)

    rows = conn.execute(sql, params).fetchall()
    conn.close()

    data = [
        {
            "p1_id": r[0], "p1_name": r[1], "p1_total": r[2],
            "p2_id": r[3], "p2_name": r[4], "p2_total": r[5],
            "p3_id": r[6], "p3_name": r[7],
            "p4_id": r[8], "p4_name": r[9],
            "pair_count": r[10],
            "support": r[11],
            "confidence": r[12],
            "lift": r[13],
            "conviction": r[14],
        }
        for r in rows
    ]

    return DataResponse(
        data=data,
        sample_size=len(data),
        data_as_of=date.today().isoformat(),
    )
