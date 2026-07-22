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
    assert 'href="/learn/clause-1?mode=card"' in html
    assert 'href="/learn/clause-1?mode=read"' in html
    assert "learn-card" in html
    assert "Recite it, then tap to check" in html
    assert "Tap to flip back" in html
    assert "learn-panel-card" in html
    assert 'data-mode="read"' in html
    assert "app.js?v=sprint30" in html


def test_card_mode_query_param_renders_card_active(client: TestClient):
    """Tab switch must work even without JS via ?mode=card."""
    response = client.get("/learn/clause-1?mode=card")
    assert response.status_code == 200
    html = response.text
    assert 'data-mode="card"' in html
    assert 'data-learn-mode="card"' in html
    assert 'aria-selected="true"' in html
    # Card tab marked active
    assert 'mode-tab is-active"\n      role="tab"\n      aria-selected="true"\n      data-learn-mode="card"' in html or (
        'data-learn-mode="card"' in html and "is-active" in html
    )
    assert "Recite it, then tap to check" in html
    assert "(1) No person shall be convicted" in html


def test_card_css_drives_panel_visibility(client: TestClient):
    css = client.get("/static/styles.css?v=sprint30c")
    assert css.status_code == 200
    text = css.text
    assert '.learn[data-mode="card"] .learn-panel-card' in text
    assert ".learn-panel-card" in text
    assert "display: none" in text


def test_card_face_shows_title_and_hides_stem_panel(client: TestClient):
    response = client.get("/learn/clause-1?mode=card")
    html = response.text
    assert "learn-card-title" in html
    assert "Article 20(1)" in html
    card_start = html.index('data-learn-panel="card"')
    card_chunk = html[card_start : card_start + 1200]
    assert "learn-stem" not in card_chunk
