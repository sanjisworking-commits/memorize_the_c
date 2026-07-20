"""Sprint 7 sheet chrome + navigation tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from constitution_memorizer.web.app import create_app

MINI_UNITS = Path(__file__).parent / "fixtures" / "learning" / "mini_units.json"


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    app = create_app(
        units_path=MINI_UNITS,
        db_path=tmp_path / "progress.db",
    )
    return TestClient(app)


def test_sheet_chrome_and_nav_links(client: TestClient):
    response = client.get("/")
    assert response.status_code == 200
    assert 'class="sheet"' in response.text
    assert 'href="/calendar"' in response.text
    assert 'href="/browse"' in response.text
    assert 'href="/progress"' in response.text
    assert 'href="/search"' in response.text
    assert "nav-link is-active" in response.text


def test_calendar_page(client: TestClient):
    response = client.get("/calendar")
    assert response.status_code == 200
    assert "Calendar" in response.text
    assert "calendar-grid" in response.text
    assert 'href="/calendar"' in response.text
    assert "is-active" in response.text


def test_search_uses_accent_cta(client: TestClient):
    response = client.get("/search")
    assert response.status_code == 200
    assert "Search" in response.text
    assert "btn-accent" in response.text
    assert 'href="/search"' in response.text
