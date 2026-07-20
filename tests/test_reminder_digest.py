"""Sprint 24 — study reminder digest."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from constitution_memorizer.notifications.digest import build_study_digest
from constitution_memorizer.progress.scheduler import ReminderEngine

MINI_UNITS = Path(__file__).parent / "fixtures" / "learning" / "mini_units.json"


def test_digest_lists_due_units(tmp_path: Path):
    engine = ReminderEngine.from_paths(tmp_path / "p.db", MINI_UNITS)
    today = date(2026, 7, 20)
    # Complete yesterday so 1-day review is due today
    engine.mark_done("clause-1", as_of=date(2026, 7, 19))
    digest = build_study_digest(engine, as_of=today, include_continue=False)
    assert digest.due_count == 1
    assert "Article 20(1)" in digest.titles[0]
    assert "1 due today" in digest.notification_title()
    assert "•" in digest.notification_body()


def test_digest_empty_skips_noise(tmp_path: Path):
    engine = ReminderEngine.from_paths(tmp_path / "p.db", MINI_UNITS)
    digest = build_study_digest(
        engine, as_of=date(2026, 7, 20), include_continue=True
    )
    assert digest.is_empty
    assert "all caught up" in digest.notification_title()
