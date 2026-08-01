"""Deterministic reminder engine over learning units (user-scoped)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Iterable, Mapping
from uuid import UUID

from constitution_memorizer.learning.schemas import LearningUnit, LearningUnitsDocument
from constitution_memorizer.progress.db import open_progress_db
from constitution_memorizer.progress.repository import (
    LEARN_MODES,
    LEARN_MODES_SET,
    NotificationFrequency,
    ProgressRecord,
    ProgressRepository,
    SplitMode,
    ThemePreference,
)
from constitution_memorizer.progress.user_ids import LOCAL_USER_ID
from constitution_memorizer.utils.json_io import read_json

INTERVAL_LADDER: tuple[int, ...] = (1, 3, 7, 14, 30, 60)
DEFAULT_EASE_FACTOR = 2.5


def advance_interval(current_interval_days: int) -> int | None:
    if current_interval_days <= 0:
        return INTERVAL_LADDER[0]
    if current_interval_days in INTERVAL_LADDER:
        index = INTERVAL_LADDER.index(current_interval_days)
        if index + 1 >= len(INTERVAL_LADDER):
            return None
        return INTERVAL_LADDER[index + 1]
    for rung in INTERVAL_LADDER:
        if rung > current_interval_days:
            return rung
    return None


@dataclass(frozen=True)
class MarkDoneResult:
    unit_id: str
    progress: ProgressRecord
    next_unit_id: str | None
    modes_complete: bool = True


class ModesIncompleteError(ValueError):
    def __init__(self, unit_id: str, seen: set[str]) -> None:
        self.unit_id = unit_id
        self.seen = frozenset(seen)
        missing = sorted(LEARN_MODES_SET - self.seen)
        super().__init__(
            f"Unit {unit_id} still needs modes: {', '.join(missing)}"
        )


class ReminderEngine:
    """
    Schedule revisions by learning_unit_id using a fixed day ladder.

    The shared learning-unit catalog is read-only. Personal data is always
    scoped through ``user_id`` (default LOCAL_USER_ID for single-tenant mode).
    Use ``for_user`` to bind a different authenticated user without cloning the catalog.
    """

    def __init__(
        self,
        repo: ProgressRepository,
        units: Mapping[str, LearningUnit],
        *,
        user_id: UUID = LOCAL_USER_ID,
    ) -> None:
        self.repo = repo
        self.units = dict(units)
        self.user_id = user_id

    def for_user(self, user_id: UUID) -> ReminderEngine:
        """Return a lightweight engine bound to ``user_id`` (shared units + repo)."""
        return ReminderEngine(self.repo, self.units, user_id=user_id)

    @classmethod
    def from_paths(
        cls,
        db_path: Path | str,
        units_path: Path | str,
        *,
        user_id: UUID = LOCAL_USER_ID,
    ) -> ReminderEngine:
        conn = open_progress_db(db_path)
        doc = LearningUnitsDocument.model_validate(read_json(Path(units_path)))
        catalog = {u.id: u for u in doc.units}
        return cls(ProgressRepository(conn), catalog, user_id=user_id)

    @classmethod
    def from_units(
        cls,
        db_path: Path | str,
        units: Iterable[LearningUnit],
        *,
        user_id: UUID = LOCAL_USER_ID,
    ) -> ReminderEngine:
        conn = open_progress_db(db_path)
        catalog = {u.id: u for u in units}
        return cls(ProgressRepository(conn), catalog, user_id=user_id)

    def get_unit(self, unit_id: str) -> LearningUnit | None:
        return self.units.get(unit_id)

    def get_progress(self, unit_id: str) -> ProgressRecord | None:
        return self.repo.get_progress(self.user_id, unit_id)

    def list_all_progress(self) -> list[ProgressRecord]:
        return self.repo.list_all_progress(self.user_id)

    def get_gloss(self, article_number: str) -> str | None:
        return self.repo.get_gloss(self.user_id, article_number)

    def upsert_gloss(self, article_number: str, text: str) -> None:
        self.repo.upsert_gloss(self.user_id, article_number, text)

    def delete_gloss(self, article_number: str) -> None:
        self.repo.delete_gloss(self.user_id, article_number)

    def delete_progress(self, unit_id: str) -> None:
        self.repo.delete_progress(self.user_id, unit_id)

    def reset_all_personal_data(self) -> None:
        self.repo.delete_all_progress(self.user_id)
        self.repo.clear_all_modes_seen(self.user_id)

    def set_split_preference(self, parent_clause_id: str, mode: SplitMode) -> None:
        self.repo.set_split_preference(self.user_id, parent_clause_id, mode)

    def get_split_preference(self, parent_clause_id: str) -> SplitMode | None:
        return self.repo.get_split_preference(self.user_id, parent_clause_id)

    def delete_split_preference(self, parent_clause_id: str) -> None:
        self.repo.delete_split_preference(self.user_id, parent_clause_id)

    def get_notification_frequency(self) -> NotificationFrequency:
        return self.repo.get_notification_frequency(self.user_id)

    def set_notification_frequency(self, frequency: NotificationFrequency) -> None:
        self.repo.set_notification_frequency(self.user_id, frequency)

    def get_theme(self) -> ThemePreference:
        return self.repo.get_theme(self.user_id)

    def set_theme(self, theme: ThemePreference) -> None:
        self.repo.set_theme(self.user_id, theme)

    def get_news_articles_raw(self) -> str:
        return self.repo.get_news_articles_raw(self.user_id)

    def set_news_articles_raw(self, value: str) -> None:
        self.repo.set_news_articles_raw(self.user_id, value)

    def mark_mode_seen(self, unit_id: str, mode: str) -> set[str]:
        if unit_id not in self.units:
            raise KeyError(f"Unknown learning unit id: {unit_id}")
        return self.repo.mark_mode_seen(self.user_id, unit_id, mode)

    def modes_seen(self, unit_id: str) -> set[str]:
        return self.repo.modes_seen(self.user_id, unit_id)

    def mark_all_modes_seen(self, unit_id: str) -> set[str]:
        seen: set[str] = set()
        for mode in LEARN_MODES:
            seen = self.mark_mode_seen(unit_id, mode)
        return seen

    def clear_modes_seen(self, unit_id: str) -> None:
        self.repo.clear_modes_seen(self.user_id, unit_id)

    def modes_complete(self, unit_id: str) -> bool:
        return self.repo.modes_complete(self.user_id, unit_id)

    def mark_done(
        self,
        unit_id: str,
        *,
        as_of: date | None = None,
        require_all_modes: bool = True,
    ) -> MarkDoneResult:
        if unit_id not in self.units:
            raise KeyError(f"Unknown learning unit id: {unit_id}")

        if require_all_modes and not self.repo.modes_complete(self.user_id, unit_id):
            raise ModesIncompleteError(unit_id, self.repo.modes_seen(self.user_id, unit_id))

        today = as_of or date.today()
        current = self.repo.ensure_progress(self.user_id, unit_id)
        if current.status == "mastered":
            progress = current
        else:
            nxt = advance_interval(current.interval_days)
            times = current.times_completed + 1
            if nxt is None:
                progress = self.repo.upsert_progress(
                    self.user_id,
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
                    self.user_id,
                    unit_id=unit_id,
                    status="review",
                    times_completed=times,
                    last_completed=today,
                    next_revision=today + timedelta(days=nxt),
                    interval_days=nxt,
                    ease_factor=DEFAULT_EASE_FACTOR,
                )

        self.repo.clear_modes_seen(self.user_id, unit_id)
        return MarkDoneResult(
            unit_id=unit_id,
            progress=progress,
            next_unit_id=self.resolve_next_unit_id(unit_id),
            modes_complete=True,
        )

    def defer_until_tomorrow(
        self,
        unit_id: str,
        *,
        as_of: date | None = None,
    ) -> MarkDoneResult:
        if unit_id not in self.units:
            raise KeyError(f"Unknown learning unit id: {unit_id}")

        today = as_of or date.today()
        current = self.repo.ensure_progress(self.user_id, unit_id)
        if current.status == "mastered":
            progress = current
        else:
            progress = self.repo.upsert_progress(
                self.user_id,
                unit_id=unit_id,
                status="review",
                times_completed=current.times_completed,
                last_completed=current.last_completed,
                next_revision=today + timedelta(days=1),
                interval_days=current.interval_days if current.interval_days > 0 else 1,
                ease_factor=current.ease_factor or DEFAULT_EASE_FACTOR,
            )

        return MarkDoneResult(
            unit_id=unit_id,
            progress=progress,
            next_unit_id=self.resolve_next_unit_id(unit_id),
        )

    def resolve_next_unit_id(self, unit_id: str) -> str | None:
        unit = self.units.get(unit_id)
        if unit is None:
            return None

        if unit.parent_clause_id:
            if unit.letter_sequence_next:
                return unit.letter_sequence_next
            parent = self.units.get(unit.parent_clause_id)
            return self._apply_entry_preference(parent.next_unit if parent else None)

        if unit.allows_letter_split and unit.child_unit_ids:
            mode = self.repo.get_split_preference(self.user_id, unit.id) or "whole"
            if mode == "letters":
                return unit.child_unit_ids[0]

        return self._apply_entry_preference(unit.next_unit)

    def _apply_entry_preference(self, candidate_id: str | None) -> str | None:
        if not candidate_id:
            return None
        candidate = self.units.get(candidate_id)
        if candidate is None:
            return candidate_id
        if candidate.allows_letter_split and candidate.child_unit_ids:
            mode = self.repo.get_split_preference(self.user_id, candidate.id) or "whole"
            if mode == "letters":
                return candidate.child_unit_ids[0]
        return candidate_id

    def next_to_learn_from_clause(self, parent_clause_id: str) -> str | None:
        return self._apply_entry_preference(parent_clause_id) or parent_clause_id

    def due_today(
        self,
        as_of: date | None = None,
        *,
        include_new: bool = False,
    ) -> list[ProgressRecord]:
        today = as_of or date.today()
        return self.repo.list_due(self.user_id, today, include_new=include_new)

    def due_unit_ids(
        self,
        as_of: date | None = None,
        *,
        include_new: bool = False,
    ) -> list[str]:
        return [r.learning_unit_id for r in self.due_today(as_of, include_new=include_new)]

    def stats(self) -> dict[str, int]:
        counts = self.repo.count_by_status(self.user_id)
        return {
            "new": counts.get("new", 0),
            "review": counts.get("review", 0),
            "mastered": counts.get("mastered", 0),
            "tracked": sum(counts.values()),
            "split_preferences": len(self.repo.list_split_preferences(self.user_id)),
        }
