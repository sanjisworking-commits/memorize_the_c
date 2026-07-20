"""Clause and nested subclause parsing helpers."""

from __future__ import annotations

import re
from dataclasses import dataclass

from constitution_memorizer.parsing.patterns import (
    CLAUSE_LABEL_RE,
    EXCEPTION_RE,
    EXPLANATION_RE,
    ILLUSTRATION_RE,
    PROVISO_RE,
)
from constitution_memorizer.schemas import LabelType, ProvisionNode, SourceProvenance
from constitution_memorizer.utils.identifiers import clause_id, subclause_id


@dataclass
class SpecialProvision:
    """A proviso, explanation, exception or illustration."""

    kind: str  # proviso | explanation | exception | illustration
    label: str | None
    text: str


def classify_label(label: str) -> LabelType:
    """Classify a parenthetical provision label."""
    if re.fullmatch(r"\d+", label):
        return LabelType.NUMERIC
    if re.fullmatch(r"\d+[A-Za-z]+", label):
        return LabelType.ALPHANUMERIC
    if re.fullmatch(r"[ivxlcdm]+", label):
        return LabelType.ROMAN
    if re.fullmatch(r"[a-z]", label):
        return LabelType.ALPHABETIC
    if re.fullmatch(r"[A-Z]", label):
        return LabelType.UPPER_ALPHA
    return LabelType.UNKNOWN


def parse_clause_line(line: str) -> tuple[str, str, LabelType] | None:
    """
    Parse a clause/subclause opening line.

    Returns ``(label, body, label_type)`` where label excludes parentheses,
    e.g. ``(\"1\", \"text...\", NUMERIC)``.
    """
    match = CLAUSE_LABEL_RE.match(line.strip())
    if not match:
        return None
    label = match.group("label")
    body = match.group("body").strip()
    return label, body, classify_label(label)


def parse_special_provision(line: str) -> SpecialProvision | None:
    """Detect proviso / explanation / exception / illustration lines."""
    stripped = line.strip()
    if not stripped:
        return None

    proviso = PROVISO_RE.match(stripped)
    if proviso:
        return SpecialProvision(kind="proviso", label=None, text=proviso.group("text").strip())

    for kind, pattern in (
        ("explanation", EXPLANATION_RE),
        ("exception", EXCEPTION_RE),
        ("illustration", ILLUSTRATION_RE),
    ):
        match = pattern.match(stripped)
        if match:
            label = match.group("label").strip()
            body = match.group("body").strip()
            text = stripped if not body else f"{label}. {body}".strip()
            return SpecialProvision(kind=kind, label=label, text=text)

    return None


def nesting_rank(label_type: LabelType) -> int:
    """
    Return a nesting rank for provision labels.

    Lower rank = outer. Numeric clauses are outermost; roman and alpha nest inside.
    """
    order = {
        LabelType.NUMERIC: 0,
        LabelType.ALPHANUMERIC: 0,
        LabelType.ALPHABETIC: 1,
        LabelType.UPPER_ALPHA: 2,
        LabelType.ROMAN: 3,
        LabelType.UNKNOWN: 4,
    }
    return order[label_type]


def make_clause_node(
    article_number: str,
    label: str,
    body: str,
    label_type: LabelType,
) -> ProvisionNode:
    """Create a top-level clause node for an Article."""
    return ProvisionNode(
        id=clause_id(article_number, label),
        label=f"({label})",
        label_type=label_type,
        text=body,
        source=SourceProvenance(raw_text=body),
    )


def make_subclause_node(
    parent_id: str,
    label: str,
    body: str,
    label_type: LabelType,
) -> ProvisionNode:
    """Create a nested subclause node."""
    return ProvisionNode(
        id=subclause_id(parent_id, f"({label})"),
        label=f"({label})",
        label_type=label_type,
        text=body,
        source=SourceProvenance(raw_text=body),
    )


def append_text(node: ProvisionNode, text: str) -> None:
    """Append continued text to a provision node."""
    text = text.strip()
    if not text:
        return
    if node.text:
        node.text = f"{node.text} {text}"
    else:
        node.text = text
    if node.source.raw_text:
        node.source.raw_text = f"{node.source.raw_text}\n{text}"
    else:
        node.source.raw_text = text
