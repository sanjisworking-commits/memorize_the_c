"""Curated Judicial Evolution notes for Learn (context, not Bare Act text)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from constitution_memorizer.utils.json_io import read_json

DEFAULT_PATH = (
    Path(__file__).resolve().parents[3]
    / "data"
    / "reference"
    / "judicial_evolution.seed.json"
)


@dataclass(frozen=True)
class JudicialEntry:
    heading: str
    body: str


@dataclass(frozen=True)
class JudicialEvolution:
    article: str
    section_title: str = "Judicial Evolution"
    entries: list[JudicialEntry] = field(default_factory=list)

    @property
    def has_entries(self) -> bool:
        return bool(self.entries)


def load_judicial_evolution(
    path: Path | str | None = None,
) -> dict[str, JudicialEvolution]:
    """Load article-number → Judicial Evolution map."""
    resolved = Path(path) if path is not None else DEFAULT_PATH
    if not resolved.exists():
        return {}
    data = read_json(resolved)
    articles = data.get("articles") or {}
    out: dict[str, JudicialEvolution] = {}
    for number, payload in articles.items():
        key = str(number)
        rows = payload.get("entries") or []
        entries = [
            JudicialEntry(
                heading=str(row.get("heading") or "").strip(),
                body=str(row.get("body") or "").strip(),
            )
            for row in rows
            if str(row.get("heading") or "").strip()
            and str(row.get("body") or "").strip()
        ]
        if not entries:
            continue
        title = str(payload.get("section_title") or "Judicial Evolution").strip()
        out[key] = JudicialEvolution(
            article=key,
            section_title=title or "Judicial Evolution",
            entries=entries,
        )
    return out


def get_judicial_evolution(
    catalog: dict[str, JudicialEvolution],
    article_number: str | None,
) -> JudicialEvolution | None:
    if not article_number:
        return None
    return catalog.get(str(article_number))
