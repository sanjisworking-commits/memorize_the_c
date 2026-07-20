"""Article heading and status parsing helpers."""

from __future__ import annotations

import re
from dataclasses import dataclass

from constitution_memorizer.parsing.patterns import (
    ARTICLE_HEADING_RE,
    ARTICLE_NUMBER_ONLY_RE,
    MAX_ARTICLE_NUMBER,
    OMITTED_RE,
    REPEALED_RE,
    TITLE_BODY_SPLIT_RE,
    TITLE_DOT_DASH_BODY_RE,
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
    return title.strip().rstrip(".—–-⎯ ").strip()


def _clean_bracket_noise(text: str) -> str:
    """Normalize diglot bracket wrappers around titles."""
    text = text.strip()
    text = re.sub(r"^\[\s*", "[", text)
    text = re.sub(r"\s*\]", "]", text)
    return text


def _detect_status_from_body(body: str) -> ArticleStatus:
    stripped = body.strip()
    if OMITTED_RE.match(stripped) or re.search(r"\[Omitted\.?\]", stripped, re.I):
        return ArticleStatus.OMITTED
    if REPEALED_RE.match(stripped) or re.search(r"\[Repealed\.?\]", stripped, re.I):
        return ArticleStatus.REPEALED
    # Diglot editions: "[ Title. ]. -Omitted by the Constitution ..."
    if re.search(r"\]\s*\.\s*[-—–⎯].*\bomitted\b", stripped, re.I):
        return ArticleStatus.OMITTED
    if re.search(r"[-—–⎯]\s*omitted by\b", stripped, re.I):
        return ArticleStatus.OMITTED
    if re.search(r"\.\s*[-—–⎯]\s*Omitted\b", stripped, re.I):
        return ArticleStatus.OMITTED
    # Diglot editions often use "Title. - Omitted." / "Title.—Omitted."
    if re.search(r"\bOmitted\.?\s*\]?\s*$", stripped, re.I) and len(stripped) < 160:
        return ArticleStatus.OMITTED
    if re.search(r"\bRepealed\b", stripped, re.I) and len(stripped) < 40:
        return ArticleStatus.REPEALED
    return ArticleStatus.ACTIVE


def split_title_and_body(title_and_body: str) -> tuple[str | None, str]:
    """Split combined title/body text after an Article number."""
    text = _clean_bracket_noise(title_and_body)
    if not text:
        return None, ""

    status = _detect_status_from_body(text)
    if status in {ArticleStatus.OMITTED, ArticleStatus.REPEALED}:
        bracketed = re.match(
            r"^\[\s*(?P<title>.+?)\s*\]\s*\.?\s*[-—–⎯].*$",
            text,
        )
        if bracketed:
            return _strip_trailing_punctuation(bracketed.group("title")), ""
        # "Title. - Omitted."
        omitted_split = re.match(
            r"^(?P<title>.+?)\.\s*[-—–⎯]\s*Omitted\b.*$",
            text,
            re.I,
        )
        if omitted_split:
            return _strip_trailing_punctuation(omitted_split.group("title")), ""
        return text.strip("[] "), ""

    # Bracketed title with body after: "[Title.]—Body" or "[Title.]. -Body"
    bracket_title = re.match(
        r"^\[\s*(?P<title>.+?)\s*\]\s*\.?\s*[-—–⎯]?\s*(?P<body>.*)$",
        text,
    )
    if bracket_title and bracket_title.group("title"):
        title = _strip_trailing_punctuation(bracket_title.group("title"))
        body = bracket_title.group("body").strip()
        if body or title:
            return (title or None), body

    dot_dash = TITLE_DOT_DASH_BODY_RE.match(text)
    if dot_dash:
        title = _strip_trailing_punctuation(dot_dash.group("title"))
        body = dot_dash.group("body").strip()
        return (title or None), body

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
    if len(text) <= 100 and not text.endswith((";", ",")):
        return _strip_trailing_punctuation(text), ""

    return None, text


def parse_article_heading_line(line: str) -> ParsedArticleHeading | None:
    """
    Detect and parse an Article heading from a single line.

    Supports footnote prefixes like ``1[21A. ...`` and ``1 [21A. ...``.
    """
    stripped = line.strip()
    # Markdown list bullets from Docling.
    stripped = re.sub(r"^[-*]\s+", "", stripped)
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
    if parts.numeric_component > MAX_ARTICLE_NUMBER:
        return None

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
            r"^(subs\.|sub\.|ins\.|omitted\b|repealed\b|added\b|renumbered\b|"
            r"art\.|arts\.|cl\.|cls\.|see\b|original\b|entries\b|entry\b|"
            r"part\s+[ivxlc]|in exercise of)",
            lower_body,
        ):
            return None
        if re.match(
            r"^(subs\.|ins\.|omitted|repealed|added|renumbered)\s+by\b",
            lower_body,
        ):
            return None
        article_status_line = bool(
            re.search(r"\]\s*\.\s*[-—–⎯].*\bomitted by\b", lower_body)
            or re.search(r"\.\s*[-—–⎯]\s*omitted by\b", lower_body)
            or re.search(r"\[?\s*omitted\.?\s*\]?", lower_body)
        )
        if (
            not article_status_line
            and re.search(
                r"\b(ins\. by|subs\. by|omitted by|renumbered as|w\.e\.f\.)\b",
                lower_body,
            )
        ):
            return None

    fn_marker = None
    if fn_marker_group:
        fn_marker = re.sub(r"\s*\[$", "", fn_marker_group).strip()

    title, opening = split_title_and_body(title_and_body)
    status = ArticleStatus.ACTIVE
    combined = title_and_body.strip()
    if combined:
        maybe = _detect_status_from_body(combined)
        if maybe != ArticleStatus.ACTIVE:
            status = maybe
            if status in {ArticleStatus.OMITTED, ArticleStatus.REPEALED}:
                title, opening = split_title_and_body(combined)
    else:
        if title and _detect_status_from_body(title) != ArticleStatus.ACTIVE:
            status = _detect_status_from_body(title)
        elif opening:
            maybe = _detect_status_from_body(opening)
            if maybe != ArticleStatus.ACTIVE:
                status = maybe

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
    return bool(re.match(r"^[A-Z\[\"]", stripped))


def looks_like_schedule_entry(line: str) -> bool:
    """
    Heuristic for schedule/list entries that mimic Article headings.

    Examples: ``1. Defence of India.``, ``1. Assamese.``, ``1. Andhra Pradesh``.
    """
    heading = parse_article_heading_line(line)
    if heading is None:
        return False
    # Real constitutional Articles usually have longer juridical titles or body.
    title = (heading.title or "").strip()
    opening = (heading.opening_text or "").strip()
    if heading.status != ArticleStatus.ACTIVE:
        return False
    if opening and len(opening) > 40:
        return False
    if not title:
        return True
    # Short noun-phrase titles without "shall"/legal verbs are often schedule items.
    if len(title) <= 60 and not re.search(
        r"\b(shall|may|means|includes|power|right|duty|constitution)\b",
        title,
        re.I,
    ):
        return True
    return False
