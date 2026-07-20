"""Deterministic text fallback splitter for flat Article bodies (Sprint 2)."""

from __future__ import annotations

import re

from constitution_memorizer.parsing.clause_parser import (
    classify_label,
    make_clause_node,
    make_subclause_node,
    nesting_rank,
)
from constitution_memorizer.schemas import LabelType, ProvisionNode

# Provision markers at line start, or immediately after a dash (Bare Act list style).
# Avoid matching mid-sentence refs like "sub-clause (a) of clause (1)".
_MARKER_RE = re.compile(
    r"(?:^|(?<=[-–—]))\s*"
    r"\((?P<label>\d+[A-Za-z]?|[a-z]|[ivxlcdm]+|[A-Z])\)\s*",
    re.MULTILINE,
)


def _looks_structured(body: str) -> bool:
    """True when body contains at least one parenthetical provision marker."""
    return _MARKER_RE.search(body or "") is not None


def split_flat_article_body(article_number: str, body: str) -> list[ProvisionNode]:
    """
    Parse a flat Article body into a synthetic clause tree.

    Returns an empty list when no provision markers are found (caller keeps
    a single ARTICLE unit). Nested roman markers under alphabetic labels are
    preserved as children of the letter node.
    """
    text = (body or "").strip()
    if not text or not _looks_structured(text):
        return []

    matches = list(_MARKER_RE.finditer(text))
    if not matches:
        return []

    # Leading prose before the first marker becomes opening text on the first clause.
    leading = text[: matches[0].start()].strip()

    roots: list[ProvisionNode] = []
    stack: list[ProvisionNode] = []

    for index, match in enumerate(matches):
        label = match.group("label")
        label_type = classify_label(label)
        # Bare Act letter clauses (a)(b)(c)… — single c/d/l/m are letters, not Roman.
        # Keep i/v/x as Roman so (i)(ii) nest under alphabetic parents.
        if len(label) == 1 and label.isalpha() and label.islower():
            if label not in {"i", "v", "x"}:
                label_type = LabelType.ALPHABETIC
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        segment = text[match.end() : end].strip()

        rank = nesting_rank(label_type)
        # Top-level: numeric / alphanumeric (and lone letters if no parent yet).
        if not stack or rank == 0:
            node = make_clause_node(article_number, label, segment, label_type)
            if leading and not roots:
                if node.text:
                    node.text = f"{leading} {node.text}".strip()
                else:
                    node.text = leading
                leading = ""
            roots.append(node)
            stack = [node]
            continue

        while len(stack) > 1 and nesting_rank(stack[-1].label_type) >= rank:
            stack.pop()

        parent = stack[-1]
        if nesting_rank(parent.label_type) >= rank:
            # Sibling at same/outer level with no deeper parent — start new root.
            node = make_clause_node(article_number, label, segment, label_type)
            roots.append(node)
            stack = [node]
            continue

        child = make_subclause_node(parent.id, label, segment, label_type)
        parent.children.append(child)
        # Keep stack as [..., parent, child] trimming peers of child.
        while len(stack) > 1 and nesting_rank(stack[-1].label_type) >= rank:
            stack.pop()
        if stack and nesting_rank(stack[-1].label_type) < rank:
            stack.append(child)
        else:
            stack = [child]

    # If leading prose remained (no clauses created somehow), drop empty result.
    if not roots and leading:
        return []
    return roots


def has_provision_markers(body: str) -> bool:
    """Public helper for callers/tests."""
    return _looks_structured(body)
