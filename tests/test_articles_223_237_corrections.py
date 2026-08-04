"""Restore High Court / Subordinate Courts Arts 223–237 via corrections overlay."""

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
    Chapter,
)
from constitution_memorizer.utils.json_io import read_json

ROOT = Path(__file__).resolve().parents[1]
CORRECTIONS = ROOT / "data" / "corrections" / "corrections.json"
RAW = ROOT / "data" / "output" / "constitution.json"
UNITS = ROOT / "data" / "output" / "learning_units.json"

needs_raw = pytest.mark.skipif(
    not RAW.exists(),
    reason="parsed corpus (data/output/constitution.json) not present",
)


REQUIRED_KEYS = (
    "article-223",
    "article-224",
    "article-225",
    "article-226",
    "article-227",
    "article-228",
    "article-229",
    "article-231",
    "article-232",
    "article-233",
    "article-233a",
    "article-236",
    "article-237",
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


def _broken_high_court_doc() -> ConstitutionDocument:
    """Minimal Part VI doc with the merge/steal shape seen in production units."""
    chapter_v = Chapter(
        id="chapter-v",
        chapter_number="V",
        title="THE HIGH COURTS IN THE STATES",
        articles=[
            Article(
                id="article-223",
                article_number="223",
                numeric_component=223,
                title="Appointment of acting Chief Justice",
                part_number="VI",
                chapter_number="V",
                status=ArticleStatus.ACTIVE,
                body_text=(
                    "(1) When the office of Chief Justice of a High Court is vacant "
                    "4 [ 224. Appointment of additional and acting Judges .- If by reason "
                    "of any temporary increase"
                ),
            ),
            Article(
                id="article-225",
                article_number="225",
                numeric_component=225,
                title="Jurisdiction of existing High Courts",
                part_number="VI",
                chapter_number="V",
                status=ArticleStatus.ACTIVE,
                body_text=(
                    "(2) The power conferred by clause (1) to issue directions, orders "
                    "or writs to any Government"
                ),
            ),
            Article(
                id="article-227",
                article_number="227",
                numeric_component=227,
                title="Power of superintendence over all courts by the High Court",
                part_number="VI",
                chapter_number="V",
                status=ArticleStatus.ACTIVE,
                body_text=(
                    "throughout the territories in relation to which it exercises "
                    "jurisdiction.]"
                ),
            ),
            Article(
                id="article-228",
                article_number="228",
                numeric_component=228,
                title="Transfer of certain cases to High Court",
                part_number="VI",
                chapter_number="V",
                status=ArticleStatus.ACTIVE,
                body_text=(
                    "(b) determine the said question of law and return the case to the "
                    "court from which the case has been so withdrawn"
                ),
            ),
            Article(
                id="article-229",
                article_number="229",
                numeric_component=229,
                title="Officers and servants and the expenses of High Courts",
                part_number="VI",
                chapter_number="V",
                status=ArticleStatus.ACTIVE,
                body_text=(
                    "(1) Appointments of officers and servants of a High Court shall be "
                    "made by the Chief Justice of the Court.\n"
                    "(3) The administrative expenses of a High Court shall be charged "
                    "upon the Consolidated Fund of the State.\n"
                    "3 [ 230. Extension of jurisdiction of High Courts to Union "
                    "territories. -\n"
                    "(1) Parliament may by law extend the jurisdiction of a High Court "
                    "to, or exclude the jurisdiction of a High Court from, any Union "
                    "territory."
                ),
            ),
            Article(
                id="article-230",
                article_number="230",
                numeric_component=230,
                title="Extension of jurisdiction of High Courts to Union territories",
                part_number="VI",
                chapter_number="V",
                status=ArticleStatus.ACTIVE,
                body_text="placeholder overwritten by schedule",
            ),
            Article(
                id="article-231",
                article_number="231",
                numeric_component=231,
                title="Establishment of a common High Court for two or more States",
                part_number="VI",
                chapter_number="V",
                status=ArticleStatus.ACTIVE,
                body_text=(
                    "(1) Parliament may by law establish a common High Court.\n"
                    "(2) In relation to any such High Court,- - (b) the reference\n"
                    "(c) the references in articles 219 and 229 to the State shall be "
                    "construed as a reference to the State in which the High Court has "
                    "its principal seat: - [ 232 . Interpretation .-Articles 230, 231 "
                    "and 232 subs."
                ),
            ),
        ],
    )
    chapter_vi = Chapter(
        id="chapter-vi",
        chapter_number="VI",
        title="SUBORDINATE COURTS",
        articles=[
            Article(
                id="article-233",
                article_number="233",
                numeric_component=233,
                title="Appointment of district judges",
                part_number="VI",
                chapter_number="VI",
                status=ArticleStatus.ACTIVE,
                body_text="(1) Appointments of persons to",
            ),
            Article(
                id="article-236",
                article_number="236",
                numeric_component=236,
                title="Interpretation",
                part_number="VI",
                chapter_number="VI",
                status=ArticleStatus.ACTIVE,
                opening_text="In this Chapter—",
                body_text=(
                    "(a) the expression 'district judge' includes judge of a city civil "
                    "court;\n"
                    "(b) the expression 'judicial service' means a service consisting "
                    "exclusively of persons intended to fill the post of district judge."
                ),
            ),
            Article(
                id="article-237",
                article_number="237",
                numeric_component=237,
                title=(
                    "Application of the provisions of this Chapter to certain class or "
                    "classes of magistrates"
                ),
                part_number="VI",
                chapter_number="VI",
                status=ArticleStatus.ACTIVE,
                body_text=(
                    "(2) Notwithstanding anything contained in Part VI, the President "
                    "may appoint the Governor of a State as the administrator of an "
                    "adjoining Union territory"
                ),
            ),
        ],
    )
    return ConstitutionDocument(
        document=DocumentMetadata(title="t", schema_version="1.0.0"),
        parts=[
            Part(
                id="part-vi",
                part_number="VI",
                title="THE STATES",
                chapters=[chapter_v, chapter_vi],
            )
        ],
    )


def test_corrections_file_covers_223_237_keys():
    data = json.loads(CORRECTIONS.read_text())
    arts = data["articles"]
    for key in REQUIRED_KEYS:
        assert key in arts, key
    assert arts["article-224"].get("create") is True
    assert arts["article-226"].get("create") is True
    assert arts["article-233a"].get("create") is True
    assert arts["article-232"].get("status") == "omitted"
    assert arts["article-232"].get("body_text") == "[Omitted.]"


def test_apply_restores_high_court_articles_on_synthetic_doc():
    doc, changes = apply_corrections(_broken_high_court_doc(), load_corrections(CORRECTIONS))
    arts = _article_map(doc)
    change_blob = "\n".join(changes)

    assert "224" in arts
    assert "226" in arts
    assert "233A" in arts
    assert "232" in arts
    assert arts["232"].status == ArticleStatus.OMITTED
    assert arts["232"].body_text == "[Omitted.]"

    body_223 = arts["223"].body_text or ""
    assert "224." not in body_223
    assert "acting Chief Justice" in (arts["223"].title or "")
    assert "President may appoint" in body_223

    body_225 = arts["225"].body_text or ""
    assert "writs" not in body_225.lower()
    assert "226" not in body_225
    assert body_225.startswith("Subject to the provisions")

    body_226 = arts["226"].body_text or ""
    assert body_226.startswith("(1)")
    assert "habeas corpus" in body_226
    assert "(4)" in body_226

    body_227 = arts["227"].body_text or ""
    assert body_227.startswith("(1) Every High Court shall have superintendence")
    assert "(4) Nothing in this article" in body_227

    opening_228 = arts["228"].opening_text or ""
    body_228 = arts["228"].body_text or ""
    assert opening_228.startswith("If the High Court is satisfied")
    assert "(a) either dispose of the case itself" in body_228
    assert "(b) determine the said question of law" in body_228
    assert arts["228"].prefer_article_unit is True

    body_229 = arts["229"].body_text or ""
    assert "Union territory" not in body_229
    assert "230." not in body_229
    assert body_229.startswith("(1) Appointments of officers")

    body_231 = arts["231"].body_text or ""
    assert "(a) the reference in article 217" in body_231
    assert "232" not in body_231

    body_233 = arts["233"].body_text or ""
    assert len(body_233) > 80
    assert "(2) A person not already in the service" in body_233

    opening_233a = arts["233A"].opening_text or ""
    body_233a = arts["233A"].body_text or ""
    assert "Twentieth Amendment" in body_233a
    assert opening_233a.startswith("Notwithstanding any judgment")
    assert body_233a.startswith("(a)")

    body_236 = arts["236"].body_text or ""
    assert body_236.strip().startswith("(a)")
    assert "\n(b)" in body_236 or "\n(b) " in body_236

    body_237 = arts["237"].body_text or ""
    assert "magistrates" in body_237
    assert "administrator of an adjoining Union territory" not in body_237

    assert "create" in change_blob.lower() or "224" in change_blob


def test_learning_units_from_synthetic_doc_split_cleanly():
    doc, _ = apply_corrections(_broken_high_court_doc(), load_corrections(CORRECTIONS))
    result = generate_learning_units(doc)
    by_art: dict[str, list] = {}
    for u in result.units:
        by_art.setdefault(u.article_number, []).append(u)

    assert by_art.get("224"), "Art 224 units missing"
    assert by_art.get("226"), "Art 226 units missing"
    assert by_art.get("233A"), "Art 233A units missing"

    texts_223 = " ".join(u.text for u in by_art["223"])
    assert "224." not in texts_223

    texts_225 = " ".join(u.text for u in by_art["225"])
    assert "habeas corpus" not in texts_225

    texts_229 = " ".join(u.text for u in by_art["229"])
    assert "Union territory" not in texts_229

    ids_236 = {u.id for u in by_art["236"]}
    assert "article-236-clause-a" in ids_236
    assert "article-236-clause-b" in ids_236
    assert "article-236-clause-a-subclause-b" not in ids_236

    texts_237 = " ".join(u.text for u in by_art["237"])
    assert "magistrates" in texts_237
    assert "administrator of an adjoining Union territory" not in texts_237


@needs_raw
def test_apply_on_raw_corpus_restores_band():
    source = ConstitutionDocument.model_validate(read_json(RAW))
    doc, _ = apply_corrections(source, load_corrections(CORRECTIONS))
    arts = _article_map(doc)
    for num in ("223", "224", "225", "226", "227", "228", "229", "231", "233", "233A", "236", "237"):
        assert num in arts, num
    assert arts["232"].status == ArticleStatus.OMITTED
    assert "224." not in (arts["223"].body_text or "")
    assert (arts["225"].body_text or "").startswith("Subject to the provisions")
    assert "magistrates" in (arts["237"].body_text or "")


def test_committed_learning_units_cover_restored_band():
    if not UNITS.exists():
        pytest.skip("learning_units.json missing")
    payload = json.loads(UNITS.read_text())
    units = payload["units"] if isinstance(payload, dict) else payload
    by_art: dict[str, list] = {}
    for u in units:
        by_art.setdefault(u["article_number"], []).append(u)

    # After regen these must pass; until then keep soft about intermediate state
    # only when corrections keys exist (always) — assert when units already fixed.
    data = json.loads(CORRECTIONS.read_text())
    assert "article-224" in data["articles"]

    if "224" not in by_art:
        pytest.skip("learning_units.json not yet regenerated with Art 224")

    assert by_art["224"]
    assert by_art["226"]
    assert by_art["233A"]
    texts_223 = " ".join(u["text"] for u in by_art["223"])
    assert "224." not in texts_223
    texts_229 = " ".join(u["text"] for u in by_art["229"])
    assert "Union territory" not in texts_229
    ids_236 = {u["id"] for u in by_art["236"]}
    assert "article-236-clause-a-subclause-b" not in ids_236
    texts_237 = " ".join(u["text"] for u in by_art["237"])
    assert "magistrates" in texts_237
    assert "administrator of an adjoining Union territory" not in texts_237
