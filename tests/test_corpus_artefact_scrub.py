"""Corpus artefact scrub + stolen-article restorations."""

from __future__ import annotations

from constitution_memorizer.corrections.apply_corrections import (
    ArticleCorrection,
    CorrectionsFile,
    apply_corrections,
)
from constitution_memorizer.corrections.artefact_scrub import (
    scrub_display_text,
    should_include_opening,
)
from constitution_memorizer.learning.learning_unit_generator import generate_learning_units
from constitution_memorizer.schemas import (
    Article,
    ArticleStatus,
    ConstitutionDocument,
    DocumentMetadata,
    ExtractionSummary,
    Part,
)
from constitution_memorizer.web.browse import _article_full_text


def test_scrub_removes_formula_and_pua():
    raw = "Hello <!-- formula-not-decoded --> world \uf02a [seven]"
    assert scrub_display_text(raw) == "Hello world [seven]"


def test_opening_body_dedupe_and_display(tmp_path=None):
    doc = ConstitutionDocument(
        document=DocumentMetadata(title="t", schema_version="1.0.0"),
        parts=[
            Part(
                id="part-iii",
                part_number="III",
                title="FUNDAMENTAL RIGHTS",
                articles=[
                    Article(
                        id="article-14",
                        article_number="14",
                        numeric_component=14,
                        title="Equality before law",
                        status=ArticleStatus.ACTIVE,
                        opening_text=(
                            "The State shall not deny to any person equality before "
                            "the law or the equal protection of the laws within the "
                            "territory of India."
                        ),
                        body_text=(
                            "The State shall not deny to any person equality before "
                            "the law or the equal protection of the laws within the "
                            "territory of India."
                        ),
                    ),
                    Article(
                        id="article-3",
                        article_number="3",
                        numeric_component=3,
                        title="Formation of new States",
                        status=ArticleStatus.ACTIVE,
                        opening_text="Parliament may by law-",
                        body_text=(
                            "Parliament may by law-\n"
                            "(a) form a new State by separation of territory;"
                        ),
                    ),
                    Article(
                        id="article-92b",
                        article_number="92B",
                        numeric_component=92,
                        title="Taxes on consignments",
                        status=ArticleStatus.ACTIVE,
                        body_text="State trade or commerce.] <!-- formula-not-decoded -->",
                    ),
                ],
            )
        ],
        extraction_summary=ExtractionSummary(),
    )
    corrections = CorrectionsFile(
        articles={"article-92b": ArticleCorrection(exclude=True)}
    )
    reviewed, changes = apply_corrections(doc, corrections)
    assert any("cleared opening" in c for c in changes)
    assert any("excluded" in c for c in changes)

    art14 = next(a for p in reviewed.parts for a in p.articles if a.id == "article-14")
    assert art14.opening_text == ""
    full = _article_full_text(art14)
    assert full.count("The State shall not deny") == 1
    assert "formula-not-decoded" not in full

    art3 = next(a for p in reviewed.parts for a in p.articles if a.id == "article-3")
    assert art3.opening_text == ""
    assert art3.body_text.startswith("Parliament may by law-")

    nums = {a.article_number for p in reviewed.parts for a in p.articles}
    assert "92B" not in nums

    units = {u.id: u for u in generate_learning_units(reviewed).units}
    assert units["article-14"].text.count("The State shall not deny") == 1
    assert "article-92b" not in units


def test_should_include_opening_helper():
    assert should_include_opening("", "body") is False
    assert should_include_opening("same", "same") is False
    assert should_include_opening("stem", "stem\n(a) more") is False
    assert should_include_opening("extra note", "body text") is True
