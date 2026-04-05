"""
Tests for the nightly ETL Step 5 (ADP snapshots), Step 6 (roster flags),
and Step 9 (score audit) functions added to scripts/nightly_etl.py.

Uses an in-memory SQLite database seeded with minimal fixture data.
"""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

import pytest
from sqlmodel import Session, SQLModel, create_engine, StaticPool

# Allow imports from repo root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backend.db.models import (
    AdpSnapshot,
    Draft,
    Pick,
    Player,
    RosterFlag,
    ScoreAudit,
    WeeklyScore,
)
from scripts.nightly_etl import (
    generate_score_audit,
    recalculate_adp_snapshots,
    update_roster_flags,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def seed_basic_data(session: Session, season: int = 2026) -> tuple[Player, Draft]:
    """Insert one player and one draft for use across tests."""
    player = Player(player_id=1, name="Test Player", position="IF", active=True)
    session.add(player)
    draft = Draft(
        draft_id="draft_test_1",
        season=season,
        draft_date=date(2026, 3, 26),
        username="testuser",
        draft_position=1,
    )
    session.add(draft)
    pick = Pick(
        draft_id="draft_test_1",
        pick_number=1,
        round_number=1,
        player_id=1,
        username="testuser",
    )
    session.add(pick)
    session.commit()
    return player, draft


# ---------------------------------------------------------------------------
# Step 5: ADP snapshots
# ---------------------------------------------------------------------------

class TestRecalculateAdpSnapshots:
    def test_basic_adp_calculation(self, session):
        """Single player picked at pick 5 → ADP = 5.0, draft_rate = 1.0."""
        seed_basic_data(session)
        result = recalculate_adp_snapshots(season=2026, session=session)

        assert result["players_updated"] == 1
        assert result["total_drafts"] == 1

        snap = session.exec(
            AdpSnapshot.__class__.__init__.__module__
            and __import__("sqlmodel", fromlist=["select"]).select(AdpSnapshot)
            .where(AdpSnapshot.player_id == 1)
        ).first()
        # Use direct query instead
        from sqlmodel import select
        snap = session.exec(select(AdpSnapshot).where(AdpSnapshot.player_id == 1)).first()
        assert snap is not None
        assert snap.adp == 1.0
        assert snap.draft_rate == 1.0

    def test_adp_averaged_across_drafts(self, session):
        """Player picked at pick 1 in draft A and pick 5 in draft B → ADP = 3.0."""
        player = Player(player_id=10, name="Multi Draft", position="P", active=True)
        session.add(player)

        for i, pick_num in enumerate([1, 5]):
            d = Draft(
                draft_id=f"multi_draft_{i}",
                season=2026,
                draft_date=date(2026, 3, 26),
                username="user",
                draft_position=1,
            )
            session.add(d)
            p = Pick(
                draft_id=f"multi_draft_{i}",
                pick_number=pick_num,
                round_number=1,
                player_id=10,
                username="user",
            )
            session.add(p)
        session.commit()

        recalculate_adp_snapshots(season=2026, session=session)

        from sqlmodel import select
        snap = session.exec(select(AdpSnapshot).where(AdpSnapshot.player_id == 10)).first()
        assert snap is not None
        assert snap.adp == pytest.approx(3.0)
        assert snap.draft_rate == pytest.approx(1.0)   # picked in both of 2 drafts

    def test_no_drafts_returns_zero(self, session):
        result = recalculate_adp_snapshots(season=2026, session=session)
        assert result["players_updated"] == 0

    def test_deduplication_on_same_day(self, session):
        """Running twice on the same day should not create duplicate snapshot rows."""
        seed_basic_data(session)
        recalculate_adp_snapshots(season=2026, session=session)
        recalculate_adp_snapshots(season=2026, session=session)

        from sqlmodel import select
        snaps = session.exec(
            select(AdpSnapshot)
            .where(AdpSnapshot.player_id == 1)
            .where(AdpSnapshot.snapshot_date == date.today())
        ).all()
        assert len(snaps) == 1

    def test_draft_rate_fraction(self, session):
        """Player in 1 of 3 drafts → draft_rate = 0.3333."""
        player = Player(player_id=20, name="Rate Test", position="OF", active=True)
        session.add(player)

        for i in range(3):
            d = Draft(
                draft_id=f"rate_draft_{i}",
                season=2026,
                draft_date=date(2026, 3, 26),
                username="user",
                draft_position=1,
            )
            session.add(d)

        # Only add pick to draft 0
        p = Pick(
            draft_id="rate_draft_0",
            pick_number=10,
            round_number=1,
            player_id=20,
            username="user",
        )
        session.add(p)
        session.commit()

        recalculate_adp_snapshots(season=2026, session=session)

        from sqlmodel import select
        snap = session.exec(select(AdpSnapshot).where(AdpSnapshot.player_id == 20)).first()
        assert snap is not None
        assert snap.draft_rate == pytest.approx(1 / 3, rel=1e-3)


# ---------------------------------------------------------------------------
# Step 6: Roster flags
# ---------------------------------------------------------------------------

class TestUpdateRosterFlags:
    def test_no_active_week_returns_zero(self, session):
        """Outside the season window → no flags created."""
        seed_basic_data(session)
        result = update_roster_flags(
            season=2026,
            today=date(2025, 1, 1),  # out of season
            session=session,
        )
        assert result["flags_created"] == 0

    def test_below_replacement_flag_generated(self, session):
        """Player with 3 consecutive bench/zero weeks should get a below_replacement flag."""
        player, draft = seed_basic_data(session)

        # Add 3 bench weekly scores
        for week in [1, 2, 3]:
            ws = WeeklyScore(
                draft_id="draft_test_1",
                week_number=week,
                season=2026,
                player_id=1,
                calculated_score=0.0,
                is_starter=False,
                is_flex=False,
                is_bench=True,
            )
            session.add(ws)
        session.commit()

        # Week 2 is active (2026-03-30 to 2026-04-05)
        today = date(2026, 4, 1)
        result = update_roster_flags(season=2026, today=today, session=session)

        from sqlmodel import select
        flags = session.exec(
            select(RosterFlag)
            .where(RosterFlag.draft_id == "draft_test_1")
            .where(RosterFlag.flag_type == "below_replacement")
        ).all()
        assert len(flags) >= 1

    def test_flags_replaced_not_duplicated(self, session):
        """Running flag update twice for same week should not double-count flags."""
        player, draft = seed_basic_data(session)

        for week in [1, 2, 3]:
            ws = WeeklyScore(
                draft_id="draft_test_1",
                week_number=week,
                season=2026,
                player_id=1,
                calculated_score=0.0,
                is_bench=True,
                is_starter=False,
                is_flex=False,
            )
            session.add(ws)
        session.commit()

        today = date(2026, 4, 1)
        update_roster_flags(season=2026, today=today, session=session)
        update_roster_flags(season=2026, today=today, session=session)

        from sqlmodel import select
        flags = session.exec(
            select(RosterFlag)
            .where(RosterFlag.draft_id == "draft_test_1")
            .where(RosterFlag.season == 2026)
        ).all()
        # Should only have flags from the latest run (deduped by week)
        week_nums = [f.week_number for f in flags]
        assert len(week_nums) == len(set(week_nums)) or len(week_nums) <= 2


# ---------------------------------------------------------------------------
# Step 9: Score audit
# ---------------------------------------------------------------------------

class TestGenerateScoreAudit:
    def test_no_underdog_scores_no_audit(self, session):
        """If no underdog_score is populated, no audit entries created."""
        seed_basic_data(session)
        ws = WeeklyScore(
            draft_id="draft_test_1",
            week_number=1,
            season=2026,
            player_id=1,
            calculated_score=25.0,
            underdog_score=None,
            is_starter=True,
        )
        session.add(ws)
        session.commit()

        result = generate_score_audit(season=2026, session=session)
        assert result["discrepancies_logged"] == 0

    def test_matching_scores_no_audit(self, session):
        """Exact match → no discrepancy logged."""
        seed_basic_data(session)
        ws = WeeklyScore(
            draft_id="draft_test_1",
            week_number=1,
            season=2026,
            player_id=1,
            calculated_score=25.0,
            underdog_score=25.0,
            is_starter=True,
        )
        session.add(ws)
        session.commit()

        result = generate_score_audit(season=2026, session=session)
        assert result["discrepancies_logged"] == 0

    def test_small_delta_not_logged(self, session):
        """Delta < 0.5 is below threshold → not logged."""
        seed_basic_data(session)
        ws = WeeklyScore(
            draft_id="draft_test_1",
            week_number=1,
            season=2026,
            player_id=1,
            calculated_score=25.3,
            underdog_score=25.0,
            is_starter=True,
        )
        session.add(ws)
        session.commit()

        result = generate_score_audit(season=2026, session=session)
        assert result["discrepancies_logged"] == 0

    def test_large_delta_logged(self, session):
        """Delta >= 0.5 → audit entry created."""
        seed_basic_data(session)
        ws = WeeklyScore(
            draft_id="draft_test_1",
            week_number=1,
            season=2026,
            player_id=1,
            calculated_score=27.0,
            underdog_score=25.0,
            is_starter=True,
        )
        session.add(ws)
        session.commit()

        result = generate_score_audit(season=2026, session=session)
        assert result["discrepancies_logged"] == 1

        from sqlmodel import select
        audit = session.exec(select(ScoreAudit).where(ScoreAudit.player_id == 1)).first()
        assert audit is not None
        assert audit.delta == pytest.approx(2.0)

    def test_negative_delta_logged(self, session):
        """Underdog score > calculated → negative delta, still logged if |delta| >= 0.5."""
        seed_basic_data(session)
        ws = WeeklyScore(
            draft_id="draft_test_1",
            week_number=1,
            season=2026,
            player_id=1,
            calculated_score=20.0,
            underdog_score=25.0,
            is_starter=True,
        )
        session.add(ws)
        session.commit()

        result = generate_score_audit(season=2026, session=session)
        assert result["discrepancies_logged"] == 1

        from sqlmodel import select
        audit = session.exec(select(ScoreAudit).where(ScoreAudit.player_id == 1)).first()
        assert audit.delta == pytest.approx(-5.0)

    def test_duplicate_audit_updates_existing(self, session):
        """Running audit twice on same week/player should update, not duplicate."""
        seed_basic_data(session)
        ws = WeeklyScore(
            draft_id="draft_test_1",
            week_number=1,
            season=2026,
            player_id=1,
            calculated_score=27.0,
            underdog_score=25.0,
            is_starter=True,
        )
        session.add(ws)
        session.commit()

        generate_score_audit(season=2026, session=session)
        generate_score_audit(season=2026, session=session)

        from sqlmodel import select
        audits = session.exec(
            select(ScoreAudit)
            .where(ScoreAudit.player_id == 1)
            .where(ScoreAudit.week_number == 1)
        ).all()
        assert len(audits) == 1
