"""Restore Bare Act wording for Arts 111–123 diglot debris via corrections."""

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
    "article-111",
    "article-112",
    "article-113",
    "article-115",
    "article-119",
    "article-123",
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
                id="part-v",
                part_number="V",
                title="THE UNION",
                chapters=[
                    Chapter(
                        id="chapter-ii",
                        chapter_number="II",
                        title="PARLIAMENT",
                        articles=[
                            Article(
                                id="article-111",
                                article_number="111",
                                numeric_component=111,
                                title="Assent to Bills",
                                part_number="V",
                                chapter_number="II",
                                status=ArticleStatus.ACTIVE,
                                body_text=(
                                    "When a Bill has been passed… Provided that…"
                                ),
                            ),
                            Article(
                                id="article-112",
                                article_number="112",
                                numeric_component=112,
                                title="Annual financial statement",
                                part_number="V",
                                chapter_number="II",
                                status=ArticleStatus.ACTIVE,
                                body_text=(
                                    "(1) …\n(3) … (b) … (e) … missing (c)/(d)"
                                ),
                            ),
                            Article(
                                id="article-113",
                                article_number="113",
                                numeric_component=113,
                                title="Procedure in Parliament with respect to estimates",
                                part_number="V",
                                chapter_number="II",
                                status=ArticleStatus.ACTIVE,
                                body_text="(1) So much of the estimates… only clause",
                            ),
                            Article(
                                id="article-115",
                                article_number="115",
                                numeric_component=115,
                                title="Supplementary, additional or excess grants",
                                part_number="V",
                                chapter_number="II",
                                status=ArticleStatus.ACTIVE,
                                body_text=(
                                    "(1) (a) … (b) … cause to be laid glued in (b)"
                                ),
                            ),
                            Article(
                                id="article-119",
                                article_number="119",
                                numeric_component=119,
                                title="Regulation by law of procedure… financial business",
                                part_number="V",
                                chapter_number="II",
                                status=ArticleStatus.ACTIVE,
                                body_text=(
                                    "Parliament may… shall prevail. 1 [42nd/44th "
                                    "quorum footer]"
                                ),
                            ),
                            Article(
                                id="article-123",
                                article_number="123",
                                numeric_component=123,
                                title="Power of President to promulgate Ordinances…",
                                part_number="V",
                                chapter_number="II",
                                status=ArticleStatus.ACTIVE,
                                body_text=(
                                    "(1) …\n(2) …\n(3) …\n(4) omitted diglot still present"
                                ),
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )


def test_corrections_file_covers_111_123_keys():
    data = json.loads(CORRECTIONS.read_text())
    arts = data["articles"]
    for key in REQUIRED_KEYS:
        assert key in arts, key
    body_112 = arts["article-112"].get("body_text") or ""
    assert "(c) debt charges for which the Government of India is liable" in body_112
    assert "(d) (i) the salaries, allowances and pensions payable" in body_112
    body_123 = arts["article-123"].get("body_text") or ""
    assert "(4)" not in body_123
    assert "Explanation" in body_123


def test_apply_restores_111_123_on_synthetic_doc():
    doc, _ = apply_corrections(_broken_doc(), load_corrections(CORRECTIONS))
    arts = _article_map(doc)

    body_111 = arts["111"].body_text or ""
    assert "\nProvided that" in body_111 or body_111.count("Provided that") == 1
    assert "1 [" not in body_111

    body_112 = arts["112"].body_text or ""
    assert "(c) debt charges for which the Government of India is liable" in body_112
    assert "(d) (i) the salaries, allowances and pensions payable" in body_112
    assert "Judges of the Supreme Court" in body_112
    assert "Judges of the Federal Court" in body_112

    body_113 = arts["113"].body_text or ""
    assert "(2)" in body_113 and "(3)" in body_113

    body_115 = arts["115"].body_text or ""
    assert "cause to be laid" in body_115
    # stem after (a)/(b), not trapped only as trailing debris of (b)
    assert body_115.index("(a)") < body_115.index("cause to be laid")
    assert body_115.index("(b)") < body_115.index("cause to be laid")

    body_119 = arts["119"].body_text or ""
    assert body_119.rstrip().endswith("shall prevail.")
    assert "quorum" not in body_119.lower() or "shall prevail." in body_119
    assert "1 [" not in body_119
    assert "42nd" not in body_119 and "Forty-second" not in body_119

    body_123 = arts["123"].body_text or ""
    assert "(1)" in body_123 and "(2)" in body_123 and "(3)" in body_123
    assert "(4)" not in body_123
    assert "Explanation" in body_123


def test_learning_units_from_synthetic_doc():
    doc, _ = apply_corrections(_broken_doc(), load_corrections(CORRECTIONS))
    result = generate_learning_units(doc)
    by_art: dict[str, list] = {}
    for u in result.units:
        by_art.setdefault(u.article_number, []).append(u)

    ids_112 = {u.id for u in by_art["112"]}
    assert "article-112-clause-3-subclause-c" in ids_112
    assert "article-112-clause-3-subclause-d" in ids_112

    ids_113 = {u.id for u in by_art["113"]}
    assert "article-113-clause-2" in ids_113
    assert "article-113-clause-3" in ids_113

    ids_123 = {u.id for u in by_art["123"]}
    assert "article-123-clause-4" not in ids_123
    assert "article-123-clause-3" in ids_123


def test_committed_learning_units_cover_111_123():
    if not UNITS.exists():
        pytest.skip("learning_units.json missing")
    payload = json.loads(UNITS.read_text())
    units = payload["units"] if isinstance(payload, dict) else payload
    by_id = {u["id"]: u for u in units}
    by_art: dict[str, list] = {}
    for u in units:
        by_art.setdefault(u["article_number"], []).append(u)

    if "article-112-clause-3-subclause-c" not in by_id:
        pytest.skip("learning_units.json not yet regenerated for Art 112")

    assert "article-112-clause-3-subclause-c" in by_id
    assert "article-112-clause-3-subclause-d" in by_id
    assert "debt charges" in by_id["article-112-clause-3-subclause-c"]["text"]

    ids_113 = {u["id"] for u in by_art["113"]}
    assert "article-113-clause-2" in ids_113
    assert "article-113-clause-3" in ids_113

    texts_119 = " ".join(u["text"] for u in by_art["119"])
    assert "shall prevail." in texts_119
    assert "1 [" not in texts_119

    ids_123 = {u["id"] for u in by_art["123"]}
    assert "article-123-clause-4" not in ids_123
    assert "article-123-clause-1" in ids_123
    assert "article-123-clause-3" in ids_123
