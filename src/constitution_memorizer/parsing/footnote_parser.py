"""Footnote and amendment-note parsing."""

from __future__ import annotations

import re
from dataclasses import dataclass

from constitution_memorizer.parsing.patterns import (
    AMENDMENT_ACT_RE,
    AMENDMENT_ORDINAL_RE,
    FOOTNOTE_RE,
    INLINE_FOOTNOTE_MARKER_RE,
    OPERATION_PATTERNS,
)
from constitution_memorizer.schemas import (
    ConstitutionDocument,
    Footnote,
    FootnoteOperation,
    SourceProvenance,
)
from constitution_memorizer.utils.identifiers import footnote_id

# Word ordinals used in amendment Act names → approximate numbers.
_ORDINAL_MAP: dict[str, int] = {
    "first": 1,
    "second": 2,
    "third": 3,
    "fourth": 4,
    "fifth": 5,
    "sixth": 6,
    "seventh": 7,
    "eighth": 8,
    "ninth": 9,
    "tenth": 10,
    "eleventh": 11,
    "twelfth": 12,
    "thirteenth": 13,
    "fourteenth": 14,
    "fifteenth": 15,
    "sixteenth": 16,
    "seventeenth": 17,
    "eighteenth": 18,
    "nineteenth": 19,
    "twentieth": 20,
    "twenty-first": 21,
    "twenty-second": 22,
    "twenty-third": 23,
    "twenty-fourth": 24,
    "twenty-fifth": 25,
    "twenty-sixth": 26,
    "twenty-seventh": 27,
    "twenty-eighth": 28,
    "twenty-ninth": 29,
    "thirtieth": 30,
    "thirty-first": 31,
    "thirty-second": 32,
    "thirty-third": 33,
    "thirty-fourth": 34,
    "thirty-fifth": 35,
    "thirty-sixth": 36,
    "thirty-seventh": 37,
    "thirty-eighth": 38,
    "thirty-ninth": 39,
    "fortieth": 40,
    "forty-first": 41,
    "forty-second": 42,
    "forty-third": 43,
    "forty-fourth": 44,
    "forty-fifth": 45,
    "forty-sixth": 46,
    "forty-seventh": 47,
    "forty-eighth": 48,
    "forty-ninth": 49,
    "fiftieth": 50,
    "fifty-first": 51,
    "sixty-ninth": 69,
    "seventy-third": 73,
    "seventy-fourth": 74,
    "seventy-fifth": 75,
    "eighty-sixth": 86,
    "ninety-first": 91,
    "ninety-third": 93,
    "ninety-seventh": 97,
    "one hundredth": 100,
}


@dataclass
class ParsedFootnoteStart:
    """A newly detected footnote start line."""

    marker: str
    text: str


def detect_footnote_start(line: str) -> ParsedFootnoteStart | None:
    """
    Detect a footnote start.

    Distinguishes footnotes from Articles by requiring amendment-like wording
    when the marker could otherwise look like an Article number, or by the
    classic ``N. Ins./Subs./...`` pattern.
    """
    stripped = line.strip()
    match = FOOTNOTE_RE.match(stripped)
    if not match:
        return None

    marker = match.group("marker")
    text = match.group("text").strip()

    # Short status-only Article forms (e.g. ``238. [Omitted.]``).
    if re.fullmatch(r"\[?\s*(Omitted|Repealed)\.?\s*\]?\.?", text, re.I):
        return None

    # Article-shaped omitted lines with a bracketed title must stay Articles:
    # ``[ Compulsory acquisition of property. ]. -Omitted by the ...``
    if re.match(r"^\[", text) and re.search(r"\bomitted by\b", text, re.I):
        return None

    # If this looks like a normal Article (number + title), reject.
    # Articles usually have a capitalized title word not starting with Subs./Ins.
    if not _looks_like_footnote_body(text):
        # Still allow short numeric markers with clear editorial verbs later;
        # without those verbs, treat as non-footnote.
        return None

    return ParsedFootnoteStart(marker=marker, text=text)


def _looks_like_footnote_body(text: str) -> bool:
    lower = text.lower().strip()
    # Short status-only phrases belong to Articles, not footnotes.
    if re.fullmatch(r"\[?\s*omitted\.?\s*\]?\.?", lower):
        return False
    if re.fullmatch(r"\[?\s*repealed\.?\s*\]?\.?", lower):
        return False

    starters = (
        "subs.",
        "sub.",
        "ins.",
        "omitted by",
        "repealed by",
        "added",
        "renumbered",
        "the words",
        "the word",
        "w.e.f.",
        "clause",
        "cl.",
        "cls.",
        "article",
        "art.",
        "arts.",
        "sub-clause",
        "subclause",
        "paragraph",
        "for the",
        "inserted",
        "substituted",
        "see ",
        "see the ",
        "see c.",
        "see notif",
        "original ",
        "part ",
        "entries ",
        "entry ",
        "in exercise of",
        "there shall be paid",
    )
    if any(lower.startswith(s) for s in starters):
        return True
    # Mid-line editorial cues common in Bare Act footnotes.
    if re.search(
        r"\b(ins\.|subs\.|omitted by|repealed by|renumbered as|w\.e\.f\.)\b",
        lower,
    ):
        return True
    return False


def detect_operation(text: str) -> FootnoteOperation:
    """Infer amendment operation from footnote text; default unknown."""
    for name, pattern in OPERATION_PATTERNS:
        if pattern.search(text):
            return FootnoteOperation(name)
    return FootnoteOperation.UNKNOWN


def extract_amendment_metadata(text: str) -> tuple[str | None, int | None, int | None]:
    """
    Extract amendment name, number and year when confidently present.

    Returns ``(amendment_name, amendment_number, year)``.
    """
    act = AMENDMENT_ACT_RE.search(text)
    amendment_name: str | None = None
    year: int | None = None
    amendment_number: int | None = None

    if act:
        inner = act.group("name").strip()
        year = int(act.group("year"))
        amendment_name = f"Constitution ({inner}) Act, {year}"
        ord_match = AMENDMENT_ORDINAL_RE.search(inner)
        if ord_match:
            ordinal = ord_match.group("ordinal").strip().lower()
            # Normalize whitespace variants of "One Hundred and ..."
            ordinal_key = re.sub(r"\s+", " ", ordinal)
            amendment_number = _ORDINAL_MAP.get(ordinal_key)
            if amendment_number is None:
                # Try without "and"
                amendment_number = _ORDINAL_MAP.get(ordinal_key.replace(" and ", " "))
    else:
        # Year alone sometimes present.
        year_match = re.search(r"\b(19|20)\d{2}\b", text)
        if year_match:
            year = int(year_match.group(0))

    return amendment_name, amendment_number, year


def extract_affected_article(text: str) -> str | None:
    """Best-effort extraction of an affected Article number from footnote text."""
    match = re.search(r"\b[Aa]rt(?:icle)?\.?\s*(\d+[A-Za-z]{0,3})\b", text)
    if match:
        return match.group(1).upper()
    return None


def build_footnote(
    marker: str,
    text: str,
    *,
    context: str | None = None,
    page_number: int | None = None,
) -> Footnote:
    """Build a Footnote model preserving exact text plus optional metadata."""
    operation = detect_operation(text)
    amendment_name, amendment_number, year = extract_amendment_metadata(text)
    affected = extract_affected_article(text)
    return Footnote(
        id=footnote_id(marker, context),
        marker=marker,
        text=text.strip(),
        operation=operation,
        amendment_name=amendment_name,
        amendment_number=amendment_number,
        year=year,
        effective_date=None,
        affected_article=affected,
        source=SourceProvenance(
            page_start=page_number,
            page_end=page_number,
            raw_text=text.strip(),
        ),
    )


def append_footnote_text(footnote: Footnote, continuation: str) -> None:
    """Append a continuation line to an existing footnote."""
    continuation = continuation.strip()
    if not continuation:
        return
    footnote.text = f"{footnote.text} {continuation}"
    if footnote.source.raw_text:
        footnote.source.raw_text = f"{footnote.source.raw_text}\n{continuation}"
    else:
        footnote.source.raw_text = continuation
    # Re-run structured extraction on full text (still secondary to exact text).
    footnote.operation = detect_operation(footnote.text)
    name, number, year = extract_amendment_metadata(footnote.text)
    if name:
        footnote.amendment_name = name
    if number is not None:
        footnote.amendment_number = number
    if year is not None:
        footnote.year = year
    affected = extract_affected_article(footnote.text)
    if affected:
        footnote.affected_article = affected


def _iter_articles(doc: ConstitutionDocument):
    for part in doc.parts:
        yield from part.articles
        for chapter in part.chapters:
            yield from chapter.articles


def associate_footnotes(doc: ConstitutionDocument) -> int:
    """
    Best-effort association of footnote markers to Articles.

    Only links when evidence is present (inline ``1[`` markers, heading footnote
    prefixes, or an ``affected_article`` already parsed from footnote text).
    Does not invent associations.
    """
    articles = list(_iter_articles(doc))
    by_number = {a.article_number: a for a in articles}
    linked = 0

    # Collect inline markers from article texts.
    for article in articles:
        corpus = "\n".join(
            [
                article.source.raw_heading or "",
                article.opening_text or "",
                article.body_text or "",
                article.title or "",
            ]
        )
        for match in INLINE_FOOTNOTE_MARKER_RE.finditer(corpus):
            marker = match.group(1)
            if marker not in article.footnote_references:
                article.footnote_references.append(marker)
                linked += 1

    # Link footnotes that name an affected Article.
    for footnote in doc.footnotes:
        if footnote.affected_article:
            target = by_number.get(footnote.affected_article)
            if target is not None and footnote.marker not in target.footnote_references:
                target.footnote_references.append(footnote.marker)
                linked += 1
            continue
        # If exactly one Article already references this marker, set affected_article.
        hosts = [a for a in articles if footnote.marker in a.footnote_references]
        if len(hosts) == 1 and footnote.affected_article is None:
            footnote.affected_article = hosts[0].article_number
            linked += 1

    return linked
