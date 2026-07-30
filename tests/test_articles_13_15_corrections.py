"""Art 13 missing clause (1); Art 15 Learn body without Explanation."""

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
    ProvisionNode,
)

_TITLE_13 = "Laws inconsistent with or in derogation of the fundamental rights"
_BODY_13 = (
    "(1) All laws in force in the territory of India immediately before the "
    "commencement of this Constitution, in so far as they are inconsistent with "
    "the provisions of this Part, shall, to the extent of such inconsistency, be "
    "void.\n"
    "(2) The State shall not make any law which takes away or abridges the rights "
    "conferred by this Part and any law made in contravention of this clause shall, "
    "to the extent of the contravention, be void.\n"
    "(3) In this article, unless the context otherwise requires,—\n"
    '(a) "law" includes any Ordinance, order, bye-law, rule, regulation, '
    "notification, custom or usage having in the territory of India the force of "
    "law;\n"
    '(b) "laws in force" includes laws passed or made by a Legislature or other '
    "competent authority in the territory of India before the commencement of this "
    "Constitution and not previously repealed, notwithstanding that any such law or "
    "any part thereof may not be then in operation either at all or in particular "
    "areas.\n"
    "(4) Nothing in this article shall apply to any amendment of this Constitution "
    "made under article 368."
)

_TITLE_15 = (
    "Prohibition of discrimination on grounds of religion, race, caste, sex or "
    "place of birth"
)


def test_article_13_restores_clause_one_and_four():
    doc = ConstitutionDocument(
        document=DocumentMetadata(title="t", schema_version="1.0.0"),
        parts=[
            Part(
                id="part-iii",
                part_number="III",
                title="FUNDAMENTAL RIGHTS",
                articles=[
                    Article(
                        id="article-13",
                        article_number="13",
                        numeric_component=13,
                        title=None,
                        part_number="III",
                        status=ArticleStatus.ACTIVE,
                        opening_text="",
                        body_text=(
                            "(2) The State shall not make any law…\n"
                            "(3) In this article… areas. 1 [(4) Nothing in this "
                            "article shall apply to any amendment of this "
                            "Constitution made under article 368.] Right to Equality"
                        ),
                        clauses=[
                            ProvisionNode(
                                id="article-13-clause-2",
                                label="(2)",
                                label_type="numeric",
                                text="The State shall not make any law…",
                            ),
                            ProvisionNode(
                                id="article-13-clause-3",
                                label="(3)",
                                label_type="numeric",
                                text=(
                                    "In this article… areas. 1 [(4) Nothing… "
                                    "Right to Equality"
                                ),
                            ),
                        ],
                    )
                ],
            )
        ],
        extraction_summary=ExtractionSummary(),
    )
    reviewed, _ = apply_corrections(
        doc,
        CorrectionsFile(
            articles={
                "article-13": ArticleCorrection(
                    title=_TITLE_13,
                    part_number="III",
                    opening_text="",
                    body_text=_BODY_13,
                )
            }
        ),
    )
    art = next(a for p in reviewed.parts for a in p.articles if a.id == "article-13")
    assert art.title == _TITLE_13
    assert art.clauses == []
    assert art.body_text.startswith("(1) All laws in force")
    assert "Right to Equality" not in art.body_text
    assert "1 [" not in art.body_text

    units = {u.id: u for u in generate_learning_units(reviewed).units}
    assert "article-13-clause-1" in units
    assert "article-13-clause-4" in units
    assert units["article-13-clause-1"].text.startswith("(1) All laws in force")
    assert "article 368" in units["article-13-clause-4"].text
    assert "Right to Equality" not in units["article-13-clause-3"].text
    assert "Right to Equality" not in units["article-13-clause-3-subclause-b"].text
    assert units["article-13-clause-1"].title == _TITLE_13


def test_article_15_omits_explanation():
    body_with_expl = (
        "(1) The State shall not discriminate against any citizen on grounds only "
        "of religion, race, caste, sex, place of birth or any of them.\n"
        "(6) Nothing in this article or sub-clause (g) of clause (1) of article 19 "
        "or clause (2) of article 29 shall prevent the State from making—\n"
        "(a) any special provision for the advancement of any economically weaker "
        "sections of citizens other than the classes mentioned in clauses (4) and "
        "(5); and\n"
        "(b) any special provision for the advancement of any economically weaker "
        "sections of citizens other than the classes mentioned in clauses (4) and "
        "(5) in so far as such special provisions relate to their admission to "
        "educational institutions including private educational institutions, "
        "whether aided or unaided by the State, other than the minority educational "
        "institutions referred to in clause (1) of article 30, which in the case of "
        "reservation would be in addition to the existing reservations and subject "
        "to a maximum of ten per cent. of the total seats in each category.\n"
        "Explanation.—For the purposes of this article and article 16, "
        '"economically weaker sections" shall be such as may be notified by the '
        "State from time to time on the basis of family income and other indicators "
        "of economic disadvantage."
    )
    body_without = body_with_expl.split("\nExplanation.—")[0]
    doc = ConstitutionDocument(
        document=DocumentMetadata(title="t", schema_version="1.0.0"),
        parts=[
            Part(
                id="part-iii",
                part_number="III",
                title="FUNDAMENTAL RIGHTS",
                articles=[
                    Article(
                        id="article-15",
                        article_number="15",
                        numeric_component=15,
                        title=_TITLE_15,
                        part_number="III",
                        status=ArticleStatus.ACTIVE,
                        opening_text="",
                        body_text=body_with_expl,
                    )
                ],
            )
        ],
        extraction_summary=ExtractionSummary(),
    )
    reviewed, _ = apply_corrections(
        doc,
        CorrectionsFile(
            articles={
                "article-15": ArticleCorrection(
                    title=_TITLE_15,
                    opening_text="",
                    body_text=body_without,
                )
            }
        ),
    )
    art = next(a for p in reviewed.parts for a in p.articles if a.id == "article-15")
    assert "Explanation" not in art.body_text
    assert "ten per cent" in art.body_text

    units = {u.id: u for u in generate_learning_units(reviewed).units}
    assert "article-15-clause-6" in units
    assert "Explanation" not in units["article-15-clause-6"].text
    assert "Explanation" not in units["article-15-clause-6-subclause-b"].text
    assert "ten per cent" in units["article-15-clause-6-subclause-b"].text
