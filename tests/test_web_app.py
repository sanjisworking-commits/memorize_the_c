"""Sprint 4 FastAPI TestClient tests for Learn / Choose / Done."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from constitution_memorizer.progress.repository import LEARN_MODES
from constitution_memorizer.web.app import create_app

MINI_UNITS = Path(__file__).parent / "fixtures" / "learning" / "mini_units.json"


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    app = create_app(
        units_path=MINI_UNITS,
        db_path=tmp_path / "progress.db",
    )
    return TestClient(app)


def _visit_all_modes(client: TestClient, unit_id: str) -> None:
    for mode in LEARN_MODES:
        resp = client.post(f"/learn/{unit_id}/seen", data={"mode": mode})
        assert resp.status_code == 200


def test_home_renders(client: TestClient):
    response = client.get("/")
    assert response.status_code == 200
    assert "Recall the C" in response.text
    assert "Today" in response.text
    assert "Due" in response.text
    assert "Continue" in response.text or "All caught up" in response.text


def test_learn_simple_unit(client: TestClient):
    response = client.get("/learn/clause-1")
    assert response.status_code == 200
    assert "Article 20(1)" in response.text
    assert "5 methods left" in response.text
    assert "kind-badge" in response.text
    assert "LearningUnitType" not in response.text


def test_choose_required_then_whole_path(client: TestClient):
    response = client.get("/learn/clause-2", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/learn/clause-2/choose"

    choose_page = client.get("/learn/clause-2/choose")
    assert choose_page.status_code == 200
    assert "Learn whole clause" in choose_page.text
    assert "Split into letters" in choose_page.text

    chosen = client.post(
        "/learn/clause-2/choose",
        data={"mode": "whole"},
        follow_redirects=False,
    )
    assert chosen.status_code == 303
    assert chosen.headers["location"] == "/learn/clause-2"

    learn = client.get("/learn/clause-2")
    assert learn.status_code == 200
    assert "Article 20(3)" in learn.text


def test_choose_letters_and_done_advances(client: TestClient):
    chosen = client.post(
        "/learn/clause-2/choose",
        data={"mode": "letters"},
        follow_redirects=False,
    )
    assert chosen.status_code == 303
    assert chosen.headers["location"] == "/learn/clause-2-a"

    _visit_all_modes(client, "clause-2-a")
    done_a = client.post("/learn/clause-2-a/done", follow_redirects=False)
    assert done_a.status_code == 303
    assert done_a.headers["location"] == "/learn/clause-2-b"

    _visit_all_modes(client, "clause-2-b")
    done_b = client.post("/learn/clause-2-b/done", follow_redirects=False)
    assert done_b.status_code == 303
    assert done_b.headers["location"] == "/learn/article-end"


def test_done_on_simple_unit_goes_to_next_or_choose(client: TestClient):
    # clause-1 next is clause-2 which needs a choice
    _visit_all_modes(client, "clause-1")
    done = client.post("/learn/clause-1/done", follow_redirects=False)
    assert done.status_code == 303
    assert done.headers["location"] == "/learn/clause-2/choose"


def test_reset_all(client: TestClient):
    _visit_all_modes(client, "clause-1")
    client.post("/learn/clause-1/done")
    reset = client.post("/reset", follow_redirects=False)
    assert reset.status_code == 303
    assert reset.headers["location"] == "/"
    home = client.get("/")
    assert home.status_code == 200
