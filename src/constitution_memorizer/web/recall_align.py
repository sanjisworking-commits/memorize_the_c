"""Token alignment for recall scoring (Type / Recite accuracy maps).

Matches the client helper in ``static/recall_align.js``: normalize words by
lowercasing and stripping non-alphanumerics, then LCS-align spoken/typed
tokens against Bare Act source tokens.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_NON_ALNUM = re.compile(r"[^a-z0-9]")


def norm_word(text: str) -> str:
    return _NON_ALNUM.sub("", text.lower())


def tokenize(text: str) -> list[str]:
    stripped = text.strip()
    if not stripped:
        return []
    return stripped.split()


@dataclass(frozen=True)
class AlignResult:
    """Alignment of spoken/typed tokens against Bare Act source words."""

    source_words: list[str]
    spoken_words: list[str]
    hit_indices: frozenset[int]
    spoken_hit_indices: frozenset[int]
    extras: list[str]

    @property
    def hits(self) -> int:
        return len(self.hit_indices)

    @property
    def total(self) -> int:
        return len(self.source_words)

    @property
    def percent(self) -> int:
        if not self.total:
            return 0
        return int(round(100 * self.hits / self.total))

    def stats_label(self) -> str:
        return f"{self.hits} / {self.total} recalled · {self.percent}%"


def align_tokens(source_words: list[str], spoken_words: list[str]) -> AlignResult:
    """Longest-common-subsequence alignment on normalized tokens."""
    src_norm = [norm_word(w) for w in source_words]
    spk_norm = [norm_word(w) for w in spoken_words]
    n = len(src_norm)
    m = len(spk_norm)

    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            if src_norm[i - 1] and src_norm[i - 1] == spk_norm[j - 1]:
                dp[i][j] = dp[i - 1][j - 1] + 1
            else:
                dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])

    hit_indices: set[int] = set()
    spoken_hit_indices: set[int] = set()
    i, j = n, m
    while i > 0 and j > 0:
        if src_norm[i - 1] and src_norm[i - 1] == spk_norm[j - 1]:
            hit_indices.add(i - 1)
            spoken_hit_indices.add(j - 1)
            i -= 1
            j -= 1
        elif dp[i - 1][j] >= dp[i][j - 1]:
            i -= 1
        else:
            j -= 1

    extras = [
        spoken_words[k]
        for k in range(m)
        if k not in spoken_hit_indices and spk_norm[k]
    ]
    return AlignResult(
        source_words=list(source_words),
        spoken_words=list(spoken_words),
        hit_indices=frozenset(hit_indices),
        spoken_hit_indices=frozenset(spoken_hit_indices),
        extras=extras,
    )


def align_text(source_text: str, spoken_text: str) -> AlignResult:
    return align_tokens(tokenize(source_text), tokenize(spoken_text))
