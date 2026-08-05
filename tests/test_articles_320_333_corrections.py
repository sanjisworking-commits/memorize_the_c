"""Arts 320–333 Bare Act correction overlays."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from constitution_memorizer.corrections.apply_corrections import load_corrections
from constitution_memorizer.web.text_annotations import (
    annotations_for_unit,
    load_text_annotations,
)

ROOT = Path(__file__).resolve().parents[1]
CORRECTIONS = ROOT / "data" / "corrections" / "corrections.json"
UNITS = ROOT / "data" / "output" / "learning_units.json"
ANNOTATIONS = ROOT / "data" / "reference" / "text_annotations.json"


def _units():
    if not UNITS.exists():
        pytest.skip("learning_units.json not generated")
    data = json.loads(UNITS.read_text())
    return {u["id"]: u for u in data["units"]}


def test_overlays_320_333_present():
    corr = load_corrections(CORRECTIONS)
    for key in (
        "article-320",
        "article-323",
        "article-323a",
        "article-323b",
        "article-329",
        "article-329a",
        "article-330",
        "article-332",
        "article-333",
    ):
        assert key in corr.articles, key
    assert corr.articles["article-329"].prefer_article_unit is True
    assert corr.articles["article-329a"].status == "omitted"
    assert corr.articles["article-323a"].part_number == "XIVA"
    assert corr.articles["article-323b"].part_number == "XIVA"


def test_articles_320_333_learning_units():
    units = _units()

    assert "shall be consulted" in units["article-320-clause-3"]["text"]
    assert "***" not in units["article-320-clause-3"]["text"]
    assert "article-320-clause-3-subclause-c" in units
    assert "article-320-clause-3-subclause-d" in units
    assert "article-320-clause-5" in units

    assert "***" not in units["article-323-clause-2"]["text"]

    assert "article-323a-clause-1" in units
    assert "article-323a-clause-3" in units
    assert "article-323a-clause-2-subclause-c" in units
    assert "article-323a-clause-2-subclause-d" in units

    assert "article-323b-clause-1" in units
    assert "article-323b-clause-3" in units
    clause2 = units["article-323b-clause-2"]["text"]
    assert "\n(h) rent" in clause2
    assert "\n(i) offences" in clause2
    assert "article-323b-clause-2-subclause-h" in units
    assert "1 [(" not in clause2

    assert units["article-329"].get("allows_letter_split")
    assert units["article-329"]["text"].startswith("Notwithstanding anything in this Constitution")
    assert units["article-329"]["text"].strip() != "]"
    assert units["article-329a"]["text"].strip() == "[Omitted.]"

    assert "article-330-clause-1-subclause-a" in units
    assert "article-330-clause-1-subclause-b" in units
    assert "article-330-clause-1-subclause-c" in units
    assert "1 [" not in units["article-330-clause-1"]["text"]
    assert "article-330-clause-3" in units
    assert "(3)" not in units["article-330-clause-2"]["text"]
    assert "Explanation" not in units["article-330-clause-2"]["text"]

    assert "1 [" not in units["article-332-clause-1"]["text"]
    assert "***" not in units["article-332-clause-1"]["text"]
    assert "article-332-clause-3a" in units
    assert "(3A)" not in units["article-332-clause-3"]["text"]
    assert "article-332-clause-3b" in units
    assert "article-332-clause-6" in units

    assert "***" not in units["article-333"]["text"]
    assert "3 [" not in units["article-333"]["text"]
    assert "nominate one member" in units["article-333"]["text"]


def test_article_323_and_330_tooltips():
    catalog = load_text_annotations(ANNOTATIONS)

    browse_323 = annotations_for_unit(catalog, "article-323-clause-2", surface="browse")
    assert browse_323 and browse_323[0].target == "Governor"
    assert browse_323[0].surfaces == ("browse",)
    assert annotations_for_unit(catalog, "article-323-clause-2", surface="learn") == []

    tip330 = annotations_for_unit(catalog, "article-330-clause-2", surface="learn")
    pop = [t for t in tip330 if t.target == "population"]
    assert pop and "last preceding census" in pop[0].note
    assert "2001" in pop[0].note
