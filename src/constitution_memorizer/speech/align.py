"""Verbatim word alignment for spoken Letters.

Needleman–Wunsch on normalized tokens. The browser never implements this;
it only paints ``{index, status}`` pairs returned by the speech route.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_NON_ALNUM = re.compile(r"[^a-z0-9]")

# Closed-class / high-frequency words are never sent as Deepgram keyterms.
_FUNCTION_WORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "as",
        "at",
        "be",
        "but",
        "by",
        "for",
        "from",
        "if",
        "in",
        "into",
        "is",
        "it",
        "its",
        "no",
        "nor",
        "not",
        "of",
        "on",
        "or",
        "so",
        "than",
        "that",
        "the",
        "this",
        "to",
        "with",
    }
)

LETTERS_ALIGN_WINDOW = 16
KEYTERM_MAX = 100
KEYTERM_MIN_LEN = 7

_MATCH_COST = 0
_SUB_COST = 1
_GAP_COST = 1


def norm_word(text: str) -> str:
    return _NON_ALNUM.sub("", text.lower())


def tokenize(text: str) -> list[str]:
    stripped = text.strip()
    if not stripped:
        return []
    return stripped.split()


def _levenshtein_at_most_one(left: str, right: str) -> bool:
    if left == right:
        return True
    n, m = len(left), len(right)
    if abs(n - m) > 1:
        return False
    if n > m:
        left, right = right, left
        n, m = m, n
    # Insertion or substitution only (n <= m, m - n <= 1).
    i = j = diffs = 0
    while i < n and j < m:
        if left[i] == right[j]:
            i += 1
            j += 1
            continue
        diffs += 1
        if diffs > 1:
            return False
        if n == m:
            i += 1
            j += 1
        else:
            j += 1
    return diffs + (m - j) <= 1


def words_match(expected: str, heard: str) -> bool:
    """Exact normalized match, then a very conservative STT fuzz.

    Never treats synonyms as equal (shall ≠ will).
    """
    left = norm_word(expected)
    right = norm_word(heard)
    if not left or not right:
        return False
    if left == right:
        return True
    if min(len(left), len(right)) < 6:
        return False
    return _levenshtein_at_most_one(left, right)


def keyterm_shortlist(source_text: str, *, limit: int = KEYTERM_MAX) -> list[str]:
    """Deduplicated jargon/terminology from the provision, not every word."""
    seen: set[str] = set()
    out: list[str] = []
    for token in tokenize(source_text):
        normalized = norm_word(token)
        if not normalized or normalized in _FUNCTION_WORDS:
            continue
        if len(normalized) < KEYTERM_MIN_LEN:
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        out.append(normalized)
        if len(out) >= limit:
            break
    return out


@dataclass(frozen=True)
class AlignmentHit:
    index: int
    status: str  # "match" | "substitute"


def align_tokens(
    expected: list[str],
    heard: list[str],
    *,
    from_index: int = 0,
    window: int = LETTERS_ALIGN_WINDOW,
) -> list[AlignmentHit]:
    """Align ``heard`` against a bounded window of ``expected`` from ``from_index``."""
    if not expected:
        return []
    start = max(0, min(from_index, len(expected)))
    slice_expected = expected[start : start + max(1, window)]
    if not slice_expected:
        return []
    n = len(slice_expected)
    m = len(heard)
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        dp[i][0] = i * _GAP_COST
    for j in range(1, m + 1):
        dp[0][j] = j * _GAP_COST
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            diag = dp[i - 1][j - 1] + (
                _MATCH_COST
                if words_match(slice_expected[i - 1], heard[j - 1])
                else _SUB_COST
            )
            delete = dp[i - 1][j] + _GAP_COST
            insert = dp[i][j - 1] + _GAP_COST
            dp[i][j] = min(diag, delete, insert)

    # Prefix alignment: all heard tokens must be consumed, but trailing
    # expected words (not yet spoken) are free. That keeps a short utterance
    # from substituting against the last word of a long window.
    best_cost = dp[0][m]
    best_i = 0
    for i in range(1, n + 1):
        cost = dp[i][m]
        if cost < best_cost or (cost == best_cost and i > best_i):
            best_cost = cost
            best_i = i

    hits: list[AlignmentHit] = []
    i, j = best_i, m
    while i > 0 or j > 0:
        if (
            i > 0
            and j > 0
            and words_match(slice_expected[i - 1], heard[j - 1])
            and dp[i][j] == dp[i - 1][j - 1] + _MATCH_COST
        ):
            hits.append(AlignmentHit(index=start + i - 1, status="match"))
            i -= 1
            j -= 1
        elif (
            i > 0
            and j > 0
            and dp[i][j] == dp[i - 1][j - 1] + _SUB_COST
        ):
            hits.append(AlignmentHit(index=start + i - 1, status="substitute"))
            i -= 1
            j -= 1
        elif i > 0 and dp[i][j] == dp[i - 1][j] + _GAP_COST:
            i -= 1
        elif j > 0:
            j -= 1
        else:
            i -= 1
    hits.reverse()
    return hits


def align_text(
    expected_text: str,
    heard_text: str,
    *,
    from_index: int = 0,
    window: int = LETTERS_ALIGN_WINDOW,
) -> list[AlignmentHit]:
    return align_tokens(
        tokenize(expected_text),
        tokenize(heard_text),
        from_index=from_index,
        window=window,
    )
