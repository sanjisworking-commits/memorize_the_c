"""Restore Bare Act wording for Arts 124B–145 diglot / NJAC debris via corrections."""

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
    "article-124b",
    "article-124c",
    "article-125",
    "article-127",
    "article-128",
    "article-131",
    "article-132",
    "article-133",
    "article-134",
    "article-134a",
    "article-139",
    "article-139a",
    "article-144",
    "article-144a",
    "article-145",
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
                        id="chapter-iv",
                        chapter_number="IV",
                        title="THE UNION JUDICIARY",
                        articles=[
                            Article(
                                id="article-125",
                                article_number="125",
                                numeric_component=125,
                                title="Salaries, etc., of Judges",
                                part_number="V",
                                chapter_number="IV",
                                status=ArticleStatus.ACTIVE,
                                body_text="(2) Every Judge… missing diglot-wrapped (1)",
                            ),
                            Article(
                                id="article-127",
                                article_number="127",
                                numeric_component=127,
                                title="Appointment of ad hoc Judges",
                                part_number="V",
                                chapter_number="IV",
                                status=ArticleStatus.ACTIVE,
                                body_text=(
                                    "(1) … National Judicial Appointments Commission…"
                                ),
                            ),
                            Article(
                                id="article-128",
                                article_number="128",
                                numeric_component=128,
                                title="Attendance of retired Judges…",
                                part_number="V",
                                chapter_number="IV",
                                status=ArticleStatus.ACTIVE,
                                body_text=(
                                    "… National Judicial Appointments Commission…"
                                ),
                            ),
                            Article(
                                id="article-131",
                                article_number="131",
                                numeric_component=131,
                                title="Original jurisdiction of the Supreme Court",
                                part_number="V",
                                chapter_number="IV",
                                status=ArticleStatus.ACTIVE,
                                body_text="(a) between the Government of India… stem glued",
                            ),
                            Article(
                                id="article-132",
                                article_number="132",
                                numeric_component=132,
                                title="Appellate jurisdiction… Constitution",
                                part_number="V",
                                chapter_number="IV",
                                status=ArticleStatus.ACTIVE,
                                body_text="(1) … 1 [134A] (2) … (3) …",
                            ),
                            Article(
                                id="article-133",
                                article_number="133",
                                numeric_component=133,
                                title="Appellate jurisdiction… civil matters",
                                part_number="V",
                                chapter_number="IV",
                                status=ArticleStatus.ACTIVE,
                                body_text="(a) … missing stem ]",
                            ),
                            Article(
                                id="article-134",
                                article_number="134",
                                numeric_component=134,
                                title="Appellate jurisdiction… criminal matters",
                                part_number="V",
                                chapter_number="IV",
                                status=ArticleStatus.ACTIVE,
                                body_text="(a) … missing stem and (2)",
                            ),
                            Article(
                                id="article-134a",
                                article_number="134A",
                                numeric_component=134,
                                title="Certificate for appeal to the Supreme Court",
                                part_number="V",
                                chapter_number="IV",
                                status=ArticleStatus.ACTIVE,
                                body_text="(a) … missing stem ]",
                            ),
                            Article(
                                id="article-139",
                                article_number="139",
                                numeric_component=139,
                                title="Conferment on the Supreme Court of powers…",
                                part_number="V",
                                chapter_number="IV",
                                status=ArticleStatus.ACTIVE,
                                body_text=(
                                    "(1) Where cases involving the same… stolen 139A"
                                ),
                            ),
                            Article(
                                id="article-144",
                                article_number="144",
                                numeric_component=144,
                                title="Civil and judicial authorities to act…",
                                part_number="V",
                                chapter_number="IV",
                                status=ArticleStatus.ACTIVE,
                                body_text="All authorities… Supreme Court. plus debris",
                            ),
                            Article(
                                id="article-145",
                                article_number="145",
                                numeric_component=145,
                                title="Rules of Court, etc.",
                                part_number="V",
                                chapter_number="IV",
                                status=ArticleStatus.ACTIVE,
                                body_text="(a) rules as to… letter-only missing parent",
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )


def test_corrections_file_covers_124b_145_keys():
    data = json.loads(CORRECTIONS.read_text())
    arts = data["articles"]
    for key in REQUIRED_KEYS:
        assert key in arts, key
    assert arts["article-124b"].get("create") is True
    assert arts["article-124b"].get("status") == "omitted"
    assert arts["article-124c"].get("status") == "omitted"
    assert arts["article-144a"].get("status") == "omitted"
    assert arts["article-139a"].get("create") is True
    assert arts["article-131"].get("prefer_article_unit") is True
    assert arts["article-131"].get("enable_letter_split") is True
    body_132 = arts["article-132"].get("body_text") or ""
    assert "(2)" not in body_132
    assert "(3)" in body_132
    body_139 = arts["article-139"].get("body_text") or ""
    assert "Parliament may by law confer" in body_139
    assert "Where cases involving the same" not in body_139


def test_apply_restores_124b_145_on_synthetic_doc():
    doc, _ = apply_corrections(_broken_doc(), load_corrections(CORRECTIONS))
    arts = _article_map(doc)

    assert arts["124B"].status.value == "omitted"
    assert (arts["124B"].body_text or "").strip() == "[Omitted.]"
    assert arts["124C"].status.value == "omitted"
    assert (arts["124C"].body_text or "").strip() == "[Omitted.]"
    assert arts["144A"].status.value == "omitted"
    assert (arts["144A"].body_text or "").strip() == "[Omitted.]"

    body_125 = arts["125"].body_text or ""
    assert "(1)" in body_125 and "(2)" in body_125
    assert "Provided that" in body_125
    assert "1 [" not in body_125

    for num in ("127", "128"):
        body = arts[num].body_text or ""
        assert "National Judicial Appointments Commission" not in body
        assert "Chief Justice of India" in body

    assert arts["131"].prefer_article_unit is True
    assert arts["131"].enable_letter_split is True
    body_131 = (arts["131"].opening_text or "") + (arts["131"].body_text or "")
    assert "Subject to the provisions of this Constitution" in body_131
    assert "(a)" in body_131 and "(c)" in body_131

    body_132 = arts["132"].body_text or ""
    assert "(1)" in body_132 and "(3)" in body_132
    assert "(2)" not in body_132
    assert "1 [" not in body_132

    body_133 = arts["133"].body_text or ""
    assert "An appeal shall lie to the Supreme Court" in body_133
    assert "(a)" in body_133 and "(b)" in body_133
    assert not body_133.rstrip().endswith("]")

    body_134 = arts["134"].body_text or ""
    assert "An appeal shall lie to the Supreme Court" in body_134
    assert "(2)" in body_134

    body_134a = (arts["134A"].opening_text or "") + (arts["134A"].body_text or "")
    assert "Every High Court" in body_134a
    assert not body_134a.rstrip().endswith("]")

    body_139 = arts["139"].body_text or ""
    assert "Parliament may by law confer on the Supreme Court" in body_139
    assert "Where cases involving the same" not in body_139

    body_139a = arts["139A"].body_text or ""
    assert "(1)" in body_139a and "(2)" in body_139a
    assert "Provided that" in body_139a

    assert (arts["144"].body_text or "").strip().startswith("All authorities")
    assert "Supreme Court." in (arts["144"].body_text or "")

    body_145 = arts["145"].body_text or ""
    assert body_145.startswith("(1) Subject to the provisions")
    assert "(cc) rules as to the proceedings in the Court under article 139A" in body_145
    assert "(5)" in body_145


def test_learning_units_from_synthetic_doc():
    doc, _ = apply_corrections(_broken_doc(), load_corrections(CORRECTIONS))
    result = generate_learning_units(doc)
    by_art: dict[str, list] = {}
    for u in result.units:
        by_art.setdefault(u.article_number, []).append(u)

    assert any(u.text.strip() == "[Omitted.]" for u in by_art["124B"])
    assert any(u.text.strip() == "[Omitted.]" for u in by_art["124C"])

    ids_125 = {u.id for u in by_art["125"]}
    assert "article-125-clause-1" in ids_125

    ids_131 = {u.id for u in by_art["131"]}
    assert "article-131" in ids_131
    assert "article-131-subclause-a" in ids_131
    assert "article-131-subclause-c" in ids_131

    ids_132 = {u.id for u in by_art["132"]}
    assert "article-132-clause-3" in ids_132
    assert "article-132-clause-2" not in ids_132

    texts_139 = " ".join(u.text for u in by_art["139"])
    texts_139a = " ".join(u.text for u in by_art["139A"])
    assert "Parliament may by law confer" in texts_139
    assert "Where cases involving the same" in texts_139a
    assert "Where cases involving the same" not in texts_139

    ids_145 = {u.id for u in by_art["145"]}
    assert "article-145-clause-1" in ids_145
    assert "article-145-clause-5" in ids_145
    # Not letter-only: parent clause unit exists alongside letter children.
    assert any(u.id.startswith("article-145-clause-1-subclause-") for u in by_art["145"])


def test_committed_learning_units_cover_124b_145():
    if not UNITS.exists():
        pytest.skip("learning_units.json missing")
    payload = json.loads(UNITS.read_text())
    units = payload["units"] if isinstance(payload, dict) else payload
    by_id = {u["id"]: u for u in units}
    by_art: dict[str, list] = {}
    for u in units:
        by_art.setdefault(u["article_number"], []).append(u)

    if "article-139a-clause-1" not in by_id and "article-139a" not in by_id:
        pytest.skip("learning_units.json not yet regenerated for Art 139A")

    assert by_id["article-124b"]["text"].strip() == "[Omitted.]"
    assert by_id["article-124c"]["text"].strip() == "[Omitted.]"
    assert by_id["article-144a"]["text"].strip() == "[Omitted.]"
    assert "article-125-clause-1" in by_id

    texts_127 = " ".join(u["text"] for u in by_art["127"])
    texts_128 = " ".join(u["text"] for u in by_art["128"])
    assert "National Judicial Appointments Commission" not in texts_127
    assert "National Judicial Appointments Commission" not in texts_128
    assert "Chief Justice of India" in texts_127
    assert "Chief Justice of India" in texts_128

    assert "article-131" in by_id
    assert "article-131-subclause-a" in by_id
    assert "article-131-subclause-c" in by_id

    ids_132 = {u["id"] for u in by_art["132"]}
    assert "article-132-clause-3" in ids_132
    assert "article-132-clause-2" not in ids_132

    texts_139 = " ".join(u["text"] for u in by_art["139"])
    texts_139a = " ".join(u["text"] for u in by_art["139A"])
    assert "Parliament may by law confer" in texts_139
    assert "Where cases involving the same" in texts_139a
    assert texts_139 != texts_139a

    assert by_id["article-144"]["text"].strip().startswith("All authorities")
    assert "article-145-clause-1" in by_id
    assert "(cc)" in by_id["article-145-clause-1"]["text"]
    assert "article-145-clause-5" in by_id
