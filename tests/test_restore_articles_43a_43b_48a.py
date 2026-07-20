"""Insert missing DPSP Articles 43A, 43B, 48A via corrections.create."""

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
from constitution_memorizer.utils.identifiers import article_sort_key
from constitution_memorizer.web.browse import _article_full_text, iter_articles


def test_create_missing_43a_43b_48a_and_relocate_45():
    doc = ConstitutionDocument(
        document=DocumentMetadata(title="t", schema_version="1.0.0"),
        parts=[
            Part(
                id="part-iv",
                part_number="IV",
                title="DIRECTIVE PRINCIPLES OF STATE POLICY",
                articles=[
                    Article(
                        id="article-43",
                        article_number="43",
                        numeric_component=43,
                        title="Living wage, etc., for workers",
                        part_number="IV",
                        status=ArticleStatus.ACTIVE,
                        body_text="The State shall endeavour to secure a living wage.",
                    ),
                    Article(
                        id="article-44",
                        article_number="44",
                        numeric_component=44,
                        title="Uniform civil code for the citizens",
                        part_number="IV",
                        status=ArticleStatus.ACTIVE,
                        body_text="The State shall endeavour to secure a uniform civil code.",
                    ),
                    Article(
                        id="article-48",
                        article_number="48",
                        numeric_component=48,
                        title="Organisation of agriculture and animal husbandry",
                        part_number="IV",
                        status=ArticleStatus.ACTIVE,
                        body_text="The State shall endeavour to organise agriculture.",
                    ),
                ],
            ),
            Part(
                id="part-xxii",
                part_number="XXII",
                title="SHORT TITLE…",
                articles=[
                    Article(
                        id="article-45",
                        article_number="45",
                        numeric_component=45,
                        title=None,
                        part_number="XXII",
                        status=ArticleStatus.ACTIVE,
                        body_text="Land revenue junk",
                    )
                ],
            ),
        ],
        extraction_summary=ExtractionSummary(),
    )
    corrections = CorrectionsFile(
        articles={
            "article-43a": ArticleCorrection(
                create=True,
                title="Participation of workers in management of industries",
                part_number="IV",
                opening_text="",
                body_text=(
                    "The State shall take steps, by suitable legislation or in any "
                    "other way, to secure the participation of workers in the "
                    "management of undertakings, establishments or other organisations "
                    "engaged in any industry."
                ),
            ),
            "article-43b": ArticleCorrection(
                create=True,
                title="Promotion of co-operative societies",
                part_number="IV",
                opening_text="",
                body_text=(
                    "The State shall endeavour to promote voluntary formation, "
                    "autonomous functioning, democratic control and professional "
                    "management of co-operative societies."
                ),
            ),
            "article-48a": ArticleCorrection(
                create=True,
                title=(
                    "Protection and improvement of environment and safeguarding of "
                    "forests and wild life"
                ),
                part_number="IV",
                opening_text="",
                body_text=(
                    "The State shall endeavour to protect and improve the environment "
                    "and to safeguard the forests and wild life of the country."
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
    reviewed, changes = apply_corrections(doc, corrections)
    part_iv = next(p for p in reviewed.parts if p.part_number == "IV")
    part_xxii = next(p for p in reviewed.parts if p.part_number == "XXII")
    nums = [a.article_number for a in part_iv.articles]
    assert nums == sorted(nums, key=article_sort_key)
    assert "43A" in nums
    assert "43B" in nums
    assert "48A" in nums
    assert "45" in nums
    assert nums.index("43") < nums.index("43A") < nums.index("43B") < nums.index("44")
    assert nums.index("48") < nums.index("48A")
    assert all(a.article_number != "45" for a in part_xxii.articles)
    assert any("created in Part IV" in c for c in changes)
    assert any("moved to Part IV" in c for c in changes)

    by_num = {a.article_number: a for a in iter_articles(reviewed)}
    assert "participation of workers" in _article_full_text(by_num["43A"]).lower()
    assert "co-operative societies" in _article_full_text(by_num["43B"])
    assert "wild life" in _article_full_text(by_num["48A"])

    units = {u.id: u for u in generate_learning_units(reviewed).units}
    assert "article-43a" in units
    assert "article-43b" in units
    assert "article-48a" in units
    assert "Part IV" in units["article-43a"].tags
