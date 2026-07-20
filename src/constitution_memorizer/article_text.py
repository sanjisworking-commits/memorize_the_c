"""Assemble Bare Act article text without duplicating opening/body/provisos."""

from __future__ import annotations

import re

from constitution_memorizer.schemas import Article, ProvisionNode

_WS = re.compile(r"\s+")


def normalize_for_compare(text: str) -> str:
    return _WS.sub(" ", text.strip().lower())


def already_present(haystack: str, needle: str) -> bool:
    """True when needle is empty or already contained in haystack (whitespace-insensitive)."""
    n = needle.strip()
    if not n:
        return True
    h = haystack.strip()
    if not h:
        return False
    return normalize_for_compare(n) in normalize_for_compare(h)


def append_unique(chunks: list[str], piece: str) -> None:
    piece = piece.strip()
    if not piece:
        return
    if already_present("\n".join(chunks), piece):
        return
    chunks.append(piece)


def collapse_duplicate_paragraphs(text: str) -> str:
    """Drop repeated paragraphs (exact, after whitespace normalize)."""
    parts = [p.strip() for p in re.split(r"\n+", text) if p.strip()]
    out: list[str] = []
    seen: set[str] = set()
    for part in parts:
        key = normalize_for_compare(part)
        if key in seen:
            continue
        seen.add(key)
        out.append(part)
    return "\n".join(out)


def provision_text(node: ProvisionNode) -> str:
    """Flatten a provision node including children (roman inlined under letters)."""
    parts: list[str] = []
    head = f"{node.label} {node.text}".strip()
    if head:
        parts.append(head)
    for child in node.children:
        child_text = provision_text(child)
        if child_text:
            append_unique(parts, child_text)
    assembled = "\n".join(parts)
    for proviso in node.provisos:
        if not already_present(assembled, proviso):
            parts.append(proviso.strip())
            assembled = "\n".join(parts)
    for expl in node.explanations:
        if not already_present(assembled, expl):
            parts.append(expl.strip())
            assembled = "\n".join(parts)
    return collapse_duplicate_paragraphs("\n".join(parts))


def article_full_text(article: Article, *, paragraph_sep: str = "\n") -> str:
    """Build display/learn text for an Article without repeating shared fields."""
    chunks: list[str] = []
    opening = article.opening_text.strip()
    body = article.body_text.strip()
    if article.clauses:
        if opening:
            chunks.append(opening)
        for clause in article.clauses:
            append_unique(chunks, provision_text(clause))
    else:
        if opening and body:
            if opening == body or body.startswith(opening) or opening.startswith(body):
                chunks.append(body if len(body) >= len(opening) else opening)
            else:
                chunks.append(opening)
                append_unique(chunks, body)
        elif opening:
            chunks.append(opening)
        elif body:
            chunks.append(body)
    assembled = paragraph_sep.join(chunks)
    for proviso in article.provisos:
        if not already_present(assembled, proviso):
            chunks.append(proviso.strip())
            assembled = paragraph_sep.join(chunks)
    for expl in article.explanations:
        if not already_present(assembled, expl):
            chunks.append(expl.strip())
            assembled = paragraph_sep.join(chunks)
    return collapse_duplicate_paragraphs(paragraph_sep.join(c for c in chunks if c)).strip()
