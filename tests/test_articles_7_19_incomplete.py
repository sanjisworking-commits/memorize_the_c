"""Art 7 repetition, Art 19 incompleteness, and related corpus fixes."""

from __future__ import annotations

from constitution_memorizer.corrections.apply_corrections import (
    ArticleCorrection,
    CorrectionsFile,
    apply_corrections,
)
from constitution_memorizer.corrections.artefact_scrub import (
    fragment_already_present,
    strip_part_running_headers,
)
from constitution_memorizer.learning.learning_unit_generator import generate_learning_units
from constitution_memorizer.schemas import (
    Article,
    ArticleStatus,
    ConstitutionDocument,
    DocumentMetadata,
    ExtractionSummary,
    Part,
    ProvisionNode,
)
from constitution_memorizer.web.browse import _article_full_text


def test_strip_part_running_header():
    raw = (
        "shall not be deemed to be a citizen of India: (Part II.-Citizenship)\n"
        "Provided that nothing in this article shall apply."
    )
    cleaned = strip_part_running_headers(raw)
    assert "Part II" not in cleaned
    assert "Provided that" in cleaned
    assert "citizen of India:" in cleaned


def test_fragment_already_present_helper():
    body = "Main text.\nProvided that the proviso applies here."
    assert fragment_already_present(body, "Provided that the proviso applies here.")
    assert not fragment_already_present(body, "Provided that something else entirely.")


def test_article_7_proviso_not_repeated_and_part_header_gone():
    proviso = (
        "Provided that nothing in this article shall apply to a person who, after "
        "having so migrated to the territory now included in Pakistan, has returned "
        "to the territory of India under a permit for resettlement or permanent return."
    )
    doc = ConstitutionDocument(
        document=DocumentMetadata(title="t", schema_version="1.0.0"),
        parts=[
            Part(
                id="part-ii",
                part_number="II",
                title="CITIZENSHIP",
                articles=[
                    Article(
                        id="article-7",
                        article_number="7",
                        numeric_component=7,
                        title="Rights of citizenship of certain migrants to Pakistan",
                        part_number="II",
                        status=ArticleStatus.ACTIVE,
                        body_text=(
                            "Notwithstanding anything in articles 5 and 6, a person who "
                            "has after the first day of March, 1947, migrated from the "
                            "territory of India to the territory now included in Pakistan "
                            "shall not be deemed to be a citizen of India: "
                            f"(Part II.-Citizenship)\n{proviso}"
                        ),
                        provisos=[proviso],
                    )
                ],
            )
        ],
        extraction_summary=ExtractionSummary(),
    )
    reviewed, changes = apply_corrections(doc, CorrectionsFile())
    art7 = next(a for p in reviewed.parts for a in p.articles if a.id == "article-7")
    assert "Part II" not in art7.body_text
    assert art7.provisos == []
    assert any("duplicate" in c and "provisos" in c for c in changes)

    full = _article_full_text(art7)
    assert full.count("Provided that nothing in this article") == 1

    units = {u.id: u for u in generate_learning_units(reviewed).units}
    assert units["article-7"].text.count("Provided that nothing in this article") == 1


def test_article_19_restored_from_truncated_stem():
    doc = ConstitutionDocument(
        document=DocumentMetadata(title="t", schema_version="1.0.0"),
        parts=[
            Part(
                id="part-iii",
                part_number="III",
                title="FUNDAMENTAL RIGHTS",
                articles=[
                    Article(
                        id="article-19",
                        article_number="19",
                        numeric_component=19,
                        title="Protection of certain rights regarding freedom of speech, etc",
                        part_number="III",
                        status=ArticleStatus.ACTIVE,
                        body_text="(1) All citizens shall have the right-",
                    ),
                    Article(
                        id="article-15",
                        article_number="15",
                        numeric_component=15,
                        title=(
                            "Prohibition of discrimination on grounds of religion, "
                            "race, caste, sex or place of birth"
                        ),
                        part_number="III",
                        status=ArticleStatus.ACTIVE,
                        body_text=(
                            "(1) The State shall not discriminate against any citizen "
                            "on grounds only of religion, race, caste, sex, place of "
                            "birth or any of them.\n(2) No citizen shall, on grounds "
                            "only of religion, race, caste, sex, place of birth or any "
                            "of them, be subject to any disability, liability, "
                            "restriction or condition with regard to-"
                        ),
                        clauses=[
                            ProvisionNode(
                                id="article-15-clause-2",
                                label="(2)",
                                label_type="numeric",
                                text=(
                                    "No citizen shall, on grounds only of religion, "
                                    "race, caste, sex, place of birth or any of them, "
                                    "be subject to any disability, liability, "
                                    "restriction or condition with regard to-"
                                ),
                            )
                        ],
                    ),
                    Article(
                        id="article-51",
                        article_number="51",
                        numeric_component=51,
                        title="Promotion of international peace and security",
                        part_number="IV",
                        status=ArticleStatus.ACTIVE,
                        body_text="The State shall endeavour to-",
                    ),
                ],
            )
        ],
        extraction_summary=ExtractionSummary(),
    )
    corrections = CorrectionsFile(
        articles={
            "article-19": ArticleCorrection(
                opening_text="",
                body_text=(
                    "(1) All citizens shall have the right—\n"
                    "(a) to freedom of speech and expression;\n"
                    "(b) to assemble peaceably and without arms;\n"
                    "(c) to form associations or unions or co-operative societies;\n"
                    "(d) to move freely throughout the territory of India;\n"
                    "(e) to reside and settle in any part of the territory of India; and\n"
                    "(g) to practise any profession, or to carry on any occupation, "
                    "trade or business.\n"
                    "(2) Nothing in sub-clause (a) of clause (1) shall affect the "
                    "operation of any existing law.\n"
                    "(6) Nothing in sub-clause (g) of the said clause shall affect "
                    "the operation of any existing law."
                ),
            ),
            "article-15": ArticleCorrection(
                opening_text="",
                body_text=(
                    "(1) The State shall not discriminate against any citizen on "
                    "grounds only of religion, race, caste, sex, place of birth or "
                    "any of them.\n"
                    "(2) No citizen shall, on grounds only of religion, race, caste, "
                    "sex, place of birth or any of them, be subject to any disability, "
                    "liability, restriction or condition with regard to—\n"
                    "(a) access to shops, public restaurants, hotels and places of "
                    "public entertainment; or\n"
                    "(b) the use of wells, tanks, bathing ghats, roads and places of "
                    "public resort maintained wholly or partly out of State funds or "
                    "dedicated to the use of the general public.\n"
                    "(3) Nothing in this article shall prevent the State from making "
                    "any special provision for women and children."
                ),
            ),
            "article-51": ArticleCorrection(
                opening_text="",
                body_text=(
                    "The State shall endeavour to—\n"
                    "(a) promote international peace and security;\n"
                    "(b) maintain just and honourable relations between nations;\n"
                    "(c) foster respect for international law and treaty obligations "
                    "in the dealings of organised peoples with one another; and\n"
                    "(d) encourage settlement of international disputes by arbitration."
                ),
            ),
        }
    )
    reviewed, changes = apply_corrections(doc, corrections)
    by_id = {a.id: a for p in reviewed.parts for a in p.articles}

    assert "freedom of speech and expression" in by_id["article-19"].body_text
    assert "(g) to practise any profession" in by_id["article-19"].body_text
    assert "(1)(f)" not in by_id["article-19"].body_text
    assert "(f) " not in by_id["article-19"].body_text
    assert by_id["article-19"].clauses == []

    assert "access to shops" in by_id["article-15"].body_text
    assert by_id["article-15"].clauses == []
    assert any("clauses cleared" in c for c in changes)

    assert "(d) encourage settlement" in by_id["article-51"].body_text

    units = {u.id: u for u in generate_learning_units(reviewed).units}
    # Flat corrected bodies are split into clause/letter units for Learn.
    assert "article-19-clause-1-subclause-a" in units
    assert "freedom of speech and expression" in units["article-19-clause-1"].text
    assert "(f)" not in units["article-19-clause-1"].text
    assert "access to shops" in units["article-15-clause-2"].text
    assert "arbitration" in units["article-51-clause-d"].text
