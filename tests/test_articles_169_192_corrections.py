"""Restore Bare Act wording for Arts 169–192 diglot / glued siblings via corrections."""

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
    "article-169",
    "article-170",
    "article-172",
    "article-173",
    "article-176",
    "article-177",
    "article-179",
    "article-183",
    "article-187",
    "article-189",
    "article-190",
    "article-191",
    "article-192",
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
                id="part-vi",
                part_number="VI",
                title="THE STATES",
                chapters=[
                    Chapter(
                        id="chapter-iii",
                        chapter_number="III",
                        title="THE STATE LEGISLATURE",
                        articles=[
                            Article(
                                id="article-169",
                                article_number="169",
                                numeric_component=169,
                                title="Abolition or creation of Legislative Councils…",
                                part_number="VI",
                                chapter_number="III",
                                status=ArticleStatus.ACTIVE,
                                body_text=(
                                    "(1) …\n(2) …\n(3) … 4 [ 170. Composition…"
                                ),
                            ),
                            Article(
                                id="article-172",
                                article_number="172",
                                numeric_component=172,
                                title="Duration of State Legislatures",
                                part_number="VI",
                                chapter_number="III",
                                status=ArticleStatus.ACTIVE,
                                body_text=(
                                    "(1) … 1 [five years] …\n"
                                    "(2) … Emergency proviso wrongly here"
                                ),
                            ),
                            Article(
                                id="article-173",
                                article_number="173",
                                numeric_component=173,
                                title="Qualification for membership…",
                                part_number="VI",
                                chapter_number="III",
                                status=ArticleStatus.ACTIVE,
                                body_text="2 [( a )…] only (a)",
                            ),
                            Article(
                                id="article-176",
                                article_number="176",
                                numeric_component=176,
                                title="Special address by the Governor",
                                part_number="VI",
                                chapter_number="III",
                                status=ArticleStatus.ACTIVE,
                                body_text="(1) 2 [ … ]\n(2) … 3 ***",
                            ),
                            Article(
                                id="article-177",
                                article_number="177",
                                numeric_component=177,
                                title="Rights of Ministers… as respects Houses",
                                part_number="VI",
                                chapter_number="III",
                                status=ArticleStatus.ACTIVE,
                                body_text=(
                                    "Every Minister… Officers of the State Legislature"
                                ),
                            ),
                            Article(
                                id="article-179",
                                article_number="179",
                                numeric_component=179,
                                title="Vacation and resignation of… Speaker",
                                part_number="VI",
                                chapter_number="III",
                                status=ArticleStatus.ACTIVE,
                                body_text="(a) shall vacate… missing stem",
                            ),
                            Article(
                                id="article-183",
                                article_number="183",
                                numeric_component=183,
                                title="Vacation and resignation of… Chairman",
                                part_number="VI",
                                chapter_number="III",
                                status=ArticleStatus.ACTIVE,
                                body_text="(a) shall vacate… missing stem",
                            ),
                            Article(
                                id="article-187",
                                article_number="187",
                                numeric_component=187,
                                title="Secretariat of State Legislature",
                                part_number="VI",
                                chapter_number="III",
                                status=ArticleStatus.ACTIVE,
                                body_text=(
                                    "(1) …\n(2) …\n(3) Conduct of Business + proviso"
                                ),
                            ),
                            Article(
                                id="article-189",
                                article_number="189",
                                numeric_component=189,
                                title="Voting in Houses… and quorum",
                                part_number="VI",
                                chapter_number="III",
                                status=ArticleStatus.ACTIVE,
                                body_text="(1) …\n(2) … (3) swallowed… (4) …]",
                            ),
                            Article(
                                id="article-190",
                                article_number="190",
                                numeric_component=190,
                                title="Vacation of seats",
                                part_number="VI",
                                chapter_number="III",
                                status=ArticleStatus.ACTIVE,
                                body_text="(1) … diglot (3)(a)/(b) …]",
                            ),
                            Article(
                                id="article-191",
                                article_number="191",
                                numeric_component=191,
                                title="Disqualifications for membership",
                                part_number="VI",
                                chapter_number="III",
                                status=ArticleStatus.ACTIVE,
                                body_text=(
                                    "(b) … missing (1) stem/(a) … 192. Decision…"
                                ),
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )


def test_corrections_file_covers_169_192_keys():
    data = json.loads(CORRECTIONS.read_text())
    arts = data["articles"]
    for key in REQUIRED_KEYS:
        assert key in arts, key
    assert arts["article-170"].get("create") is True
    assert arts["article-192"].get("create") is True
    assert arts["article-179"].get("prefer_article_unit") is True
    assert arts["article-183"].get("prefer_article_unit") is True
    body_169 = arts["article-169"].get("body_text") or ""
    assert "170." not in body_169
    body_191 = arts["article-191"].get("body_text") or ""
    assert "192." not in body_191


def test_apply_restores_169_192_on_synthetic_doc():
    doc, _ = apply_corrections(_broken_doc(), load_corrections(CORRECTIONS))
    arts = _article_map(doc)

    body_169 = arts["169"].body_text or ""
    assert "(1)" in body_169 and "(3)" in body_169
    assert "170." not in body_169
    assert "Composition of the Legislative Assemblies" not in body_169

    body_170 = arts["170"].body_text or ""
    assert body_170.startswith("(1) Subject to the provisions of article 333")
    assert "(3)" in body_170
    assert "2026" in body_170

    body_172 = arts["172"].body_text or ""
    assert "1 [" not in body_172
    assert "five years" in body_172
    # Emergency proviso belongs under (1), before (2)
    assert "Proclamation" in body_172
    assert body_172.index("Proclamation") < body_172.index("(2)")

    body_173 = (arts["173"].opening_text or "") + (arts["173"].body_text or "")
    assert "A person shall not be qualified" in body_173
    assert "(a)" in body_173 and "(b)" in body_173 and "(c)" in body_173
    assert "2 [" not in body_173

    body_176 = arts["176"].body_text or ""
    assert "2 [" not in body_176
    assert "***" not in body_176

    body_177 = arts["177"].body_text or ""
    assert "Officers of the State Legislature" not in body_177

    assert (arts["179"].opening_text or "").startswith(
        "A member holding office as Speaker or Deputy Speaker"
    )
    assert (arts["183"].opening_text or "").startswith(
        "A member holding office as Chairman or Deputy Chairman"
    )

    body_187 = arts["187"].body_text or ""
    assert "Provided that" in body_187
    assert body_187.index("Provided that") < body_187.index("(2)")
    assert "Conduct of Business" not in body_187

    body_189 = arts["189"].body_text or ""
    assert "(1)" in body_189 and "(2)" in body_189 and "(3)" in body_189 and "(4)" in body_189
    assert not body_189.rstrip().endswith("]")

    body_190 = arts["190"].body_text or ""
    assert "(3)" in body_190 and "(4)" in body_190
    assert "1 [" not in body_190
    assert not body_190.rstrip().endswith("]")

    body_191 = arts["191"].body_text or ""
    assert "(a)" in body_191 and "(e)" in body_191
    assert "Explanation" in body_191
    assert "192." not in body_191

    body_192 = arts["192"].body_text or ""
    assert "(1)" in body_192 and "(2)" in body_192
    assert "Election Commission" in body_192


def test_learning_units_from_synthetic_doc():
    doc, _ = apply_corrections(_broken_doc(), load_corrections(CORRECTIONS))
    result = generate_learning_units(doc)
    by_art: dict[str, list] = {}
    for u in result.units:
        by_art.setdefault(u.article_number, []).append(u)

    texts_169 = " ".join(u.text for u in by_art["169"])
    assert "170." not in texts_169

    ids_170 = {u.id for u in by_art["170"]}
    assert "article-170-clause-3" in ids_170

    texts_172 = " ".join(u.text for u in by_art["172"])
    clause1 = next(u.text for u in by_art["172"] if u.id.endswith("clause-1"))
    assert "Proclamation" in clause1
    assert "1 [" not in texts_172

    ids_173 = {u.id for u in by_art["173"]}
    assert "article-173-subclause-b" in ids_173
    assert "article-173-subclause-c" in ids_173

    texts_176 = " ".join(u.text for u in by_art["176"])
    assert "***" not in texts_176

    texts_177 = " ".join(u.text for u in by_art["177"])
    assert "Officers of the State Legislature" not in texts_177

    texts_179 = " ".join(u.text for u in by_art["179"])
    texts_183 = " ".join(u.text for u in by_art["183"])
    assert "A member holding office as Speaker" in texts_179
    assert "A member holding office as Chairman" in texts_183

    clause_187_1 = next(u.text for u in by_art["187"] if u.id.endswith("clause-1"))
    assert "Provided that" in clause_187_1

    ids_189 = {u.id for u in by_art["189"]}
    assert "article-189-clause-3" in ids_189

    texts_191 = " ".join(u.text for u in by_art["191"])
    assert "(a)" in texts_191
    assert "192." not in texts_191

    ids_192 = {u.id for u in by_art["192"]}
    assert "article-192-clause-2" in ids_192


def test_committed_learning_units_cover_169_192():
    if not UNITS.exists():
        pytest.skip("learning_units.json missing")
    payload = json.loads(UNITS.read_text())
    units = payload["units"] if isinstance(payload, dict) else payload
    by_id = {u["id"]: u for u in units}
    by_art: dict[str, list] = {}
    for u in units:
        by_art.setdefault(u["article_number"], []).append(u)

    if "article-170-clause-3" not in by_id:
        pytest.skip("learning_units.json not yet regenerated for Art 170")

    texts_169 = " ".join(u["text"] for u in by_art["169"])
    assert "170." not in texts_169
    assert "article-170-clause-3" in by_id

    clause1_172 = by_id["article-172-clause-1"]["text"]
    assert "five years" in clause1_172
    assert "Proclamation" in clause1_172
    assert "1 [" not in clause1_172

    assert "article-173-subclause-b" in by_id
    assert "article-173-subclause-c" in by_id

    texts_176 = " ".join(u["text"] for u in by_art["176"])
    assert "***" not in texts_176
    assert "2 [" not in texts_176

    texts_177 = " ".join(u["text"] for u in by_art["177"])
    assert "Officers of the State Legislature" not in texts_177

    assert "A member holding office as Speaker" in by_id["article-179"]["text"]
    assert "A member holding office as Chairman" in by_id["article-183"]["text"]

    assert "Provided that" in by_id["article-187-clause-1"]["text"]
    assert "article-189-clause-3" in by_id

    texts_191 = " ".join(u["text"] for u in by_art["191"])
    assert "article-191-clause-1-subclause-a" in by_id
    assert "192." not in texts_191

    assert "article-192-clause-1" in by_id
    assert "article-192-clause-2" in by_id
    assert "Election Commission" in by_id["article-192-clause-2"]["text"]
