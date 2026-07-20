"""Sprint 20 — Progress mastery map."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from constitution_memorizer.progress.scheduler import ReminderEngine
from constitution_memorizer.web.app import create_app
from constitution_memorizer.web.progress_stats import (
    article_mastery_state,
    progress_dashboard,
)

MINI_UNITS = Path(__file__).parent / "fixtures" / "learning" / "mini_units.json"
MINI_REVIEWED = Path(__file__).parent / "fixtures" / "learning" / "mini_reviewed.json"


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "progress.db"


@pytest.fixture
def engine(db_path: Path) -> ReminderEngine:
    return ReminderEngine.from_paths(db_path, MINI_UNITS)


@pytest.fixture
def client(db_path: Path) -> TestClient:
    app = create_app(
        units_path=MINI_UNITS,
        db_path=db_path,
        reviewed_path=MINI_REVIEWED,
    )
    return TestClient(app)


def test_progress_page_has_stat_tiles_and_mastery_map(client: TestClient):
    response = client.get("/progress")
    assert response.status_code == 200
    html = response.text
    assert "Progress" in html
    assert "Mastery map" in html
    assert "Tracked articles" in html
    assert "progress-stat-grid" in html
    assert "Tracked units" in html
    assert "Completed" in html
    assert "Mastered" in html
    assert "Remaining" in html
    assert "mastery-map" in html
    assert "Part III" in html
    assert "Fundamental Rights" in html
    assert "mastery-cell" in html
    assert "styles.css?v=sprint20" in html


def test_progress_css_mastery_cell_states(client: TestClient):
    css = client.get("/static/styles.css?v=sprint20")
    assert css.status_code == 200
    text = css.text
    assert ".mastery-cell.is-new" in text
    assert ".mastery-cell.is-learning" in text
    assert ".mastery-cell.is-review" in text
    assert ".mastery-cell.is-mastered" in text
    assert ".mastery-cell.is-due" in text
    assert "width: 16px" in text
    assert ".tracked-progress-bar" in text


def test_mastery_map_article_20_is_clickable(client: TestClient):
    html = client.get("/progress").text
    assert 'title="Article 20' in html
    assert "mastery-cell is-new is-tracked" in html or "mastery-cell is-due is-tracked" in html
    assert 'href="/learn/' in html


def test_article_states_learning_due_and_tracked_row(client: TestClient, engine: ReminderEngine):
    today = date(2026, 7, 20)
    engine.mark_done("clause-1", as_of=today)
    # Partial article 20 → learning; continue may mark due
    state = article_mastery_state(
        engine, "20", today=today, continue_id="clause-2"
    )
    assert state in {"learning", "due"}

    from constitution_memorizer.schemas import ConstitutionDocument
    from constitution_memorizer.utils.json_io import read_json

    reviewed = ConstitutionDocument.model_validate(read_json(MINI_REVIEWED))
    dash = progress_dashboard(engine, reviewed=reviewed, today=today)
    assert any(r.article_number == "20" for r in dash["tracked_rows"])
    row20 = next(r for r in dash["tracked_rows"] if r.article_number == "20")
    assert row20.completed >= 1
    assert row20.bar_percent > 0
    assert "Article 20" in row20.title

    html = client.get("/progress").text
    assert "tracked-article-row" in html
    assert "tracked-progress-bar" in html
    assert "Article 20" in html


def test_mastered_article_state(engine: ReminderEngine):
    today = date(2026, 7, 20)
    # Master every required unit for article 21 (single ARTICLE unit)
    engine.mark_done("article-end", as_of=today)
    # Climb ladder to mastered
    for _ in range(6):
        engine.mark_done("article-end", as_of=today)
    state = article_mastery_state(engine, "21", today=today, continue_id=None)
    assert state == "mastered"


def test_split_preference_still_affects_required_counts(engine: ReminderEngine):
    from constitution_memorizer.web.progress_stats import path_units_for_article

    engine.set_split_preference("clause-2", "letters")
    required, pending = path_units_for_article(engine, "20")
    assert pending is False
    assert [u.id for u in required] == ["clause-1", "clause-2-a", "clause-2-b"]
