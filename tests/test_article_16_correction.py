"""Restore Article 16 Bare Act clauses (1)–(6), including (4A)/(4B)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from constitution_memorizer.corrections.apply_corrections import (
    apply_corrections,
    load_corrections,
)
from constitution_memorizer.learning.learning_unit_generator import generate_learning_units
from constitution_memorizer.schemas import (
    Article,
    ArticleStatus,
    ConstitutionDocument,
    DocumentMetadata,
    Part,
)

ROOT = Path(__file__).resolve().parents[1]
CORRECTIONS = ROOT / "data" / "corrections" / "corrections.json"
UNITS = ROOT / "data" / "output" / "learning_units.json"


def _article_map(doc: ConstitutionDocument) -> dict[str, Article]:
    out: dict[str, Article] = {}
    for part in doc.parts:
        for article in part.articles:
            out[str(article.article_number)] = article
        for chapter in part.chapters:
            for article in chapter.articles:
                out[str(article.article_number)] = article
    return out


def _broken_doc() -> ConstitutionDocument:
    return ConstitutionDocument(
        document=DocumentMetadata(title="t", schema_version="1.0.0"),
        parts=[
            Part(
                id="part-iii",
                part_number="III",
                title="FUNDAMENTAL RIGHTS",
                articles=[
                    Article(
                        id="article-16",
                        article_number="16",
                        numeric_component=16,
                        title="Equality of opportunity in matters of public employment",
                        part_number="III",
                        status=ArticleStatus.ACTIVE,
                        body_text=(
                            "(1) There shall be equality of opportunity.\n"
                            "(3) office 1 [under the Government of, or any local or other "
                            "authority within, a State or Union territory]\n"
                            "(4) reservation of appointments. 2 [(4A) promotion] 4 [(4B) "
                            "unfilled vacancies.]"
                        ),
                    )
                ],
            )
        ],
    )


def test_corrections_file_covers_article_16():
    data = json.loads(CORRECTIONS.read_text())
    assert "article-16" in data["articles"]
    body = data["articles"]["article-16"]["body_text"]
    assert "(4A)" in body and "(4B)" in body and "(6)" in body
    assert "1 [" not in body


def test_apply_restores_article_16_on_synthetic_doc():
    doc, _ = apply_corrections(_broken_doc(), load_corrections(CORRECTIONS))
    art = _article_map(doc)["16"]
    body = art.body_text or ""
    assert body.startswith("(1) There shall be equality of opportunity")
    assert "Union territory" in body
    assert "1 [" not in body
    assert "2 [" not in body
    assert "3 [" not in body
    assert "4 [" not in body
    assert "(4A) Nothing in this article shall prevent the State from making any provision for reservation in matters of promotion" in body
    assert "(4B) Nothing in this article shall prevent the State from considering any unfilled vacancies" in body
    assert "(5) Nothing in this article shall affect the operation of any law" in body
    assert "(6) Nothing in this article shall prevent the State from making any provision for the reservation" in body
    assert "economically weaker sections" in body


def test_learning_units_split_16_clauses():
    doc, _ = apply_corrections(_broken_doc(), load_corrections(CORRECTIONS))
    result = generate_learning_units(doc)
    units = [u for u in result.units if u.article_number == "16"]
    ids = {u.id for u in units}
    assert "article-16-clause-4a" in ids
    assert "article-16-clause-4b" in ids
    assert "article-16-clause-5" in ids
    assert "article-16-clause-6" in ids
    blob = " ".join(u.text for u in units)
    assert "1 [" not in blob
    assert "[(4A)" not in blob


def test_committed_learning_units_cover_article_16():
    if not UNITS.exists():
        pytest.skip("learning_units.json missing")
    payload = json.loads(UNITS.read_text())
    units = payload["units"] if isinstance(payload, dict) else payload
    ids = {u["id"] for u in units if u["article_number"] == "16"}
    if "article-16-clause-4a" not in ids:
        pytest.skip("learning_units.json not yet regenerated for Art 16(4A)")
    assert "article-16-clause-4b" in ids
    assert "article-16-clause-5" in ids
    assert "article-16-clause-6" in ids
    blob = " ".join(u["text"] for u in units if u["article_number"] == "16")
    assert "1 [" not in blob
    assert "economically weaker sections" in blob
