"""
FastAPI dependency: provides a SQLModel Session for each request.
Runs lightweight column migrations on startup for additive schema changes.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Generator

from sqlalchemy import text
from sqlmodel import Session, create_engine

from backend.db.models import create_db_and_tables

logger = logging.getLogger(__name__)

DB_PATH = Path("data/bestball.db")

_engine = None

# Each entry is (table, column, column_definition).
# Applied once on startup — safe to run repeatedly (IF NOT EXISTS check).
_MIGRATIONS = [
    ("podcast_episodes", "series", "TEXT"),
    ("articles", "category", "TEXT"),
    ("picks", "projection_adp", "REAL"),
]


def _run_migrations(engine) -> None:
    """Add any missing columns to existing tables."""
    with engine.connect() as conn:
        for table, column, col_def in _MIGRATIONS:
            try:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {col_def}"))
                conn.commit()
                logger.info("Migration: added %s.%s", table, column)
            except Exception:
                # Column already exists — SQLite raises OperationalError; safe to ignore.
                pass


def get_engine():
    global _engine
    if _engine is None:
        _engine = create_db_and_tables(str(DB_PATH))
        _run_migrations(_engine)
    return _engine


def get_session() -> Generator[Session, None, None]:
    with Session(get_engine()) as session:
        yield session
