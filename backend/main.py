"""
FastAPI application entry point for MLB Best Ball Hub.

Registers all routers and configures CORS for the Vercel-hosted frontend.
Run locally: uvicorn backend.main:app --reload
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from datetime import date

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.db.s3_sync import sync_data_from_s3
from backend.routers import admin, adp, content, history, leaderboard, players, teams

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Pull data from S3 on startup when running in production."""
    sync_data_from_s3()
    yield


app = FastAPI(
    title="MLB Best Ball Hub API",
    description="Data API for The Dinger — Underdog Fantasy MLB best ball tournament",
    version="1.0.0",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------

# Allow Vercel preview URLs and local dev
ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:3000",
    "https://stacking-dingers.vercel.app",
    "https://stacking-dingers-production.up.railway.app",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=False,
    allow_methods=["GET", "PATCH", "POST", "DELETE"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(players.router, prefix="/api/players",   tags=["players"])
app.include_router(teams.router,   prefix="/api/teams",     tags=["teams"])
app.include_router(adp.router,     prefix="/api/adp",       tags=["adp"])
app.include_router(history.router, prefix="/api/history",   tags=["history"])
app.include_router(leaderboard.router, prefix="/api/leaderboard", tags=["leaderboard"])
app.include_router(content.router, prefix="/api/content",  tags=["content"])
app.include_router(admin.router,   prefix="/api/admin",     tags=["admin"])


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/health")
def health():
    return {"status": "ok", "date": date.today().isoformat()}
