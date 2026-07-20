"""Curated amendment history for Browse + Learn footnotes (Sprint 21)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from constitution_memorizer.utils.json_io import read_json

DEFAULT_AMENDMENTS_PATH = (
    Path(__file__).resolve().parents[3] / "data" / "reference" / "amendments.seed.json"
)


@dataclass(frozen=True)
class Amendment:
    article: str
    no: str
    year: str
    text: str


@dataclass(frozen=True)
class ArticleAmendments:
    article: str
    amendments: list[Amendment] = field(default_factory=list)
    learn_note: str | None = None

    @property
    def has_amendments(self) -> bool:
        return len(self.amendments) > 0

    @property
    def count_label(self) -> str:
        n = len(self.amendments)
        if n == 0:
            return "unamended"
        if n == 1:
            return "1 amendment"
        return f"{n} amendments"


def load_amendments(path: Path | str | None = None) -> dict[str, ArticleAmendments]:
    """Load curated amendment seed keyed by article number."""
    resolved = Path(path) if path is not None else DEFAULT_AMENDMENTS_PATH
    if not resolved.exists():
        return {}
    data = read_json(resolved)
    articles = data.get("articles") or {}
    out: dict[str, ArticleAmendments] = {}
    for number, payload in articles.items():
        key = str(number)
        rows = payload.get("amendments") or []
        amendments = [
            Amendment(
                article=key,
                no=str(row["no"]),
                year=str(row["year"]),
                text=str(row["text"]),
            )
            for row in rows
        ]
        note = payload.get("learn_note")
        out[key] = ArticleAmendments(
            article=key,
            amendments=amendments,
            learn_note=str(note) if note else None,
        )
    return out


def get_article_amendments(
    catalog: dict[str, ArticleAmendments],
    article_number: str | None,
) -> ArticleAmendments | None:
    """Return curated entry, or None when the article is not in the seed."""
    if not article_number:
        return None
    return catalog.get(str(article_number))
