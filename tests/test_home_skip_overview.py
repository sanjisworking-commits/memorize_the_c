"""Sprint 29 — Home skips Part Overview."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from constitution_memorizer.progress.scheduler import ReminderEngine
from constitution_memorizer.web.service import continue_unit_id, due_checklist

MINI_UNITS = Path(__file__).parent / "fixtures" / "learning" / "mini_units.json"


def test_continue_skips_part_overview(tmp_path: Path):
    engine = ReminderEngine.from_paths(tmp_path / "p.db", MINI_UNITS)
    cid = continue_unit_id(engine)
    assert cid == "clause-1"
    assert cid != "part-overview"


def test_due_checklist_skips_part_overview(tmp_path: Path):
    engine = ReminderEngine.from_paths(tmp_path / "p.db", MINI_UNITS)
    engine.mark_done("part-overview", as_of=date(2026, 7, 19))
    # Overview due tomorrow path — mark and force due
    # After mark_done, overview is review with next_revision; if due, still filtered
    due = due_checklist(engine, as_of=date(2026, 7, 20))
    assert all(u.type.value != "PART_OVERVIEW" for u in due)
    assert all(u.id != "part-overview" for u in due)
