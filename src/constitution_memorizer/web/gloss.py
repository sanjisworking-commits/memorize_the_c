"""Per-article Explain-it-back placeholders (Sprint 22)."""

from __future__ import annotations

from pathlib import Path

from constitution_memorizer.utils.json_io import read_json

DEFAULT_GLOSS_PLACEHOLDERS_PATH = (
    Path(__file__).resolve().parents[3]
    / "data"
    / "reference"
    / "gloss_placeholders.seed.json"
)

FALLBACK_PLACEHOLDER = "e.g. Explain this article in your own words…"


def load_gloss_placeholders(path: Path | str | None = None) -> dict[str, str]:
    """Return article_number → placeholder string (always starts with 'e.g. ')."""
    resolved = Path(path) if path is not None else DEFAULT_GLOSS_PLACEHOLDERS_PATH
    if not resolved.exists():
        return {}
    data = read_json(resolved)
    out: dict[str, str] = {}
    for number, text in (data.get("placeholders") or {}).items():
        value = str(text).strip()
        if value and not value.startswith("e.g. "):
            value = "e.g. " + value
        if value:
            out[str(number)] = value
    return out


def gloss_placeholder_for(
    placeholders: dict[str, str],
    article_number: str,
    *,
    fallback: str = FALLBACK_PLACEHOLDER,
) -> str:
    return placeholders.get(str(article_number), fallback)
