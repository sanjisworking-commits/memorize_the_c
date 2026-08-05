"""Study reminder digest — Constitution + Memory log."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from constitution_memorizer.notifications.digest import build_study_digest
from constitution_memorizer.progress.memory import MemoryEngine
from constitution_memorizer.progress.scheduler import ReminderEngine

MINI_UNITS = Path(__file__).parent / "fixtures" / "learning" / "mini_units.json"


def test_digest_lists_due_units(tmp_path: Path):
    engine = ReminderEngine.from_paths(tmp_path / "p.db", MINI_UNITS)
    today = date(2026, 7, 20)
    # Complete yesterday so 1-day review is due today
    engine.mark_all_modes_seen("clause-1")
    engine.mark_done("clause-1", as_of=date(2026, 7, 19))
    digest = build_study_digest(engine, as_of=today, include_continue=False)
    assert digest.due_count == 1
    assert "Article 20(1)" in digest.titles[0]
    assert "1 due" in digest.notification_title()
    assert "due today" not in digest.notification_title()
    assert "•" in digest.notification_body()


def test_digest_empty_skips_noise(tmp_path: Path):
    engine = ReminderEngine.from_paths(tmp_path / "p.db", MINI_UNITS)
    digest = build_study_digest(
        engine, as_of=date(2026, 7, 20), include_continue=True
    )
    assert digest.is_empty
    assert "all caught up" in digest.notification_title()


def test_digest_includes_memory_only(tmp_path: Path):
    db = tmp_path / "p.db"
    engine = ReminderEngine.from_paths(db, MINI_UNITS)
    memory = MemoryEngine.from_db_path(db)
    today = date(2026, 7, 20)
    entry = memory.create(
        title="UNESCO sites",
        acronym="ABCD",
        logged_date=today - timedelta(days=1),
    )
    assert entry.next_revision == today
    digest = build_study_digest(
        engine, as_of=today, include_continue=False, memory=memory
    )
    assert digest.constitution_due_count == 0
    assert digest.memory_due_count == 1
    assert digest.due_count == 1
    assert "UNESCO sites (ABCD)" in digest.memory_titles
    body = digest.notification_body()
    assert "• UNESCO sites (ABCD)" in body
    assert "Constitution:" not in body
    assert "1 due" in digest.notification_title()


def test_digest_constitution_and_memory_sections(tmp_path: Path):
    db = tmp_path / "p.db"
    engine = ReminderEngine.from_paths(db, MINI_UNITS)
    memory = MemoryEngine.from_db_path(db)
    today = date(2026, 7, 20)
    engine.mark_all_modes_seen("clause-1")
    engine.mark_done("clause-1", as_of=date(2026, 7, 19))
    memory.create(
        title="Duties acronym",
        acronym="FD",
        logged_date=today - timedelta(days=2),
    )
    digest = build_study_digest(
        engine, as_of=today, include_continue=False, memory=memory
    )
    assert digest.due_count == 2
    body = digest.notification_body()
    assert "Constitution:" in body
    assert "Memory log:" in body
    assert "Article 20(1)" in body
    assert "Duties acronym (FD)" in body
    assert "2 due" in digest.notification_title()


def test_digest_memory_overdue_included(tmp_path: Path):
    db = tmp_path / "p.db"
    engine = ReminderEngine.from_paths(db, MINI_UNITS)
    memory = MemoryEngine.from_db_path(db)
    today = date(2026, 7, 20)
    memory.create(
        title="Old list",
        logged_date=today - timedelta(days=5),
    )
    digest = build_study_digest(
        engine, as_of=today, include_continue=False, memory=memory
    )
    assert digest.memory_due_count == 1
    assert "Old list" in digest.memory_titles[0]
