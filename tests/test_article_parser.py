"""Tests for Article heading detection and status assignment."""

from __future__ import annotations

from pathlib import Path

from constitution_memorizer.parsing.article_parser import parse_article_heading_line
from constitution_memorizer.parsing.constitution_parser import parse_markdown
from constitution_memorizer.schemas import ArticleStatus
from constitution_memorizer.utils.identifiers import article_sort_key

FIXTURES = Path(__file__).parent / "fixtures"


def _articles_by_number(text: str) -> dict[str, object]:
    doc, _ = parse_markdown(text)
    result = {}
    for part in doc.parts:
        for article in part.articles:
            result[article.article_number] = article
        for chapter in part.chapters:
            for article in chapter.articles:
                result[article.article_number] = article
    return result


def test_numeric_article() -> None:
    heading = parse_article_heading_line("14. Equality before law.")
    assert heading is not None
    assert heading.number_parts.article_number == "14"
    assert heading.title == "Equality before law"


def test_article_with_alphabetic_suffix() -> None:
    heading = parse_article_heading_line("21A. Right to education.—The State shall provide.")
    assert heading is not None
    assert heading.number_parts.article_number == "21A"
    assert heading.number_parts.numeric_component == 21
    assert heading.number_parts.suffix == "A"
    assert heading.title == "Right to education"
    assert "State shall provide" in heading.opening_text


def test_article_with_two_letter_suffix() -> None:
    heading = parse_article_heading_line(
        "243ZG. Bar to interference by courts in electoral matters."
    )
    assert heading is not None
    assert heading.number_parts.article_number == "243ZG"


def test_article_heading_and_body_same_line() -> None:
    heading = parse_article_heading_line(
        "14. Equality before law.—The State shall not deny to any person equality."
    )
    assert heading is not None
    assert heading.title == "Equality before law"
    assert heading.opening_text.startswith("The State shall not deny")


def test_article_heading_split_across_lines() -> None:
    text = "PART III\nFUNDAMENTAL RIGHTS\n15\nProhibition of discrimination on grounds of religion, race, caste, sex or place of birth.—\n(1) The State shall not discriminate against any citizen.\n"
    articles = _articles_by_number(text)
    assert "15" in articles
    assert articles["15"].title is not None
    assert "Prohibition of discrimination" in articles["15"].title


def test_leading_footnote_marker_not_in_article_number() -> None:
    heading = parse_article_heading_line(
        "1[21A. Right to education.—The State shall provide free education."
    )
    assert heading is not None
    assert heading.number_parts.article_number == "21A"
    assert heading.footnote_marker == "1"


def test_omitted_article() -> None:
    heading = parse_article_heading_line("31. [Omitted.]")
    assert heading is not None
    assert heading.status == ArticleStatus.OMITTED


def test_repealed_article() -> None:
    heading = parse_article_heading_line("238. Repealed.")
    assert heading is not None
    assert heading.status == ArticleStatus.REPEALED


def test_sample_fixture_articles() -> None:
    text = (FIXTURES / "sample_articles.md").read_text(encoding="utf-8")
    articles = _articles_by_number(text)
    assert "14" in articles
    assert "21A" in articles
    assert "239AA" in articles
    assert "243ZG" in articles
    assert articles["31"].status == ArticleStatus.OMITTED
    assert articles["238"].status == ArticleStatus.REPEALED
    assert articles["2A"].status == ArticleStatus.OMITTED


def test_natural_article_sort_order() -> None:
    numbers = ["239B", "21A", "20", "239AA", "22", "21", "239A", "239", "239AB"]
    ordered = sorted(numbers, key=article_sort_key)
    assert ordered == ["20", "21", "21A", "22", "239", "239A", "239AA", "239AB", "239B"]
