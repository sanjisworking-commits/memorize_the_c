"""Structural validation of parsed Constitution documents."""

from __future__ import annotations

import re
from collections import Counter

from constitution_memorizer.schemas import (
    Article,
    ArticleStatus,
    ConstitutionDocument,
    Issue,
    Part,
)
from constitution_memorizer.utils.identifiers import (
    article_sort_key,
    is_valid_article_number,
)

_HEADER_IN_BODY_RE = re.compile(
    r"\bTHE CONSTITUTION OF INDIA\b",
    re.IGNORECASE,
)
_ISOLATED_PAGE_IN_BODY_RE = re.compile(
    r"(?m)^\s*\d{1,4}\s*$",
)


def _iter_articles(doc: ConstitutionDocument) -> list[Article]:
    articles: list[Article] = []
    for part in doc.parts:
        articles.extend(part.articles)
        for chapter in part.chapters:
            articles.extend(chapter.articles)
    return articles


def _count_nested_provisions(articles: list[Article]) -> tuple[int, int, int, int]:
    clauses = 0
    subclauses = 0
    provisos = 0
    explanations = 0

    def walk(nodes: list) -> None:
        nonlocal subclauses, provisos, explanations
        for node in nodes:
            subclauses += 1
            provisos += len(node.provisos)
            explanations += len(node.explanations)
            walk(node.children)

    for article in articles:
        provisos += len(article.provisos)
        explanations += len(article.explanations)
        for clause in article.clauses:
            clauses += 1
            provisos += len(clause.provisos)
            explanations += len(clause.explanations)
            walk(clause.children)
    return clauses, subclauses, provisos, explanations


def _validate_clause_sequence(article: Article) -> list[Issue]:
    issues: list[Issue] = []
    numeric_labels: list[int] = []
    for clause in article.clauses:
        label = clause.label.strip("()")
        if label.isdigit():
            numeric_labels.append(int(label))
    if len(numeric_labels) >= 2:
        expected = list(range(numeric_labels[0], numeric_labels[0] + len(numeric_labels)))
        if numeric_labels != expected:
            issues.append(
                Issue(
                    code="broken_clause_sequence",
                    message=(
                        f"Article {article.article_number} clause sequence "
                        f"{numeric_labels} looks broken (expected contiguous)"
                    ),
                    element_id=article.id,
                    severity="warning",
                )
            )
    return issues


def validate_document(doc: ConstitutionDocument) -> tuple[list[Issue], list[Issue]]:
    """
    Validate a ConstitutionDocument.

    Returns ``(warnings, errors)``.
    """
    warnings: list[Issue] = []
    errors: list[Issue] = []
    articles = _iter_articles(doc)

    # Duplicate Article IDs / numbers
    id_counts = Counter(a.id for a in articles)
    for aid, count in id_counts.items():
        if count > 1:
            errors.append(
                Issue(
                    code="duplicate_article_id",
                    message=f"Duplicate Article ID '{aid}' appears {count} times",
                    element_id=aid,
                    severity="error",
                )
            )

    number_counts = Counter(a.article_number for a in articles)
    for num, count in number_counts.items():
        if count > 1:
            errors.append(
                Issue(
                    code="duplicate_article_number",
                    message=f"Duplicate Article number '{num}' appears {count} times",
                    element_id=f"article-{num.lower()}",
                    severity="error",
                )
            )

    for part in doc.parts:
        if not part.part_number or part.part_number == "UNKNOWN":
            warnings.append(
                Issue(
                    code="missing_part_number",
                    message=f"Part '{part.id}' has missing or unknown part number",
                    element_id=part.id,
                )
            )
        if not part.chapters and not part.articles:
            warnings.append(
                Issue(
                    code="empty_part",
                    message=f"Part {part.part_number} has no chapters or articles",
                    element_id=part.id,
                )
            )
        for chapter in part.chapters:
            if not chapter.articles:
                warnings.append(
                    Issue(
                        code="empty_chapter",
                        message=(
                            f"Chapter {chapter.chapter_number} in Part "
                            f"{part.part_number} has no articles"
                        ),
                        element_id=chapter.id,
                    )
                )

    footnote_markers = {f.marker for f in doc.footnotes}
    referenced_markers: set[str] = set()

    for article in articles:
        if not is_valid_article_number(article.article_number):
            errors.append(
                Issue(
                    code="invalid_article_number",
                    message=f"Article number '{article.article_number}' does not match supported pattern",
                    element_id=article.id,
                    severity="error",
                )
            )
        if not article.title and article.status == ArticleStatus.ACTIVE:
            warnings.append(
                Issue(
                    code="missing_article_title",
                    message=f"Article {article.article_number} is missing a title",
                    element_id=article.id,
                )
            )
        has_content = bool(
            article.body_text.strip()
            or article.opening_text.strip()
            or article.clauses
            or article.status in {ArticleStatus.OMITTED, ArticleStatus.REPEALED}
        )
        if not has_content:
            warnings.append(
                Issue(
                    code="empty_article",
                    message=f"Article {article.article_number} has no content",
                    element_id=article.id,
                )
            )

        try:
            ArticleStatus(article.status)
        except ValueError:
            errors.append(
                Issue(
                    code="invalid_status",
                    message=f"Article {article.article_number} has invalid status '{article.status}'",
                    element_id=article.id,
                    severity="error",
                )
            )

        src = article.source
        if (
            src.page_start is not None
            and src.page_end is not None
            and src.page_start > src.page_end
        ):
            errors.append(
                Issue(
                    code="broken_source_range",
                    message=(
                        f"Article {article.article_number} has page_start "
                        f"{src.page_start} > page_end {src.page_end}"
                    ),
                    element_id=article.id,
                    severity="error",
                )
            )

        body_for_scan = "\n".join(
            [
                article.body_text,
                article.opening_text,
                article.title or "",
            ]
        )
        if _HEADER_IN_BODY_RE.search(body_for_scan):
            warnings.append(
                Issue(
                    code="residual_header_in_body",
                    message=f"Possible page header remaining in Article {article.article_number}",
                    element_id=article.id,
                )
            )
        if _ISOLATED_PAGE_IN_BODY_RE.search(article.body_text):
            warnings.append(
                Issue(
                    code="residual_page_number_in_body",
                    message=f"Possible page number remaining in Article {article.article_number}",
                    element_id=article.id,
                )
            )

        for ref in article.footnote_references:
            referenced_markers.add(ref)
            if ref not in footnote_markers:
                warnings.append(
                    Issue(
                        code="missing_footnote_target",
                        message=(
                            f"Article {article.article_number} references footnote "
                            f"'{ref}' which was not found"
                        ),
                        element_id=article.id,
                    )
                )

        warnings.extend(_validate_clause_sequence(article))

    for footnote in doc.footnotes:
        if footnote.marker not in referenced_markers and footnote.affected_article is None:
            warnings.append(
                Issue(
                    code="footnote_without_reference",
                    message=f"Footnote '{footnote.marker}' has no identifiable in-text reference",
                    element_id=footnote.id,
                )
            )

    for schedule in doc.schedules:
        if not (
            schedule.body_text.strip()
            or schedule.sections
            or schedule.lists
            or schedule.tables
        ):
            warnings.append(
                Issue(
                    code="empty_schedule",
                    message=f"Schedule {schedule.schedule_number} has no content",
                    element_id=schedule.id,
                )
            )

    # Suspicious article ordering within each part
    for part in doc.parts:
        part_articles = list(part.articles)
        for chapter in part.chapters:
            part_articles.extend(chapter.articles)
        numbers = [a.article_number for a in part_articles]
        sorted_numbers = sorted(numbers, key=article_sort_key)
        if numbers and numbers != sorted_numbers:
            # Only warn if significantly out of order (not just one swap).
            mismatches = sum(1 for a, b in zip(numbers, sorted_numbers) if a != b)
            if mismatches >= 2:
                warnings.append(
                    Issue(
                        code="suspicious_article_ordering",
                        message=(
                            f"Part {part.part_number} article order may be suspicious "
                            f"({mismatches} positions differ from natural sort)"
                        ),
                        element_id=part.id,
                    )
                )

    if doc.unclassified_content:
        warnings.append(
            Issue(
                code="unclassified_content",
                message=f"{len(doc.unclassified_content)} unclassified content block(s) retained",
                severity="warning",
            )
        )

    # Duplicate text blocks across articles (identical body)
    body_counts = Counter(
        a.body_text.strip() for a in articles if len(a.body_text.strip()) > 80
    )
    for body, count in body_counts.items():
        if count > 1:
            warnings.append(
                Issue(
                    code="duplicate_text_blocks",
                    message=f"Identical body text appears in {count} articles (length={len(body)})",
                )
            )

    return warnings, errors


def collect_counts(doc: ConstitutionDocument) -> dict[str, int]:
    """Collect structural counts for the extraction report."""
    articles = _iter_articles(doc)
    clauses, subclauses, provisos, explanations = _count_nested_provisions(articles)
    tables = sum(len(s.tables) for s in doc.schedules)
    chapters = sum(len(p.chapters) for p in doc.parts)
    omitted = sum(1 for a in articles if a.status == ArticleStatus.OMITTED)
    repealed = sum(1 for a in articles if a.status == ArticleStatus.REPEALED)
    return {
        "parts_found": len(doc.parts),
        "chapters_found": chapters,
        "articles_found": len(articles),
        "clauses_found": clauses,
        "subclauses_found": subclauses,
        "provisos_found": provisos,
        "explanations_found": explanations,
        "footnotes_found": len(doc.footnotes),
        "schedules_found": len(doc.schedules),
        "tables_found": tables,
        "omitted_articles_found": omitted,
        "repealed_articles_found": repealed,
        "unclassified_blocks": len(doc.unclassified_content),
    }
