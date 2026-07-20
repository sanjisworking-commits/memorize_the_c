"""Home / learn navigation helpers over ReminderEngine."""

from __future__ import annotations

from datetime import date

from constitution_memorizer.learning.schemas import LearningUnit, LearningUnitType
from constitution_memorizer.progress.scheduler import ReminderEngine


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
    """
    Map a requested unit id to the concrete learn target.

    Split-capable clauses with no preference should be handled by the choose route
    before calling this.
    """
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
    """Due review units, filtered by split preferences."""
    today = as_of or date.today()
    items: list[LearningUnit] = []
    for record in engine.due_today(as_of=today):
        unit = engine.get_unit(record.learning_unit_id)
        if unit is None:
            continue
        if not unit_visible_for_preference(engine, unit):
            continue
        items.append(unit)
    return items


def continue_unit_id(
    engine: ReminderEngine,
    *,
    as_of: date | None = None,
) -> str | None:
    """First non-mastered chain unit, respecting letter preferences."""
    today = as_of or date.today()
    chain = sorted(
        (u for u in engine.units.values() if u.revision_order > 0),
        key=lambda u: u.revision_order,
    )
    for unit in chain:
        if not unit_visible_for_preference(engine, unit):
            continue
        target_id = unit.id
        if unit.allows_letter_split:
            mode = engine.get_split_preference(unit.id)
            if mode is None:
                return unit.id  # send to choose via /learn
            if mode == "letters":
                target_id = engine.next_to_learn_from_clause(unit.id) or unit.id
                target = engine.get_unit(target_id)
                if target is None:
                    continue
                unit = target

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
        # In review but not yet due — keep scanning for a new unit further along.
        if progress.status == "review":
            continue
    return None


def unit_type_label(unit: LearningUnit) -> str:
    return unit.type.value if isinstance(unit.type, LearningUnitType) else str(unit.type)


def earliest_upcoming_revision(
    engine: ReminderEngine,
    *,
    as_of: date | None = None,
) -> date | None:
    """Soonest next_revision strictly after as_of (for Home 'caught up' copy)."""
    today = as_of or date.today()
    row = engine.repo.conn.execute(
        """
        SELECT next_revision FROM learning_unit_progress
        WHERE status = 'review'
          AND next_revision IS NOT NULL
          AND next_revision > ?
        ORDER BY next_revision ASC
        LIMIT 1
        """,
        (today.isoformat(),),
    ).fetchone()
    if row is None or row["next_revision"] is None:
        return None
    return date.fromisoformat(str(row["next_revision"]))


def home_lede(*, due_count: int, has_continue: bool) -> str:
    if due_count == 1:
        return "1 unit due for review."
    if due_count > 1:
        return f"{due_count} units due for review."
    if has_continue:
        return "Nothing due today — continue along the Constitution."
    return "Nothing due today."
