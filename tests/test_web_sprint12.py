"""Sprint 12 — Again tomorrow + mobile sticky footer."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from constitution_memorizer.progress.scheduler import ReminderEngine
from constitution_memorizer.web.app import create_app

MINI_UNITS = Path(__file__).parent / "fixtures" / "learning" / "mini_units.json"


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    app = create_app(
        units_path=MINI_UNITS,
        db_path=tmp_path / "progress.db",
    )
    return TestClient(app)


@pytest.fixture
def engine(tmp_path: Path) -> ReminderEngine:
    return ReminderEngine.from_paths(tmp_path / "progress.db", MINI_UNITS)


def test_learn_shows_again_tomorrow_and_sticky_markup(client: TestClient):
    response = client.get("/learn/clause-1")
    assert response.status_code == 200
    assert "Again tomorrow" in response.text
    assert "learn-actions" in response.text
    assert 'action="/learn/clause-1/again"' in response.text
    assert "btn-ghost" in response.text
    assert "Done — next unitDone" not in response.text
    assert "Again tomorrowAgain" not in response.text
    assert "label-short" not in response.text


def test_again_tomorrow_defers_without_advancing_ladder(
    client: TestClient,
    engine: ReminderEngine,
):
    day0 = date(2026, 7, 20)
    # Seed via mark_done first so interval is on the ladder.
    engine.mark_all_modes_seen("clause-1")
    engine.mark_done("clause-1", as_of=day0)
    progress = engine.repo.get_progress("clause-1")
    assert progress is not None
    assert progress.interval_days == 1
    assert progress.times_completed == 1

    # Re-bind client to same db by using engine paths — client has its own db.
    # Exercise the HTTP route on the client's engine instead:
    again = client.post("/learn/clause-1/again", follow_redirects=False)
    assert again.status_code == 303
    assert again.headers["location"] == "/learn/clause-2/choose"

    # Client DB is separate; verify defer via engine API directly too.
    deferred = engine.defer_until_tomorrow("clause-1", as_of=day0 + timedelta(days=2))
    assert deferred.progress.times_completed == 1
    assert deferred.progress.interval_days == 1
    assert deferred.progress.next_revision == day0 + timedelta(days=3)
    assert deferred.progress.status == "review"
    assert deferred.next_unit_id == "clause-2"


def test_again_route_schedules_tomorrow_on_fresh_unit(client: TestClient, tmp_path: Path):
    app = create_app(units_path=MINI_UNITS, db_path=tmp_path / "again.db")
    c = TestClient(app)
    response = c.post("/learn/clause-1/again", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/learn/clause-2/choose"

    eng = ReminderEngine.from_paths(tmp_path / "again.db", MINI_UNITS)
    progress = eng.repo.get_progress("clause-1")
    assert progress is not None
    assert progress.status == "review"
    assert progress.times_completed == 0
    assert progress.interval_days == 1
    assert progress.next_revision == date.today() + timedelta(days=1)
