"""Home / learn navigation helpers over ReminderEngine."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from constitution_memorizer.learning.schemas import LearningUnit, LearningUnitType
from constitution_memorizer.progress.repository import LEARN_MODES_SET
from constitution_memorizer.progress.scheduler import ReminderEngine

_CHIP_LABEL_RE = re.compile(r"\([^)]+\)")


@dataclass(frozen=True)
class SiblingChip:
    """One chip in the Learn sibling / letter rail."""

    unit_id: str
    label: str
    state: str  # current | done | idle


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
    """Due review units, filtered by split preferences (no Part Overview)."""
    today = as_of or date.today()
    items: list[LearningUnit] = []
    for record in engine.due_today(as_of=today):
        unit = engine.get_unit(record.learning_unit_id)
        if unit is None:
            continue
        if unit.type == LearningUnitType.PART_OVERVIEW:
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
    """First non-mastered chain unit, skipping Part Overview; respects letter prefs."""
    today = as_of or date.today()
    chain = sorted(
        (u for u in engine.units.values() if u.revision_order > 0),
        key=lambda u: u.revision_order,
    )
    for unit in chain:
        if unit.type == LearningUnitType.PART_OVERVIEW:
            continue
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


def part_label_from_tags(tags: list[str] | None) -> str | None:
    for tag in tags or []:
        if tag.lower().startswith("part "):
            return tag
    return None


def kind_badge_label(unit: LearningUnit) -> str:
    """Prototype badge: Article / Clause / Subclause (not enum SCREAMING)."""
    raw = unit_type_label(unit)
    mapping = {
        "ARTICLE": "Article",
        "CLAUSE": "Clause",
        "SUBCLAUSE": "Subclause",
        "PART_OVERVIEW": "Part",
        "SCHEDULE_ENTRY": "Schedule",
    }
    return mapping.get(raw, raw.replace("_", " ").title())


def unit_crumb(unit: LearningUnit) -> str:
    """Breadcrumb under the type badge (Part · Article …)."""
    parts: list[str] = []
    part = part_label_from_tags(unit.tags)
    if part:
        parts.append(part)
    title = (unit.title or "").strip()
    if unit.type == LearningUnitType.SUBCLAUSE and unit.article_number:
        parts.append(f"Article {unit.article_number}")
        if title:
            parts.append(title)
    elif unit.type == LearningUnitType.CLAUSE and unit.article_number:
        art = f"Article {unit.article_number}"
        if title:
            parts.append(f"{art} — {title}")
        else:
            parts.append(art)
    elif title and unit.type == LearningUnitType.ARTICLE:
        # Title already shown as lede; crumb stays Part-only when possible.
        pass
    elif title and not parts:
        parts.append(title)
    return " · ".join(parts)


def session_progress(
    engine: ReminderEngine,
    unit: LearningUnit,
) -> tuple[int, int, int]:
    """
    Return (completed_count, position_1based, chain_length) for the global
    revision chain (units with revision_order > 0).
    """
    chain = sorted(
        (u for u in engine.units.values() if u.revision_order > 0),
        key=lambda u: u.revision_order,
    )
    if not chain:
        return 0, 1, 1
    completed = 0
    position = 1
    for index, item in enumerate(chain, start=1):
        progress = engine.repo.get_progress(item.id)
        if progress is not None and progress.status == "mastered":
            completed += 1
        if item.id == unit.id:
            position = index
    return completed, position, len(chain)


def learn_meta_line(
    unit: LearningUnit,
    progress: object | None,
) -> str:
    """Quiet footer meta: status · time · difficulty."""
    status = "new"
    if progress is not None:
        status = getattr(progress, "status", None) or "new"
        times = getattr(progress, "times_completed", 0) or 0
        nxt = getattr(progress, "next_revision", None)
        if status == "review" and times:
            bit = f"review · completed {times}×"
            if nxt is not None:
                bit += f" · next {nxt}"
            return (
                f"{bit} · ~{unit.estimated_learning_time}s · "
                f"difficulty {unit.difficulty}/5"
            )
        if status == "mastered":
            return (
                f"mastered · ~{unit.estimated_learning_time}s · "
                f"difficulty {unit.difficulty}/5"
            )
    return (
        f"{status} · ~{unit.estimated_learning_time}s · "
        f"difficulty {unit.difficulty}/5"
    )


def chip_label(unit: LearningUnit) -> str:
    """Clause/letter chip text from display_title — last `(…)` group."""
    matches = _CHIP_LABEL_RE.findall(unit.display_title)
    if matches:
        return matches[-1]
    return unit.display_title


def _chip_state(
    engine: ReminderEngine,
    *,
    unit_id: str,
    current_id: str,
    mark_done: bool,
) -> str:
    if unit_id == current_id:
        return "current"
    if mark_done:
        progress = engine.repo.get_progress(unit_id)
        if progress is not None and progress.status in {"mastered", "review"}:
            return "done"
        if progress is not None and (progress.times_completed or 0) > 0:
            return "done"
    return "idle"


def sibling_chips(
    engine: ReminderEngine,
    unit: LearningUnit,
) -> list[SiblingChip]:
    """
    Learn rail chips.

    - CLAUSE: sibling numbered clauses of the same article (shown when >1)
    - SUBCLAUSE: letter children of the parent clause
    """
    siblings: list[LearningUnit] = []
    mark_done = False

    if unit.type == LearningUnitType.CLAUSE and unit.article_number:
        siblings = sorted(
            (
                u
                for u in engine.units.values()
                if u.type == LearningUnitType.CLAUSE
                and u.article_number == unit.article_number
            ),
            key=lambda u: (u.revision_order, u.display_title),
        )
    elif unit.type == LearningUnitType.SUBCLAUSE and unit.parent_clause_id:
        mark_done = True
        parent = engine.get_unit(unit.parent_clause_id)
        if parent is not None:
            for child_id in parent.child_unit_ids:
                child = engine.get_unit(child_id)
                if child is not None:
                    siblings.append(child)

    if len(siblings) <= 1:
        return []

    return [
        SiblingChip(
            unit_id=item.id,
            label=chip_label(item),
            state=_chip_state(
                engine,
                unit_id=item.id,
                current_id=unit.id,
                mark_done=mark_done,
            ),
        )
        for item in siblings
    ]


def subclause_stem_text(
    engine: ReminderEngine,
    unit: LearningUnit,
) -> str | None:
    """
    Gray stem above a letter unit: parent clause text with letter bodies removed.

    Bare Act wording only — no paraphrase.
    """
    if unit.type != LearningUnitType.SUBCLAUSE or not unit.parent_clause_id:
        return None
    parent = engine.get_unit(unit.parent_clause_id)
    if parent is None or not parent.text.strip():
        return None

    remainder = parent.text
    children = [
        child
        for child_id in parent.child_unit_ids
        if (child := engine.get_unit(child_id)) is not None and child.text.strip()
    ]
    for child in sorted(children, key=lambda c: len(c.text), reverse=True):
        if child.text in remainder:
            remainder = remainder.replace(child.text, "", 1)

    cleaned = "\n".join(
        line.rstrip() for line in remainder.splitlines() if line.strip()
    ).strip()
    return cleaned or None


def done_button_label(unit: LearningUnit) -> str:
    """Prototype CTA: next letter while walking a letter sequence."""
    if unit.type == LearningUnitType.SUBCLAUSE and unit.letter_sequence_next:
        return "Done — next letter"
    return "Done — next unit"


LEARN_MODE_LABELS: dict[str, str] = {
    "read": "Read",
    "cloze": "Cloze",
    "letters": "Letters",
    "type": "Type",
    "recite": "Recite",
    "card": "Card",
}


def methods_tracker_line(seen_count: int) -> str:
    """Copy under the Learn mode tab bar (METHODS-THEME-HANDOFF)."""
    if seen_count >= len(LEARN_MODES_SET):
        return "All 6 methods visited — revision complete, mark it Done"
    return (
        f"{seen_count} of 6 methods visited · revision completes "
        "when you've been through all six"
    )


def done_button_state(unit: LearningUnit, seen: set[str]) -> dict[str, object]:
    """Locked Done until all six modes visited; unlocks on the last (Card if in order)."""
    missing = LEARN_MODES_SET - set(seen)
    remaining = len(missing)
    if remaining > 0:
        label = f"{remaining} method{'s' if remaining != 1 else ''} left"
        return {
            "unlocked": False,
            "label": label,
            "disabled": True,
            "missing": sorted(missing),
        }
    return {
        "unlocked": True,
        "label": done_button_label(unit),
        "disabled": False,
        "missing": [],
    }
