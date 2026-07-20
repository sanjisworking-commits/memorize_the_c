"""Sprint 13 — Learn Card recall mode (flip title ⇄ text)."""

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


def test_learn_enables_card_tab_and_flashcard_markup(client: TestClient):
    response = client.get("/learn/clause-1")
    assert response.status_code == 200
    html = response.text
    assert 'data-learn-mode="read"' in html
    assert 'data-learn-mode="card"' in html
    assert "learn-card" in html
    assert "Recite it, then tap to check" in html
    assert "Tap to flip back" in html
    assert "learn-panel-card" in html
    assert 'data-learn-panel="card"' in html
    # Card starts hidden; Read is default
    assert 'data-mode="read"' in html
    # Other modes still stubbed
    assert "Coming in later sprints" in html
    assert "Cloze" in html


def test_card_face_shows_title_and_hides_stem_panel(client: TestClient):
    """Card panel carries title/kind; stem stays only in the Read panel."""
    response = client.get("/learn/clause-1")
    html = response.text
    assert "learn-card-title" in html
    assert "Article 20(1)" in html
    assert "learn-card-kind" in html
    # Stem (if any) lives under read panel only — card panel has no learn-stem
    card_start = html.index('data-learn-panel="card"')
    card_chunk = html[card_start : card_start + 1200]
    assert "learn-stem" not in card_chunk
    assert "(1) No person shall be convicted" in card_chunk
