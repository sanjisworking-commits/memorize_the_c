"""Generate Learning Units from constitution.reviewed.json (Sprint 1)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from constitution_memorizer.exceptions import InputValidationError
from constitution_memorizer.learning.schemas import (
    LearningUnit,
    LearningUnitsDocument,
    LearningUnitType,
)
from constitution_memorizer.learning.time_difficulty import (
    estimate_difficulty,
    estimate_learning_time_seconds,
)
from constitution_memorizer.schemas import (
    Article,
    ArticleStatus,
    ConstitutionDocument,
    Part,
    ProvisionNode,
    Schedule,
)
from constitution_memorizer.utils.identifiers import article_sort_key
from constitution_memorizer.utils.json_io import read_json, write_json

logger = logging.getLogger(__name__)

_FUNDAMENTAL_RIGHTS_PARTS = {"III"}


def _strip_label_parens(label: str) -> str:
    cleaned = label.strip()
    if cleaned.startswith("(") and cleaned.endswith(")"):
        return cleaned[1:-1]
    return cleaned


def _provision_text(node: ProvisionNode) -> str:
    """Flatten a provision node including children for Sprint 1 clause units."""
    parts: list[str] = []
    head = f"{node.label} {node.text}".strip()
    if head:
        parts.append(head)
    for child in node.children:
        child_text = _provision_text(child)
        if child_text:
            parts.append(child_text)
    for proviso in node.provisos:
        parts.append(proviso)
    for expl in node.explanations:
        parts.append(expl)
    return "\n".join(parts)


def _article_full_text(article: Article) -> str:
    chunks: list[str] = []
    if article.opening_text.strip():
        chunks.append(article.opening_text.strip())
    if article.clauses:
        for clause in article.clauses:
            chunks.append(_provision_text(clause))
    elif article.body_text.strip():
        chunks.append(article.body_text.strip())
    for proviso in article.provisos:
        chunks.append(proviso)
    for expl in article.explanations:
        chunks.append(expl)
    return "\n".join(c for c in chunks if c).strip()


def _part_tags(part: Part) -> list[str]:
    tags: list[str] = []
    if part.part_number and part.part_number != "UNKNOWN":
        tags.append(f"Part {part.part_number}")
    if part.title:
        tags.append(part.title.strip())
    if part.part_number in _FUNDAMENTAL_RIGHTS_PARTS:
        tags.append("Fundamental Rights")
    return tags


def _iter_articles(doc: ConstitutionDocument) -> list[tuple[Part, Article]]:
    pairs: list[tuple[Part, Article]] = []
    for part in doc.parts:
        for article in part.articles:
            pairs.append((part, article))
        for chapter in part.chapters:
            for article in chapter.articles:
                pairs.append((part, article))
    pairs.sort(key=lambda item: article_sort_key(item[1].article_number))
    return pairs


def _has_nested_children(clauses: list[ProvisionNode]) -> bool:
    return any(bool(c.children) for c in clauses)


def _make_unit(
    *,
    unit_id: str,
    unit_type: LearningUnitType,
    display_title: str,
    text: str,
    parent_id: str | None = None,
    article_number: str | None = None,
    title: str | None = None,
    tags: list[str] | None = None,
    clause_count: int = 0,
    has_nested_children: bool = False,
) -> LearningUnit:
    return LearningUnit(
        id=unit_id,
        type=unit_type,
        parent_id=parent_id,
        article_number=article_number,
        display_title=display_title,
        title=title,
        text=text,
        difficulty=estimate_difficulty(
            text=text,
            clause_count=clause_count,
            has_nested_children=has_nested_children,
            unit_type=unit_type.value,
        ),
        estimated_learning_time=estimate_learning_time_seconds(text),
        tags=list(tags or []),
    )


def _units_for_article(part: Part, article: Article) -> list[LearningUnit]:
    """Sprint 1: ARTICLE or CLAUSE units only (no SUBCLAUSE emission yet)."""
    tags = _part_tags(part)
    parent_article_id = article.id
    clauses = article.clauses

    if not clauses:
        text = _article_full_text(article)
        if not text and article.status == ArticleStatus.OMITTED:
            text = article.title or f"Article {article.article_number} [Omitted.]"
            tags = [*tags, "omitted"]
        if not text and article.status == ArticleStatus.REPEALED:
            text = article.title or f"Article {article.article_number} [Repealed.]"
            tags = [*tags, "repealed"]
        if not text:
            return []
        return [
            _make_unit(
                unit_id=article.id,
                unit_type=LearningUnitType.ARTICLE,
                parent_id=part.id,
                article_number=article.article_number,
                display_title=f"Article {article.article_number}",
                title=article.title,
                text=text,
                tags=tags,
                clause_count=0,
            )
        ]

    units: list[LearningUnit] = []
    nested = _has_nested_children(clauses)
    for clause in clauses:
        label = _strip_label_parens(clause.label)
        text = _provision_text(clause)
        if not text:
            continue
        unit_id = clause.id or f"{article.id}-clause-{label.lower()}"
        units.append(
            _make_unit(
                unit_id=unit_id,
                unit_type=LearningUnitType.CLAUSE,
                parent_id=parent_article_id,
                article_number=article.article_number,
                display_title=f"Article {article.article_number}({label})",
                title=article.title,
                text=text,
                tags=tags,
                clause_count=len(clauses),
                has_nested_children=nested or bool(clause.children),
            )
        )
    # If clauses existed but produced no text, fall back to whole article.
    if not units:
        text = _article_full_text(article)
        if text:
            return [
                _make_unit(
                    unit_id=article.id,
                    unit_type=LearningUnitType.ARTICLE,
                    parent_id=part.id,
                    article_number=article.article_number,
                    display_title=f"Article {article.article_number}",
                    title=article.title,
                    text=text,
                    tags=tags,
                    clause_count=len(clauses),
                    has_nested_children=nested,
                )
            ]
    return units


def _units_for_schedule(schedule: Schedule) -> list[LearningUnit]:
    tags = [f"Schedule {schedule.schedule_number}"]
    if schedule.title:
        tags.append(schedule.title)
    units: list[LearningUnit] = []

    for section in schedule.sections:
        text = section.body_text.strip() or (section.title or "")
        if not text and not section.title:
            continue
        section_id = section.id or f"{schedule.id}-section-{len(units) + 1}"
        units.append(
            _make_unit(
                unit_id=section_id,
                unit_type=LearningUnitType.SCHEDULE_ENTRY,
                parent_id=schedule.id,
                display_title=(
                    f"Schedule {schedule.schedule_number}: {section.title}"
                    if section.title
                    else f"Schedule {schedule.schedule_number} section"
                ),
                title=section.title,
                text=text or (section.title or ""),
                tags=tags,
            )
        )

    for lst in schedule.lists:
        items = lst.items or []
        if items:
            for index, item in enumerate(items, start=1):
                item_text = item.strip()
                if not item_text:
                    continue
                entry_id = f"{lst.id or schedule.id}-item-{index}"
                list_name = lst.name or "List"
                units.append(
                    _make_unit(
                        unit_id=entry_id,
                        unit_type=LearningUnitType.SCHEDULE_ENTRY,
                        parent_id=schedule.id,
                        display_title=(
                            f"Schedule {schedule.schedule_number} {list_name} — {index}"
                        ),
                        title=list_name,
                        text=item_text,
                        tags=[*tags, list_name],
                    )
                )
        elif lst.body_text.strip():
            list_id = lst.id or f"{schedule.id}-list-{len(units) + 1}"
            units.append(
                _make_unit(
                    unit_id=list_id,
                    unit_type=LearningUnitType.SCHEDULE_ENTRY,
                    parent_id=schedule.id,
                    display_title=(
                        f"Schedule {schedule.schedule_number}: {lst.name or 'List'}"
                    ),
                    title=lst.name,
                    text=lst.body_text.strip(),
                    tags=tags,
                )
            )

    if not units:
        text = schedule.body_text.strip()
        if text:
            units.append(
                _make_unit(
                    unit_id=schedule.id,
                    unit_type=LearningUnitType.SCHEDULE_ENTRY,
                    parent_id=None,
                    display_title=f"Schedule {schedule.schedule_number}",
                    title=schedule.title,
                    text=text,
                    tags=tags,
                )
            )
    return units


def _link_sequence(units: list[LearningUnit]) -> None:
    for index, unit in enumerate(units):
        unit.revision_order = index + 1
        unit.previous_unit = units[index - 1].id if index > 0 else None
        unit.next_unit = units[index + 1].id if index + 1 < len(units) else None


def generate_learning_units(doc: ConstitutionDocument) -> LearningUnitsDocument:
    """
    Generate Sprint 1 learning units from a reviewed ConstitutionDocument.

    Alphabetic letter-splitting choice is deferred to Sprint 2; clauses with
    alphabetic children are kept as single CLAUSE units with nested text inlined.
    """
    units: list[LearningUnit] = []

    for part in doc.parts:
        if part.part_number == "UNKNOWN":
            continue
        overview_text = part.title or f"Part {part.part_number}"
        units.append(
            _make_unit(
                unit_id=f"{part.id}-overview",
                unit_type=LearningUnitType.PART_OVERVIEW,
                parent_id=part.id,
                display_title=f"Part {part.part_number} overview",
                title=part.title,
                text=overview_text,
                tags=_part_tags(part),
            )
        )

    for part, article in _iter_articles(doc):
        if part.part_number == "UNKNOWN":
            # Still include articles attached to unknown part.
            pass
        units.extend(_units_for_article(part, article))

    for schedule in sorted(
        doc.schedules,
        key=lambda s: (s.schedule_number_normalized is None, s.schedule_number_normalized or 0),
    ):
        units.extend(_units_for_schedule(schedule))

    _link_sequence(units)
    return LearningUnitsDocument(
        schema_version="1.0.0",
        source_document="constitution.reviewed.json",
        unit_count=len(units),
        units=units,
    )


def generate_learning_units_from_path(
    input_path: Path,
    output_path: Path,
    *,
    force: bool = False,
) -> LearningUnitsDocument:
    """Load reviewed JSON, generate units, and write learning_units.json."""
    if not input_path.exists():
        raise InputValidationError(f"Reviewed constitution JSON not found: {input_path}")

    data = read_json(input_path)
    doc = ConstitutionDocument.model_validate(data)
    result = generate_learning_units(doc)
    payload = result.model_dump(mode="json")
    write_json(output_path, payload, force=force, indent=2)
    min_path = output_path.parent / f"{output_path.stem}.min.json"
    write_json(min_path, payload, force=True, minified=True)
    logger.info(
        "Generated %s learning units → %s",
        result.unit_count,
        output_path,
    )
    return result


def summarize_units(doc: LearningUnitsDocument) -> dict[str, Any]:
    """Return simple distribution stats for CLI output."""
    by_type: dict[str, int] = {}
    lengths: list[int] = []
    for unit in doc.units:
        by_type[unit.type.value] = by_type.get(unit.type.value, 0) + 1
        lengths.append(len(unit.text))
    return {
        "unit_count": doc.unit_count,
        "by_type": by_type,
        "avg_chars": round(sum(lengths) / len(lengths), 1) if lengths else 0,
        "min_chars": min(lengths) if lengths else 0,
        "max_chars": max(lengths) if lengths else 0,
    }
