"""Browse helpers: Article views from reviewed Bare Act JSON (Sprint 5 / 21)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from constitution_memorizer.learning.schemas import LearningUnit, LearningUnitType
from constitution_memorizer.progress.scheduler import ReminderEngine
from constitution_memorizer.schemas import Article, ConstitutionDocument
from constitution_memorizer.utils.identifiers import article_sort_key
from constitution_memorizer.utils.json_io import read_json
from constitution_memorizer.web.amendments import (
    Amendment,
    ArticleAmendments,
    get_article_amendments,
)
from constitution_memorizer.web.progress_stats import path_units_for_article


@dataclass
class ArticleBrowseView:
    """Renderable Article for the Browse page."""

    article_number: str
    title: str | None
    part_number: str | None
    status: str
    full_text: str
    learn_units: list[LearningUnit] = field(default_factory=list)
    # None = article not in amendment seed; [] = curated unamended
    amendments: list[Amendment] | None = None
    amendment_meta: str | None = None
    show_unamended: bool = False


def load_reviewed_document(path: Path | None) -> ConstitutionDocument | None:
    if path is None or not path.exists():
        return None
    return ConstitutionDocument.model_validate(read_json(path))


def _article_full_text(article: Article) -> str:
    from constitution_memorizer.corrections.artefact_scrub import (  # noqa: PLC0415
        scrub_display_text,
        should_include_opening,
    )

    chunks: list[str] = []
    opening = scrub_display_text(article.opening_text).strip()
    body = scrub_display_text(article.body_text).strip()
    if article.clauses:
        if opening:
            chunks.append(opening)
        for clause in article.clauses:
            head = scrub_display_text(f"{clause.label} {clause.text}").strip()
            if head:
                chunks.append(head)
            for child in clause.children:
                child_head = scrub_display_text(f"{child.label} {child.text}").strip()
                if child_head:
                    chunks.append(child_head)
                for grand in child.children:
                    g = scrub_display_text(f"{grand.label} {grand.text}").strip()
                    if g:
                        chunks.append(g)
    elif body:
        if should_include_opening(opening, body):
            chunks.append(opening)
        chunks.append(body)
    elif opening:
        chunks.append(opening)
    for proviso in article.provisos:
        cleaned = scrub_display_text(proviso)
        if cleaned:
            chunks.append(cleaned)
    for expl in article.explanations:
        cleaned = scrub_display_text(expl)
        if cleaned:
            chunks.append(cleaned)
    return "\n\n".join(c for c in chunks if c).strip()


def iter_articles(doc: ConstitutionDocument) -> list[Article]:
    articles: list[Article] = []
    for part in doc.parts:
        articles.extend(part.articles)
        for chapter in part.chapters:
            articles.extend(chapter.articles)
    articles.sort(key=lambda a: article_sort_key(a.article_number))
    return articles


def list_article_numbers(
    engine: ReminderEngine,
    reviewed: ConstitutionDocument | None,
) -> list[str]:
    if reviewed is not None:
        return [a.article_number for a in iter_articles(reviewed)]
    numbers = sorted(
        {
            u.article_number
            for u in engine.units.values()
            if u.article_number
        },
        key=article_sort_key,
    )
    return numbers


def adjacent_article_numbers(
    engine: ReminderEngine,
    reviewed: ConstitutionDocument | None,
    article_number: str,
) -> tuple[str | None, str | None]:
    """Return (previous, next) article numbers in Browse order."""
    numbers = list_article_numbers(engine, reviewed)
    if not numbers:
        return None, None
    target = article_number.lower()
    for index, number in enumerate(numbers):
        if number.lower() == target:
            prev_n = numbers[index - 1] if index > 0 else None
            next_n = numbers[index + 1] if index + 1 < len(numbers) else None
            return prev_n, next_n
    return None, None


def get_article(
    reviewed: ConstitutionDocument | None,
    article_number: str,
) -> Article | None:
    if reviewed is None:
        return None
    target = article_number.lower()
    for article in iter_articles(reviewed):
        if article.article_number.lower() == target:
            return article
    return None


def learn_units_for_article(
    engine: ReminderEngine,
    article_number: str,
) -> list[LearningUnit]:
    """Chain-level units for the article (clauses/articles; not letter children)."""
    units = [
        u
        for u in engine.units.values()
        if (u.article_number or "").lower() == article_number.lower()
        and u.type != LearningUnitType.SUBCLAUSE
        and (u.revision_order > 0 or u.type == LearningUnitType.ARTICLE)
    ]
    units.sort(key=lambda u: (u.revision_order or 10_000, u.id))
    return units


def _is_unit_memorized(engine: ReminderEngine, unit_id: str) -> bool:
    progress = engine.repo.get_progress(unit_id)
    if progress is None:
        return False
    return progress.times_completed > 0 or progress.status in {"review", "mastered"}


def build_amendment_meta(
    engine: ReminderEngine,
    article_number: str,
    curated: ArticleAmendments | None,
) -> str | None:
    """Meta line under the article title (units · memorized · amendments)."""
    if curated is None:
        return None
    path_units, _ = path_units_for_article(engine, article_number)
    unit_n = len(path_units)
    memorized_n = sum(1 for u in path_units if _is_unit_memorized(engine, u.id))
    unit_label = "1 unit" if unit_n == 1 else f"{unit_n} units"
    mem_label = "1 memorized" if memorized_n == 1 else f"{memorized_n} memorized"
    return (
        f"{unit_label} · {mem_label} · {curated.count_label} — "
        "open any clause below in Learn"
    )


def build_article_view(
    engine: ReminderEngine,
    reviewed: ConstitutionDocument | None,
    article_number: str,
    *,
    amendments_catalog: dict[str, ArticleAmendments] | None = None,
) -> ArticleBrowseView | None:
    article = get_article(reviewed, article_number)
    learn_units = learn_units_for_article(engine, article_number)

    if article is None and not learn_units:
        return None

    curated = get_article_amendments(amendments_catalog or {}, article_number)
    amendments_list: list[Amendment] | None
    show_unamended = False
    if curated is None:
        amendments_list = None
    else:
        amendments_list = list(curated.amendments)
        show_unamended = not curated.has_amendments
    meta = build_amendment_meta(engine, article_number, curated)

    if article is not None:
        return ArticleBrowseView(
            article_number=article.article_number,
            title=article.title,
            part_number=article.part_number,
            status=article.status.value if hasattr(article.status, "value") else str(article.status),
            full_text=_article_full_text(article),
            learn_units=learn_units,
            amendments=amendments_list,
            amendment_meta=meta,
            show_unamended=show_unamended,
        )

    text = "\n\n".join(u.text for u in learn_units if u.text)
    return ArticleBrowseView(
        article_number=article_number,
        title=learn_units[0].title if learn_units else None,
        part_number=None,
        status="unknown",
        full_text=text,
        learn_units=learn_units,
        amendments=amendments_list,
        amendment_meta=meta,
        show_unamended=show_unamended,
    )
