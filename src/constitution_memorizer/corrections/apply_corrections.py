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
    # One Learn card titled "Article N" (keep lettered body intact).
    prefer_article_unit: bool | None = None
    # With prefer_article_unit: emit letter SUBCLAUSE siblings for Letters mode.
    enable_letter_split: bool | None = None


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


# Bare Act part titles for parts the diglot parser sometimes drops entirely.
_PART_TITLES: dict[str, str] = {
    "VII": "THE STATES IN PART B OF THE FIRST SCHEDULE",
    "VIII": "THE UNION TERRITORIES",
    "IX": "THE PANCHAYATS",
    "IXA": "THE MUNICIPALITIES",
    "IXB": "THE CO-OPERATIVE SOCIETIES",
}


def _find_part(doc: ConstitutionDocument, part_number: str) -> Part | None:
    target = part_number.strip().upper()
    for part in doc.parts:
        if (part.part_number or "").strip().upper() == target:
            return part
    return None


def _ensure_part(doc: ConstitutionDocument, part_number: str) -> Part:
    """Return existing Part or create a stub Part so create-overlays can land."""
    existing = _find_part(doc, part_number)
    if existing is not None:
        return existing
    number = part_number.strip().upper()
    title = _PART_TITLES.get(number, f"PART {number}")
    part = Part(
        id=f"part-{number.lower()}",
        part_number=number,
        title=title,
        articles=[],
        chapters=[],
    )
    # Insert after the previous roman/alphanumeric part when possible.
    insert_at = len(doc.parts)
    order = [
        "I", "II", "III", "IV", "IVA", "V", "VI", "VII", "VIII",
        "IX", "IXA", "IXB", "X", "XI", "XII", "XIII", "XIV", "XIVA",
        "XV", "XVI", "XVII", "XVIII", "XIX", "XX", "XXI", "XXII",
    ]
    try:
        target_idx = order.index(number)
    except ValueError:
        target_idx = -1
    if target_idx >= 0:
        for index, existing_part in enumerate(doc.parts):
            existing_num = (existing_part.part_number or "").strip().upper()
            if existing_num not in order:
                continue
            if order.index(existing_num) > target_idx:
                insert_at = index
                break
    doc.parts.insert(insert_at, part)
    logger.info("Created missing Part %s (%s) for corrections placement", number, title)
    return part


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


def _insert_article_sorted_list(articles: list[Article], article: Article) -> None:
    """Insert into an articles list keeping Bare Act article order."""
    key = article_sort_key(article.article_number)
    insert_at = len(articles)
    for index, existing in enumerate(articles):
        if article_sort_key(existing.article_number) > key:
            insert_at = index
            break
    articles.insert(insert_at, article)


def _insert_article_sorted(part: Part, article: Article) -> None:
    """Insert into part.articles keeping Bare Act article order."""
    _insert_article_sorted_list(part.articles, article)


def _find_chapter(part: Part, chapter_number: str):
    target = chapter_number.strip().upper()
    for chapter in part.chapters:
        if (chapter.chapter_number or "").strip().upper() == target:
            return chapter
    return None


def _ensure_article_in_part(
    doc: ConstitutionDocument,
    article: Article,
    part_number: str,
) -> str | None:
    """
    Place ``article`` under the Part matching ``part_number``.

    When ``article.chapter_number`` matches a Chapter in that Part, insert into
    the Chapter list (e.g. Art 81 → Part V / Chapter II). Otherwise attach to
    ``part.articles``.

    Returns a change note when the article was moved or newly attached.
    """
    part = _ensure_part(doc, part_number)

    target_chapter = (
        _find_chapter(part, article.chapter_number) if article.chapter_number else None
    )
    if target_chapter is not None:
        if any(a.id == article.id for a in target_chapter.articles):
            article.part_number = part_number
            return None
    elif any(a.id == article.id for a in part.articles):
        article.part_number = part_number
        return None

    detached = _detach_article(doc, article.id)
    target = detached if detached is not None else article
    target.part_number = part_number
    if target_chapter is not None:
        _insert_article_sorted_list(target_chapter.articles, target)
        where = f"Part {part_number} Chapter {target_chapter.chapter_number}"
    else:
        _insert_article_sorted(part, target)
        where = f"Part {part_number}"
    if detached is None:
        return f"{target.id}: created in {where}"
    return f"{target.id}: moved to {where}"


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
        prefer_article_unit=bool(corr.prefer_article_unit),
        enable_letter_split=bool(corr.enable_letter_split),
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
            # Corrected body is authoritative Bare Act text; drop structured debris
            # that would otherwise be re-appended by learning-unit full-text assembly.
            if article.explanations:
                article.explanations = []
                changes.append(f"{article_id}: explanations cleared for corrected body")
            if article.provisos:
                article.provisos = []
                changes.append(f"{article_id}: provisos cleared for corrected body")
        # Even when body_text is unchanged (e.g. already "[Omitted.]"), allow a
        # correction pass to scrub leftover explanation/proviso glue.
        elif corr.body_text is not None and (
            article.explanations or article.provisos or article.clauses
        ):
            if article.clauses:
                article.clauses = []
                changes.append(f"{article_id}: clauses cleared for corrected body")
            if article.explanations:
                article.explanations = []
                changes.append(f"{article_id}: explanations cleared for corrected body")
            if article.provisos:
                article.provisos = []
                changes.append(f"{article_id}: provisos cleared for corrected body")
        if corr.opening_text is not None and corr.opening_text != article.opening_text:
            changes.append(f"{article_id}: opening_text updated")
            article.opening_text = corr.opening_text
        if corr.manual_review_status is not None:
            changes.append(
                f"{article_id}: manual_review_status → {corr.manual_review_status!r}"
            )
            article.manual_review_status = corr.manual_review_status
        if (
            corr.prefer_article_unit is not None
            and corr.prefer_article_unit != article.prefer_article_unit
        ):
            changes.append(
                f"{article_id}: prefer_article_unit → {corr.prefer_article_unit!r}"
            )
            article.prefer_article_unit = corr.prefer_article_unit
        if (
            corr.enable_letter_split is not None
            and corr.enable_letter_split != article.enable_letter_split
        ):
            changes.append(
                f"{article_id}: enable_letter_split → {corr.enable_letter_split!r}"
            )
            article.enable_letter_split = corr.enable_letter_split

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
