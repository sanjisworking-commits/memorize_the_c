"""Deterministic JSON read/write helpers."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from constitution_memorizer.exceptions import OverwriteRefusedError

logger = logging.getLogger(__name__)


def ensure_parent_dir(path: Path) -> None:
    """Create parent directories for ``path`` if they do not exist."""
    path.parent.mkdir(parents=True, exist_ok=True)


def check_overwrite(path: Path, force: bool) -> None:
    """Raise if ``path`` exists and ``force`` is False."""
    if path.exists() and not force:
        raise OverwriteRefusedError(
            f"Refusing to overwrite existing file without --force: {path}"
        )


def write_json(
    path: Path,
    data: Any,
    *,
    force: bool = False,
    indent: int | None = 2,
    minified: bool = False,
) -> Path:
    """
    Write ``data`` as UTF-8 JSON with ``ensure_ascii=False``.

    When ``minified`` is True, separators are compact and indent is ignored.
    """
    check_overwrite(path, force)
    ensure_parent_dir(path)

    if minified:
        text = json.dumps(data, ensure_ascii=False, separators=(",", ":"), sort_keys=False)
    else:
        text = json.dumps(data, ensure_ascii=False, indent=indent, sort_keys=False)
        text += "\n"

    path.write_text(text, encoding="utf-8")
    logger.info("Wrote JSON: %s", path)
    return path


def read_json(path: Path) -> Any:
    """Read a UTF-8 JSON file."""
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def write_text(path: Path, content: str, *, force: bool = False) -> Path:
    """Write a UTF-8 text file, respecting the overwrite policy."""
    check_overwrite(path, force)
    ensure_parent_dir(path)
    path.write_text(content, encoding="utf-8")
    logger.info("Wrote text: %s", path)
    return path


def read_text(path: Path) -> str:
    """Read a UTF-8 text file."""
    return path.read_text(encoding="utf-8")


def model_to_dict(model: Any) -> dict[str, Any]:
    """Convert a Pydantic model (or compatible object) to a plain dict."""
    if hasattr(model, "model_dump"):
        return model.model_dump(mode="json")
    if hasattr(model, "dict"):
        return model.dict()
    if isinstance(model, dict):
        return model
    raise TypeError(f"Cannot convert type to dict: {type(model)!r}")
