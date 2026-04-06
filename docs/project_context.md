# Project Context — MLB Best Ball Hub

## Repository

| Field | Value |
|---|---|
| Repo name | Stacking-Dingers |
| GitHub URL | https://github.com/wsjones4193/Stacking-Dingers |
| Default branch | master |
| Local path | `C:\Users\wsjon\OneDrive\Stacking Dingers\Website` |

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11, FastAPI, uvicorn |
| ORM / DB | SQLModel + SQLite (`data/bestball.db`) |
| Stats queries | DuckDB + Parquet (`data/gamelogs/{season}.parquet`) |
| ETL | Python scripts, GitHub Actions (nightly, March–September) |
| Frontend | React + Vite + TypeScript |
| Charts | Recharts |
| Deployment — backend | Railway (`stacking-dingers-production.up.railway.app`) |
| Deployment — frontend | Vercel (`stacking-dingers.vercel.app`) |
| Data storage | S3 (SQLite + Parquet files) |
| Testing | pytest + FastAPI TestClient |

### Key dependencies (`requirements.txt`)

- `fastapi`, `uvicorn[standard]`
- `sqlmodel`, `sqlalchemy`
- `pandas`, `duckdb`, `pyarrow`
- `mlb-statsapi`, `rapidfuzz`, `httpx`
- `boto3` (S3 uploads)
- `pytest`, `pytest-asyncio`, `pytest-cov`

---

## Data Sources

| Source | Purpose | Frequency |
|---|---|---|
| MLB Stats API (`mlb-statsapi`) | Game logs, roster positions, IL transactions | Nightly |
| Underdog Fantasy CSV exports | Draft pick data (2022–2026) | One-time per season |
| Fangraphs (Steamer + ATC) | Preseason + RoS projections | Daily preseason / nightly in-season |
| YouTube RSS feed | Podcast episodes (@StackingDingers channel) | Nightly |
| Internal SQLite (`bestball.db`) | All relational data (drafts, picks, scores, flags, articles, podcasts) | Maintained by ETL |
| Internal Parquet (`data/gamelogs/`) | Game-by-game stats and scoring | Maintained by ETL |

### Underdog CSV URLs

| Season | URL |
|---|---|
| 2026 | Not yet published |
| 2025 | https://underdognetwork.com/baseball/analysis/mlb-best-ball-downloadable-pick-by-pick-data |
| 2024 | https://underdognetwork.com/baseball/analysis/the-dinger-2024-downloadable-pick-by-pick-data |
| 2023 | https://underdognetwork.com/baseball/analysis/downloadable-fantasy-baseball-pick-by-pick-data-the-dinger-2023 |
| 2022 | https://underdognetwork.com/baseball/news-and-lineups/downloadable-fantasy-baseball-pick-by-pick-data-the-dinger-2022 |

---

## Project Structure

```
/
├── backend/
│   ├── main.py                 # FastAPI app entry point
│   ├── constants.py            # season calendar, scoring weights, roster rules
│   ├── schemas.py              # Pydantic response models
│   ├── routers/
│   │   ├── players.py
│   │   ├── teams.py
│   │   ├── adp.py
│   │   ├── history.py
│   │   ├── leaderboard.py
│   │   ├── content.py          # articles + podcasts public endpoints
│   │   └── admin.py            # player mapping, score audit, article CRUD, podcast sync
│   ├── services/               # business logic (scoring, lineup, BPCOR, flags)
│   ├── etl/
│   │   ├── draft_data.py
│   │   ├── game_logs.py
│   │   ├── projections.py
│   │   ├── team_profiles.py
│   │   └── youtube_sync.py     # YouTube RSS → podcast_episodes table
│   └── db/                     # SQLModel models, Parquet helpers, player mapping
├── frontend/                   # React + Vite + TypeScript
│   └── src/
│       ├── pages/
│       │   ├── PlayerHub.tsx
│       │   ├── TeamAnalyzer.tsx
│       │   ├── ADPExplorer.tsx
│       │   ├── HistoryBrowser.tsx
│       │   ├── Leaderboard.tsx
│       │   ├── Articles.tsx    # article list + detail view
│       │   ├── Podcasts.tsx    # episode grid with YouTube links
│       │   └── Admin.tsx       # player mapping, score audit, article editor, podcast sync
│       └── components/
│           ├── Sidebar.tsx     # nav: Player Hub, Team Analyzer, ADP, History, Leaderboard, Articles, Podcasts
│           └── ...
├── scripts/
│   ├── nightly_etl.py          # ETL orchestrator (includes YouTube sync)
│   ├── load_historical.py      # one-time historical data loader
│   ├── clean_historical.py     # normalizes raw Underdog CSVs
│   └── upload_to_s3.py         # pushes bestball.db + Parquet to S3
├── tests/
│   ├── api/                    # smoke tests (FastAPI TestClient)
│   ├── etl/                    # ETL unit tests
│   └── services/               # scoring, lineup, BPCOR unit tests
├── data/
│   ├── bestball.db             # SQLite database
│   ├── gamelogs/               # {season}.parquet
│   ├── adp_history/            # {season}.parquet
│   └── fangraphs_player_map.csv
├── logo/
│   └── stacking_dingers_logo.webp
├── docs/
│   ├── app-spec.md             # full feature specification
│   ├── project_context.md      # this file
│   ├── workflow.md             # Git workflow rules
│   └── tasks.md                # coding execution rules
└── .github/workflows/
    └── nightly_etl.yml         # GitHub Actions cron (2am ET, March–September)
```
