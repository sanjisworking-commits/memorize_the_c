"""Sprint 8 Home screen tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from constitution_memorizer.web.app import create_app
from constitution_memorizer.web.service import home_lede

MINI_UNITS = Path(__file__).parent / "fixtures" / "learning" / "mini_units.json"


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    app = create_app(
        units_path=MINI_UNITS,
        db_path=tmp_path / "progress.db",
    )
    return TestClient(app)


def test_home_lede_copy():
    assert home_lede(due_count=0, has_continue=True).startswith("Nothing due")
    assert "1 unit due" in home_lede(due_count=1, has_continue=False)
    assert "3 units due" in home_lede(due_count=3, has_continue=False)


def test_home_continue_card_and_footer(client: TestClient):
    response = client.get("/")
    assert response.status_code == 200
    assert "Today" in response.text
    assert "continue-card" in response.text
    assert "Continue" in response.text
    assert "Due" in response.text
    assert "Reset all progress" in response.text
    assert "link-reset" in response.text
    assert "home-stat-line" in response.text
    assert "LearningUnitType" not in response.text
    assert "LEARNINGUNITTYPE" not in response.text
