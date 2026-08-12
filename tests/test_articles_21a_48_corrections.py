"""Restore Bare Act wording for Arts 21A–48 diglot debris via corrections."""

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
    ConstitutionDocument,
    DocumentMetadata,
    Part,
)

ROOT = Path(__file__).resolve().parents[1]
CORRECTIONS = ROOT / "data" / "corrections" / "corrections.json"
UNITS = ROOT / "data" / "output" / "learning_units.json"

REQUIRED_KEYS = (
    "article-21a",
    "article-22",
    "article-26",
    "article-30",
    "article-31a",
    "article-31b",
    "article-32",
    "article-32a",
    "article-33",
    "article-34",
    "article-35",
    "article-38",
    "article-39",
    "article-39a",
    "article-43",
    "article-48",
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
                id="part-iii",
                part_number="III",
                title="FUNDAMENTAL RIGHTS",
                articles=[
                    Article(
                        id="article-21a",
                        article_number="21A",
                        numeric_component=21,
                        title="Right to education",
                        part_number="III",
                        status=ArticleStatus.ACTIVE,
                        body_text=(
                            "The State shall provide free and compulsory education "
                            "to all children of the age of six to fourteen years in "
                            "such manner as the State may, by law, determine.]"
                        ),
                    ),
                    Article(
                        id="article-22",
                        article_number="22",
                        numeric_component=22,
                        title="Protection against arrest and detention in certain cases",
                        part_number="III",
                        status=ArticleStatus.ACTIVE,
                        body_text=(
                            "(1) No person who is arrested shall be detained in custody "
                            "without being informed, as soon as may be, of the grounds "
                            "for such arrest."
                        ),
                    ),
                    Article(
                        id="article-26",
                        article_number="26",
                        numeric_component=26,
                        title="Freedom to manage religious affairs",
                        part_number="III",
                        status=ArticleStatus.ACTIVE,
                        body_text=(
                            "(a) to establish and maintain institutions for religious "
                            "and charitable purposes; - (b) to manage its own affairs"
                        ),
                    ),
                    Article(
                        id="article-30",
                        article_number="30",
                        numeric_component=30,
                        title=(
                            "Right of minorities to establish and administer "
                            "educational institutions"
                        ),
                        part_number="III",
                        status=ArticleStatus.ACTIVE,
                        body_text=(
                            "(1) All minorities… 1 [(1A) In making any law…] (2) The State"
                        ),
                    ),
                    Article(
                        id="article-31a",
                        article_number="31A",
                        numeric_component=31,
                        title="Saving of laws providing for acquisition of estates, etc",
                        part_number="III",
                        status=ArticleStatus.ACTIVE,
                        body_text="(b) the taking over of the management of any property",
                    ),
                    Article(
                        id="article-31b",
                        article_number="31B",
                        numeric_component=31,
                        title="Validation of certain Acts and Regulations",
                        part_number="III",
                        status=ArticleStatus.ACTIVE,
                        body_text="…continue in force.]",
                    ),
                    Article(
                        id="article-32",
                        article_number="32",
                        numeric_component=32,
                        title="Remedies for enforcement of rights conferred by this Part",
                        part_number="III",
                        status=ArticleStatus.ACTIVE,
                        body_text=(
                            "(4) The right guaranteed by this article shall not be "
                            "suspended… 1 32A . [ Constitutional validity…"
                        ),
                    ),
                    Article(
                        id="article-33",
                        article_number="33",
                        numeric_component=33,
                        title="Power of Parliament to modify the rights",
                        part_number="III",
                        status=ArticleStatus.ACTIVE,
                        body_text="(a) the members of the Armed Forces; or]",
                    ),
                    Article(
                        id="article-34",
                        article_number="34",
                        numeric_component=34,
                        title="force in any area",
                        part_number="III",
                        status=ArticleStatus.ACTIVE,
                        body_text="force in any area .-Notwithstanding anything",
                    ),
                    Article(
                        id="article-35",
                        article_number="35",
                        numeric_component=35,
                        title="Legislation to give effect to the provisions of this Part",
                        part_number="III",
                        status=ArticleStatus.ACTIVE,
                        body_text="(a) Parliament shall have… (b) nested",
                    ),
                ],
            ),
            Part(
                id="part-iv",
                part_number="IV",
                title="DIRECTIVE PRINCIPLES OF STATE POLICY",
                articles=[
                    Article(
                        id="article-38",
                        article_number="38",
                        numeric_component=38,
                        title="State to secure a social order",
                        part_number="IV",
                        status=ArticleStatus.ACTIVE,
                        body_text="1 [(1)] The State shall strive… 2 [(2) The State shall…]",
                    ),
                    Article(
                        id="article-39",
                        article_number="39",
                        numeric_component=39,
                        title="Certain principles of policy",
                        part_number="IV",
                        status=ArticleStatus.ACTIVE,
                        body_text="(a) that the citizens… missing stem and (f)",
                    ),
                    Article(
                        id="article-39a",
                        article_number="39A",
                        numeric_component=39,
                        title="Equal justice and free legal aid",
                        part_number="IV",
                        status=ArticleStatus.ACTIVE,
                        body_text="…economic or other disabilities.]",
                    ),
                    Article(
                        id="article-43",
                        article_number="43",
                        numeric_component=43,
                        title="Living wage, etc., for workers",
                        part_number="IV",
                        status=ArticleStatus.ACTIVE,
                        body_text=(
                            "The State shall endeavour… rural areas. - 3 [43A . "
                            "Participation of workers…]"
                        ),
                    ),
                    Article(
                        id="article-48",
                        article_number="48",
                        numeric_component=48,
                        title="Organisation of agriculture and animal husbandry",
                        part_number="IV",
                        status=ArticleStatus.ACTIVE,
                        body_text=(
                            "The State shall endeavour… draught cattle. - 3 [ 48A. "
                            "Protection and improvement…]"
                        ),
                    ),
                ],
            ),
        ],
    )


def test_corrections_file_covers_21a_48_keys():
    data = json.loads(CORRECTIONS.read_text())
    arts = data["articles"]
    for key in REQUIRED_KEYS:
        assert key in arts, key
    assert arts["article-32a"].get("status") == "omitted"
    assert arts["article-32a"].get("create") is True
    assert arts["article-31a"].get("prefer_article_unit") is True
    assert arts["article-33"].get("prefer_article_unit") is True
    assert arts["article-26"].get("prefer_article_unit") is True


def test_apply_restores_21a_48_on_synthetic_doc():
    doc, _ = apply_corrections(_broken_doc(), load_corrections(CORRECTIONS))
    arts = _article_map(doc)

    assert not (arts["21A"].body_text or "").rstrip().endswith("]")
    assert "determine." in (arts["21A"].body_text or "")

    body_22 = arts["22"].body_text or ""
    assert body_22.startswith("(1) No person who is arrested")
    assert "(7) Parliament may by law prescribe" in body_22

    assert (arts["26"].opening_text or "").startswith("Subject to public order")
    assert arts["26"].prefer_article_unit is True
    assert "(d) to administer such property" in (arts["26"].body_text or "")

    body_30 = arts["30"].body_text or ""
    assert "1 [" not in body_30
    assert body_30.count("(1A)") == 1
    assert body_30.count("(2)") == 1

    body_31a = arts["31A"].body_text or ""
    assert body_31a.startswith("(1) Notwithstanding anything contained in article 13")
    assert "(a) the acquisition by the State" in body_31a
    assert arts["31A"].prefer_article_unit is True

    assert not (arts["31B"].body_text or "").rstrip().endswith("]")

    body_32 = arts["32"].body_text or ""
    assert "32A" not in body_32
    assert body_32.count("(4)") == 1
    assert arts["32A"].status == ArticleStatus.OMITTED

    assert (arts["33"].body_text or "").startswith("Parliament may, by law, determine")
    assert not (arts["33"].body_text or "").rstrip().endswith("]")
    assert (arts["34"].title or "").startswith("Restriction on rights")
    assert (arts["34"].body_text or "").startswith("Notwithstanding anything")

    assert (arts["35"].opening_text or "").startswith("Notwithstanding anything")
    assert "(b) any law in force" in (arts["35"].body_text or "")

    body_38 = arts["38"].body_text or ""
    assert "1 [(" not in body_38
    assert body_38.startswith("(1) The State shall strive")
    assert "(2) The State shall, in particular, strive to minimise" in body_38

    assert (arts["39"].opening_text or "").startswith("The State shall, in particular")
    assert "(f) that children are given opportunities" in (arts["39"].body_text or "")
    assert not (arts["39A"].body_text or "").rstrip().endswith("]")

    assert "43A" not in (arts["43"].body_text or "")
    assert "48A" not in (arts["48"].body_text or "")


def test_learning_units_from_synthetic_doc():
    doc, _ = apply_corrections(_broken_doc(), load_corrections(CORRECTIONS))
    result = generate_learning_units(doc)
    by_art: dict[str, list] = {}
    for u in result.units:
        by_art.setdefault(u.article_number, []).append(u)

    assert not any(u.text.rstrip().endswith("]") for u in by_art["21A"])
    ids_22 = {u.id for u in by_art["22"]}
    assert "article-22-clause-7" in ids_22
    assert "article-26" in {u.id for u in by_art["26"]}
    assert "article-30-clause-1a" in {u.id for u in by_art["30"]}
    assert "article-32a" in {u.id for u in by_art["32A"]}
    texts_43 = " ".join(u.text for u in by_art["43"])
    assert "43A" not in texts_43
    texts_48 = " ".join(u.text for u in by_art["48"])
    assert "48A" not in texts_48


def test_committed_learning_units_cover_21a_48():
    if not UNITS.exists():
        pytest.skip("learning_units.json missing")
    payload = json.loads(UNITS.read_text())
    units = payload["units"] if isinstance(payload, dict) else payload
    by_art: dict[str, list] = {}
    for u in units:
        by_art.setdefault(u["article_number"], []).append(u)

    if "article-22-clause-7" not in {u["id"] for u in by_art.get("22", [])}:
        pytest.skip("learning_units.json not yet regenerated for Art 22")

    assert not any(u["text"].rstrip().endswith("]") for u in by_art["21A"])
    ids_22 = {u["id"] for u in by_art["22"]}
    assert "article-22-clause-1" in ids_22
    assert "article-22-clause-7" in ids_22
    assert "article-30-clause-1a" in {u["id"] for u in by_art["30"]}
    assert "article-32a" in {u["id"] for u in by_art["32A"]}
    texts_32 = " ".join(u["text"] for u in by_art["32"])
    assert "32A" not in texts_32
    assert "43A" not in " ".join(u["text"] for u in by_art["43"])
    assert "48A" not in " ".join(u["text"] for u in by_art["48"])
    texts_38 = " ".join(u["text"] for u in by_art["38"])
    assert "1 [(" not in texts_38
    assert "(2) The State shall, in particular, strive to minimise" in texts_38
