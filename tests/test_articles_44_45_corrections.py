"""Corrections for Article 44 glue and Article 45 schedule mis-parse."""

from __future__ import annotations

from constitution_memorizer.corrections.apply_corrections import (
    ArticleCorrection,
    CorrectionsFile,
    apply_corrections,
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


def test_articles_44_and_45_restored_from_glued_schedule_debris():
    doc = ConstitutionDocument(
        document=DocumentMetadata(title="test", schema_version="1.0.0"),
        parts=[
            Part(
                id="part-iv",
                part_number="IV",
                title="DIRECTIVE PRINCIPLES OF STATE POLICY",
                articles=[
                    Article(
                        id="article-44",
                        article_number="44",
                        numeric_component=44,
                        title="Uniform civil code for the citizens",
                        part_number="IV",
                        status=ArticleStatus.ACTIVE,
                        opening_text=(
                            "The State shall endeavour to secure for the citizens a "
                            "uniform civil code throughout the territory of India. - "
                            "2 [ 45. Provision for early childhood care…"
                        ),
                        body_text=(
                            "The State shall endeavour to secure for the citizens a "
                            "uniform civil code throughout the territory of India. - "
                            "2 [ 45. Provision for early childhood care and education "
                            "to children below the age of six years. -The State shall "
                            "endeavour to provide early childhood care and education "
                            "for all children until they complete the age of six years.]"
                        ),
                    ),
                ],
            ),
            Part(
                id="part-xxii",
                part_number="XXII",
                title="SHORT TITLE, COMMENCEMENT, AUTHORITATIVE TEXT…",
                articles=[
                    Article(
                        id="article-45",
                        article_number="45",
                        numeric_component=45,
                        title=None,
                        part_number="XXII",
                        status=ArticleStatus.ACTIVE,
                        opening_text=(
                            "Land revenue, including the assessment and collection "
                            "of revenue…"
                        ),
                        body_text=(
                            "Land revenue, including the assessment and collection of "
                            "revenue, the maintenance of land records… "
                            "<!-- formula-not-decoded --> 53. Taxes on the consumption "
                            "or sale of electricity. <!-- formula-not-decoded -->"
                        ),
                    ),
                ],
            ),
        ],
        extraction_summary=ExtractionSummary(),
    )
    corrections = CorrectionsFile(
        articles={
            "article-44": ArticleCorrection(
                opening_text="",
                body_text=(
                    "The State shall endeavour to secure for the citizens a uniform "
                    "civil code throughout the territory of India."
                ),
            ),
            "article-45": ArticleCorrection(
                title=(
                    "Provision for early childhood care and education to children "
                    "below the age of six years"
                ),
                part_number="IV",
                opening_text="",
                body_text=(
                    "The State shall endeavour to provide early childhood care and "
                    "education for all children until they complete the age of six years."
                ),
            ),
        }
    )
    reviewed, _ = apply_corrections(doc, corrections)
    by_id = {
        a.id: a
        for p in reviewed.parts
        for a in list(p.articles) + [x for ch in p.chapters for x in ch.articles]
    }
    assert by_id["article-44"].body_text.startswith("The State shall endeavour to secure")
    assert "45." not in by_id["article-44"].body_text
    assert by_id["article-44"].opening_text == ""
    assert by_id["article-45"].part_number == "IV"
    assert "Land revenue" not in by_id["article-45"].body_text
    assert "formula-not-decoded" not in by_id["article-45"].body_text
    assert "early childhood care" in by_id["article-45"].body_text

    units = {u.id: u for u in generate_learning_units(reviewed).units}
    assert units["article-44"].text.count("uniform civil code") == 1
    assert "45." not in units["article-44"].text
    assert "early childhood care" in units["article-45"].text
    assert "formula-not-decoded" not in units["article-45"].text
    assert "Part IV" in units["article-45"].tags
