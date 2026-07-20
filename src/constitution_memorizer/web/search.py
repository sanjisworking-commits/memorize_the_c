"""Parse Constitution search queries into deep-link targets (Sprint 5)."""

from __future__ import annotations

import re
from dataclasses import dataclass

from constitution_memorizer.learning.schemas import LearningUnit, LearningUnitType
from constitution_memorizer.progress.scheduler import ReminderEngine
from constitution_memorizer.utils.identifiers import article_id, clause_id, subclause_id

# 20 | Article 20 | 20(2) | 19(1)(a) | art. 243R(2)(a)
_QUERY_RE = re.compile(
    r"""
    ^\s*
    (?:art(?:icle)?\.?\s*)?
    (?P<article>\d+[A-Za-z]*)
    (?:\((?P<clause>\d+[A-Za-z]?)\))?
    (?:\((?P<letter>[a-z])\))?
    \s*$
    """,
    re.IGNORECASE | re.VERBOSE,
)


@dataclass(frozen=True)
class SearchHit:
    """Resolved search target."""

    kind: str  # article | clause | subclause | unknown
    article_number: str | None
    query: str
    redirect_url: str | None
    unit: LearningUnit | None = None
    message: str | None = None


def parse_search_query(query: str) -> tuple[str, str | None, str | None] | None:
    """
    Return (article_number, clause_label_or_None, letter_or_None).

    clause_label is without parentheses, e.g. \"2\" or \"2A\".
    """
    match = _QUERY_RE.match(query or "")
    if not match:
        return None
    article = match.group("article")
    clause = match.group("clause")
    letter = match.group("letter")
    if letter:
        letter = letter.lower()
    return article, clause, letter


def _find_article_unit(engine: ReminderEngine, article_number: str) -> LearningUnit | None:
    aid = article_id(article_number)
    direct = engine.get_unit(aid)
    if direct is not None:
        return direct
    # Prefer any ARTICLE-typed unit; else first chain unit for the article.
    candidates = [
        u
        for u in engine.units.values()
        if (u.article_number or "").lower() == article_number.lower()
    ]
    for u in candidates:
        if u.type == LearningUnitType.ARTICLE:
            return u
    chain = sorted(
        (u for u in candidates if u.revision_order > 0),
        key=lambda u: u.revision_order,
    )
    return chain[0] if chain else (candidates[0] if candidates else None)


def _find_clause_unit(
    engine: ReminderEngine,
    article_number: str,
    clause_label: str,
) -> LearningUnit | None:
    cid = clause_id(article_number, clause_label)
    unit = engine.get_unit(cid)
    if unit is not None:
        return unit
    needle = f"({clause_label.lower()})"
    for u in engine.units.values():
        if u.type != LearningUnitType.CLAUSE:
            continue
        if (u.article_number or "").lower() != article_number.lower():
            continue
        if needle in u.display_title.lower() or u.id.endswith(f"-clause-{clause_label.lower()}"):
            return u
    return None


def _find_subclause_unit(
    engine: ReminderEngine,
    article_number: str,
    clause_label: str,
    letter: str,
) -> LearningUnit | None:
    parent = _find_clause_unit(engine, article_number, clause_label)
    if parent is None:
        return None
    sid = subclause_id(parent.id, letter)
    unit = engine.get_unit(sid)
    if unit is not None:
        return unit
    for child_id in parent.child_unit_ids:
        child = engine.get_unit(child_id)
        if child is None:
            continue
        if child.display_title.lower().endswith(f"({letter})") or child.id.endswith(
            f"-subclause-{letter}"
        ):
            return child
    return None


def resolve_search(engine: ReminderEngine, query: str) -> SearchHit:
    """
    Resolve a user query to a browse/learn redirect.

    - ``20`` → browse article
    - ``20(2)`` → learn clause (or choose if split-capable and unset)
    - ``19(1)(a)`` → set letters preference on parent, learn subclause
    """
    raw = (query or "").strip()
    parsed = parse_search_query(raw)
    if parsed is None:
        return SearchHit(
            kind="unknown",
            article_number=None,
            query=raw,
            redirect_url=None,
            message="Try forms like 20, 20(2), or 19(1)(a).",
        )

    article, clause, letter = parsed

    if letter and clause:
        unit = _find_subclause_unit(engine, article, clause, letter)
        if unit is None:
            return SearchHit(
                kind="subclause",
                article_number=article,
                query=raw,
                redirect_url=None,
                message=f"No unit found for Article {article}({clause})({letter}).",
            )
        parent_id = unit.parent_clause_id
        if parent_id:
            engine.set_split_preference(parent_id, "letters")
        return SearchHit(
            kind="subclause",
            article_number=article,
            query=raw,
            redirect_url=f"/learn/{unit.id}",
            unit=unit,
        )

    if clause:
        unit = _find_clause_unit(engine, article, clause)
        if unit is None:
            return SearchHit(
                kind="clause",
                article_number=article,
                query=raw,
                redirect_url=None,
                message=f"No unit found for Article {article}({clause}).",
            )
        if unit.allows_letter_split and engine.get_split_preference(unit.id) is None:
            return SearchHit(
                kind="clause",
                article_number=article,
                query=raw,
                redirect_url=f"/learn/{unit.id}/choose",
                unit=unit,
            )
        target_id = engine.next_to_learn_from_clause(unit.id) or unit.id
        return SearchHit(
            kind="clause",
            article_number=article,
            query=raw,
            redirect_url=f"/learn/{target_id}",
            unit=engine.get_unit(target_id) or unit,
        )

    # Article-level → browse page
    unit = _find_article_unit(engine, article)
    return SearchHit(
        kind="article",
        article_number=article,
        query=raw,
        redirect_url=f"/browse/article/{article}",
        unit=unit,
        message=None if unit else f"Article {article} not found in learning units; browse may still show Bare Act text if reviewed JSON is loaded.",
    )
