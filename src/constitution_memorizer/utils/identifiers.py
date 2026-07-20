"""Stable deterministic identifiers and Article sorting helpers."""

from __future__ import annotations

import re
from typing import NamedTuple

# Article numbers: 14, 21A, 239AA, 243ZG, 2A, etc.
ARTICLE_NUMBER_RE = re.compile(
    r"^(?P<numeric>\d+)(?P<suffix>[A-Za-z]{0,3})$"
)

ROMAN_TO_INT: dict[str, int] = {
    "I": 1,
    "II": 2,
    "III": 3,
    "IV": 4,
    "V": 5,
    "VI": 6,
    "VII": 7,
    "VIII": 8,
    "IX": 9,
    "X": 10,
    "XI": 11,
    "XII": 12,
    "XIII": 13,
    "XIV": 14,
    "XV": 15,
    "XVI": 16,
    "XVII": 17,
    "XVIII": 18,
    "XIX": 19,
    "XX": 20,
    "XXI": 21,
    "XXII": 22,
}

ORDINAL_SCHEDULE: dict[str, int] = {
    "FIRST": 1,
    "SECOND": 2,
    "THIRD": 3,
    "FOURTH": 4,
    "FIFTH": 5,
    "SIXTH": 6,
    "SEVENTH": 7,
    "EIGHTH": 8,
    "NINTH": 9,
    "TENTH": 10,
    "ELEVENTH": 11,
    "TWELFTH": 12,
}

ORDINAL_TO_NAME: dict[int, str] = {v: k.lower() for k, v in ORDINAL_SCHEDULE.items()}


class ArticleNumberParts(NamedTuple):
    """Parsed components of an Article number string."""

    article_number: str
    numeric_component: int
    suffix: str


def normalize_roman(value: str) -> str:
    """Normalize a Roman numeral string to uppercase without spaces."""
    return value.strip().upper().replace(" ", "")


def roman_to_int(value: str) -> int | None:
    """Convert a Roman numeral to an integer, or None if unknown."""
    return ROMAN_TO_INT.get(normalize_roman(value))


def parse_article_number(raw: str) -> ArticleNumberParts | None:
    """
    Parse an Article number string into numeric and suffix components.

    Accepts forms such as ``21A``, ``239AA``, ``243ZG``. Returns None if invalid.
    """
    cleaned = raw.strip().upper().replace(" ", "")
    match = ARTICLE_NUMBER_RE.match(cleaned)
    if not match:
        return None
    numeric = int(match.group("numeric"))
    suffix = match.group("suffix").upper()
    article_number = f"{numeric}{suffix}"
    return ArticleNumberParts(
        article_number=article_number,
        numeric_component=numeric,
        suffix=suffix,
    )


def article_id(article_number: str) -> str:
    """Return a stable Article ID such as ``article-21a``."""
    parts = parse_article_number(article_number)
    if parts is None:
        slug = re.sub(r"[^a-z0-9]+", "-", article_number.strip().lower()).strip("-")
        return f"article-{slug or 'unknown'}"
    return f"article-{parts.article_number.lower()}"


def part_id(part_number: str) -> str:
    """Return a stable Part ID such as ``part-iii``."""
    roman = normalize_roman(part_number)
    return f"part-{roman.lower()}"


def chapter_id(part_number: str, chapter_number: str) -> str:
    """Return a stable Chapter ID such as ``part-v-chapter-i``."""
    return f"{part_id(part_number)}-chapter-{normalize_roman(chapter_number).lower()}"


def clause_id(article_number: str, clause_number: str) -> str:
    """Return a stable clause ID such as ``article-19-clause-1``."""
    return f"{article_id(article_number)}-clause-{clause_number.lower()}"


def subclause_id(parent_id: str, label: str) -> str:
    """
    Return a stable subclause ID.

    Example: ``article-19-clause-1-subclause-a`` for label ``(a)``.
    """
    cleaned = label.strip().lower()
    if cleaned.startswith("(") and cleaned.endswith(")"):
        cleaned = cleaned[1:-1]
    cleaned = re.sub(r"[^a-z0-9]+", "", cleaned)
    return f"{parent_id}-subclause-{cleaned or 'x'}"


def schedule_id(schedule_number: str) -> str:
    """
    Return a stable Schedule ID such as ``schedule-seven``.

    Accepts ordinal words (SEVENTH), Roman numerals, or digits.
    """
    upper = schedule_number.strip().upper()
    if upper in ORDINAL_SCHEDULE:
        n = ORDINAL_SCHEDULE[upper]
        return f"schedule-{ORDINAL_TO_NAME[n]}"
    # Strip trailing "SCHEDULE" if present
    upper = re.sub(r"\s*SCHEDULE\s*$", "", upper).strip()
    if upper in ORDINAL_SCHEDULE:
        n = ORDINAL_SCHEDULE[upper]
        return f"schedule-{ORDINAL_TO_NAME[n]}"
    roman_n = roman_to_int(upper)
    if roman_n is not None and roman_n in ORDINAL_TO_NAME:
        return f"schedule-{ORDINAL_TO_NAME[roman_n]}"
    if upper.isdigit():
        n = int(upper)
        name = ORDINAL_TO_NAME.get(n, str(n))
        return f"schedule-{name}"
    slug = re.sub(r"[^a-z0-9]+", "-", upper.lower()).strip("-")
    return f"schedule-{slug or 'unknown'}"


def schedule_number_normalized(schedule_number: str) -> int | None:
    """Return the numeric schedule index when recognizable."""
    upper = schedule_number.strip().upper()
    upper = re.sub(r"\s*SCHEDULE\s*$", "", upper).strip()
    if upper in ORDINAL_SCHEDULE:
        return ORDINAL_SCHEDULE[upper]
    roman_n = roman_to_int(upper)
    if roman_n is not None:
        return roman_n
    if upper.isdigit():
        return int(upper)
    return None


def footnote_id(marker: str, context: str | None = None) -> str:
    """Return a stable footnote ID."""
    marker_slug = re.sub(r"[^a-z0-9]+", "", marker.lower()) or "x"
    if context:
        ctx = re.sub(r"[^a-z0-9]+", "-", context.lower()).strip("-")
        return f"footnote-{ctx}-{marker_slug}"
    return f"footnote-{marker_slug}"


def unclassified_id(index: int) -> str:
    """Return a zero-padded unclassified content ID."""
    return f"unclassified-{index:04d}"


def article_sort_key(article_number: str) -> tuple[int, str]:
    """
    Natural sort key for Article numbers.

    Ensures ``20 < 21 < 21A < 22 < 239 < 239A < 239AA < 239AB < 239B``.
    Lexicographic suffix ordering is intentional for same-numeric families.
    """
    parts = parse_article_number(article_number)
    if parts is None:
        return (10**9, article_number.upper())
    return (parts.numeric_component, parts.suffix)


def is_valid_article_number(article_number: str) -> bool:
    """Return True if the Article number matches the supported pattern."""
    return parse_article_number(article_number) is not None
