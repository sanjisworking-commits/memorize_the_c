"""Word-level Bare Act footnotes for Learn Read/Card hover."""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from pathlib import Path

from markupsafe import Markup

from constitution_memorizer.utils.json_io import read_json

DEFAULT_ANNOTATIONS_PATH = (
    Path(__file__).resolve().parents[3] / "data" / "reference" / "text_annotations.json"
)


@dataclass(frozen=True)
class TextAnnotation:
    target: str
    note: str


def load_text_annotations(
    path: Path | str | None = None,
) -> dict[str, list[TextAnnotation]]:
    """Load unit-id → annotation list map."""
    resolved = Path(path) if path is not None else DEFAULT_ANNOTATIONS_PATH
    if not resolved.exists():
        return {}
    data = read_json(resolved)
    units = data.get("units") or {}
    out: dict[str, list[TextAnnotation]] = {}
    for unit_id, rows in units.items():
        anns: list[TextAnnotation] = []
        for row in rows or []:
            target = str(row.get("target") or "").strip()
            note = str(row.get("note") or "").strip()
            if target and note:
                anns.append(TextAnnotation(target=target, note=note))
        if anns:
            out[str(unit_id)] = anns
    return out


def annotations_for_unit(
    catalog: dict[str, list[TextAnnotation]],
    unit_id: str | None,
) -> list[TextAnnotation]:
    if not unit_id:
        return []
    return list(catalog.get(unit_id) or [])


def annotate_plain_text(text: str, annotations: list[TextAnnotation]) -> Markup:
    """
    Escape plain Bare Act text and wrap the first whole-word hit of each target.

    Memorized modes keep ``unit.text`` plain; Read/Card may render this HTML.
    """
    if not text:
        return Markup("")
    if not annotations:
        return Markup(html.escape(text))

    remaining = text
    chunks: list[str] = []
    for ann in annotations:
        pattern = re.compile(rf"(?<!\w)({re.escape(ann.target)})(?!\w)")
        match = pattern.search(remaining)
        if match is None:
            continue
        chunks.append(html.escape(remaining[: match.start()]))
        word = html.escape(match.group(1))
        tip = html.escape(ann.note)
        chunks.append(
            '<span class="bare-fn" tabindex="0">'
            f'<span class="bare-fn-word">{word}</span>'
            f'<span class="bare-fn-tip" role="tooltip">{tip}</span>'
            "</span>"
        )
        remaining = remaining[match.end() :]
    chunks.append(html.escape(remaining))
    return Markup("".join(chunks))
