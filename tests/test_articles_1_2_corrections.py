"""Article 1 / 2 correction overlay restores Bare Act text."""

from __future__ import annotations

from constitution_memorizer.corrections.apply_corrections import (
    ArticleCorrection,
    CorrectionsFile,
    apply_corrections,
)
from constitution_memorizer.learning.learning_unit_generator import generate_learning_units
from constitution_memorizer.learning.text_fallback_splitter import split_flat_article_body
from constitution_memorizer.schemas import (
    Article,
    ArticleStatus,
    ConstitutionDocument,
    DocumentMetadata,
    ExtractionSummary,
    Part,
)


def test_letter_c_is_alphabetic_in_text_fallback():
    body = (
        "(3) The territory of India shall comprise—\n"
        "(a) the territories of the States;\n"
        "(b) the Union territories specified in the First Schedule; and\n"
        "(c) such other territories as may be acquired."
    )
    roots = split_flat_article_body("1", body)
    assert len(roots) == 1
    assert [c.label for c in roots[0].children] == ["(a)", "(b)", "(c)"]


def test_article_1_and_2_corrections_produce_clean_units():
    doc = ConstitutionDocument(
        document=DocumentMetadata(title="test", schema_version="1.0.0"),
        parts=[
            Part(
                id="part-i",
                part_number="UNKNOWN",
                title="THE UNION AND ITS TERRITORY",
                articles=[
                    Article(
                        id="article-1",
                        article_number="1",
                        numeric_component=1,
                        title='DEMOCRATIC REPUBLIC" (w.e.f. 3',
                        status=ArticleStatus.ACTIVE,
                        opening_text="1-1977).",
                        body_text="1-1977).",
                    ),
                    Article(
                        id="article-2",
                        article_number="2",
                        numeric_component=2,
                        title="Admission or establishment of new States",
                        part_number="I",
                        status=ArticleStatus.ACTIVE,
                        opening_text=(
                            "Parliament may by law admit into the Union, or establish, "
                            "new States on such terms and conditions as it thinks fit. "
                            "3 [ 2A. omitted w.e.f. ]"
                        ),
                        body_text=(
                            "Parliament may by law admit into the Union, or establish, "
                            "new States on such terms and conditions as it thinks fit. "
                            "3 [ 2A. omitted w.e.f. ]"
                        ),
                    ),
                ],
            )
        ],
        extraction_summary=ExtractionSummary(),
    )
    corrections = CorrectionsFile(
        articles={
            "article-1": ArticleCorrection(
                title="Name and territory of the Union",
                part_number="I",
                opening_text="",
                body_text=(
                    "(1) India, that is Bharat, shall be a Union of States.\n"
                    "(2) The States and the territories thereof shall be as specified "
                    "in the First Schedule.\n"
                    "(3) The territory of India shall comprise—\n"
                    "(a) the territories of the States;\n"
                    "(b) the Union territories specified in the First Schedule; and\n"
                    "(c) such other territories as may be acquired."
                ),
            ),
            "article-2": ArticleCorrection(
                opening_text="",
                body_text=(
                    "Parliament may by law admit into the Union, or establish, "
                    "new States on such terms and conditions as it thinks fit."
                ),
            ),
        }
    )
    reviewed, _ = apply_corrections(doc, corrections)
    units = {u.id: u for u in generate_learning_units(reviewed).units}

    assert "article-1-clause-1" in units
    assert "India, that is Bharat" in units["article-1-clause-1"].text
    assert "DEMOCRATIC" not in (units["article-1-clause-1"].title or "")
    assert "Part I" in units["article-1-clause-1"].tags
    assert "article-1-clause-3-subclause-c" in units
    assert "acquired" in units["article-1-clause-3-subclause-c"].text

    art2 = units["article-2"]
    assert art2.text.startswith("Parliament may by law")
    assert "2A" not in art2.text
    assert "w.e.f" not in art2.text
