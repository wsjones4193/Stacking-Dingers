"""
FastAPI dependency: provides a SQLModel Session for each request.
"""

from __future__ import annotations

from pathlib import Path
from typing import Generator

from sqlmodel import Session, create_engine

from backend.db.models import create_db_and_tables

DB_PATH = Path("data/bestball.db")

_engine = None


def get_engine():
    global _engine
    if _engine is None:
        _engine = create_db_and_tables(str(DB_PATH))
    return _engine


def get_session() -> Generator[Session, None, None]:
    with Session(get_engine()) as session:
        yield session
