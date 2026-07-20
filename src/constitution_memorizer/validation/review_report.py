"""Corpus review report builder for Phase 2 hardening."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any

from constitution_memorizer.schemas import Article, ConstitutionDocument
from constitution_memorizer.utils.identifiers import article_sort_key
from constitution_memorizer.validation.validator import collect_counts, validate_document


def _iter_articles(doc: ConstitutionDocument) -> list[Article]:
    articles: list[Article] = []
    for part in doc.parts:
        articles.extend(part.articles)
        for chapter in part.chapters:
            articles.extend(chapter.articles)
    return articles


def build_corpus_review_report(doc: ConstitutionDocument) -> dict[str, Any]:
    """Build a machine-readable corpus review report."""
    articles = _iter_articles(doc)
    warnings, errors = validate_document(doc)
    counts = collect_counts(doc)

    number_counts = Counter(a.article_number for a in articles)
    duplicate_candidates = [
        {"article_number": num, "count": count}
        for num, count in sorted(number_counts.items(), key=lambda x: (-x[1], article_sort_key(x[0])))
        if count > 1
    ]

    empty_articles = [
        {"id": a.id, "article_number": a.article_number, "part_number": a.part_number}
        for a in articles
        if not (
            a.body_text.strip()
            or a.opening_text.strip()
            or a.clauses
            or a.status.value in {"omitted", "repealed"}
        )
    ]

    missing_titles = [
        {"id": a.id, "article_number": a.article_number}
        for a in articles
        if not a.title and a.status.value == "active"
    ]

    schedule_numbers = [s.schedule_number for s in doc.schedules]
    expected_schedules = [
        "FIRST",
        "SECOND",
        "THIRD",
        "FOURTH",
        "FIFTH",
        "SIXTH",
        "SEVENTH",
        "EIGHTH",
        "NINTH",
        "TENTH",
        "ELEVENTH",
        "TWELFTH",
    ]
    missing_schedules = [s for s in expected_schedules if s not in schedule_numbers]

    unclassified_clusters = Counter(
        u.possible_type or "unknown" for u in doc.unclassified_content
    )

    uncertain_headings = [
        {
            "id": u.id,
            "possible_type": u.possible_type,
            "text": u.text[:200],
            "reason": u.reason,
        }
        for u in doc.unclassified_content
        if u.possible_type
        in {"unknown", "duplicate_article", "appendix_part", "chapter_subsection"}
    ][:100]

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "counts": counts,
        "unique_article_numbers": len(number_counts),
        "duplicate_article_candidates": duplicate_candidates,
        "empty_articles": empty_articles[:100],
        "missing_titles_sample": missing_titles[:100],
        "missing_titles_count": len(missing_titles),
        "schedules_found": schedule_numbers,
        "missing_schedules": missing_schedules,
        "parts": [
            {
                "id": p.id,
                "part_number": p.part_number,
                "title": p.title,
                "articles": len(p.articles)
                + sum(len(c.articles) for c in p.chapters),
                "chapters": len(p.chapters),
            }
            for p in doc.parts
        ],
        "unclassified_clusters": dict(unclassified_clusters),
        "uncertain_headings": uncertain_headings,
        "validation_error_codes": dict(Counter(e.code for e in errors)),
        "validation_warning_codes": dict(Counter(w.code for w in warnings)),
        "omitted_articles": [
            a.article_number for a in articles if a.status.value == "omitted"
        ],
        "repealed_articles": [
            a.article_number for a in articles if a.status.value == "repealed"
        ],
    }
