"""Browse helpers: Article views from reviewed Bare Act JSON (Sprint 5)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from constitution_memorizer.learning.schemas import LearningUnit, LearningUnitType
from constitution_memorizer.progress.scheduler import ReminderEngine
from constitution_memorizer.schemas import Article, ConstitutionDocument
from constitution_memorizer.utils.identifiers import article_sort_key
from constitution_memorizer.utils.json_io import read_json


@dataclass
class ArticleBrowseView:
    """Renderable Article for the Browse page."""

    article_number: str
    title: str | None
    part_number: str | None
    status: str
    full_text: str
    learn_units: list[LearningUnit] = field(default_factory=list)


def load_reviewed_document(path: Path | None) -> ConstitutionDocument | None:
    if path is None or not path.exists():
        return None
    return ConstitutionDocument.model_validate(read_json(path))


def _article_full_text(article: Article) -> str:
    chunks: list[str] = []
    if article.opening_text.strip():
        chunks.append(article.opening_text.strip())
    if article.clauses:
        for clause in article.clauses:
            head = f"{clause.label} {clause.text}".strip()
            if head:
                chunks.append(head)
            for child in clause.children:
                child_head = f"{child.label} {child.text}".strip()
                if child_head:
                    chunks.append(child_head)
                for grand in child.children:
                    g = f"{grand.label} {grand.text}".strip()
                    if g:
                        chunks.append(g)
    elif article.body_text.strip():
        chunks.append(article.body_text.strip())
    for proviso in article.provisos:
        chunks.append(proviso)
    for expl in article.explanations:
        chunks.append(expl)
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


def build_article_view(
    engine: ReminderEngine,
    reviewed: ConstitutionDocument | None,
    article_number: str,
) -> ArticleBrowseView | None:
    article = get_article(reviewed, article_number)
    learn_units = learn_units_for_article(engine, article_number)

    if article is None and not learn_units:
        return None

    if article is not None:
        return ArticleBrowseView(
            article_number=article.article_number,
            title=article.title,
            part_number=article.part_number,
            status=article.status.value if hasattr(article.status, "value") else str(article.status),
            full_text=_article_full_text(article),
            learn_units=learn_units,
        )

    # Fallback: stitch learning-unit text when reviewed JSON is unavailable.
    text = "\n\n".join(u.text for u in learn_units if u.text)
    return ArticleBrowseView(
        article_number=article_number,
        title=learn_units[0].title if learn_units else None,
        part_number=None,
        status="unknown",
        full_text=text,
        learn_units=learn_units,
    )
