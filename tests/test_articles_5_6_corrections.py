"""Art 5 / 6 — restore missing Bare Act opening stems."""

from __future__ import annotations

from constitution_memorizer.corrections.apply_corrections import (
    ArticleCorrection,
    CorrectionsFile,
    apply_corrections,
    load_corrections,
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
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORRECTIONS = ROOT / "data" / "corrections" / "corrections.json"
UNITS = ROOT / "data" / "output" / "learning_units.json"

STEM_5 = "At the commencement of this Constitution, every person who has his domicile in the territory of India and—"
STEM_6 = (
    "Notwithstanding anything in article 5, a person who has migrated to the "
    "territory of India from the territory now included in Pakistan shall be "
    "deemed to be a citizen of India at the commencement of this Constitution if—"
)


def _broken_citizenship_doc() -> ConstitutionDocument:
    return ConstitutionDocument(
        document=DocumentMetadata(title="t", schema_version="1.0.0"),
        parts=[
            Part(
                id="part-ii",
                part_number="II",
                title="CITIZENSHIP",
                articles=[
                    Article(
                        id="article-5",
                        article_number="5",
                        numeric_component=5,
                        title="Citizenship at the commencement of the Constitution",
                        part_number="II",
                        status=ArticleStatus.ACTIVE,
                        body_text=(
                            "(a) who was born in the territory of India; or\n"
                            "(b) either of whose parents was born in the territory of India; or\n"
                            "(c) who has been ordinarily resident in the territory of India "
                            "for not less than five years immediately preceding such "
                            "commencement, shall be a citizen of India."
                        ),
                    ),
                    Article(
                        id="article-6",
                        article_number="6",
                        numeric_component=6,
                        title=(
                            "Rights of citizenship of certain persons who have "
                            "migrated to India from Pakistan"
                        ),
                        part_number="II",
                        status=ArticleStatus.ACTIVE,
                        body_text=(
                            "(a) he or either of his parents or any of his grand-parents "
                            "was born in India as defined in the Government of India Act, "
                            "1935 (as originally enacted); and ( b )( i ) in the case where "
                            "such person has so migrated before the nineteenth day of "
                            "July, 1948, he has been ordinarily resident in the territory "
                            "of India since the date of his migration, or ( ii ) mangled"
                        ),
                    ),
                ],
            )
        ],
        extraction_summary=ExtractionSummary(),
    )


def test_articles_5_and_6_stems_restored_from_corrections_file():
    corr = load_corrections(CORRECTIONS)
    reviewed, _ = apply_corrections(_broken_citizenship_doc(), corr)
    arts = {a.id: a for p in reviewed.parts for a in p.articles}

    assert arts["article-5"].body_text.startswith(STEM_5)
    assert "(a) who was born in the territory of India; or" in arts["article-5"].body_text
    assert arts["article-5"].body_text.rstrip().endswith("shall be a citizen of India.")
    assert arts["article-5"].prefer_article_unit is True
    assert arts["article-5"].enable_letter_split is True

    assert arts["article-6"].body_text.startswith(STEM_6)
    assert "Government of India Act, 1935" in arts["article-6"].body_text
    assert "(b) (i)" in arts["article-6"].body_text
    assert "Provided that no person shall be so registered" in arts["article-6"].body_text
    assert arts["article-6"].prefer_article_unit is True
    assert arts["article-6"].enable_letter_split is True


def test_articles_5_and_6_units_keep_stem_and_letter_siblings():
    corr = CorrectionsFile(
        articles={
            "article-5": ArticleCorrection(
                title="Citizenship at the commencement of the Constitution",
                part_number="II",
                opening_text="",
                body_text=(
                    f"{STEM_5}\n"
                    "(a) who was born in the territory of India; or\n"
                    "(b) either of whose parents was born in the territory of India; or\n"
                    "(c) who has been ordinarily resident in the territory of India for "
                    "not less than five years immediately preceding such commencement,\n"
                    "shall be a citizen of India."
                ),
                prefer_article_unit=True,
                enable_letter_split=True,
                manual_review_status="approved",
            ),
            "article-6": ArticleCorrection(
                title=(
                    "Rights of citizenship of certain persons who have "
                    "migrated to India from Pakistan"
                ),
                part_number="II",
                opening_text="",
                body_text=(
                    f"{STEM_6}\n"
                    "(a) he or either of his parents or any of his grand-parents was born "
                    "in India as defined in the Government of India Act, 1935 "
                    "(as originally enacted); and\n"
                    "(b) (i) in the case where such person has so migrated before the "
                    "nineteenth day of July, 1948, he has been ordinarily resident in the "
                    "territory of India since the date of his migration, or\n"
                    "(ii) in the case where such person has so migrated on or after the "
                    "nineteenth day of July, 1948, he has been registered as a citizen of "
                    "India by an officer appointed in that behalf by the Government of the "
                    "Dominion of India on an application made by him therefor to such "
                    "officer before the commencement of this Constitution in the form and "
                    "manner prescribed by that Government:\n"
                    "Provided that no person shall be so registered unless he has been "
                    "resident in the territory of India for at least six months "
                    "immediately preceding the date of his application."
                ),
                prefer_article_unit=True,
                enable_letter_split=True,
                manual_review_status="approved",
            ),
        }
    )
    reviewed, _ = apply_corrections(_broken_citizenship_doc(), corr)
    by_id = {u.id: u for u in generate_learning_units(reviewed).units}

    assert STEM_5 in by_id["article-5"].text
    assert "article-5-subclause-a" in by_id
    assert "article-5-subclause-b" in by_id
    assert "article-5-subclause-c" in by_id
    assert "article-5-clause-a" not in by_id

    assert STEM_6 in by_id["article-6"].text
    assert "article-6-subclause-a" in by_id
    assert "article-6-subclause-b" in by_id
    assert "article-6-clause-a" not in by_id
    assert "( b )" not in by_id["article-6"].text
    # Nested roman under (b) must stay on the (b) letter card.
    assert "(ii)" in by_id["article-6-subclause-b"].text
    assert "Provided that no person shall be so registered" in by_id[
        "article-6-subclause-b"
    ].text


def test_committed_learning_units_include_art_5_and_6_stems():
    if not UNITS.exists():
        return
    payload = __import__("json").loads(UNITS.read_text(encoding="utf-8"))
    units = payload["units"] if isinstance(payload, dict) else payload
    by_art: dict[str, list] = {}
    for u in units:
        by_art.setdefault(u["article_number"], []).append(u)

    texts_5 = "\n".join(u["text"] for u in by_art["5"])
    assert STEM_5 in texts_5
    assert any(u["id"] == "article-5" for u in by_art["5"])

    texts_6 = "\n".join(u["text"] for u in by_art["6"])
    assert STEM_6 in texts_6
    assert any(u["id"] == "article-6" for u in by_art["6"])
    assert "( b )" not in texts_6
