"""Tests for the constitution state-machine parser and schedules."""

from __future__ import annotations

from pathlib import Path

from constitution_memorizer.parsing.constitution_parser import parse_markdown
from constitution_memorizer.parsing.schedule_parser import parse_schedule_heading
from constitution_memorizer.schemas import ArticleStatus

FIXTURES = Path(__file__).parent / "fixtures"


def test_preamble_extraction() -> None:
    text = """PREAMBLE

WE, THE PEOPLE OF INDIA, having solemnly resolved to constitute India into a
SOVEREIGN SOCIALIST SECULAR DEMOCRATIC REPUBLIC

and to secure to all its citizens:

JUSTICE, social, economic and political;

26th day of November, 1949.

PART I
THE UNION AND ITS TERRITORY

1. Name and territory of the Union.—India, that is Bharat, shall be a Union of States.
"""
    doc, _ = parse_markdown(text)
    assert doc.preamble is not None
    assert "WE, THE PEOPLE OF INDIA" in doc.preamble.text
    assert doc.preamble.enactment_date_line is not None
    assert len(doc.parts) >= 1
    assert doc.parts[0].part_number == "I"
    assert doc.parts[0].articles[0].article_number == "1"


def test_part_and_chapter_detection() -> None:
    text = """PART V
THE UNION

CHAPTER I
THE EXECUTIVE

52. The President of India.—There shall be a President of India.
"""
    doc, _ = parse_markdown(text)
    assert doc.parts[0].part_number == "V"
    assert doc.parts[0].title == "THE UNION"
    assert doc.parts[0].chapters
    assert doc.parts[0].chapters[0].chapter_number == "I"
    assert doc.parts[0].chapters[0].articles[0].article_number == "52"


def test_part_title_on_same_line() -> None:
    text = """PART I—THE UNION AND ITS TERRITORY

1. Name and territory of the Union.—India shall be a Union of States.
"""
    doc, _ = parse_markdown(text)
    assert doc.parts[0].title == "THE UNION AND ITS TERRITORY"


def test_unclassified_content_retained() -> None:
    text = """PART I
UNION

1. Name.—India shall be a Union of States.

SOME WEIRD UNPARSED BLOCK THAT IS NOT A HEADING
"""
    doc, events = parse_markdown(text)
    # After article text, stray lines may be appended to article OR unclassified.
    # Either way nothing should be silently dropped from events/document.
    combined = "\n".join(u.text for u in doc.unclassified_content)
    article_text = doc.parts[0].articles[0].opening_text + doc.parts[0].articles[0].body_text
    assert (
        "SOME WEIRD UNPARSED BLOCK" in combined
        or "SOME WEIRD UNPARSED BLOCK" in article_text
    )


def test_sample_articles_fixture_omitted_and_repealed() -> None:
    text = (FIXTURES / "sample_articles.md").read_text(encoding="utf-8")
    doc, _ = parse_markdown(text)
    articles = {
        a.article_number: a
        for part in doc.parts
        for a in [*part.articles, *[x for ch in part.chapters for x in ch.articles]]
    }
    assert articles["31"].status == ArticleStatus.OMITTED
    assert articles["238"].status == ArticleStatus.REPEALED


def test_schedule_heading_and_lists() -> None:
    heading = parse_schedule_heading("SEVENTH SCHEDULE")
    assert heading is not None
    assert heading.schedule_number == "SEVENTH"

    text = (FIXTURES / "sample_schedules.md").read_text(encoding="utf-8")
    doc, _ = parse_markdown(text)
    assert len(doc.schedules) >= 2
    seventh = next(s for s in doc.schedules if s.schedule_number == "SEVENTH")
    assert seventh.body_text
    assert len(seventh.lists) >= 1
    assert any("Union List" in (lst.name or "") for lst in seventh.lists)


def test_never_silently_drops_unclassified() -> None:
    text = "COMPLETELY UNSTRUCTURED CONTENT WITHOUT MARKERS\n"
    doc, _ = parse_markdown(text)
    assert doc.unclassified_content or doc.preamble or doc.parts
    # Front matter / unknown lines should be retained.
    assert doc.unclassified_content
