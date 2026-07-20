"""Apply external correction overlays without mutating raw extraction."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from constitution_memorizer.exceptions import ConstitutionMemorizerError, InputValidationError
from constitution_memorizer.schemas import Article, ArticleStatus, ConstitutionDocument
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

    for article_id, corr in corrections.articles.items():
        article = by_id.get(article_id)
        if article is None:
            changes.append(f"SKIP {article_id}: article not found")
            logger.warning("Correction target not found: %s", article_id)
            continue
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
        if corr.manual_review_status is not None:
            changes.append(
                f"{article_id}: manual_review_status → {corr.manual_review_status!r}"
            )
            article.manual_review_status = corr.manual_review_status

    reviewed.extraction_summary.warnings.append(
        f"Applied {len(corrections.articles)} correction entr(y/ies); "
        f"{len(changes)} change note(s)"
    )
    return reviewed, changes


def corrections_to_dict(corrections: CorrectionsFile) -> dict[str, Any]:
    """Serialize corrections to a plain dict."""
    return corrections.model_dump(mode="json")
