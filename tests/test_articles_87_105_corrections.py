"""Restore Bare Act wording for Arts 87–105 diglot debris via corrections."""

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
    "article-87",
    "article-94",
    "article-98",
    "article-100",
    "article-101",
    "article-102",
    "article-103",
    "article-105",
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
                                id="article-87",
                                article_number="87",
                                numeric_component=87,
                                title="Special address by the President",
                                part_number="V",
                                chapter_number="II",
                                status=ArticleStatus.ACTIVE,
                                body_text=(
                                    "(1) At the commencement of 2 [the first session "
                                    "after each general election…] the President…\n"
                                    "(2) Provision shall be made… such address 3 ***."
                                ),
                            ),
                            Article(
                                id="article-94",
                                article_number="94",
                                numeric_component=94,
                                title="Vacation and resignation of Speaker",
                                part_number="V",
                                chapter_number="II",
                                status=ArticleStatus.ACTIVE,
                                body_text="(a) shall vacate his office… missing stem",
                            ),
                            Article(
                                id="article-98",
                                article_number="98",
                                numeric_component=98,
                                title="Secretariat of Parliament",
                                part_number="V",
                                chapter_number="II",
                                status=ArticleStatus.ACTIVE,
                                body_text=(
                                    "(1) Each House of Parliament shall have a "
                                    "separate secretarial staff:\n"
                                    "(2) Parliament may by law regulate…"
                                ),
                            ),
                            Article(
                                id="article-100",
                                article_number="100",
                                numeric_component=100,
                                title="Voting in Houses… and quorum",
                                part_number="V",
                                chapter_number="II",
                                status=ArticleStatus.ACTIVE,
                                body_text=(
                                    "(1) Save as otherwise…\n"
                                    "(2) Either House… proceedings. 1 [(3) Until "
                                    "Parliament… House.\n"
                                    "(4) If at any time… quorum.]"
                                ),
                            ),
                            Article(
                                id="article-101",
                                article_number="101",
                                numeric_component=101,
                                title="Vacation of seats",
                                part_number="V",
                                chapter_number="II",
                                status=ArticleStatus.ACTIVE,
                                body_text=(
                                    "(1) No person shall be a member of both Houses…"
                                ),
                            ),
                            Article(
                                id="article-102",
                                article_number="102",
                                numeric_component=102,
                                title="Disqualifications for membership",
                                part_number="V",
                                chapter_number="II",
                                status=ArticleStatus.ACTIVE,
                                body_text=(
                                    "(b) if he is of unsound mind… 2 [ Explanation."
                                    "For the purposes of this clause] … 3 [(2) A person…]"
                                ),
                            ),
                            Article(
                                id="article-103",
                                article_number="103",
                                numeric_component=103,
                                title="Decision on questions as to disqualifications",
                                part_number="V",
                                chapter_number="II",
                                status=ArticleStatus.ACTIVE,
                                body_text=(
                                    "(1) If any question arises… decision shall be final."
                                ),
                            ),
                            Article(
                                id="article-105",
                                article_number="105",
                                numeric_component=105,
                                title="Powers, privileges, etc.",
                                part_number="V",
                                chapter_number="II",
                                status=ArticleStatus.ACTIVE,
                                body_text=(
                                    "(1) Subject to the provisions…\n"
                                    "(2) No member… proceedings. 1 [(3) In other "
                                    "respects… 1978.]]."
                                ),
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )


def test_corrections_file_covers_87_105_keys():
    data = json.loads(CORRECTIONS.read_text())
    arts = data["articles"]
    for key in REQUIRED_KEYS:
        assert key in arts, key
    assert arts["article-94"].get("prefer_article_unit") is True
    assert (arts["article-94"].get("opening_text") or "").startswith(
        "A member holding office as Speaker"
    )


def test_apply_restores_87_105_on_synthetic_doc():
    doc, _ = apply_corrections(_broken_doc(), load_corrections(CORRECTIONS))
    arts = _article_map(doc)

    body_87 = arts["87"].body_text or ""
    assert "2 [" not in body_87
    assert "***" not in body_87
    assert "the first session after each general election" in body_87
    assert body_87.rstrip().endswith("such address.")

    assert (arts["94"].opening_text or "").startswith(
        "A member holding office as Speaker or Deputy Speaker"
    )
    assert "(a) shall vacate his office" in (arts["94"].body_text or "")

    body_98 = arts["98"].body_text or ""
    assert "Provided that nothing in this clause shall be construed as" in body_98
    assert "(3) Until provision is made by Parliament" in body_98

    body_100 = arts["100"].body_text or ""
    assert "1 [(" not in body_100
    assert not body_100.rstrip().endswith("]")
    assert (
        "(3) Until Parliament by law otherwise provides, the quorum"
        in body_100
    )
    assert "(4) If at any time during a meeting of a House" in body_100

    body_101 = arts["101"].body_text or ""
    assert "(2) No person shall be a member both of Parliament" in body_101
    assert "(4) If for a period of sixty days" in body_101

    body_102 = arts["102"].body_text or ""
    assert body_102.startswith(
        "(1) A person shall be disqualified for being chosen as"
    )
    assert "(a) if he holds any office of profit" in body_102
    assert "2 [" not in body_102
    assert "Explanation.—For the purposes of this clause," in body_102
    assert "(2) A person shall be disqualified for being a member" in body_102

    body_103 = arts["103"].body_text or ""
    assert "his decision shall be final" in body_103
    assert "(2) Before giving any decision" in body_103
    assert "]" not in body_103.replace("[Omitted.]", "")

    body_105 = arts["105"].body_text or ""
    assert "(3) In other respects, the powers, privileges" in body_105
    assert "(2) No member of Parliament shall be liable" in body_105
    assert "1 [(" not in body_105
    assert "2 [" not in body_105


def test_learning_units_from_synthetic_doc():
    doc, _ = apply_corrections(_broken_doc(), load_corrections(CORRECTIONS))
    result = generate_learning_units(doc)
    by_art: dict[str, list] = {}
    for u in result.units:
        by_art.setdefault(u.article_number, []).append(u)

    texts_87 = " ".join(u.text for u in by_art["87"])
    assert "2 [" not in texts_87
    assert "***" not in texts_87

    texts_94 = " ".join(u.text for u in by_art["94"])
    assert "A member holding office as Speaker" in texts_94

    texts_98 = " ".join(u.text for u in by_art["98"])
    assert "Provided that nothing in this clause shall be construed as" in texts_98

    ids_100 = {u.id for u in by_art["100"]}
    assert "article-100-clause-3" in ids_100
    assert "article-100-clause-4" in ids_100

    ids_101 = {u.id for u in by_art["101"]}
    assert "article-101-clause-2" in ids_101
    assert "article-101-clause-4" in ids_101

    texts_102 = " ".join(u.text for u in by_art["102"])
    assert "(a) if he holds any office of profit" in texts_102
    assert "2 [" not in texts_102

    ids_103 = {u.id for u in by_art["103"]}
    assert "article-103-clause-2" in ids_103

    ids_105 = {u.id for u in by_art["105"]}
    assert "article-105-clause-3" in ids_105


def test_committed_learning_units_cover_87_105():
    if not UNITS.exists():
        pytest.skip("learning_units.json missing")
    payload = json.loads(UNITS.read_text())
    units = payload["units"] if isinstance(payload, dict) else payload
    by_art: dict[str, list] = {}
    for u in units:
        by_art.setdefault(u["article_number"], []).append(u)

    if "article-100-clause-3" not in {u["id"] for u in by_art.get("100", [])}:
        pytest.skip("learning_units.json not yet regenerated for Art 100")

    texts_87 = " ".join(u["text"] for u in by_art["87"])
    assert "2 [" not in texts_87
    assert "***" not in texts_87

    texts_94 = " ".join(u["text"] for u in by_art["94"])
    assert "A member holding office as Speaker" in texts_94

    texts_98 = " ".join(u["text"] for u in by_art["98"])
    assert "Provided that nothing in this clause shall be construed as" in texts_98

    ids_100 = {u["id"] for u in by_art["100"]}
    assert "article-100-clause-3" in ids_100
    assert not any(u["text"].rstrip().endswith("]") for u in by_art["100"])

    ids_101 = {u["id"] for u in by_art["101"]}
    assert "article-101-clause-2" in ids_101

    texts_102 = " ".join(u["text"] for u in by_art["102"])
    assert "(a) if he holds any office of profit" in texts_102
    assert "2 [" not in texts_102

    assert "article-103-clause-2" in {u["id"] for u in by_art["103"]}
    assert "article-105-clause-3" in {u["id"] for u in by_art["105"]}
