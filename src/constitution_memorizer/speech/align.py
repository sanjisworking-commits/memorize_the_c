"""Verbatim word alignment for spoken Letters.

Needleman–Wunsch on normalized tokens. The browser never implements this;
it only paints ``{index, status}`` pairs returned by the speech route.

Letters completion uses *speakable* targets: clause numbering and
punctuation-only tokens are ignored. Blue/correct requires an exact
normalized match — no generic fuzzy substitutions.
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

# Clause/sub-clause markers and punctuation-only tokens. Keep in sync with
# isStructuralLettersToken in app.js.
_STRUCTURAL_RE = re.compile(
    r"""
    ^
    (?:
        [\(\[]?\d+[A-Za-z]?[\)\]]?\.?   # (1), 1., (1a), 12A
      | \(\d+\)\([A-Za-z]\)             # (1)(a)
      | \([A-Za-z]\)                    # (a)
      | \([ivxlcdmIVXLCDM]+\)           # (i), (iv), (iii)
      | [-–—−•·.,;:()/\[\]]+            # punctuation-only
    )
    $
    """,
    re.VERBOSE,
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


def is_structural_token(token: str) -> bool:
    """True for numbering / punctuation the learner is not asked to speak."""
    raw = (token or "").strip()
    if not raw:
        return True
    if _STRUCTURAL_RE.match(raw):
        return True
    return re.search(r"[A-Za-z]", raw) is None


def speakable_targets(source_text: str) -> list[tuple[int, str]]:
    """Display-index + token for whitespace words that must be spoken."""
    return [
        (index, token)
        for index, token in enumerate(tokenize(source_text))
        if not is_structural_token(token)
    ]


def words_match(expected: str, heard: str) -> bool:
    """Exact normalized match only. shall ≠ will; promulgation ≠ promulgaton."""
    left = norm_word(expected)
    right = norm_word(heard)
    if not left or not right:
        return False
    return left == right


def keyterm_shortlist(source_text: str, *, limit: int = KEYTERM_MAX) -> list[str]:
    """Deduplicated jargon/terminology from the provision, not every word."""
    seen: set[str] = set()
    out: list[str] = []
    for token in tokenize(source_text):
        if is_structural_token(token):
            continue
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
    index_map: list[int] | None = None,
) -> list[AlignmentHit]:
    """Align ``heard`` against a bounded window of ``expected`` from ``from_index``.

    ``from_index`` and returned ``index`` values are *display* indexes when
    ``index_map`` is omitted (identity). Pass ``index_map`` when ``expected``
    is already a speakable slice whose display indexes differ from 0..n.
    """
    if not expected:
        return []
    display = index_map if index_map is not None else list(range(len(expected)))
    if len(display) != len(expected):
        display = list(range(len(expected)))

    start_pos = 0
    for pos, display_index in enumerate(display):
        if display_index >= from_index:
            start_pos = pos
            break
    else:
        return []

    slice_expected = expected[start_pos : start_pos + max(1, window)]
    slice_display = display[start_pos : start_pos + max(1, window)]
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
            hits.append(AlignmentHit(index=slice_display[i - 1], status="match"))
            i -= 1
            j -= 1
        elif (
            i > 0
            and j > 0
            and dp[i][j] == dp[i - 1][j - 1] + _SUB_COST
        ):
            hits.append(AlignmentHit(index=slice_display[i - 1], status="substitute"))
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
    targets = speakable_targets(expected_text)
    return align_tokens(
        [word for _index, word in targets],
        tokenize(heard_text),
        from_index=from_index,
        window=window,
        index_map=[index for index, _word in targets],
    )
