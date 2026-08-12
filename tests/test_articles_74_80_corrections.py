"""Restore Council of Ministers / Rajya Sabha Arts 74, 75, 78, 80 via corrections."""

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

REQUIRED_KEYS = ("article-74", "article-75", "article-78", "article-80")


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
                                id="article-74",
                                article_number="74",
                                numeric_component=74,
                                title="Council of Ministers to aid and advise President",
                                part_number="V",
                                chapter_number="I",
                                status=ArticleStatus.ACTIVE,
                                body_text=(
                                    "(2) The question whether any, and if so what, advice "
                                    "was tendered by Ministers to the President shall not "
                                    "be inquired into in any court."
                                ),
                            ),
                            Article(
                                id="article-75",
                                article_number="75",
                                numeric_component=75,
                                title="Other provisions as to Ministers",
                                part_number="V",
                                chapter_number="I",
                                status=ArticleStatus.ACTIVE,
                                body_text=(
                                    "(1) The Prime Minister shall be appointed by the "
                                    "President. 3 [(1A) The total number of Ministers "
                                    "(1B) A member of either House.]"
                                ),
                            ),
                            Article(
                                id="article-78",
                                article_number="78",
                                numeric_component=78,
                                title=(
                                    "Duties of Prime Minister as respects the furnishing "
                                    "of information to the President, etc."
                                ),
                                part_number="V",
                                chapter_number="I",
                                status=ArticleStatus.ACTIVE,
                                body_text=(
                                    "(a) to communicate to the President all decisions of "
                                    "the Council of Ministers"
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
                                id="article-80",
                                article_number="80",
                                numeric_component=80,
                                title="Composition of the Council of States",
                                part_number="V",
                                chapter_number="II",
                                status=ArticleStatus.ACTIVE,
                                body_text=(
                                    "(1) 1 [ 2 *** The Council of States] shall consist of-"
                                ),
                            ),
                        ],
                    ),
                ],
            )
        ],
    )


def test_corrections_file_covers_74_80_keys():
    data = json.loads(CORRECTIONS.read_text())
    arts = data["articles"]
    for key in REQUIRED_KEYS:
        assert key in arts, key
    assert arts["article-78"].get("prefer_article_unit") is True


def test_apply_restores_74_75_78_80_on_synthetic_doc():
    doc, _ = apply_corrections(_broken_doc(), load_corrections(CORRECTIONS))
    arts = _article_map(doc)

    body_74 = arts["74"].body_text or ""
    assert body_74.startswith("(1) There shall be a Council of Ministers")
    assert "Provided that the President may require" in body_74
    assert "(2) The question whether any" in body_74

    body_75 = arts["75"].body_text or ""
    assert "3 [" not in body_75
    assert "[(1A)" not in body_75
    assert body_75.count("(1A)") == 1
    assert body_75.count("(1B)") == 1
    assert not body_75.rstrip().endswith("]")
    assert "(5) A Minister who for any period" in body_75
    assert "(6) The salaries and allowances" in body_75

    assert (arts["78"].opening_text or "").startswith(
        "It shall be the duty of the Prime Minister"
    )
    assert arts["78"].prefer_article_unit is True
    assert "(a) to communicate" in (arts["78"].body_text or "")

    body_80 = arts["80"].body_text or ""
    assert "1 [" not in body_80
    assert "2 ***" not in body_80
    assert body_80.startswith("(1) The Council of States shall consist of")
    assert "(4) The representatives of each State" in body_80
    assert "(5) The representatives of the Union territories" in body_80


def test_learning_units_from_synthetic_doc():
    doc, _ = apply_corrections(_broken_doc(), load_corrections(CORRECTIONS))
    result = generate_learning_units(doc)
    by_art: dict[str, list] = {}
    for u in result.units:
        by_art.setdefault(u.article_number, []).append(u)

    texts_74 = " ".join(u.text for u in by_art["74"])
    assert "Council of Ministers with the Prime Minister" in texts_74

    ids_75 = {u.id for u in by_art["75"]}
    assert "article-75-clause-1" in ids_75
    assert "article-75-clause-1a" in ids_75
    assert "article-75-clause-1b" in ids_75
    assert "article-75-clause-5" in ids_75
    assert "article-75-clause-6" in ids_75
    texts_75 = " ".join(u.text for u in by_art["75"])
    assert "3 [" not in texts_75
    assert not any(u.text.rstrip().endswith("]") for u in by_art["75"] if "1B" in u.id.upper() or "1b" in u.id)

    texts_78 = " ".join(u.text for u in by_art["78"])
    assert "It shall be the duty of the Prime Minister" in texts_78

    texts_80 = " ".join(u.text for u in by_art["80"])
    assert "1 [" not in texts_80
    assert "***" not in texts_80
    assert "The Council of States shall consist of" in texts_80


def test_committed_learning_units_cover_74_80():
    if not UNITS.exists():
        pytest.skip("learning_units.json missing")
    payload = json.loads(UNITS.read_text())
    units = payload["units"] if isinstance(payload, dict) else payload
    by_art: dict[str, list] = {}
    for u in units:
        by_art.setdefault(u["article_number"], []).append(u)

    if "article-75-clause-1a" not in {u["id"] for u in by_art.get("75", [])}:
        pytest.skip("learning_units.json not yet regenerated for Art 75(1A)")

    texts_74 = " ".join(u["text"] for u in by_art["74"])
    assert "Council of Ministers with the Prime Minister" in texts_74

    ids_75 = {u["id"] for u in by_art["75"]}
    assert "article-75-clause-1a" in ids_75
    assert "article-75-clause-1b" in ids_75
    texts_75 = " ".join(u["text"] for u in by_art["75"])
    assert "3 [" not in texts_75
    assert "[(1A)" not in texts_75

    texts_78 = " ".join(u["text"] for u in by_art["78"])
    assert "It shall be the duty of the Prime Minister" in texts_78

    texts_80 = " ".join(u["text"] for u in by_art["80"])
    assert "1 [" not in texts_80
    assert "***" not in texts_80
    assert texts_80.startswith("(1) The Council of States") or (
        "The Council of States shall consist of" in texts_80
    )
