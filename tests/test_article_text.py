"""Tests for article text assembly (no duplicated opening/body/provisos)."""

from __future__ import annotations

from constitution_memorizer.article_text import article_full_text, collapse_duplicate_paragraphs
from constitution_memorizer.schemas import Article, ArticleStatus


def _article(**kwargs) -> Article:
    defaults = dict(
        id="article-21",
        article_number="21",
        numeric_component=21,
        title="Protection of life and personal liberty",
        part_number="III",
        status=ArticleStatus.ACTIVE,
        opening_text="",
        body_text="",
        clauses=[],
        provisos=[],
        explanations=[],
    )
    defaults.update(kwargs)
    return Article(**defaults)


def test_identical_opening_and_body_not_repeated():
    text = (
        "No person shall be deprived of his life or personal liberty "
        "except according to procedure established by law."
    )
    result = article_full_text(
        _article(opening_text=text, body_text=text)
    )
    assert result == text
    assert result.count("No person shall be deprived") == 1


def test_proviso_already_in_body_not_appended_again():
    proviso = (
        "Provided that during any period when the Vice-President acts as President "
        "he shall not perform the duties of the office of Chairman."
    )
    opening = (
        "The Vice-President shall be ex officio Chairman of the Council of the States "
        "and shall not hold any other office of profit:"
    )
    body = f"{opening}\n{proviso}"
    result = article_full_text(
        _article(
            id="article-64",
            article_number="64",
            numeric_component=64,
            title="The Vice-President to be ex officio Chairman of the Council of States",
            part_number="V",
            opening_text=opening,
            body_text=body,
            provisos=[proviso],
        )
    )
    assert result.count("Provided that during any period") == 1
    assert opening.split(":")[0] in result


def test_collapse_duplicate_paragraphs():
    line = "Same line twice."
    assert collapse_duplicate_paragraphs(f"{line}\n\n{line}") == line
