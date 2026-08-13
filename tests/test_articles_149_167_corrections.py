"""Restore Bare Act wording for Arts 149–167 diglot debris via corrections."""

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
    "article-149",
    "article-151",
    "article-153",
    "article-156",
    "article-158",
    "article-159",
    "article-162",
    "article-164",
    "article-166",
    "article-167",
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
                        id="chapter-v",
                        chapter_number="V",
                        title="COMPTROLLER AND AUDITOR-GENERAL OF INDIA",
                        articles=[
                            Article(
                                id="article-149",
                                article_number="149",
                                numeric_component=149,
                                title="Duties and powers of the Comptroller…",
                                part_number="V",
                                chapter_number="V",
                                status=ArticleStatus.ACTIVE,
                                body_text=(
                                    "The Comptroller… 150. Form of accounts… ]"
                                ),
                            ),
                            Article(
                                id="article-151",
                                article_number="151",
                                numeric_component=151,
                                title="Audit reports",
                                part_number="V",
                                chapter_number="V",
                                status=ArticleStatus.ACTIVE,
                                body_text=(
                                    "(1) …\n(2) … Governor 3 *** or Rajpramukh…"
                                ),
                            ),
                        ],
                    ),
                ],
            ),
            Part(
                id="part-vi",
                part_number="VI",
                title="THE STATES",
                chapters=[
                    Chapter(
                        id="chapter-ii",
                        chapter_number="II",
                        title="THE EXECUTIVE",
                        articles=[
                            Article(
                                id="article-153",
                                article_number="153",
                                numeric_component=153,
                                title="Governors of States",
                                part_number="VI",
                                chapter_number="II",
                                status=ArticleStatus.ACTIVE,
                                body_text="There shall be a Governor… 3 [ Provided… ]",
                            ),
                            Article(
                                id="article-156",
                                article_number="156",
                                numeric_component=156,
                                title="Term of office of Governor",
                                part_number="VI",
                                chapter_number="II",
                                status=ArticleStatus.ACTIVE,
                                body_text="(1) …\n(2) …\n(3) … missing successor proviso",
                            ),
                            Article(
                                id="article-158",
                                article_number="158",
                                numeric_component=158,
                                title="Conditions of Governor's office",
                                part_number="VI",
                                chapter_number="II",
                                status=ArticleStatus.ACTIVE,
                                body_text="(1) …\n(3) … glued (3A)",
                            ),
                            Article(
                                id="article-159",
                                article_number="159",
                                numeric_component=159,
                                title="Oath or affirmation by the Governor",
                                part_number="VI",
                                chapter_number="II",
                                status=ArticleStatus.ACTIVE,
                                body_text="I, A.B., do swear… flattened oath",
                            ),
                            Article(
                                id="article-162",
                                article_number="162",
                                numeric_component=162,
                                title="Extent of executive power of State",
                                part_number="VI",
                                chapter_number="II",
                                status=ArticleStatus.ACTIVE,
                                body_text=(
                                    "Council of Ministers\nSubject to… Provided…"
                                ),
                            ),
                            Article(
                                id="article-164",
                                article_number="164",
                                numeric_component=164,
                                title="Other provisions as to Ministers",
                                part_number="VI",
                                chapter_number="II",
                                status=ArticleStatus.ACTIVE,
                                body_text="(1) … missing 1A/1B/4/5 diglot states",
                            ),
                            Article(
                                id="article-166",
                                article_number="166",
                                numeric_component=166,
                                title="Conduct of business of the Government of a State",
                                part_number="VI",
                                chapter_number="II",
                                status=ArticleStatus.ACTIVE,
                                body_text=(
                                    "(1) …\n(2) …\n(3) …\n<!-- image --> * * * *"
                                ),
                            ),
                            Article(
                                id="article-167",
                                article_number="167",
                                numeric_component=167,
                                title="Duties of Chief Minister…",
                                part_number="VI",
                                chapter_number="II",
                                status=ArticleStatus.ACTIVE,
                                body_text="(a) to communicate… missing stem",
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )


def test_corrections_file_covers_149_167_keys():
    data = json.loads(CORRECTIONS.read_text())
    arts = data["articles"]
    for key in REQUIRED_KEYS:
        assert key in arts, key
    assert "article-150" in arts  # keep Art 150 overlay intact
    assert arts["article-167"].get("prefer_article_unit") is True
    assert arts["article-167"].get("enable_letter_split") is True
    body_164 = arts["article-164"].get("body_text") or ""
    assert "(1A)" in body_164 and "(1B)" in body_164
    assert "(4)" in body_164 and "(5)" in body_164


def test_apply_restores_149_167_on_synthetic_doc():
    doc, _ = apply_corrections(_broken_doc(), load_corrections(CORRECTIONS))
    arts = _article_map(doc)

    body_149 = arts["149"].body_text or ""
    assert "150." not in body_149
    assert not body_149.rstrip().endswith("]")
    assert "Form of accounts" not in body_149

    body_151 = arts["151"].body_text or ""
    assert "***" not in body_151
    assert "Rajpramukh" not in body_151
    assert "Governor of the State" in body_151

    body_153 = arts["153"].body_text or ""
    assert "3 [" not in body_153
    assert "Provided that" in body_153
    assert not body_153.rstrip().endswith("]")

    body_156 = arts["156"].body_text or ""
    assert "continue to hold office until his successor enters upon his office" in body_156

    body_158 = arts["158"].body_text or ""
    assert "(3A)" in body_158
    assert "(4)" in body_158

    body_159 = arts["159"].body_text or ""
    assert "swear in the name of God" in body_159
    assert "solemnly affirm" in body_159

    body_162 = arts["162"].body_text or ""
    assert "Council of Ministers" not in body_162
    assert "Provided that" in body_162

    body_164 = arts["164"].body_text or ""
    assert "(1A)" in body_164 and "(1B)" in body_164
    assert "(4)" in body_164 and "(5)" in body_164

    body_166 = arts["166"].body_text or ""
    assert "(1)" in body_166 and "(3)" in body_166
    assert "(4)" not in body_166
    assert "<!-- image -->" not in body_166
    assert "* * * *" not in body_166

    assert (arts["167"].opening_text or "").startswith(
        "It shall be the duty of the Chief Minister"
    )
    assert arts["167"].prefer_article_unit is True
    assert "(a)" in (arts["167"].body_text or "")


def test_learning_units_from_synthetic_doc():
    doc, _ = apply_corrections(_broken_doc(), load_corrections(CORRECTIONS))
    result = generate_learning_units(doc)
    by_art: dict[str, list] = {}
    for u in result.units:
        by_art.setdefault(u.article_number, []).append(u)

    texts_149 = " ".join(u.text for u in by_art["149"])
    assert "150." not in texts_149

    texts_151 = " ".join(u.text for u in by_art["151"])
    assert "***" not in texts_151
    assert "Rajpramukh" not in texts_151

    ids_158 = {u.id for u in by_art["158"]}
    assert "article-158-clause-3a" in ids_158

    ids_164 = {u.id for u in by_art["164"]}
    assert "article-164-clause-1a" in ids_164
    assert "article-164-clause-4" in ids_164
    assert "article-164-clause-5" in ids_164

    texts_166 = " ".join(u.text for u in by_art["166"])
    assert "<!-- image -->" not in texts_166
    assert "* * * *" not in texts_166
    assert "article-166-clause-4" not in {u.id for u in by_art["166"]}

    ids_167 = {u.id for u in by_art["167"]}
    assert "article-167" in ids_167
    assert "article-167-subclause-a" in ids_167
    texts_167 = " ".join(u.text for u in by_art["167"])
    assert "It shall be the duty of the Chief Minister" in texts_167


def test_committed_learning_units_cover_149_167():
    if not UNITS.exists():
        pytest.skip("learning_units.json missing")
    payload = json.loads(UNITS.read_text())
    units = payload["units"] if isinstance(payload, dict) else payload
    by_id = {u["id"]: u for u in units}
    by_art: dict[str, list] = {}
    for u in units:
        by_art.setdefault(u["article_number"], []).append(u)

    if "article-158-clause-3a" not in by_id:
        pytest.skip("learning_units.json not yet regenerated for Art 158")

    texts_149 = " ".join(u["text"] for u in by_art["149"])
    assert "150." not in texts_149
    assert "]" not in by_id["article-149"]["text"][-5:]

    texts_151 = " ".join(u["text"] for u in by_art["151"])
    assert "***" not in texts_151
    assert "Rajpramukh" not in texts_151

    assert "continue to hold office until his successor" in by_id["article-156-clause-3"][
        "text"
    ]
    assert "article-158-clause-3a" in by_id
    assert "article-164-clause-1a" in by_id
    assert "article-164-clause-4" in by_id
    assert "article-164-clause-5" in by_id

    texts_166 = " ".join(u["text"] for u in by_art["166"])
    assert "<!-- image -->" not in texts_166
    assert "* * * *" not in texts_166
    assert "****" not in texts_166

    assert "article-167" in by_id
    assert "It shall be the duty of the Chief Minister" in by_id["article-167"]["text"]
    assert "article-167-subclause-a" in by_id
