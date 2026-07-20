"""Article heading and status parsing helpers."""

from __future__ import annotations

import re
from dataclasses import dataclass

from constitution_memorizer.parsing.patterns import (
    ARTICLE_HEADING_RE,
    ARTICLE_NUMBER_ONLY_RE,
    OMITTED_RE,
    REPEALED_RE,
    TITLE_BODY_SPLIT_RE,
    TITLE_PERIOD_BODY_RE,
)
from constitution_memorizer.schemas import ArticleStatus
from constitution_memorizer.utils.identifiers import (
    ArticleNumberParts,
    parse_article_number,
)


@dataclass
class ParsedArticleHeading:
    """Result of detecting an Article heading line."""

    number_parts: ArticleNumberParts
    title: str | None
    opening_text: str
    status: ArticleStatus
    footnote_marker: str | None
    raw_heading: str
    remainder: str


def _strip_trailing_punctuation(title: str) -> str:
    return title.strip().rstrip(".—–- ").strip()


def _detect_status_from_body(body: str) -> ArticleStatus:
    stripped = body.strip()
    if OMITTED_RE.match(stripped) or re.search(r"\[Omitted\.?\]", stripped, re.I):
        return ArticleStatus.OMITTED
    if REPEALED_RE.match(stripped) or re.search(r"\[Repealed\.?\]", stripped, re.I):
        return ArticleStatus.REPEALED
    if re.search(r"\bRepealed\b", stripped, re.I) and len(stripped) < 40:
        return ArticleStatus.REPEALED
    return ArticleStatus.ACTIVE


def split_title_and_body(title_and_body: str) -> tuple[str | None, str]:
    """Split combined title/body text after an Article number."""
    text = title_and_body.strip()
    if not text:
        return None, ""

    status = _detect_status_from_body(text)
    if status in {ArticleStatus.OMITTED, ArticleStatus.REPEALED}:
        return text.strip("[] "), ""

    em_match = TITLE_BODY_SPLIT_RE.match(text)
    if em_match:
        title = _strip_trailing_punctuation(em_match.group("title"))
        body = em_match.group("body").strip()
        return (title or None), body

    # "Equality before law. The State shall..."
    period_match = TITLE_PERIOD_BODY_RE.match(text)
    if period_match:
        title = _strip_trailing_punctuation(period_match.group("title"))
        body = period_match.group("body").strip()
        return (title or None), body

    # Title-only ending with period.
    if text.endswith(".") and len(text) < 120 and ".—" not in text:
        return _strip_trailing_punctuation(text), ""

    # Ambiguous: treat whole string as title if short; else opening body.
    if len(text) <= 80 and not text.endswith((";", ",")):
        return _strip_trailing_punctuation(text), ""

    return None, text


def parse_article_heading_line(line: str) -> ParsedArticleHeading | None:
    """
    Detect and parse an Article heading from a single line.

    Supports footnote prefixes like ``1[21A. ...``.
    """
    stripped = line.strip()
    if not stripped:
        return None

    match = ARTICLE_HEADING_RE.match(stripped)
    number_only = False
    if not match:
        match = ARTICLE_NUMBER_ONLY_RE.match(stripped)
        number_only = True
        if not match:
            return None

    number_raw = match.group("number")
    parts = parse_article_number(number_raw)
    if parts is None:
        return None

    # Guard: footnote-like lines "1. Subs. by..." should not match as articles.
    # Short status-only Article forms such as "238. Repealed." / "31. [Omitted.]"
    # must still be accepted.
    fn_marker_group = match.groupdict().get("fn_marker")
    title_and_body = "" if number_only else (match.groupdict().get("title_and_body") or "")
    if not fn_marker_group and not number_only:
        lower_body = title_and_body.lower().strip()
        status_only = bool(
            OMITTED_RE.match(title_and_body.strip())
            or REPEALED_RE.match(title_and_body.strip())
            or re.fullmatch(r"\[?\s*Omitted\.?\s*\]?\.?", title_and_body.strip(), re.I)
            or re.fullmatch(r"\[?\s*Repealed\.?\s*\]?\.?", title_and_body.strip(), re.I)
        )
        if not status_only and re.match(
            r"^(subs\.|ins\.|omitted\b|repealed\b|added\b|renumbered\b)",
            lower_body,
        ):
            return None
        # Editorial footnote verbs followed by "by" are never Article titles.
        if re.match(
            r"^(subs\.|ins\.|omitted|repealed|added|renumbered)\s+by\b",
            lower_body,
        ):
            return None

    fn_marker = None
    if fn_marker_group:
        fn_marker = fn_marker_group.rstrip("[")

    title, opening = split_title_and_body(title_and_body)
    status = ArticleStatus.ACTIVE
    if title and _detect_status_from_body(title) != ArticleStatus.ACTIVE:
        status = _detect_status_from_body(title)
    elif opening:
        maybe = _detect_status_from_body(opening)
        if maybe != ArticleStatus.ACTIVE:
            status = maybe

    # Also check combined for [Omitted.] / Repealed. after number with no other title.
    combined = title_and_body.strip()
    if combined:
        maybe = _detect_status_from_body(combined)
        if maybe != ArticleStatus.ACTIVE:
            status = maybe
            if status in {ArticleStatus.OMITTED, ArticleStatus.REPEALED}:
                title = combined.strip("[] ").rstrip(".")
                opening = ""

    return ParsedArticleHeading(
        number_parts=parts,
        title=title,
        opening_text=opening,
        status=status,
        footnote_marker=fn_marker,
        raw_heading=stripped,
        remainder=opening,
    )


def looks_like_article_title_line(line: str) -> bool:
    """Heuristic: a following line that is likely an Article title."""
    stripped = line.strip()
    if not stripped or len(stripped) > 120:
        return False
    if ARTICLE_HEADING_RE.match(stripped) or ARTICLE_NUMBER_ONLY_RE.match(stripped):
        return False
    if stripped.startswith("("):
        return False
    # Prefer title-case / sentence starting with capital.
    return bool(re.match(r"^[A-Z\[\"]", stripped))
