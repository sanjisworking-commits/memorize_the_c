"""Article / unit progress aggregates (Sprint 5)."""

from __future__ import annotations

from dataclasses import dataclass

from constitution_memorizer.learning.schemas import LearningUnit, LearningUnitType
from constitution_memorizer.progress.scheduler import ReminderEngine
from constitution_memorizer.utils.identifiers import article_sort_key


@dataclass(frozen=True)
class ArticleProgress:
    article_number: str
    required: int
    completed: int
    percent: float
    pending_choice: bool


def path_units_for_article(
    engine: ReminderEngine,
    article_number: str,
) -> tuple[list[LearningUnit], bool]:
    """
    Units that count toward Article completion under current preferences.

    Returns (units, pending_choice) where pending_choice means a split-capable
    clause still needs whole/letters selection (counted as the parent clause).
    """
    articles_units = [
        u
        for u in engine.units.values()
        if (u.article_number or "").lower() == article_number.lower()
    ]
    required: list[LearningUnit] = []
    pending_choice = False

    for unit in articles_units:
        if unit.type == LearningUnitType.ARTICLE:
            required.append(unit)
            continue
        if unit.type != LearningUnitType.CLAUSE:
            continue
        if unit.allows_letter_split:
            mode = engine.get_split_preference(unit.id)
            if mode is None:
                pending_choice = True
                required.append(unit)
            elif mode == "letters":
                for child_id in unit.child_unit_ids:
                    child = engine.get_unit(child_id)
                    if child is not None:
                        required.append(child)
            else:
                required.append(unit)
        else:
            required.append(unit)

    return required, pending_choice


def _is_completed(engine: ReminderEngine, unit_id: str) -> bool:
    progress = engine.repo.get_progress(unit_id)
    if progress is None:
        return False
    return progress.times_completed > 0 or progress.status in {"review", "mastered"}


def article_progress(
    engine: ReminderEngine,
    article_number: str,
) -> ArticleProgress | None:
    required, pending = path_units_for_article(engine, article_number)
    if not required:
        return None
    completed = sum(1 for u in required if _is_completed(engine, u.id))
    percent = round(100.0 * completed / len(required), 1)
    return ArticleProgress(
        article_number=article_number,
        required=len(required),
        completed=completed,
        percent=percent,
        pending_choice=pending,
    )


def all_article_progress(engine: ReminderEngine) -> list[ArticleProgress]:
    numbers = sorted(
        {u.article_number for u in engine.units.values() if u.article_number},
        key=article_sort_key,
    )
    rows: list[ArticleProgress] = []
    for number in numbers:
        row = article_progress(engine, number)
        if row is not None:
            rows.append(row)
    return rows


def unit_type_totals(engine: ReminderEngine) -> dict[str, int]:
    totals: dict[str, int] = {}
    for unit in engine.units.values():
        key = unit.type.value
        totals[key] = totals.get(key, 0) + 1
    return totals


def progress_dashboard(engine: ReminderEngine) -> dict:
    """Bundle stats for the Progress page."""
    engine_stats = engine.stats()
    articles = all_article_progress(engine)
    started = [a for a in articles if a.completed > 0]
    complete = [a for a in articles if a.required and a.completed >= a.required]
    avg = (
        round(sum(a.percent for a in articles) / len(articles), 1) if articles else 0.0
    )
    return {
        "engine": engine_stats,
        "by_type": unit_type_totals(engine),
        "articles": articles,
        "articles_started": len(started),
        "articles_complete": len(complete),
        "articles_total": len(articles),
        "avg_article_percent": avg,
    }
