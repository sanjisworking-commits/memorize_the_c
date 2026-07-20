"""Sprint 3 tests for SQLite progress and ReminderEngine."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest

from constitution_memorizer.learning.schemas import LearningUnit, LearningUnitType
from constitution_memorizer.progress.db import open_progress_db
from constitution_memorizer.progress.repository import ProgressRepository
from constitution_memorizer.progress.scheduler import (
    INTERVAL_LADDER,
    ReminderEngine,
    advance_interval,
)


def _unit(
    unit_id: str,
    *,
    unit_type: LearningUnitType = LearningUnitType.CLAUSE,
    next_unit: str | None = None,
    previous_unit: str | None = None,
    allows_letter_split: bool = False,
    child_unit_ids: list[str] | None = None,
    parent_clause_id: str | None = None,
    letter_sequence_next: str | None = None,
    letter_sequence_prev: str | None = None,
    revision_order: int = 0,
) -> LearningUnit:
    return LearningUnit(
        id=unit_id,
        type=unit_type,
        display_title=unit_id,
        text=f"Text for {unit_id}",
        estimated_learning_time=30,
        next_unit=next_unit,
        previous_unit=previous_unit,
        revision_order=revision_order,
        allows_letter_split=allows_letter_split,
        child_unit_ids=child_unit_ids or [],
        parent_clause_id=parent_clause_id,
        letter_sequence_next=letter_sequence_next,
        letter_sequence_prev=letter_sequence_prev,
    )


@pytest.fixture
def catalog() -> dict[str, LearningUnit]:
    """
    Chain: overview → clause-1 → clause-2(split a,b) → article-end

    Global next links are clause-level; letter units link among themselves.
    """
    units = [
        _unit(
            "part-overview",
            unit_type=LearningUnitType.PART_OVERVIEW,
            next_unit="clause-1",
            revision_order=1,
        ),
        _unit(
            "clause-1",
            next_unit="clause-2",
            previous_unit="part-overview",
            revision_order=2,
        ),
        _unit(
            "clause-2",
            next_unit="article-end",
            previous_unit="clause-1",
            revision_order=3,
            allows_letter_split=True,
            child_unit_ids=["clause-2-a", "clause-2-b"],
        ),
        _unit(
            "clause-2-a",
            unit_type=LearningUnitType.SUBCLAUSE,
            parent_clause_id="clause-2",
            letter_sequence_next="clause-2-b",
        ),
        _unit(
            "clause-2-b",
            unit_type=LearningUnitType.SUBCLAUSE,
            parent_clause_id="clause-2",
            letter_sequence_prev="clause-2-a",
        ),
        _unit(
            "article-end",
            unit_type=LearningUnitType.ARTICLE,
            previous_unit="clause-2",
            revision_order=4,
        ),
    ]
    return {u.id: u for u in units}


@pytest.fixture
def engine(tmp_path: Path, catalog: dict[str, LearningUnit]) -> ReminderEngine:
    db = tmp_path / "progress.db"
    return ReminderEngine.from_units(db, catalog.values())


def test_interval_ladder_and_mastered_sentinel():
    assert advance_interval(0) == 1
    assert advance_interval(1) == 3
    assert advance_interval(3) == 7
    assert advance_interval(7) == 14
    assert advance_interval(14) == 30
    assert advance_interval(30) == 60
    assert advance_interval(60) is None
    assert INTERVAL_LADDER == (1, 3, 7, 14, 30, 60)


def test_mark_done_advances_new_to_review_intervals(engine: ReminderEngine):
    day0 = date(2026, 7, 20)
    result = engine.mark_done("clause-1", as_of=day0)
    assert result.progress.status == "review"
    assert result.progress.interval_days == 1
    assert result.progress.times_completed == 1
    assert result.progress.last_completed == day0
    assert result.progress.next_revision == day0 + timedelta(days=1)
    assert result.next_unit_id == "clause-2"

    day1 = day0 + timedelta(days=1)
    result2 = engine.mark_done("clause-1", as_of=day1)
    assert result2.progress.interval_days == 3
    assert result2.progress.next_revision == day1 + timedelta(days=3)
    assert result2.progress.times_completed == 2


def test_mark_done_reaches_mastered_after_top_rung(engine: ReminderEngine):
    day = date(2026, 1, 1)
    # Climb 1→3→7→14→30→60 then one more completion masters.
    for expected in (1, 3, 7, 14, 30, 60):
        result = engine.mark_done("clause-1", as_of=day)
        assert result.progress.status == "review"
        assert result.progress.interval_days == expected
        day = result.progress.next_revision  # type: ignore[assignment]

    mastered = engine.mark_done("clause-1", as_of=day)
    assert mastered.progress.status == "mastered"
    assert mastered.progress.next_revision is None
    assert mastered.progress.interval_days == 60
    assert mastered.progress.times_completed == 7

    # Idempotent-ish: further done keeps mastered.
    again = engine.mark_done("clause-1", as_of=day + timedelta(days=1))
    assert again.progress.status == "mastered"
    assert again.progress.times_completed == 7


def test_due_today_lists_review_rows(engine: ReminderEngine):
    day0 = date(2026, 7, 20)
    engine.mark_done("clause-1", as_of=day0)
    assert engine.due_unit_ids(as_of=day0) == []
    assert engine.due_unit_ids(as_of=day0 + timedelta(days=1)) == ["clause-1"]

    stats = engine.stats()
    assert stats["review"] == 1
    assert stats["mastered"] == 0
    assert stats["tracked"] == 1


def test_split_preference_crud(engine: ReminderEngine):
    assert engine.get_split_preference("clause-2") is None
    engine.set_split_preference("clause-2", "letters")
    assert engine.get_split_preference("clause-2") == "letters"
    engine.set_split_preference("clause-2", "whole")
    assert engine.get_split_preference("clause-2") == "whole"
    engine.repo.delete_split_preference("clause-2")
    assert engine.get_split_preference("clause-2") is None


def test_next_unit_whole_vs_letters(engine: ReminderEngine):
    # Default whole: clause-1 → clause-2
    assert engine.mark_done("clause-1", as_of=date(2026, 7, 1)).next_unit_id == "clause-2"
    assert engine.next_to_learn_from_clause("clause-2") == "clause-2"

    engine.set_split_preference("clause-2", "letters")
    # Entering the split clause prefers first letter.
    assert engine.mark_done("part-overview", as_of=date(2026, 7, 2)).next_unit_id == "clause-1"
    assert engine.resolve_next_unit_id("clause-1") == "clause-2-a"
    assert engine.next_to_learn_from_clause("clause-2") == "clause-2-a"

    # Walk letters then resume global chain at article-end.
    assert engine.resolve_next_unit_id("clause-2-a") == "clause-2-b"
    assert engine.resolve_next_unit_id("clause-2-b") == "article-end"

    # Completing the parent under letters preference points into letters.
    assert engine.resolve_next_unit_id("clause-2") == "clause-2-a"


def test_schema_tables_exist(tmp_path: Path):
    conn = open_progress_db(tmp_path / "p.db")
    tables = {
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    assert "learning_unit_progress" in tables
    assert "split_preference" in tables
    repo = ProgressRepository(conn)
    repo.ensure_progress("x")
    assert repo.get_progress("x") is not None
