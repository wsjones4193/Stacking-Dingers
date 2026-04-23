"""
Import ADP data from an Underdog rankings CSV export.

CSV columns: id, firstName, lastName, adp, projectedPoints, positionRank,
             slotName, teamName, lineupStatus, byeWeek

Usage:
  python -m backend.soccer.etl.adp_import <path_to_csv>
  python -m backend.soccer.etl.adp_import  # reads data/soccer/latest_adp.csv
"""

from __future__ import annotations

import csv
import logging
import sys
from datetime import date
from pathlib import Path

from sqlmodel import Session, select

from backend.db.deps import get_engine
from backend.soccer.constants import UNDERDOG_POSITION_MAP
from backend.soccer.db_models import SoccerAdpSnapshot, SoccerPlayer, SoccerPlayerIdMap

logger = logging.getLogger(__name__)

DEFAULT_CSV = Path("data/soccer/latest_adp.csv")


def _parse_name(first: str, last: str) -> str:
    first = first.strip().strip('"')
    last = last.strip().strip('"')
    if not first:
        return last
    return f"{first} {last}".strip()


def run_import(csv_path: Path) -> None:
    today = date.today()
    logger.info("Importing ADP from %s for %s", csv_path, today.isoformat())

    rows = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            underdog_id = row.get("id", "").strip().strip('"')
            name = _parse_name(row.get("firstName", ""), row.get("lastName", ""))
            adp_raw = row.get("adp", "").strip().strip('"')
            slot = row.get("slotName", "").strip().strip('"')
            team = row.get("teamName", "").strip().strip('"')
            status = row.get("lineupStatus", "").strip().strip('"')

            if not underdog_id or not name:
                continue

            position = UNDERDOG_POSITION_MAP.get(slot, slot)
            try:
                adp = float(adp_raw) if adp_raw and adp_raw != "-" else None
            except ValueError:
                adp = None
            active = status.upper() != "OUT"

            rows.append({
                "underdog_id": underdog_id,
                "name": name,
                "position": position,
                "nationality": team or None,
                "adp": adp,
                "active": active,
            })

    engine = get_engine()
    new_players = 0
    updated_players = 0
    new_snapshots = 0

    with Session(engine) as session:
        for r in rows:
            # Find or create player
            player = session.exec(
                select(SoccerPlayer).where(SoccerPlayer.underdog_id == r["underdog_id"])
            ).first()

            if not player:
                player = SoccerPlayer(
                    name=r["name"],
                    position=r["position"],
                    nationality=r["nationality"],
                    underdog_id=r["underdog_id"],
                    active=r["active"],
                )
                session.add(player)
                session.flush()

                # Stub ID map entry for future FBref linking
                session.add(SoccerPlayerIdMap(
                    underdog_id=r["underdog_id"],
                    underdog_name=r["name"],
                    confirmed=False,
                ))
                new_players += 1
            else:
                # Update name/nationality/status in case it changed
                player.name = r["name"]
                player.nationality = r["nationality"]
                player.active = r["active"]
                updated_players += 1

            # Upsert today's ADP snapshot
            existing = session.exec(
                select(SoccerAdpSnapshot)
                .where(SoccerAdpSnapshot.player_id == player.player_id)
                .where(SoccerAdpSnapshot.snapshot_date == today)
            ).first()

            if existing:
                existing.adp = r["adp"]
            else:
                session.add(SoccerAdpSnapshot(
                    player_id=player.player_id,
                    snapshot_date=today,
                    adp=r["adp"],
                ))
                new_snapshots += 1

        session.commit()

    logger.info(
        "Done — new players: %d, updated: %d, snapshots saved: %d",
        new_players, updated_players, new_snapshots,
    )
    print(f"Imported {len(rows)} players — {new_players} new, {updated_players} updated, {new_snapshots} ADP snapshots saved for {today}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_CSV
    if not path.exists():
        print(f"File not found: {path}")
        sys.exit(1)
    run_import(path)
