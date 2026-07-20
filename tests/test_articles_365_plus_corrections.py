"""Restore Articles 365–395 via corrections (titles, bodies, missing creates)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from constitution_memorizer.corrections.apply_corrections import (
    apply_corrections,
    load_corrections,
)
from constitution_memorizer.learning.learning_unit_generator import generate_learning_units
from constitution_memorizer.schemas import ArticleStatus, ConstitutionDocument
from constitution_memorizer.utils.json_io import read_json

ROOT = Path(__file__).resolve().parents[1]
CORRECTIONS = ROOT / "data" / "corrections" / "corrections.json"
RAW = ROOT / "data" / "output" / "constitution.json"

needs_raw = pytest.mark.skipif(
    not RAW.exists(),
    reason="parsed corpus (data/output/constitution.json) not present",
)


def _article_map(doc: ConstitutionDocument) -> dict[str, object]:
    out: dict[str, object] = {}
    for part in doc.parts:
        for article in part.articles:
            out[str(article.article_number)] = article
        for chapter in part.chapters:
            for article in chapter.articles:
                out[str(article.article_number)] = article
    return out


def test_corrections_file_covers_365_plus_keys():
    data = json.loads(CORRECTIONS.read_text())
    arts = data["articles"]
    for key in (
        "article-366",
        "article-368",
        "article-370",
        "article-371a",
        "article-371e",
        "article-371f",
        "article-372a",
        "article-379",
        "article-393",
        "article-394",
        "article-394a",
    ):
        assert key in arts


@needs_raw
def test_apply_restores_366_368_371e_394_and_creates_missing():
    source = ConstitutionDocument.model_validate(read_json(RAW))
    doc, _changes = apply_corrections(source, load_corrections(CORRECTIONS))
    arts = _article_map(doc)

    art366 = arts["366"]
    assert art366.title == "Definitions"
    assert "(30)" in (art366.body_text or "")
    assert "goods and services tax" in (art366.body_text or "")

    assert arts["367"].title == "Interpretation"
    assert "Provided that, subject to the provisions" in (arts["367"].body_text or "")

    art368 = arts["368"]
    assert art368.title and "amend the Constitution" in art368.title
    body_368 = art368.body_text or ""
    assert body_368.startswith("(1)")
    assert "(2) An amendment" in body_368
    assert "(3) Nothing in article 13" in body_368
    assert art368.clauses == []

    assert arts["371E"].body_text == (
        "Parliament may by law provide for the establishment of a University "
        "in the State of Andhra Pradesh."
    )
    assert "371F" not in (arts["371E"].body_text or "")

    assert "370" in arts and (arts["370"].body_text or "").startswith("(1)")
    assert "371F" in arts
    assert "372A" in arts
    assert "393" in arts
    assert arts["393"].body_text == (
        "This Constitution may be called the Constitution of India."
    )
    assert "394A" in arts
    assert "394A" not in (arts["394"].body_text or "")
    assert (arts["394"].body_text or "").startswith("This article and articles")

    assert arts["379"].status == ArticleStatus.OMITTED
    assert arts["379"].body_text == "[Omitted.]"
    assert arts["383"].body_text == "[Omitted.]"


@needs_raw
def test_learning_units_for_368_and_371e_are_sensible():
    source = ConstitutionDocument.model_validate(read_json(RAW))
    doc, _ = apply_corrections(source, load_corrections(CORRECTIONS))
    result = generate_learning_units(doc)
    titles_368 = [u.display_title for u in result.units if u.article_number == "368"]
    assert "Article 368(1)" in titles_368
    assert "Article 368(2)" in titles_368
    assert not any(t == "Article 368(a)" for t in titles_368)

    units_371e = [u for u in result.units if u.article_number == "371E"]
    assert units_371e
    assert all("Sikkim" not in u.text for u in units_371e)
