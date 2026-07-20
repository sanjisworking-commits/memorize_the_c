"""Deterministic learning-time and difficulty heuristics."""

from __future__ import annotations

import re

_WORD_RE = re.compile(r"\b[\w''-]+\b", re.UNICODE)


def count_words(text: str) -> int:
    """Count whitespace-separated word-like tokens."""
    if not text or not text.strip():
        return 0
    return len(_WORD_RE.findall(text))


def estimate_learning_time_seconds(text: str) -> int:
    """
    Estimate learning time from word count.

    - Under 80 words → 30s
    - 80–150 → 60s
    - 150–300 → 120s
    - 300+ → 180–300s scaled by length (capped at 300)
    """
    words = count_words(text)
    if words < 80:
        return 30
    if words <= 150:
        return 60
    if words <= 300:
        return 120
    # 300+ → 3–5 minutes
    extra = min(120, ((words - 300) // 50) * 30)
    return min(300, 180 + extra)


def estimate_difficulty(
    *,
    text: str,
    clause_count: int = 0,
    has_nested_children: bool = False,
    unit_type: str = "ARTICLE",
) -> int:
    """
    Estimate difficulty 1–5 from length and structure.

    1 — very short
    2 — single clause / short article
    3 — multiple clauses
    4 — nested structure
    5 — very long provision
    """
    words = count_words(text)
    if words >= 300 or (has_nested_children and words >= 200):
        return 5
    if has_nested_children or (clause_count >= 2 and words >= 150):
        return 4
    if clause_count >= 2 or (
        unit_type in {"CLAUSE", "SUBCLAUSE"} and words >= 80
    ):
        return 3
    if words < 40 and unit_type == "ARTICLE":
        return 1
    return 2
