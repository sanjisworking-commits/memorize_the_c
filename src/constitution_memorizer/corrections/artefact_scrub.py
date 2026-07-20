"""Deterministic scrub of Docling/display artefacts in reviewed Articles."""

from __future__ import annotations

import re

from constitution_memorizer.schemas import Article, ConstitutionDocument, ProvisionNode

_FORMULA_RE = re.compile(r"<!--\s*formula-not-decoded\s*-->", re.IGNORECASE)
_PUA_RE = re.compile(r"[\ue000-\uf8ff]")
_MULTI_SPACE_RE = re.compile(r"[^\S\n\r]{2,}")
_MULTI_BLANK_RE = re.compile(r"\n{3,}")
_LEADING_DASH_RE = re.compile(r"(?m)^-\s+")
_TRAILING_DASH_RE = re.compile(r"[ \t]+-[ \t]*$", re.MULTILINE)


def scrub_display_text(text: str) -> str:
    """
    Remove extraction junk that is not Bare Act wording.

    Does not paraphrase legal text — only drops Docling placeholders,
    private-use glyphs, and collapsed dash/whitespace debris.
    """
    if not text:
        return text
    cleaned = _FORMULA_RE.sub("", text)
    cleaned = _PUA_RE.sub("", cleaned)
    cleaned = _LEADING_DASH_RE.sub("", cleaned)
    cleaned = _TRAILING_DASH_RE.sub("", cleaned)
    cleaned = _MULTI_SPACE_RE.sub(" ", cleaned)
    cleaned = _MULTI_BLANK_RE.sub("\n\n", cleaned)
    cleaned = "\n".join(line.rstrip() for line in cleaned.split("\n"))
    return cleaned.strip()


def _scrub_provision(node: ProvisionNode) -> bool:
    changed = False
    new_text = scrub_display_text(node.text)
    if new_text != node.text:
        node.text = new_text
        changed = True
    for child in node.children:
        if _scrub_provision(child):
            changed = True
    for index, proviso in enumerate(list(node.provisos)):
        cleaned = scrub_display_text(proviso)
        if cleaned != proviso:
            node.provisos[index] = cleaned
            changed = True
    for index, expl in enumerate(list(node.explanations)):
        cleaned = scrub_display_text(expl)
        if cleaned != expl:
            node.explanations[index] = cleaned
            changed = True
    return changed


def _dedupe_opening_against_body(article: Article) -> str | None:
    """
    Clear opening_text when it duplicates or is a prefix of body_text.

    Browse/Learn concatenate opening + body; duplicate openings cause
    visible repetition across hundreds of Articles.
    """
    opening = article.opening_text.strip()
    body = article.body_text.strip()
    if not opening or not body:
        return None
    if opening == body:
        article.opening_text = ""
        return "cleared opening identical to body"
    if body.startswith(opening):
        article.opening_text = ""
        return "cleared opening that prefixes body"
    if opening.startswith(body) and len(opening) > len(body) + 20:
        article.body_text = article.opening_text
        article.opening_text = ""
        return "moved longer opening into body; cleared opening"
    return None


def scrub_article(article: Article) -> list[str]:
    """Scrub one article; return human-readable change notes."""
    notes: list[str] = []
    for field in ("opening_text", "body_text"):
        raw = getattr(article, field) or ""
        cleaned = scrub_display_text(raw)
        if cleaned != raw:
            setattr(article, field, cleaned)
            notes.append(f"{article.id}: scrubbed {field}")

    if article.title:
        cleaned_title = " ".join(scrub_display_text(article.title).split())
        if cleaned_title != article.title:
            article.title = cleaned_title or None
            notes.append(f"{article.id}: scrubbed title")

    for index, proviso in enumerate(list(article.provisos)):
        cleaned = scrub_display_text(proviso)
        if cleaned != proviso:
            article.provisos[index] = cleaned
            notes.append(f"{article.id}: scrubbed proviso")
    for index, expl in enumerate(list(article.explanations)):
        cleaned = scrub_display_text(expl)
        if cleaned != expl:
            article.explanations[index] = cleaned
            notes.append(f"{article.id}: scrubbed explanation")

    for clause in article.clauses:
        if _scrub_provision(clause):
            notes.append(f"{article.id}: scrubbed clause text")

    dedupe = _dedupe_opening_against_body(article)
    if dedupe:
        notes.append(f"{article.id}: {dedupe}")
    return notes


def scrub_document(doc: ConstitutionDocument) -> list[str]:
    """Scrub every article and schedule field in a reviewed document copy."""
    notes: list[str] = []
    for part in doc.parts:
        for article in part.articles:
            notes.extend(scrub_article(article))
        for chapter in part.chapters:
            for article in chapter.articles:
                notes.extend(scrub_article(article))

    for schedule in doc.schedules:
        for field in ("title", "body_text"):
            raw = getattr(schedule, field) or ""
            if not isinstance(raw, str) or not raw:
                continue
            cleaned = scrub_display_text(raw)
            if field == "title":
                cleaned = " ".join(cleaned.split())
            if cleaned != raw:
                setattr(schedule, field, cleaned)
                notes.append(f"{schedule.id}: scrubbed {field}")
        for section in schedule.sections:
            for field in ("title", "body_text"):
                raw = getattr(section, field) or ""
                if not isinstance(raw, str) or not raw:
                    continue
                cleaned = scrub_display_text(raw)
                if field == "title":
                    cleaned = " ".join(cleaned.split())
                if cleaned != raw:
                    setattr(section, field, cleaned)
                    notes.append(f"{section.id or schedule.id}: scrubbed section {field}")
        for lst in schedule.lists:
            for field in ("name", "body_text"):
                raw = getattr(lst, field) or ""
                if not isinstance(raw, str) or not raw:
                    continue
                cleaned = scrub_display_text(raw)
                if cleaned != raw:
                    setattr(lst, field, cleaned)
                    notes.append(f"{lst.id or schedule.id}: scrubbed list {field}")
            new_items: list[str] = []
            items_changed = False
            for item in lst.items:
                cleaned = scrub_display_text(item)
                new_items.append(cleaned)
                if cleaned != item:
                    items_changed = True
            if items_changed:
                lst.items = new_items
                notes.append(f"{lst.id or schedule.id}: scrubbed list items")
    return notes


def should_include_opening(opening: str, body: str) -> bool:
    """False when opening would duplicate body in concatenated display text."""
    op = opening.strip()
    bd = body.strip()
    if not op:
        return False
    if not bd:
        return True
    if op == bd:
        return False
    if bd.startswith(op):
        return False
    return True
