"""Insert missing Article 81 via corrections.create into Part V Chapter II."""

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
    Chapter,
    ConstitutionDocument,
    DocumentMetadata,
    ExtractionSummary,
    Part,
)
from constitution_memorizer.web.browse import _article_full_text, iter_articles


def test_create_missing_article_81_in_part_v_chapter_ii():
    doc = ConstitutionDocument(
        document=DocumentMetadata(title="t", schema_version="1.0.0"),
        parts=[
            Part(
                id="part-v",
                part_number="V",
                title="THE UNION",
                chapters=[
                    Chapter(
                        id="part-v-chapter-ii",
                        chapter_number="II",
                        title="PARLIAMENT",
                        articles=[
                            Article(
                                id="article-80",
                                article_number="80",
                                numeric_component=80,
                                title="Composition of the Council of States",
                                part_number="V",
                                chapter_number="II",
                                status=ArticleStatus.ACTIVE,
                                body_text="(1) The Council of States shall consist of—",
                            ),
                            Article(
                                id="article-82",
                                article_number="82",
                                numeric_component=82,
                                title="Readjustment after each census",
                                part_number="V",
                                chapter_number="II",
                                status=ArticleStatus.ACTIVE,
                                body_text="Upon the completion of each census…",
                            ),
                        ],
                    )
                ],
            )
        ],
        extraction_summary=ExtractionSummary(),
    )
    body = (
        "(1) Subject to the provisions of article 331, the House of the People "
        "shall consist of—\n"
        "(a) not more than five hundred and thirty members chosen by direct "
        "election from territorial constituencies in the States; and\n"
        "(b) not more than twenty members to represent the Union territories, "
        "chosen in such manner as Parliament may by law provide.\n\n"
        "(2) For the purposes of sub-clause (a) of clause (1),—\n"
        "(a) there shall be allotted to each State a number of seats in the "
        "House of the People in such manner that the ratio between that number "
        "and the population of the State is, so far as practicable, the same "
        "for all States; and\n"
        "(b) each State shall be divided into territorial constituencies in "
        "such manner that the ratio between the population of each constituency "
        "and the number of seats allotted to it is, so far as practicable, the "
        "same throughout the State:\n"
        "Provided that the provisions of sub-clause (a) of this clause shall "
        "not be applicable for the purpose of allotment of seats in the House "
        "of the People to any State so long as the population of that State "
        "does not exceed six millions.\n\n"
        "(3) In this article, the expression \"population\" means the population "
        "as ascertained at the last preceding census of which the relevant "
        "figures have been published:\n"
        "Provided that the reference in this clause to the last preceding "
        "census of which the relevant figures have been published shall, until "
        "the relevant figures for the first census taken after the year 2026 "
        "have been published, be construed,—\n"
        "(i) for the purposes of sub-clause (a) of clause (2) and the proviso "
        "to that clause, as a reference to the 1971 census; and\n"
        "(ii) for the purposes of sub-clause (b) of clause (2) as a reference "
        "to the 2001 census."
    )
    corrections = CorrectionsFile(
        articles={
            "article-81": ArticleCorrection(
                create=True,
                title="Composition of the House of the People",
                part_number="V",
                chapter_number="II",
                opening_text="",
                body_text=body,
            ),
        }
    )
    reviewed, changes = apply_corrections(doc, corrections)
    chapter = reviewed.parts[0].chapters[0]
    nums = [a.article_number for a in chapter.articles]
    assert nums == ["80", "81", "82"]
    art81 = chapter.articles[1]
    assert art81.title == "Composition of the House of the People"
    assert art81.chapter_number == "II"
    assert "five hundred and thirty" in art81.body_text
    assert "1971 census" in art81.body_text
    assert "2001 census" in art81.body_text
    assert any("created in Part V Chapter II" in c for c in changes)

    by_num = {a.article_number: a for a in iter_articles(reviewed)}
    assert "81" in by_num
    assert "house of the people shall consist" in _article_full_text(by_num["81"]).lower()

    units = {u.id: u for u in generate_learning_units(reviewed).units}
    assert any(uid.startswith("article-81") for uid in units)
    assert "Part V" in next(u.tags for uid, u in units.items() if uid.startswith("article-81"))
