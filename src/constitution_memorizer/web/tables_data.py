"""Load static quick-reference Tables tab payloads (Sprint 29)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from constitution_memorizer.utils.json_io import read_json

DEFAULT_TABLES_DIR = (
    Path(__file__).resolve().parents[3] / "data" / "reference" / "tables"
)


@dataclass(frozen=True)
class TableTabMeta:
    id: str
    label: str


@dataclass(frozen=True)
class TableBlock:
    label: str | None
    head: list[str]
    rows: list[list[str]]
    muted_values: frozenset[str] = field(default_factory=frozenset)


@dataclass(frozen=True)
class TableTabPayload:
    id: str
    label: str
    title: str
    note: str
    grid: str
    tables: list[TableBlock]


def list_table_tabs(tables_dir: Path | str | None = None) -> list[TableTabMeta]:
    root = Path(tables_dir) if tables_dir is not None else DEFAULT_TABLES_DIR
    index_path = root / "index.json"
    if not index_path.exists():
        return []
    data = read_json(index_path)
    return [
        TableTabMeta(id=str(t["id"]), label=str(t["label"]))
        for t in (data.get("tabs") or [])
    ]


def load_table_tab(
    tab_id: str,
    tables_dir: Path | str | None = None,
) -> TableTabPayload | None:
    root = Path(tables_dir) if tables_dir is not None else DEFAULT_TABLES_DIR
    path = root / f"{tab_id}.json"
    if not path.exists():
        return None
    data = read_json(path)
    blocks: list[TableBlock] = []
    for block in data.get("tables") or []:
        muted = block.get("muted_row_values") or []
        blocks.append(
            TableBlock(
                label=block.get("label"),
                head=[str(h) for h in (block.get("head") or [])],
                rows=[[str(c) for c in row] for row in (block.get("rows") or [])],
                muted_values=frozenset(str(v) for v in muted),
            )
        )
    return TableTabPayload(
        id=str(data.get("id") or tab_id),
        label=str(data.get("label") or tab_id),
        title=str(data.get("title") or ""),
        note=str(data.get("note") or ""),
        grid=str(data.get("grid") or "1fr"),
        tables=blocks,
    )


def row_is_muted(block: TableBlock, row: list[str]) -> bool:
    if not row or not block.muted_values:
        return False
    return row[0] in block.muted_values
