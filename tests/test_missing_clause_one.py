"""Missing leading clause (1) when structured clauses start at (2)."""

from __future__ import annotations

from constitution_memorizer.corrections.apply_corrections import (
    ArticleCorrection,
    CorrectionsFile,
    apply_corrections,
)
from constitution_memorizer.corrections.artefact_scrub import (
    clauses_skip_leading_clause_one,
    strip_trailing_section_headers,
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


def test_strip_trailing_section_header():
    raw = (
        "(4) No person holding any office of profit or trust under the State shall, "
        "without the consent of the President, accept any present, emolument, or "
        "office of any kind from or under any foreign State. Right to Freedom"
    )
    cleaned = strip_trailing_section_headers(raw)
    assert cleaned.endswith("foreign State.")
    assert "Right to Freedom" not in cleaned


def test_article_18_clause_one_restored_and_section_glue_removed():
    doc = ConstitutionDocument(
        document=DocumentMetadata(title="t", schema_version="1.0.0"),
        parts=[
            Part(
                id="part-iii",
                part_number="III",
                title="FUNDAMENTAL RIGHTS",
                articles=[
                    Article(
                        id="article-18",
                        article_number="18",
                        numeric_component=18,
                        title="Abolition of titles",
                        part_number="III",
                        status=ArticleStatus.ACTIVE,
                        body_text=(
                            "(1) No title, not being a military or academic distinction, "
                            "shall be conferred by the State.\n"
                            "(2) No citizen of India shall accept any title from any "
                            "foreign State.\n"
                            "(3) No person who is not a citizen of India shall, while he "
                            "holds any office of profit or trust under the State, accept "
                            "without the consent of the President any title from any "
                            "foreign State.\n"
                            "(4) No person holding any office of profit or trust under "
                            "the State shall, without the consent of the President, "
                            "accept any present, emolument, or office of any kind from "
                            "or under any foreign State. Right to Freedom"
                        ),
                        clauses=[
                            ProvisionNode(
                                id="article-18-clause-2",
                                label="(2)",
                                label_type="numeric",
                                text=(
                                    "No citizen of India shall accept any title from any "
                                    "foreign State."
                                ),
                            ),
                            ProvisionNode(
                                id="article-18-clause-3",
                                label="(3)",
                                label_type="numeric",
                                text=(
                                    "No person who is not a citizen of India shall, while "
                                    "he holds any office of profit or trust under the "
                                    "State, accept without the consent of the President "
                                    "any title from any foreign State."
                                ),
                            ),
                            ProvisionNode(
                                id="article-18-clause-4",
                                label="(4)",
                                label_type="numeric",
                                text=(
                                    "No person holding any office of profit or trust "
                                    "under the State shall, without the consent of the "
                                    "President, accept any present, emolument, or office "
                                    "of any kind from or under any foreign State. "
                                    "Right to Freedom"
                                ),
                            ),
                        ],
                    ),
                    Article(
                        id="article-20",
                        article_number="20",
                        numeric_component=20,
                        title="Protection in respect of conviction for offences",
                        part_number="III",
                        status=ArticleStatus.ACTIVE,
                        body_text=(
                            "(1) No person shall be convicted of any offence except for "
                            "violation of a law in force at the time of the commission "
                            "of the act charged as an offence, nor be subjected to a "
                            "penalty greater than that which might have been inflicted "
                            "under the law in force at the time of the commission of "
                            "the offence.\n"
                            "(2) No person shall be prosecuted and punished for the same "
                            "offence more than once.\n"
                            "(3) No person accused of any offence shall be compelled to "
                            "be a witness against himself."
                        ),
                        clauses=[
                            ProvisionNode(
                                id="article-20-clause-2",
                                label="(2)",
                                label_type="numeric",
                                text=(
                                    "No person shall be prosecuted and punished for the "
                                    "same offence more than once."
                                ),
                            ),
                            ProvisionNode(
                                id="article-20-clause-3",
                                label="(3)",
                                label_type="numeric",
                                text=(
                                    "No person accused of any offence shall be compelled "
                                    "to be a witness against himself."
                                ),
                            ),
                        ],
                    ),
                ],
            )
        ],
        extraction_summary=ExtractionSummary(),
    )
    assert clauses_skip_leading_clause_one(doc.parts[0].articles[0]) is True

    reviewed, changes = apply_corrections(
        doc,
        CorrectionsFile(
            articles={
                "article-18": ArticleCorrection(
                    opening_text="",
                    body_text=(
                        "(1) No title, not being a military or academic distinction, "
                        "shall be conferred by the State.\n"
                        "(2) No citizen of India shall accept any title from any "
                        "foreign State.\n"
                        "(3) No person who is not a citizen of India shall, while he "
                        "holds any office of profit or trust under the State, accept "
                        "without the consent of the President any title from any "
                        "foreign State.\n"
                        "(4) No person holding any office of profit or trust under "
                        "the State shall, without the consent of the President, "
                        "accept any present, emolument, or office of any kind from "
                        "or under any foreign State."
                    ),
                )
            }
        ),
    )
    by_id = {a.id: a for p in reviewed.parts for a in p.articles}

    art18 = by_id["article-18"]
    assert art18.clauses == []
    assert "Right to Freedom" not in art18.body_text
    full18 = _article_full_text(art18)
    assert full18.startswith("(1) No title")
    assert "(2) No citizen of India" in full18
    assert "Right to Freedom" not in full18

    art20 = by_id["article-20"]
    assert art20.clauses == []
    full20 = _article_full_text(art20)
    assert full20.startswith("(1) No person shall be convicted")
    assert "(3) No person accused" in full20
    assert any("missing leading (1)" in c for c in changes)

    units = {u.id: u for u in generate_learning_units(reviewed).units}
    assert "article-18-clause-1" in units
    assert "military or academic distinction" in units["article-18-clause-1"].text
    assert "article-20-clause-1" in units
    assert "convicted of any offence" in units["article-20-clause-1"].text


def test_partial_body_prepends_clause_one_onto_richer_tree():
    """When body is thinner than clauses, keep clauses but prepend (1)."""
    short_one = (
        "There shall be constituted in every Metropolitan area a Metropolitan "
        "Planning Committee to prepare a draft development plan for the "
        "Metropolitan area as a whole."
    )
    long_two = (
        "The Legislature of a State may, by law, make provision with respect to-"
        + (" more detail about composition and representation." * 20)
    )
    doc = ConstitutionDocument(
        document=DocumentMetadata(title="t", schema_version="1.0.0"),
        parts=[
            Part(
                id="part-ix",
                part_number="IXA",
                title="MUNICIPALITIES",
                articles=[
                    Article(
                        id="article-243ze",
                        article_number="243ZE",
                        numeric_component=243,
                        suffix="ZE",
                        title="Committee for Metropolitan planning",
                        status=ArticleStatus.ACTIVE,
                        body_text=f"(1) {short_one}\n(2) truncated stem-",
                        clauses=[
                            ProvisionNode(
                                id="article-243ze-clause-2",
                                label="(2)",
                                label_type="numeric",
                                text=long_two,
                                children=[
                                    ProvisionNode(
                                        id="article-243ze-clause-2-a",
                                        label="(a)",
                                        label_type="alphabetic",
                                        text="the composition of the Committees;",
                                    )
                                ],
                            )
                        ],
                    )
                ],
            )
        ],
        extraction_summary=ExtractionSummary(),
    )
    reviewed, changes = apply_corrections(doc, CorrectionsFile())
    art = next(a for p in reviewed.parts for a in p.articles)
    assert art.clauses[0].label == "(1)"
    assert short_one in art.clauses[0].text
    assert art.clauses[1].label == "(2)"
    assert any("prepended clause (1)" in c for c in changes)
    full = _article_full_text(art)
    assert full.lstrip().startswith("(1)")
    assert "composition of the Committees" in full
