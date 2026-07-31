"""Browse due/overdue banners, count bubbles, and nav badge."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from constitution_memorizer.progress.scheduler import ReminderEngine
from constitution_memorizer.web.app import create_app
from constitution_memorizer.web.browse import (
    article_due_summaries,
    browse_due_total,
    browse_parts_sections,
)

MINI_UNITS = Path(__file__).parent / "fixtures" / "learning" / "mini_units.json"


def test_article_due_summaries_due_and_overdue(tmp_path: Path):
    engine = ReminderEngine.from_paths(tmp_path / "p.db", MINI_UNITS)
    today = date(2026, 7, 20)
    # clause-1 due today
    engine.mark_all_modes_seen("clause-1")
    engine.mark_done("clause-1", as_of=date(2026, 7, 19))
    # clause-2 overdue (next_revision yesterday)
    engine.mark_all_modes_seen("clause-2")
    engine.mark_done("clause-2", as_of=date(2026, 7, 18))
    summaries = article_due_summaries(engine, as_of=today)
    assert "20" in summaries
    # both units are Article 20
    assert summaries["20"].due_count == 2
    assert summaries["20"].due_kind == "overdue"
    assert browse_due_total(engine, as_of=today) == 2


def test_browse_parts_sections_attaches_due_fields(tmp_path: Path):
    engine = ReminderEngine.from_paths(tmp_path / "p.db", MINI_UNITS)
    today = date(2026, 7, 20)
    engine.mark_all_modes_seen("clause-1")
    engine.mark_done("clause-1", as_of=date(2026, 7, 19))
    sections = browse_parts_sections(engine, None, as_of=today)
    cards = [c for s in sections for c in s.cards]
    art20 = next(c for c in cards if c.article_number == "20")
    assert art20.due_count == 1
    assert art20.due_kind == "due"
    untouched = [c for c in cards if c.article_number != "20"]
    assert all(c.due_count == 0 and c.due_kind is None for c in untouched)


def test_browse_index_html_banner_and_nav_badge(tmp_path: Path):
    db = tmp_path / "progress.db"
    engine = ReminderEngine.from_paths(db, MINI_UNITS)
    engine.mark_all_modes_seen("clause-1")
    engine.mark_done("clause-1", as_of=date.today() - timedelta(days=1))
    client = TestClient(create_app(units_path=MINI_UNITS, db_path=db))
    home = client.get("/")
    assert home.status_code == 200
    assert "nav-due-badge" in home.text
    browse = client.get("/browse")
    assert browse.status_code == 200
    assert "browse-due-banner" in browse.text
    assert "browse-due-bubble" in browse.text
    assert "Due" in browse.text
    assert "nav-due-badge" in browse.text


def test_browse_overdue_banner_label(tmp_path: Path):
    db = tmp_path / "progress.db"
    engine = ReminderEngine.from_paths(db, MINI_UNITS)
    engine.mark_all_modes_seen("clause-1")
    engine.mark_done("clause-1", as_of=date.today() - timedelta(days=3))
    client = TestClient(create_app(units_path=MINI_UNITS, db_path=db))
    html = client.get("/browse").text
    assert "Overdue" in html
    assert "is-overdue" in html


def test_browse_no_dues_unchanged(tmp_path: Path):
    db = tmp_path / "progress.db"
    ReminderEngine.from_paths(db, MINI_UNITS)
    client = TestClient(create_app(units_path=MINI_UNITS, db_path=db))
    html = client.get("/browse").text
    assert "browse-due-banner" not in html
    assert "nav-due-badge" not in client.get("/").text
