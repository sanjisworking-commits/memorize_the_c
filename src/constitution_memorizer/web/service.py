"""Home / learn navigation helpers over ReminderEngine."""

from __future__ import annotations

from datetime import date

from constitution_memorizer.learning.schemas import LearningUnit, LearningUnitType
from constitution_memorizer.progress.scheduler import ReminderEngine
from constitution_memorizer.web.card_readiness import is_learn_ready


def unit_visible_for_preference(engine: ReminderEngine, unit: LearningUnit) -> bool:
    """Hide clause-or-letter units that conflict with the chosen split mode."""
    if unit.type == LearningUnitType.SUBCLAUSE and unit.parent_clause_id:
        mode = engine.get_split_preference(unit.parent_clause_id) or "whole"
        return mode == "letters"
    if unit.allows_letter_split:
        mode = engine.get_split_preference(unit.id) or "whole"
        if mode == "letters":
            return False
    return True


def resolve_learn_target(engine: ReminderEngine, unit_id: str) -> str:
    unit = engine.get_unit(unit_id)
    if unit is None:
        return unit_id
    if unit.allows_letter_split:
        mode = engine.get_split_preference(unit.id) or "whole"
        if mode == "letters":
            return engine.next_to_learn_from_clause(unit.id) or unit_id
    return unit_id


def needs_split_choice(engine: ReminderEngine, unit: LearningUnit) -> bool:
    return bool(
        unit.allows_letter_split
        and engine.get_split_preference(unit.id) is None
    )


def due_checklist(
    engine: ReminderEngine,
    *,
    as_of: date | None = None,
) -> list[LearningUnit]:
    """Due review units: preference + Learn readiness."""
    today = as_of or date.today()
    items: list[LearningUnit] = []
    for record in engine.due_today(as_of=today):
        unit = engine.get_unit(record.learning_unit_id)
        if unit is None:
            continue
        if not unit_visible_for_preference(engine, unit):
            continue
        if not is_learn_ready(unit):
            continue
        items.append(unit)
    return items


def continue_unit_id(
    engine: ReminderEngine,
    *,
    as_of: date | None = None,
) -> str | None:
    """First non-mastered ready chain unit."""
    today = as_of or date.today()
    chain = sorted(
        (u for u in engine.units.values() if u.revision_order > 0),
        key=lambda u: u.revision_order,
    )
    for unit in chain:
        if not unit_visible_for_preference(engine, unit):
            continue
        if unit.allows_letter_split:
            mode = engine.get_split_preference(unit.id)
            if mode is None:
                return unit.id
            if mode == "letters":
                target_id = engine.next_to_learn_from_clause(unit.id) or unit.id
                target = engine.get_unit(target_id)
                if target is None:
                    continue
                unit = target

        if not is_learn_ready(unit):
            continue

        progress = engine.repo.get_progress(unit.id)
        if progress is None or progress.status == "new":
            return unit.id
        if progress.status == "mastered":
            continue
        if (
            progress.status == "review"
            and progress.next_revision is not None
            and progress.next_revision <= today
        ):
            return unit.id
        if progress.status == "review":
            continue
    return None
