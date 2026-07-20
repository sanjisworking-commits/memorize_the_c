"""Card contracts: required fields + quality checks before UI render."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from constitution_memorizer.learning.schemas import LearningUnit, LearningUnitType
from constitution_memorizer.web.browse import ArticleBrowseView

_GARBAGE_TITLE = re.compile(
    r"(w\.e\.f\.|DEMOCRATIC REPUBLIC\"|^\s*\]\s*$)",
    re.IGNORECASE,
)
_GARBAGE_BODY = re.compile(
    r"(^\s*1-19\d{2}\)\.\s*$|^\s*\]\s*\n\s*\]\s*$)",
    re.IGNORECASE | re.MULTILINE,
)
_OMITTED_TAG = re.compile(r"\bomitted\b|\brepealed\b", re.IGNORECASE)


@dataclass
class ReadinessResult:
    """Outcome of checking a card against its contract."""

    ok: bool
    card: str
    subject_id: str
    missing_fields: list[str] = field(default_factory=list)
    quality_flags: list[str] = field(default_factory=list)

    @property
    def reasons(self) -> list[str]:
        return [
            *[f"missing:{name}" for name in self.missing_fields],
            *self.quality_flags,
        ]


def type_label(unit: LearningUnit) -> str:
    """Human-readable unit type for templates."""
    return unit.type.value if isinstance(unit.type, LearningUnitType) else str(unit.type)


def part_label_from_tags(tags: list[str]) -> str | None:
    for tag in tags:
        if tag.lower().startswith("part "):
            return tag
    return None


def _alpha_ratio(text: str) -> float:
    letters = sum(1 for ch in text if ch.isalpha())
    return letters / max(len(text), 1)


def _has_duplicate_paragraphs(text: str) -> bool:
    parts = [p.strip() for p in re.split(r"\n+", text) if p.strip()]
    if len(parts) < 2:
        # Also catch exact doubled single-block text.
        half = len(text) // 2
        if half >= 40 and text[:half].strip() == text[half:].strip():
            return True
        return False
    return len(parts) != len(set(parts))


def _truncated_open_clause(text: str) -> bool:
    """True when body ends mid-list (colon/dash) with no following proviso/items."""
    stripped = text.strip()
    if not stripped:
        return False
    if stripped.endswith((":", "-", "—", "–")):
        return True
    # "(1) … Panchayats:" style already covered; also bare "make provisions-"
    return bool(re.search(r"\b(provisions?|namely|follows?)\s*:\s*$", stripped, re.I))


def check_learn_unit(unit: LearningUnit) -> ReadinessResult:
    """Contract for Learn / Home checklist cards."""
    missing: list[str] = []
    flags: list[str] = []

    if not unit.id:
        missing.append("id")
    if unit.type is None:
        missing.append("type")
    if not (unit.display_title or "").strip():
        missing.append("display_title")
    if unit.estimated_learning_time < 1:
        missing.append("estimated_learning_time")

    text = (unit.text or "").strip()
    title = (unit.title or "").strip()
    tags_blob = " ".join(unit.tags or [])
    is_omitted = bool(_OMITTED_TAG.search(tags_blob)) or (
        title.lower().endswith("[omitted.]") if title else False
    )
    # Part overviews are title banners; letter stubs are often short by design.
    short_ok = unit.type in (
        LearningUnitType.PART_OVERVIEW,
        LearningUnitType.SUBCLAUSE,
    )

    if not text:
        missing.append("text")
    else:
        if len(text) < 40 and not is_omitted and not short_ok:
            flags.append("too_short")
        if (
            title
            and text.replace(" ", "") == title.replace(" ", "")
            and not is_omitted
            and unit.type != LearningUnitType.PART_OVERVIEW
        ):
            flags.append("title_only")
        if _has_duplicate_paragraphs(text):
            flags.append("duplicate_paragraphs")
        if _alpha_ratio(text) < 0.5 and not is_omitted:
            flags.append("low_alpha_ratio")
        if _GARBAGE_BODY.search(text) or (title and _GARBAGE_TITLE.search(title)):
            flags.append("garbage_fragment")
        if _truncated_open_clause(text):
            flags.append("truncated_open_clause")

    ok = not missing and not flags
    return ReadinessResult(
        ok=ok,
        card="learn",
        subject_id=unit.id or "",
        missing_fields=missing,
        quality_flags=flags,
    )


def check_browse_article(view: ArticleBrowseView) -> ReadinessResult:
    """Contract for Browse article body."""
    missing: list[str] = []
    flags: list[str] = []
    if not view.article_number:
        missing.append("article_number")
    text = (view.full_text or "").strip()
    title = (view.title or "").strip()
    if not text:
        missing.append("full_text")
    else:
        if len(text) < 40:
            flags.append("too_short")
        if _has_duplicate_paragraphs(text):
            flags.append("duplicate_paragraphs")
        if _GARBAGE_BODY.search(text) or (title and _GARBAGE_TITLE.search(title)):
            flags.append("garbage_fragment")
        if _truncated_open_clause(text):
            flags.append("truncated_open_clause")
    if title and _GARBAGE_TITLE.search(title):
        if "garbage_fragment" not in flags:
            flags.append("garbage_fragment")
    return ReadinessResult(
        ok=not missing and not flags,
        card="browse",
        subject_id=f"article-{view.article_number}",
        missing_fields=missing,
        quality_flags=flags,
    )


def check_choose_unit(
    unit: LearningUnit,
    *,
    children: list[LearningUnit],
) -> ReadinessResult:
    """Contract for the whole-vs-letters Choose screen.

    Each child must resolve and pass Learn readiness (SUBCLAUSE stubs are
    exempt from length heuristics inside check_learn_unit).
    """
    missing: list[str] = []
    flags: list[str] = []
    if not unit.allows_letter_split:
        flags.append("not_split_capable")
    if not unit.child_unit_ids:
        missing.append("child_unit_ids")
    if not (unit.display_title or "").strip():
        missing.append("display_title")
    if len(children) != len(unit.child_unit_ids):
        flags.append("unresolved_child_ids")
    for child in children:
        child_result = check_learn_unit(child)
        if not child_result.ok:
            flags.append(f"child_not_ready:{child.id}")
            break
    return ReadinessResult(
        ok=not missing and not flags,
        card="choose",
        subject_id=unit.id,
        missing_fields=missing,
        quality_flags=flags,
    )


def is_learn_ready(unit: LearningUnit) -> bool:
    return check_learn_unit(unit).ok


def summarize_readiness(units: list[LearningUnit]) -> dict[str, int | dict[str, int]]:
    """Counts of ready/unready units and quality-flag frequencies."""
    ready = 0
    unready = 0
    flag_counts: dict[str, int] = {}
    for unit in units:
        result = check_learn_unit(unit)
        if result.ok:
            ready += 1
            continue
        unready += 1
        for flag in result.quality_flags:
            flag_counts[flag] = flag_counts.get(flag, 0) + 1
        for name in result.missing_fields:
            key = f"missing:{name}"
            flag_counts[key] = flag_counts.get(key, 0) + 1
    return {
        "ready": ready,
        "unready": unready,
        "flags": dict(sorted(flag_counts.items(), key=lambda item: (-item[1], item[0]))),
    }


def status_label(*, ready: bool, raw_status: str | None) -> str:
    """Human Browse status line."""
    if not ready:
        return "Incomplete extraction"
    if not raw_status:
        return "Active"
    normalized = raw_status.strip().lower()
    if normalized in {"", "unknown"}:
        return "Active"
    return normalized.replace("_", " ").capitalize()
