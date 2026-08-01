"""Word-level Bare Act footnotes for Learn Read/Card hover."""

from __future__ import annotations

import html
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from markupsafe import Markup

from constitution_memorizer.utils.json_io import read_json

logger = logging.getLogger(__name__)

DEFAULT_ANNOTATIONS_PATH = (
    Path(__file__).resolve().parents[3] / "data" / "reference" / "text_annotations.json"
)

ContentNodeType = Literal["text", "note_ref"]


@dataclass(frozen=True)
class NoteRecord:
    """Reusable secondary note referenced by note_ref content nodes."""

    id: str
    note: str


@dataclass(frozen=True)
class ContentText:
    value: str


@dataclass(frozen=True)
class ContentNoteRef:
    label: str
    note_id: str


ContentNode = ContentText | ContentNoteRef


@dataclass(frozen=True)
class TextAnnotation:
    """Word annotation: legacy flat note and/or structured tip content."""

    target: str
    note: str = ""
    content: tuple[ContentNode, ...] = ()


@dataclass(frozen=True)
class TextAnnotationsCatalog:
    """Loaded annotations file: unit map + shared notes."""

    units: dict[str, list[TextAnnotation]] = field(default_factory=dict)
    notes: dict[str, NoteRecord] = field(default_factory=dict)

    def __contains__(self, key: object) -> bool:
        return key in self.units

    def __getitem__(self, key: str) -> list[TextAnnotation]:
        return self.units[key]

    def get(self, key: str, default: list[TextAnnotation] | None = None) -> list[TextAnnotation]:
        return self.units.get(key, [] if default is None else default)


def _parse_content_nodes(raw: object) -> tuple[ContentNode, ...]:
    if not isinstance(raw, list):
        return ()
    nodes: list[ContentNode] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        kind = str(item.get("type") or "").strip()
        if kind == "text":
            value = str(item.get("value") or "")
            if value:
                nodes.append(ContentText(value=value))
        elif kind == "note_ref":
            label = str(item.get("label") or "").strip()
            note_id = str(item.get("note_id") or "").strip()
            if label and note_id:
                nodes.append(ContentNoteRef(label=label, note_id=note_id))
        else:
            logger.warning("Skipping unsupported annotation content type: %r", kind)
    return tuple(nodes)


def load_text_annotations(
    path: Path | str | None = None,
) -> TextAnnotationsCatalog:
    """Load unit-id → annotation list map and shared notes."""
    resolved = Path(path) if path is not None else DEFAULT_ANNOTATIONS_PATH
    if not resolved.exists():
        return TextAnnotationsCatalog()
    data = read_json(resolved)
    notes_raw = data.get("notes") or {}
    notes: dict[str, NoteRecord] = {}
    if isinstance(notes_raw, dict):
        for note_id, row in notes_raw.items():
            if not isinstance(row, dict):
                continue
            note_text = str(row.get("note") or "").strip()
            nid = str(note_id).strip()
            if nid and note_text:
                notes[nid] = NoteRecord(id=nid, note=note_text)

    units_raw = data.get("units") or {}
    out: dict[str, list[TextAnnotation]] = {}
    for unit_id, rows in units_raw.items():
        anns: list[TextAnnotation] = []
        for row in rows or []:
            if not isinstance(row, dict):
                continue
            target = str(row.get("target") or "").strip()
            if not target:
                continue
            note = str(row.get("note") or "").strip()
            content = _parse_content_nodes(row.get("content"))
            if not note and not content:
                continue
            anns.append(TextAnnotation(target=target, note=note, content=content))
        if anns:
            out[str(unit_id)] = anns
    return TextAnnotationsCatalog(units=out, notes=notes)


def annotations_for_unit(
    catalog: TextAnnotationsCatalog | dict[str, list[TextAnnotation]],
    unit_id: str | None,
) -> list[TextAnnotation]:
    if not unit_id:
        return []
    if isinstance(catalog, TextAnnotationsCatalog):
        return list(catalog.get(unit_id) or [])
    return list(catalog.get(unit_id) or [])


def _sanitize_id_part(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip()).strip("-").lower()
    return cleaned or "x"


def _plain_tip_fallback(ann: TextAnnotation, notes: dict[str, NoteRecord]) -> str:
    """Plain-text tip for title/data-note attributes (no nested controls)."""
    if ann.content:
        parts: list[str] = []
        for node in ann.content:
            if isinstance(node, ContentText):
                parts.append(node.value)
            else:
                parts.append(node.label)
        return "".join(parts).strip()
    return ann.note


def render_tip_inner(
    ann: TextAnnotation,
    notes: dict[str, NoteRecord],
    *,
    id_prefix: str,
) -> str:
    """
    Render tip body HTML from structured nodes or legacy note.

    All text is escaped. note_ref becomes a button + nested tip (one level).
    Missing note_id renders the label as plain escaped text (no button).
    """
    if not ann.content:
        return html.escape(ann.note)

    chunks: list[str] = []
    nested_index = 0
    for node in ann.content:
        if isinstance(node, ContentText):
            chunks.append(html.escape(node.value))
            continue
        record = notes.get(node.note_id)
        label = html.escape(node.label)
        if record is None:
            logger.warning("Missing annotation note_id %r; rendering plain label", node.note_id)
            chunks.append(label)
            continue
        nested_index += 1
        tip_id = (
            f"{_sanitize_id_part(id_prefix)}-nested-"
            f"{_sanitize_id_part(node.note_id)}-{nested_index}"
        )
        note_body = html.escape(record.note)
        chunks.append(
            f'<button type="button" class="bare-fn-nested-trigger" '
            f'aria-expanded="false" aria-controls="{tip_id}">'
            f"{label}</button>"
            f'<span id="{tip_id}" class="bare-fn-nested-tip" role="tooltip" hidden>'
            f"{note_body}</span>"
        )
    return "".join(chunks)


def annotate_plain_text(
    text: str,
    annotations: list[TextAnnotation],
    *,
    notes: dict[str, NoteRecord] | None = None,
    unit_id: str | None = None,
) -> Markup:
    """
    Escape plain Bare Act text and wrap the first whole-word hit of each target.

    Tip copy lives in a ``hidden`` ``.bare-fn-tip`` element (shown by CSS/JS on
    hover/focus/tap). Memorized modes keep ``unit.text`` plain.
    """
    if not text:
        return Markup("")
    if not annotations:
        return Markup(html.escape(text))

    note_map = notes or {}
    remaining = text
    chunks: list[str] = []
    for index, ann in enumerate(annotations):
        pattern = re.compile(rf"(?<!\w)({re.escape(ann.target)})(?!\w)")
        match = pattern.search(remaining)
        if match is None:
            continue
        chunks.append(html.escape(remaining[: match.start()]))
        word = html.escape(match.group(1))
        plain = _plain_tip_fallback(ann, note_map)
        tip_attr = html.escape(plain, quote=True)
        id_prefix = f"{unit_id or 'fn'}-fn-{index}"
        tip_body = render_tip_inner(ann, note_map, id_prefix=id_prefix)
        # Structured tips omit title= (nested controls are not expressible there).
        title_attr = "" if ann.content else f' title="{tip_attr}"'
        chunks.append(
            f'<span class="bare-fn" tabindex="0" data-note="{tip_attr}"'
            f"{title_attr}>"
            f'<span class="bare-fn-word">{word}</span>'
            f'<sup class="bare-fn-mark" aria-hidden="true">*</sup>'
            f'<span class="bare-fn-tip" role="tooltip" hidden>{tip_body}</span>'
            "</span>"
        )
        remaining = remaining[match.end() :]
    chunks.append(html.escape(remaining))
    return Markup("".join(chunks))
