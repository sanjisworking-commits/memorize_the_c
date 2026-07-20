"""Corrections for Art 201 duplication, Art 124 artefacts, and fake 20B–20C."""

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
from constitution_memorizer.web.browse import build_article_view, list_article_numbers
from constitution_memorizer.progress.scheduler import ReminderEngine


def _doc_with_bad_articles() -> ConstitutionDocument:
    return ConstitutionDocument(
        document=DocumentMetadata(title="test", schema_version="1.0.0"),
        parts=[
            Part(
                id="part-iii",
                part_number="III",
                title="FUNDAMENTAL RIGHTS",
                articles=[
                    Article(
                        id="article-20",
                        article_number="20",
                        numeric_component=20,
                        title="Protection in respect of conviction for offences",
                        status=ArticleStatus.ACTIVE,
                        body_text="(1) No person shall be convicted.",
                    ),
                    Article(
                        id="article-20b",
                        article_number="20B",
                        numeric_component=20,
                        title="Autonomous regions…",
                        status=ArticleStatus.ACTIVE,
                        body_text="(1) Notwithstanding anything in this Schedule,-",
                    ),
                    Article(
                        id="article-20ba",
                        article_number="20BA",
                        numeric_component=20,
                        title="Exercise of discretionary powers…",
                        status=ArticleStatus.ACTIVE,
                        body_text="The Governor in the discharge of his functions…",
                    ),
                    Article(
                        id="article-20bb",
                        article_number="20BB",
                        numeric_component=20,
                        title="Exercise of discretionary powers…",
                        status=ArticleStatus.ACTIVE,
                        body_text="The Governor, in the discharge of his functions…",
                    ),
                    Article(
                        id="article-20c",
                        article_number="20C",
                        numeric_component=20,
                        title="Interpretation",
                        status=ArticleStatus.ACTIVE,
                        body_text="Subject to any provision made in this behalf…",
                    ),
                    Article(
                        id="article-21",
                        article_number="21",
                        numeric_component=21,
                        title="Protection of life and personal liberty",
                        status=ArticleStatus.ACTIVE,
                        body_text=(
                            "No person shall be deprived of his life or personal "
                            "liberty except according to procedure established by law."
                        ),
                    ),
                ],
            ),
            Part(
                id="part-v",
                part_number="V",
                title="THE UNION",
                articles=[
                    Article(
                        id="article-124",
                        article_number="124",
                        numeric_component=124,
                        title="Establishment and constitution of the Supreme Court",
                        status=ArticleStatus.ACTIVE,
                        opening_text=(
                            "(1) There shall be a Supreme Court… "
                            "<!-- formula-not-decoded --> 4 [Provided that]- -"
                        ),
                        body_text=(
                            "(1) There shall be a Supreme Court… "
                            "<!-- formula-not-decoded --> 4 [Provided that]- -\n"
                            "(a) a Judge may resign;"
                        ),
                    ),
                ],
            ),
            Part(
                id="part-vi",
                part_number="VI",
                title="THE STATES",
                articles=[
                    Article(
                        id="article-201",
                        article_number="201",
                        numeric_component=201,
                        title="Bills reserved for consideration",
                        status=ArticleStatus.ACTIVE,
                        opening_text=(
                            "When a Bill is reserved by a Governor for the "
                            "consideration of the President, the President shall "
                            "declare either that he assents to the Bill or that "
                            "he withholds assent therefrom:"
                        ),
                        body_text=(
                            "When a Bill is reserved by a Governor for the "
                            "consideration of the President, the President shall "
                            "declare either that he assents to the Bill or that "
                            "he withholds assent therefrom:\n"
                            "Provided that, where the Bill is not a Money Bill, "
                            "the President may direct the Governor to return the Bill."
                        ),
                    ),
                ],
            ),
        ],
        extraction_summary=ExtractionSummary(),
    )


def test_exclude_schedule_paragraphs_and_fix_201_124(tmp_path):
    doc = _doc_with_bad_articles()
    corrections = CorrectionsFile(
        articles={
            "article-20b": ArticleCorrection(exclude=True),
            "article-20ba": ArticleCorrection(exclude=True),
            "article-20bb": ArticleCorrection(exclude=True),
            "article-20c": ArticleCorrection(exclude=True),
            "article-201": ArticleCorrection(
                opening_text="",
                body_text=(
                    "When a Bill is reserved by a Governor for the consideration "
                    "of the President, the President shall declare either that he "
                    "assents to the Bill or that he withholds assent therefrom:\n"
                    "Provided that, where the Bill is not a Money Bill, the "
                    "President may direct the Governor to return the Bill."
                ),
            ),
            "article-124": ArticleCorrection(
                opening_text="",
                body_text=(
                    "(1) There shall be a Supreme Court of India consisting of a "
                    "Chief Justice of India and, until Parliament by law "
                    "prescribes a larger number, of not more than seven other Judges.\n"
                    "(2) Every Judge of the Supreme Court shall be appointed by the "
                    "President by warrant under his hand and seal and shall hold "
                    "office until he attains the age of sixty-five years:\n"
                    "Provided that—\n"
                    "(a) a Judge may, by writing under his hand addressed to the "
                    "President, resign his office;\n"
                    "(b) a Judge may be removed from his office in the manner "
                    "provided in clause (4)."
                ),
            ),
        }
    )
    reviewed, changes = apply_corrections(doc, corrections)
    assert any("excluded" in c for c in changes)

    numbers = {a.article_number for p in reviewed.parts for a in p.articles}
    assert "20B" not in numbers
    assert "20BA" not in numbers
    assert "20BB" not in numbers
    assert "20C" not in numbers
    assert "20" in numbers
    assert "21" in numbers

    units_doc = generate_learning_units(reviewed)
    unit_ids = {u.id for u in units_doc.units}
    assert not any("20b" in uid.lower() for uid in unit_ids)
    assert "article-201" in unit_ids

    art201 = next(u for u in units_doc.units if u.id == "article-201")
    assert art201.text.count("When a Bill is reserved") == 1
    assert "formula-not-decoded" not in art201.text

    clause1 = next(u for u in units_doc.units if u.id == "article-124-clause-1")
    assert "formula-not-decoded" not in clause1.text
    assert "\uf02a" not in clause1.text
    assert "Provided that]-" not in clause1.text

    engine = ReminderEngine.from_units(
        tmp_path / "p.db",
        units_doc.units,
    )
    browse_nums = list_article_numbers(engine, reviewed)
    assert "20B" not in browse_nums
    assert "20C" not in browse_nums
    assert "20" in browse_nums

    view = build_article_view(engine, reviewed, "201")
    assert view is not None
    assert view.full_text.count("When a Bill is reserved") == 1
