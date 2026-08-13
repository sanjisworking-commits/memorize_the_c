"""Restore Bare Act wording for Arts 49 and 51 diglot / Learn shape."""

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
from constitution_memorizer.web.text_annotations import (
    annotations_for_unit,
    load_text_annotations,
)

ROOT = Path(__file__).resolve().parents[1]
CORRECTIONS = ROOT / "data" / "corrections" / "corrections.json"
UNITS = ROOT / "data" / "output" / "learning_units.json"
ANNOTATIONS = ROOT / "data" / "reference" / "text_annotations.json"


def test_corrections_file_covers_49_51():
    data = json.loads(CORRECTIONS.read_text())
    arts = data["articles"]
    assert "article-49" in arts
    assert "article-51" in arts
    body_49 = arts["article-49"]["body_text"]
    assert "1 [" not in body_49
    assert "declared by or under law made by Parliament" in body_49
    assert arts["article-51"].get("prefer_article_unit") is True
    assert arts["article-51"].get("enable_letter_split") is True
    assert (arts["article-51"].get("opening_text") or "").startswith(
        "The State shall endeavour to"
    )


def test_apply_restores_49_51_on_synthetic_doc():
    doc = ConstitutionDocument(
        document=DocumentMetadata(title="t", schema_version="1.0.0"),
        parts=[
            Part(
                id="part-iv",
                part_number="IV",
                title="DIRECTIVE PRINCIPLES OF STATE POLICY",
                articles=[
                    Article(
                        id="article-49",
                        article_number="49",
                        numeric_component=49,
                        title="Protection of monuments…",
                        part_number="IV",
                        status=ArticleStatus.ACTIVE,
                        body_text=(
                            "… 1 [declared by or under law made by Parliament] …"
                        ),
                    ),
                    Article(
                        id="article-51",
                        article_number="51",
                        numeric_component=51,
                        title="Promotion of international peace and security",
                        part_number="IV",
                        status=ArticleStatus.ACTIVE,
                        body_text="(a) promote… stem glued",
                    ),
                ],
            )
        ],
    )
    reviewed, _ = apply_corrections(doc, load_corrections(CORRECTIONS))
    by = {a.article_number: a for p in reviewed.parts for a in p.articles}
    assert "1 [" not in (by["49"].body_text or "")
    assert "declared by or under law made by Parliament" in (by["49"].body_text or "")
    assert by["51"].prefer_article_unit is True
    assert by["51"].enable_letter_split is True

    units = {u.id: u for u in generate_learning_units(reviewed).units}
    assert "article-51" in units
    assert "article-51-subclause-a" in units
    assert units["article-51"].text.startswith("The State shall endeavour to")
    assert not units["article-51-subclause-a"].text.startswith(
        "(a) The State shall endeavour"
    )


def test_committed_units_and_tip_for_49_51():
    if not UNITS.exists():
        pytest.skip("learning_units.json missing")
    payload = json.loads(UNITS.read_text())
    units = {u["id"]: u for u in payload["units"]}
    if "article-51-subclause-a" not in units:
        pytest.skip("units not regenerated for Art 51")

    assert "1 [" not in units["article-49"]["text"]
    assert "declared by or under law made by Parliament" in units["article-49"]["text"]
    assert units["article-51"]["allows_letter_split"] is True
    assert "article-51-subclause-d" in units

    catalog = load_text_annotations(ANNOTATIONS)
    tip = annotations_for_unit(catalog, "article-49")
    assert tip and tip[0].target == "declared by or under law made by Parliament"
