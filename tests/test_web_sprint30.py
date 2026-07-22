"""Sprint 30 — six-method Done gate, How-to-use, rebrand, theme."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from constitution_memorizer.progress.scheduler import ModesIncompleteError, ReminderEngine
from constitution_memorizer.web.app import create_app

MINI_UNITS = Path(__file__).parent / "fixtures" / "learning" / "mini_units.json"
MINI_REVIEWED = Path(__file__).parent / "fixtures" / "learning" / "mini_reviewed.json"


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    app = create_app(
        units_path=MINI_UNITS,
        db_path=tmp_path / "progress.db",
        reviewed_path=MINI_REVIEWED if MINI_REVIEWED.exists() else None,
    )
    return TestClient(app)


@pytest.fixture
def engine(tmp_path: Path) -> ReminderEngine:
    return ReminderEngine.from_paths(tmp_path / "progress.db", MINI_UNITS)


def test_brand_and_how_to_use(client: TestClient):
    html = client.get("/").text
    assert "Recall the C" in html
    assert "brand-c.png" in html
    assert "How to use" in html
    assert "Read the Bare Act wording twice, verbatim." in html
    assert "Flip the card and self-grade your recall." in html
    assert "theme-toggle" in html
    assert "styles.css?v=sprint30e" in html


def test_learn_marks_read_and_locks_done(client: TestClient):
    html = client.get("/learn/clause-1").text
    assert "methods-tracker" in html
    assert "1 of 6 methods visited" in html
    assert "Read ✓" in html
    assert "btn-done-locked" in html
    assert "5 methods left" in html
    assert 'aria-disabled="true"' in html


def test_seen_endpoint_unlocks_done(client: TestClient):
    client.get("/learn/clause-1")  # marks read
    for mode in ("cloze", "letters", "type", "recite"):
        resp = client.post("/learn/clause-1/seen", data={"mode": mode})
        assert resp.status_code == 200
        assert resp.json()["done"]["unlocked"] is False
    # Card is the last method — unlocks Done
    resp = client.post("/learn/clause-1/seen", data={"mode": "card"})
    data = resp.json()
    assert data["complete"] is True
    assert data["remaining"] == 0
    assert data["done"]["unlocked"] is True
    assert data["done"]["label"] == "Done — next unit"
    html = client.get("/learn/clause-1?mode=card").text
    assert "All 6 methods visited" in html
    assert "Done — next unit" in html
    assert "btn-done-locked" not in html
    assert 'data-done-unlocked="true"' in html
    assert 'aria-disabled="false"' in html


def test_card_alone_does_not_unlock(client: TestClient):
    client.get("/learn/clause-1?mode=card")
    html = client.get("/learn/clause-1?mode=card").text
    assert "btn-done-locked" in html
    assert "methods left" in html


def test_done_blocked_until_six_modes(client: TestClient):
    client.get("/learn/clause-1")  # marks read
    resp = client.post("/learn/clause-1/done", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/learn/clause-1"


def test_done_advances_after_all_modes(client: TestClient):
    client.get("/learn/clause-1")
    for mode in ("cloze", "letters", "type", "recite", "card"):
        client.post("/learn/clause-1/seen", data={"mode": mode})
    resp = client.post("/learn/clause-1/done", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"].startswith("/learn/")


def test_mark_done_clears_modes_for_next_cycle(engine: ReminderEngine):
    engine.mark_all_modes_seen("clause-1")
    assert engine.modes_complete("clause-1")
    engine.mark_done("clause-1", as_of=date(2026, 7, 21))
    assert engine.modes_seen("clause-1") == set()


def test_mark_done_raises_when_incomplete(engine: ReminderEngine):
    engine.mark_mode_seen("clause-1", "read")
    with pytest.raises(ModesIncompleteError):
        engine.mark_done("clause-1", as_of=date(2026, 7, 21))


def test_theme_api_persists(client: TestClient):
    resp = client.post("/api/theme", data={"theme": "dark"})
    assert resp.status_code == 200
    assert resp.json()["theme"] == "dark"
    # Preference surfaces on next page via context processor
    html = client.get("/").text
    assert 'data-theme-preference="dark"' in html


def test_reset_unit_clears_modes(client: TestClient):
    client.get("/learn/clause-1")
    client.post("/learn/clause-1/seen", data={"mode": "cloze"})
    html = client.get("/learn/clause-1").text
    assert "Cloze ✓" in html
    client.post("/learn/clause-1/reset")
    html = client.get("/learn/clause-1").text
    assert "1 of 6 methods visited" in html
    assert "Cloze ✓" not in html
    assert "Read ✓" in html
