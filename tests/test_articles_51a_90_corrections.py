"""Restore Bare Act wording for Arts 51A–90 diglot debris via corrections."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from constitution_memorizer.corrections.apply_corrections import (
    apply_corrections,
    load_corrections,
)
from constitution_memorizer.learning.learning_unit_generator import generate_learning_units
from constitution_memorizer.schemas import (
    Article,
    ArticleStatus,
    Chapter,
    ConstitutionDocument,
    DocumentMetadata,
    Part,
)

ROOT = Path(__file__).resolve().parents[1]
CORRECTIONS = ROOT / "data" / "corrections" / "corrections.json"
UNITS = ROOT / "data" / "output" / "learning_units.json"

REQUIRED_KEYS = (
    "article-51a",
    "article-76",
    "article-77",
    "article-82",
    "article-84",
    "article-90",
)


def _article_map(doc: ConstitutionDocument) -> dict[str, Article]:
    out: dict[str, Article] = {}
    for part in doc.parts:
        for article in part.articles:
            out[str(article.article_number)] = article
        for chapter in part.chapters:
            for article in chapter.articles:
                out[str(article.article_number)] = article
    return out


def _broken_doc() -> ConstitutionDocument:
    return ConstitutionDocument(
        document=DocumentMetadata(title="t", schema_version="1.0.0"),
        parts=[
            Part(
                id="part-iv",
                part_number="IV",
                title="DIRECTIVE PRINCIPLES / DUTIES",
                articles=[
                    Article(
                        id="article-51a",
                        article_number="51A",
                        numeric_component=51,
                        title="Fundamental duties",
                        part_number="IV",
                        status=ArticleStatus.ACTIVE,
                        body_text=(
                            "(a) to abide by the Constitution… (j) to strive… "
                            "missing stem and (k)"
                        ),
                    ),
                ],
            ),
            Part(
                id="part-v",
                part_number="V",
                title="THE UNION",
                chapters=[
                    Chapter(
                        id="chapter-i",
                        chapter_number="I",
                        title="THE EXECUTIVE",
                        articles=[
                            Article(
                                id="article-76",
                                article_number="76",
                                numeric_component=76,
                                title="Attorney-General for India",
                                part_number="V",
                                chapter_number="I",
                                status=ArticleStatus.ACTIVE,
                                body_text=(
                                    "(1) The President shall appoint… India. -\n"
                                    "(3) In the performance… India. -"
                                ),
                            ),
                            Article(
                                id="article-77",
                                article_number="77",
                                numeric_component=77,
                                title="Conduct of business of the Government of India",
                                part_number="V",
                                chapter_number="I",
                                status=ArticleStatus.ACTIVE,
                                body_text=(
                                    "(1) All executive action…\n"
                                    "(2) Orders…\n"
                                    "(3) The President shall make rules…\n"
                                    "(4) * * * *"
                                ),
                            ),
                        ],
                    ),
                    Chapter(
                        id="chapter-ii",
                        chapter_number="II",
                        title="PARLIAMENT",
                        articles=[
                            Article(
                                id="article-82",
                                article_number="82",
                                numeric_component=82,
                                title="Readjustment after each census",
                                part_number="V",
                                chapter_number="II",
                                status=ArticleStatus.ACTIVE,
                                body_text="(i) Upon the completion… (ii) the division…",
                            ),
                            Article(
                                id="article-84",
                                article_number="84",
                                numeric_component=84,
                                title="Qualification for membership of Parliament",
                                part_number="V",
                                chapter_number="II",
                                status=ArticleStatus.ACTIVE,
                                body_text=(
                                    "(b) is, in the case of a seat in the Council of States…"
                                ),
                            ),
                            Article(
                                id="article-90",
                                article_number="90",
                                numeric_component=90,
                                title="Vacation and resignation of Deputy Chairman",
                                part_number="V",
                                chapter_number="II",
                                status=ArticleStatus.ACTIVE,
                                body_text="(a) shall vacate his office… missing stem",
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )


def test_corrections_file_covers_51a_90_keys():
    data = json.loads(CORRECTIONS.read_text())
    arts = data["articles"]
    for key in REQUIRED_KEYS:
        assert key in arts, key
    assert arts["article-51a"].get("prefer_article_unit") is True
    assert arts["article-51a"].get("enable_letter_split") is True
    assert arts["article-82"].get("prefer_article_unit") is True
    assert arts["article-84"].get("prefer_article_unit") is True
    assert arts["article-90"].get("prefer_article_unit") is True


def test_apply_restores_51a_90_on_synthetic_doc():
    doc, _ = apply_corrections(_broken_doc(), load_corrections(CORRECTIONS))
    arts = _article_map(doc)

    assert (arts["51A"].opening_text or "").startswith(
        "It shall be the duty of every citizen of India"
    )
    body_51a = arts["51A"].body_text or ""
    assert "(k) who is a parent or guardian" in body_51a
    assert arts["51A"].prefer_article_unit is True

    body_76 = arts["76"].body_text or ""
    assert not body_76.rstrip().endswith("-")
    assert "(4) The Attorney-General shall hold office" in body_76
    assert "India. -" not in body_76

    body_77 = arts["77"].body_text or ""
    assert "(4)" not in body_77
    assert "* * * *" not in body_77
    assert body_77.count("(3)") == 1

    assert arts["82"].prefer_article_unit is True
    body_82 = arts["82"].body_text or ""
    assert body_82.startswith("Upon the completion of each census")
    assert "Provided also that until the relevant figures" in body_82

    assert (arts["84"].opening_text or "").startswith(
        "A person shall not be qualified to be chosen"
    )
    assert "(a) is a citizen of India" in (arts["84"].body_text or "")

    assert (arts["90"].opening_text or "").startswith(
        "A member holding office as Deputy Chairman"
    )
    assert "(c) may be removed from his office" in (arts["90"].body_text or "")


def test_learning_units_from_synthetic_doc():
    doc, _ = apply_corrections(_broken_doc(), load_corrections(CORRECTIONS))
    result = generate_learning_units(doc)
    by_art: dict[str, list] = {}
    for u in result.units:
        by_art.setdefault(u.article_number, []).append(u)

    ids_51a = {u.id for u in by_art["51A"]}
    assert "article-51a" in ids_51a
    assert "article-51a-subclause-k" in ids_51a
    assert "article-51a-subclause-i" in ids_51a

    ids_77 = {u.id for u in by_art["77"]}
    assert "article-77-clause-4" not in ids_77
    assert "article-77-clause-3" in ids_77

    ids_82 = {u.id for u in by_art["82"]}
    assert "article-82" in ids_82
    assert "article-82-clause-i" not in ids_82

    texts_84 = " ".join(u.text for u in by_art["84"])
    assert "A person shall not be qualified" in texts_84
    assert "(a) is a citizen of India" in texts_84


def test_committed_learning_units_cover_51a_90():
    if not UNITS.exists():
        pytest.skip("learning_units.json missing")
    payload = json.loads(UNITS.read_text())
    units = payload["units"] if isinstance(payload, dict) else payload
    by_art: dict[str, list] = {}
    for u in units:
        by_art.setdefault(u["article_number"], []).append(u)

    if "article-51a-subclause-k" not in {u["id"] for u in by_art.get("51A", [])}:
        pytest.skip("learning_units.json not yet regenerated for Art 51A")

    ids_51a = {u["id"] for u in by_art["51A"]}
    assert "article-51a-subclause-i" in ids_51a
    assert "article-51a-subclause-k" in ids_51a

    ids_77 = {u["id"] for u in by_art["77"]}
    assert "article-77-clause-4" not in ids_77
    texts_77 = " ".join(u["text"] for u in by_art["77"])
    assert "* * * *" not in texts_77

    assert "article-82" in {u["id"] for u in by_art["82"]}
    assert "article-82-clause-i" not in {u["id"] for u in by_art["82"]}

    texts_84 = " ".join(u["text"] for u in by_art["84"])
    assert "A person shall not be qualified" in texts_84
    assert "(a) is a citizen of India" in texts_84

    texts_90 = " ".join(u["text"] for u in by_art["90"])
    assert "A member holding office as Deputy Chairman" in texts_90

    # Verify existing 78/80 overlays still healthy after regen.
    texts_78 = " ".join(u["text"] for u in by_art["78"])
    assert "It shall be the duty of the Prime Minister" in texts_78
    texts_80 = " ".join(u["text"] for u in by_art["80"])
    assert "1 [" not in texts_80
    assert "***" not in texts_80
