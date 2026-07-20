"""Tests for clause, subclause, proviso and explanation parsing."""

from __future__ import annotations

from constitution_memorizer.parsing.clause_parser import (
    classify_label,
    parse_clause_line,
    parse_special_provision,
)
from constitution_memorizer.parsing.constitution_parser import parse_markdown
from constitution_memorizer.schemas import LabelType


def test_numeric_clause() -> None:
    parsed = parse_clause_line("(1) All citizens shall have the right—")
    assert parsed is not None
    label, body, label_type = parsed
    assert label == "1"
    assert label_type == LabelType.NUMERIC
    assert body.startswith("All citizens")


def test_alphanumeric_clause() -> None:
    parsed = parse_clause_line("(1A) Notwithstanding anything in clause (1)—")
    assert parsed is not None
    label, _, label_type = parsed
    assert label == "1A"
    assert label_type == LabelType.ALPHANUMERIC


def test_alphabetic_subclause() -> None:
    parsed = parse_clause_line("(a) to freedom of speech and expression;")
    assert parsed is not None
    label, body, label_type = parsed
    assert label == "a"
    assert label_type == LabelType.ALPHABETIC
    assert "freedom of speech" in body


def test_roman_nested_provision() -> None:
    parsed = parse_clause_line("(i) including trade unions;")
    assert parsed is not None
    label, _, label_type = parsed
    assert label == "i"
    assert label_type == LabelType.ROMAN


def test_continued_text_across_lines() -> None:
    text = """PART III
RIGHTS

19. Protection of certain rights.—
(1) All citizens shall have the right
to freedom of speech and expression across lines.
"""
    doc, _ = parse_markdown(text)
    article = doc.parts[0].articles[0]
    assert article.clauses
    assert "across lines" in article.clauses[0].text


def test_proviso_association() -> None:
    text = """PART III
RIGHTS

19. Protection.—
(1) All citizens shall have the right.
Provided that the State may impose reasonable restrictions.
"""
    doc, _ = parse_markdown(text)
    article = doc.parts[0].articles[0]
    assert article.clauses
    assert any("Provided that" in p for p in article.clauses[0].provisos)


def test_explanation_association() -> None:
    text = """PART III
RIGHTS

19. Protection.—
(1) All citizens shall have the right.
Explanation.—For the purposes of this article, “law” includes ordinance.
"""
    doc, _ = parse_markdown(text)
    article = doc.parts[0].articles[0]
    assert article.clauses
    assert any("law" in e for e in article.clauses[0].explanations)


def test_nested_structure_in_article_19() -> None:
    text = """PART III
FUNDAMENTAL RIGHTS

19. Protection of certain rights regarding freedom of speech, etc.—
(1) All citizens shall have the right—
(a) to freedom of speech and expression;
(b) to assemble peaceably and without arms;
(i) including trade unions;
(2) Nothing in sub-clause (a) of clause (1) shall affect existing law.
"""
    doc, _ = parse_markdown(text)
    article = doc.parts[0].articles[0]
    assert len(article.clauses) >= 2
    first = article.clauses[0]
    assert any(c.label == "(a)" for c in first.children)
    assert any(c.label == "(b)" for c in first.children)


def test_special_provision_helpers() -> None:
    proviso = parse_special_provision("Provided further that nothing herein shall apply.")
    assert proviso is not None
    assert proviso.kind == "proviso"
    expl = parse_special_provision("Explanation I. The expression means X.")
    assert expl is not None
    assert expl.kind == "explanation"
    assert classify_label("A") == LabelType.UPPER_ALPHA
