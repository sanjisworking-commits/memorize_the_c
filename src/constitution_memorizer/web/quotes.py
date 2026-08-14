"""Curated civic quotes for the Learn completion layer."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def load_quotes(path: Path | str | None) -> list[dict[str, str]]:
    """Load ``[{text, author}, ...]``. Missing or empty files yield ``[]``."""
    if path is None:
        return []
    resolved = Path(path)
    if not resolved.is_file():
        return []
    raw = json.loads(resolved.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        return []
    out: list[dict[str, str]] = []
    for row in raw:
        if not isinstance(row, dict):
            continue
        text = str(row.get("text") or "").strip()
        author = str(row.get("author") or "").strip()
        if not text or not author:
            continue
        out.append({"text": text, "author": author})
    return out


def get_quote_for(quotes: list[dict[str, str]], seed: str) -> dict[str, str] | None:
    """Stateless deterministic pick. Same seed always returns the same quote."""
    if not quotes:
        return None
    digest = hashlib.sha1(seed.encode("utf-8")).hexdigest()
    index = int(digest, 16) % len(quotes)
    chosen: dict[str, Any] = quotes[index]
    return {"text": str(chosen["text"]), "author": str(chosen["author"])}
