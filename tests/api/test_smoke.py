"""
Smoke tests for all API endpoints.

Uses an in-memory SQLite database and the FastAPI TestClient.
Verifies:
- All endpoints return 200 (or 404 for missing resources)
- Response shape has the expected `data` key
- No server errors on empty databases
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, StaticPool

from backend.db.models import create_db_and_tables
from backend.db.deps import get_session
from backend.main import app


# ---------------------------------------------------------------------------
# Test database fixture
# ---------------------------------------------------------------------------

TEST_DB_URL = "sqlite://"   # in-memory


@pytest.fixture(name="client")
def client_fixture():
    """
    Create a TestClient with a fresh in-memory SQLite database.
    Overrides the get_session dependency so no real data/ files are needed.
    """
    engine = create_engine(
        TEST_DB_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    def override_get_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


# ---------------------------------------------------------------------------
# Players
# ---------------------------------------------------------------------------

class TestPlayersEndpoints:
    def test_search_empty(self, client):
        r = client.get("/api/players/search?q=Aaron")
        assert r.status_code == 200
        body = r.json()
        assert "data" in body
        assert body["data"] == []

    def test_player_not_found(self, client):
        r = client.get("/api/players/999999")
        assert r.status_code == 404

    def test_player_history_not_found(self, client):
        r = client.get("/api/players/999999/history")
        assert r.status_code == 404

    def test_search_returns_data_key(self, client):
        r = client.get("/api/players/search?q=test")
        assert r.status_code == 200
        assert "data" in r.json()


# ---------------------------------------------------------------------------
# Teams
# ---------------------------------------------------------------------------

class TestTeamsEndpoints:
    def test_search_empty(self, client):
        r = client.get("/api/teams/search?username=someuser")
        assert r.status_code == 200
        assert r.json()["data"] == []

    def test_team_not_found(self, client):
        r = client.get("/api/teams/nonexistent_draft_id")
        assert r.status_code == 404

    def test_search_returns_data_key(self, client):
        r = client.get("/api/teams/search?username=test")
        assert r.status_code == 200
        assert "data" in r.json()


# ---------------------------------------------------------------------------
# ADP
# ---------------------------------------------------------------------------

class TestAdpEndpoints:
    def test_scatter_empty(self, client):
        r = client.get("/api/adp/scatter")
        assert r.status_code == 200
        assert "data" in r.json()

    def test_scatter_position_filter(self, client):
        r = client.get("/api/adp/scatter?position=P")
        assert r.status_code == 200

    def test_movement_empty(self, client):
        r = client.get("/api/adp/movement")
        assert r.status_code == 200
        assert r.json()["data"] == []

    def test_scarcity_empty(self, client):
        r = client.get("/api/adp/scarcity")
        assert r.status_code == 200
        assert r.json()["data"] == []

    def test_scarcity_with_prior_season(self, client):
        r = client.get("/api/adp/scarcity?season=2026&prior_season=2025")
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# Leaderboard
# ---------------------------------------------------------------------------

class TestLeaderboardEndpoints:
    def test_leaderboard_empty(self, client):
        r = client.get("/api/leaderboard")
        assert r.status_code == 200
        body = r.json()
        assert "data" in body
        assert body["data"]["entries"] == []
        assert body["data"]["total"] == 0

    def test_leaderboard_sort_by_peak(self, client):
        r = client.get("/api/leaderboard?sort_by=peak_2wk_score")
        assert r.status_code == 200

    def test_leaderboard_pagination(self, client):
        r = client.get("/api/leaderboard?page=1&page_size=10")
        assert r.status_code == 200
        assert r.json()["data"]["page"] == 1


# ---------------------------------------------------------------------------
# History modules
# ---------------------------------------------------------------------------

class TestHistoryEndpoints:
    def test_module_list(self, client):
        r = client.get("/api/history/modules")
        assert r.status_code == 200
        modules = r.json()["data"]
        assert len(modules) == 5
        assert all("module_id" in m for m in modules)

    def test_module_1_empty(self, client):
        r = client.get("/api/history/modules/1")
        assert r.status_code == 200
        assert "data" in r.json()

    def test_module_2_empty(self, client):
        r = client.get("/api/history/modules/2")
        assert r.status_code == 200

    def test_module_3_empty(self, client):
        r = client.get("/api/history/modules/3")
        assert r.status_code == 200

    def test_module_4_empty(self, client):
        r = client.get("/api/history/modules/4")
        assert r.status_code == 200

    def test_module_5_empty(self, client):
        r = client.get("/api/history/modules/5")
        assert r.status_code == 200

    def test_module_4_leaderboard_mode(self, client):
        r = client.get("/api/history/modules/4?leaderboard_mode=true")
        assert r.status_code == 200

    def test_module_5_position_filter(self, client):
        r = client.get("/api/history/modules/5?position=P")
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# Admin
# ---------------------------------------------------------------------------

class TestAdminEndpoints:
    def test_mapping_list_empty(self, client):
        r = client.get("/api/admin/player-mapping")
        assert r.status_code == 200
        assert r.json()["data"] == []

    def test_mapping_not_found(self, client):
        r = client.patch("/api/admin/player-mapping/999999", json={"confirmed": True})
        assert r.status_code == 404

    def test_mapping_create(self, client):
        payload = {
            "underdog_id": "ud_test_123",
            "underdog_name": "Test Player",
            "mlb_id": 123456,
            "mlb_name": "Test Player",
            "season": 2026,
        }
        r = client.post("/api/admin/player-mapping", json=payload)
        assert r.status_code == 200
        result = r.json()["data"]
        assert result["underdog_id"] == "ud_test_123"
        assert result["confirmed"] is True

    def test_mapping_patch_after_create(self, client):
        # Create first
        payload = {
            "underdog_id": "ud_patch_test",
            "underdog_name": "Patch Test",
            "season": 2026,
        }
        r = client.post("/api/admin/player-mapping", json=payload)
        assert r.status_code == 200
        map_id = r.json()["data"]["map_id"]

        # Then patch
        r2 = client.patch(
            f"/api/admin/player-mapping/{map_id}",
            json={"mlb_id": 987654, "notes": "manual correction"},
        )
        assert r2.status_code == 200
        assert r2.json()["data"]["mlb_id"] == 987654

    def test_score_audit_empty(self, client):
        r = client.get("/api/admin/score-audit")
        assert r.status_code == 200
        assert r.json()["data"] == []

    def test_mapping_unconfirmed_filter(self, client):
        r = client.get("/api/admin/player-mapping?confirmed=false")
        assert r.status_code == 200

    def test_mapping_unmatched_filter(self, client):
        r = client.get("/api/admin/player-mapping?unmatched_only=true")
        assert r.status_code == 200
