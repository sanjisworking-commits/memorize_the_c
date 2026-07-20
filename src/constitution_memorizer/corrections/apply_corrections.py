"""Apply external correction overlays without mutating raw extraction."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from constitution_memorizer.corrections.artefact_scrub import scrub_document
from constitution_memorizer.exceptions import ConstitutionMemorizerError, InputValidationError
from constitution_memorizer.schemas import Article, ArticleStatus, ConstitutionDocument, Part
from constitution_memorizer.utils.identifiers import (
    article_id as make_article_id,
    article_sort_key,
    parse_article_number,
)
from constitution_memorizer.utils.json_io import read_json

logger = logging.getLogger(__name__)


class ArticleCorrection(BaseModel):
    """Fields that may be overridden for a single Article."""

    model_config = ConfigDict(extra="forbid")

    title: str | None = None
    status: ArticleStatus | None = None
    part_number: str | None = None
    chapter_number: str | None = None
    manual_review_status: str | None = None
    body_text: str | None = None
    opening_text: str | None = None
    # Drop mis-parsed nodes (e.g. Sixth Schedule paragraphs mistaken for Articles).
    exclude: bool | None = None
    # Insert a missing Article (parser never emitted the node).
    create: bool | None = None


class CorrectionsFile(BaseModel):
    """Root corrections overlay document."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0.0"
    description: str | None = None
    notes: list[str] = Field(default_factory=list)
    articles: dict[str, ArticleCorrection] = Field(default_factory=dict)


def load_corrections(path: Path) -> CorrectionsFile:
    """Load and validate a corrections JSON file."""
    if not path.exists():
        raise InputValidationError(f"Corrections file not found: {path}")
    data = read_json(path)
    try:
        return CorrectionsFile.model_validate(data)
    except Exception as exc:  # noqa: BLE001
        raise ConstitutionMemorizerError(f"Invalid corrections file: {exc}") from exc


def _iter_articles(doc: ConstitutionDocument) -> list[Article]:
    articles: list[Article] = []
    for part in doc.parts:
        articles.extend(part.articles)
        for chapter in part.chapters:
            articles.extend(chapter.articles)
    return articles


def _find_part(doc: ConstitutionDocument, part_number: str) -> Part | None:
    target = part_number.strip().upper()
    for part in doc.parts:
        if (part.part_number or "").strip().upper() == target:
            return part
    return None


def _detach_article(doc: ConstitutionDocument, article_id: str) -> Article | None:
    """Remove an article from whichever part/chapter holds it."""
    for part in doc.parts:
        for index, article in enumerate(part.articles):
            if article.id == article_id:
                return part.articles.pop(index)
        for chapter in part.chapters:
            for index, article in enumerate(chapter.articles):
                if article.id == article_id:
                    return chapter.articles.pop(index)
    return None


def _insert_article_sorted(part: Part, article: Article) -> None:
    """Insert into part.articles keeping Bare Act article order."""
    key = article_sort_key(article.article_number)
    insert_at = len(part.articles)
    for index, existing in enumerate(part.articles):
        if article_sort_key(existing.article_number) > key:
            insert_at = index
            break
    part.articles.insert(insert_at, article)


def _ensure_article_in_part(
    doc: ConstitutionDocument,
    article: Article,
    part_number: str,
) -> str | None:
    """
    Place ``article`` under the Part matching ``part_number``.

    Returns a change note when the article was moved or newly attached.
    """
    part = _find_part(doc, part_number)
    if part is None:
        logger.warning(
            "Correction part_number %s not found for %s", part_number, article.id
        )
        return f"SKIP {article.id}: part {part_number!r} not found for placement"

    if any(a.id == article.id for a in part.articles):
        article.part_number = part_number
        return None

    detached = _detach_article(doc, article.id)
    if detached is None:
        article.part_number = part_number
        _insert_article_sorted(part, article)
        return f"{article.id}: created in Part {part_number}"

    detached.part_number = part_number
    _insert_article_sorted(part, detached)
    return f"{detached.id}: moved to Part {part_number}"


def _create_article_from_correction(
    article_id: str,
    corr: ArticleCorrection,
) -> Article | None:
    """Build a new Article from a create-correction entry."""
    slug = article_id[len("article-") :] if article_id.startswith("article-") else article_id
    parts = parse_article_number(slug)
    if parts is None:
        logger.warning("Cannot create %s: invalid article number slug", article_id)
        return None
    if not corr.body_text:
        logger.warning("Cannot create %s: body_text required", article_id)
        return None
    if not corr.part_number:
        logger.warning("Cannot create %s: part_number required", article_id)
        return None

    return Article(
        id=make_article_id(parts.article_number),
        article_number=parts.article_number,
        numeric_component=parts.numeric_component,
        suffix=parts.suffix,
        title=corr.title,
        status=corr.status or ArticleStatus.ACTIVE,
        part_number=corr.part_number,
        chapter_number=corr.chapter_number,
        body_text=corr.body_text,
        opening_text=corr.opening_text or "",
        manual_review_status=corr.manual_review_status,
    )


def _remove_articles(doc: ConstitutionDocument, article_ids: set[str]) -> list[str]:
    """Remove articles by id from parts/chapters. Returns change notes."""
    changes: list[str] = []
    for part in doc.parts:
        kept = [a for a in part.articles if a.id not in article_ids]
        if len(kept) != len(part.articles):
            part.articles = kept
        for chapter in part.chapters:
            kept_ch = [a for a in chapter.articles if a.id not in article_ids]
            if len(kept_ch) != len(chapter.articles):
                chapter.articles = kept_ch
    for article_id in sorted(article_ids):
        changes.append(f"{article_id}: excluded from reviewed corpus")
    return changes


def apply_corrections(
    doc: ConstitutionDocument,
    corrections: CorrectionsFile,
) -> tuple[ConstitutionDocument, list[str]]:
    """
    Apply corrections onto a deep copy of ``doc``.

    Returns the reviewed document and a list of human-readable change notes.
    Raw extraction artefacts are never modified by this function.
    """
    reviewed = doc.model_copy(deep=True)
    by_id = {a.id: a for a in _iter_articles(reviewed)}
    changes: list[str] = []
    exclude_ids: set[str] = set()

    for article_id, corr in corrections.articles.items():
        if corr.exclude:
            if article_id not in by_id:
                changes.append(f"SKIP {article_id}: article not found (exclude)")
                logger.warning("Correction exclude target not found: %s", article_id)
                continue
            exclude_ids.add(article_id)
            continue

        article = by_id.get(article_id)
        if article is None:
            if not corr.create:
                changes.append(f"SKIP {article_id}: article not found")
                logger.warning("Correction target not found: %s", article_id)
                continue
            created = _create_article_from_correction(article_id, corr)
            if created is None:
                changes.append(f"SKIP {article_id}: create failed")
                continue
            place_note = _ensure_article_in_part(
                reviewed, created, corr.part_number or ""
            )
            if place_note and place_note.startswith("SKIP"):
                changes.append(place_note)
                continue
            if place_note:
                changes.append(place_note)
            by_id[created.id] = created
            article = created
        if corr.title is not None and corr.title != article.title:
            changes.append(f"{article_id}: title {article.title!r} → {corr.title!r}")
            article.title = corr.title
        if corr.status is not None and corr.status != article.status:
            changes.append(
                f"{article_id}: status {article.status.value} → {corr.status.value}"
            )
            article.status = corr.status
        if corr.part_number is not None and corr.part_number != article.part_number:
            changes.append(
                f"{article_id}: part_number {article.part_number!r} → {corr.part_number!r}"
            )
            article.part_number = corr.part_number
            move_note = _ensure_article_in_part(reviewed, article, corr.part_number)
            if move_note:
                changes.append(move_note)
                by_id[article.id] = article
        if (
            corr.chapter_number is not None
            and corr.chapter_number != article.chapter_number
        ):
            changes.append(
                f"{article_id}: chapter_number {article.chapter_number!r} → "
                f"{corr.chapter_number!r}"
            )
            article.chapter_number = corr.chapter_number
        if corr.body_text is not None and corr.body_text != article.body_text:
            changes.append(f"{article_id}: body_text updated")
            article.body_text = corr.body_text
            if article.clauses:
                article.clauses = []
                changes.append(f"{article_id}: clauses cleared for corrected body")
        if corr.opening_text is not None and corr.opening_text != article.opening_text:
            changes.append(f"{article_id}: opening_text updated")
            article.opening_text = corr.opening_text
        if corr.manual_review_status is not None:
            changes.append(
                f"{article_id}: manual_review_status → {corr.manual_review_status!r}"
            )
            article.manual_review_status = corr.manual_review_status

    if exclude_ids:
        changes.extend(_remove_articles(reviewed, exclude_ids))

    scrub_notes = scrub_document(reviewed)
    changes.extend(scrub_notes)

    reviewed.extraction_summary.warnings.append(
        f"Applied {len(corrections.articles)} correction entr(y/ies); "
        f"{len(changes)} change note(s)"
    )
    return reviewed, changes


def corrections_to_dict(corrections: CorrectionsFile) -> dict[str, Any]:
    """Serialize corrections to a plain dict."""
    return corrections.model_dump(mode="json")
