"""Deterministic reminder engine over learning units (Sprint 3)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Iterable, Mapping

from constitution_memorizer.learning.schemas import LearningUnit, LearningUnitsDocument
from constitution_memorizer.progress.db import open_progress_db
from constitution_memorizer.progress.repository import (
    ProgressRecord,
    ProgressRepository,
    SplitMode,
)
from constitution_memorizer.utils.json_io import read_json

# Fixed revision ladder (days). Completing at the top rung → mastered.
INTERVAL_LADDER: tuple[int, ...] = (1, 3, 7, 14, 30, 60)
DEFAULT_EASE_FACTOR = 2.5


def advance_interval(current_interval_days: int) -> int | None:
    """
    Return the next ladder interval, or None when the unit should be mastered.

    - new / 0 → 1
    - 1 → 3 → 7 → 14 → 30 → 60
    - already at 60 → None (mastered on this completion)
    """
    if current_interval_days <= 0:
        return INTERVAL_LADDER[0]
    if current_interval_days in INTERVAL_LADDER:
        index = INTERVAL_LADDER.index(current_interval_days)
        if index + 1 >= len(INTERVAL_LADDER):
            return None
        return INTERVAL_LADDER[index + 1]
    # Snap upward to the next rung if an unexpected value appears.
    for rung in INTERVAL_LADDER:
        if rung > current_interval_days:
            return rung
    return None


@dataclass(frozen=True)
class MarkDoneResult:
    """Result of marking a unit complete."""

    unit_id: str
    progress: ProgressRecord
    next_unit_id: str | None


class ReminderEngine:
    """
    Schedule revisions by learning_unit_id using a fixed day ladder.

    Next-unit resolution respects split_preference:
    - whole (default): follow LearningUnit.next_unit (clause-level chain)
    - letters: walk letter_sequence_* among SUBCLAUSE children
    """

    def __init__(
        self,
        repo: ProgressRepository,
        units: Mapping[str, LearningUnit],
    ) -> None:
        self.repo = repo
        self.units = dict(units)

    @classmethod
    def from_paths(
        cls,
        db_path: Path | str,
        units_path: Path | str,
    ) -> ReminderEngine:
        conn = open_progress_db(db_path)
        doc = LearningUnitsDocument.model_validate(read_json(Path(units_path)))
        catalog = {u.id: u for u in doc.units}
        return cls(ProgressRepository(conn), catalog)

    @classmethod
    def from_units(
        cls,
        db_path: Path | str,
        units: Iterable[LearningUnit],
    ) -> ReminderEngine:
        conn = open_progress_db(db_path)
        catalog = {u.id: u for u in units}
        return cls(ProgressRepository(conn), catalog)

    def get_unit(self, unit_id: str) -> LearningUnit | None:
        return self.units.get(unit_id)

    def set_split_preference(self, parent_clause_id: str, mode: SplitMode) -> None:
        self.repo.set_split_preference(parent_clause_id, mode)

    def get_split_preference(self, parent_clause_id: str) -> SplitMode | None:
        return self.repo.get_split_preference(parent_clause_id)

    def mark_done(
        self,
        unit_id: str,
        *,
        as_of: date | None = None,
    ) -> MarkDoneResult:
        """Advance the interval ladder for unit_id and return preference-aware next id."""
        if unit_id not in self.units:
            raise KeyError(f"Unknown learning unit id: {unit_id}")

        today = as_of or date.today()
        current = self.repo.ensure_progress(unit_id)
        if current.status == "mastered":
            progress = current
        else:
            nxt = advance_interval(current.interval_days)
            times = current.times_completed + 1
            if nxt is None:
                progress = self.repo.upsert_progress(
                    unit_id=unit_id,
                    status="mastered",
                    times_completed=times,
                    last_completed=today,
                    next_revision=None,
                    interval_days=INTERVAL_LADDER[-1],
                    ease_factor=DEFAULT_EASE_FACTOR,
                )
            else:
                progress = self.repo.upsert_progress(
                    unit_id=unit_id,
                    status="review",
                    times_completed=times,
                    last_completed=today,
                    next_revision=today + timedelta(days=nxt),
                    interval_days=nxt,
                    ease_factor=DEFAULT_EASE_FACTOR,
                )

        return MarkDoneResult(
            unit_id=unit_id,
            progress=progress,
            next_unit_id=self.resolve_next_unit_id(unit_id),
        )

    def resolve_next_unit_id(self, unit_id: str) -> str | None:
        """
        Preference-aware successor after studying unit_id.

        - SUBCLAUSE: letter_sequence_next, else parent clause's global next
        - CLAUSE with letters preference: first letter child
        - Otherwise: LearningUnit.next_unit, entering a letter path when the
          successor clause has preference ``letters``
        """
        unit = self.units.get(unit_id)
        if unit is None:
            return None

        # Letter path walk.
        if unit.parent_clause_id:
            if unit.letter_sequence_next:
                return unit.letter_sequence_next
            parent = self.units.get(unit.parent_clause_id)
            return self._apply_entry_preference(parent.next_unit if parent else None)

        if unit.allows_letter_split and unit.child_unit_ids:
            mode = self.repo.get_split_preference(unit.id) or "whole"
            if mode == "letters":
                return unit.child_unit_ids[0]

        return self._apply_entry_preference(unit.next_unit)

    def _apply_entry_preference(self, candidate_id: str | None) -> str | None:
        """If candidate is a split-capable clause preferred as letters, enter children."""
        if not candidate_id:
            return None
        candidate = self.units.get(candidate_id)
        if candidate is None:
            return candidate_id
        if candidate.allows_letter_split and candidate.child_unit_ids:
            mode = self.repo.get_split_preference(candidate.id) or "whole"
            if mode == "letters":
                return candidate.child_unit_ids[0]
        return candidate_id

    def next_to_learn_from_clause(self, parent_clause_id: str) -> str | None:
        """
        Entry point after a split choice: whole → clause itself; letters → first child.
        """
        return self._apply_entry_preference(parent_clause_id) or parent_clause_id

    def due_today(
        self,
        as_of: date | None = None,
        *,
        include_new: bool = False,
    ) -> list[ProgressRecord]:
        today = as_of or date.today()
        return self.repo.list_due(today, include_new=include_new)

    def due_unit_ids(
        self,
        as_of: date | None = None,
        *,
        include_new: bool = False,
    ) -> list[str]:
        return [r.learning_unit_id for r in self.due_today(as_of, include_new=include_new)]

    def stats(self) -> dict[str, int]:
        counts = self.repo.count_by_status()
        return {
            "new": counts.get("new", 0),
            "review": counts.get("review", 0),
            "mastered": counts.get("mastered", 0),
            "tracked": sum(counts.values()),
            "split_preferences": len(self.repo.list_split_preferences()),
        }
