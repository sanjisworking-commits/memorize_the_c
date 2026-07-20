"""Tests for footnote detection and structured amendment metadata."""

from __future__ import annotations

from pathlib import Path

from constitution_memorizer.parsing.article_parser import parse_article_heading_line
from constitution_memorizer.parsing.constitution_parser import parse_markdown
from constitution_memorizer.parsing.footnote_parser import (
    build_footnote,
    detect_footnote_start,
    detect_operation,
)
from constitution_memorizer.schemas import FootnoteOperation

FIXTURES = Path(__file__).parent / "fixtures"


def test_amendment_insertion_note() -> None:
    start = detect_footnote_start(
        "2. Ins. by the Constitution (Eighty-sixth Amendment) Act, 2002, s. 2."
    )
    assert start is not None
    footnote = build_footnote(start.marker, start.text)
    assert footnote.operation == FootnoteOperation.INSERTED
    assert footnote.year == 2002
    assert footnote.amendment_number == 86
    assert footnote.amendment_name is not None
    assert "Eighty-sixth" in footnote.amendment_name


def test_substitution_note() -> None:
    start = detect_footnote_start(
        "1. Subs. by the Constitution (Forty-fourth Amendment) Act, 1978, s. 2."
    )
    assert start is not None
    assert detect_operation(start.text) == FootnoteOperation.SUBSTITUTED


def test_omission_note() -> None:
    start = detect_footnote_start(
        "3. Omitted by the Constitution (Forty-fourth Amendment) Act, 1978, s. 5."
    )
    assert start is not None
    assert detect_operation(start.text) == FootnoteOperation.OMITTED


def test_footnote_not_mistaken_for_article() -> None:
    line = "1. Subs. by the Constitution (Forty-fourth Amendment) Act, 1978."
    assert detect_footnote_start(line) is not None
    assert parse_article_heading_line(line) is None


def test_multiple_footnotes_and_article() -> None:
    text = (FIXTURES / "sample_footnotes.md").read_text(encoding="utf-8")
    doc, _ = parse_markdown(text)
    markers = {f.marker for f in doc.footnotes}
    assert {"1", "2", "3", "4", "5", "6"} <= markers
    # Article 14 should still be detected.
    numbers = []
    for part in doc.parts:
        numbers.extend(a.article_number for a in part.articles)
    assert "14" in numbers


def test_footnote_continued_across_lines() -> None:
    text = """PART III
RIGHTS

14. Equality before law.

6. Ins. by the Constitution (Forty-second Amendment) Act, 1976, s. 2.
This footnote continues on a second line with more detail about Article 14.
"""
    doc, _ = parse_markdown(text)
    footnote_6 = next(f for f in doc.footnotes if f.marker == "6")
    assert "continues on a second line" in footnote_6.text
    assert footnote_6.affected_article == "14"


def test_exact_text_preserved() -> None:
    original = "Ins. by the Constitution (Eighty-sixth Amendment) Act, 2002, s. 2 (w.e.f. 1-4-2010)."
    footnote = build_footnote("2", original)
    assert footnote.text == original
