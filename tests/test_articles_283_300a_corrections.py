"""Arts 283–300A Bare Act correction overlays."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from constitution_memorizer.corrections.apply_corrections import load_corrections

ROOT = Path(__file__).resolve().parents[1]
CORRECTIONS = ROOT / "data" / "corrections" / "corrections.json"
UNITS = ROOT / "data" / "output" / "learning_units.json"
ANNOTATIONS = ROOT / "data" / "reference" / "text_annotations.json"


def _units():
    if not UNITS.exists():
        pytest.skip("learning_units.json not generated")
    data = json.loads(UNITS.read_text())
    return {u["id"]: u for u in data["units"]}


def test_overlays_283_300a_present():
    corr = load_corrections(CORRECTIONS)
    for key in (
        "article-283",
        "article-284",
        "article-286",
        "article-287",
        "article-288",
        "article-290",
        "article-290a",
        "article-291",
        "article-294",
        "article-296",
        "article-297",
        "article-298",
        "article-299",
        "article-300",
        "article-300a",
    ):
        assert key in corr.articles, key
    assert corr.articles["article-284"].prefer_article_unit is True
    assert corr.articles["article-284"].enable_letter_split is True
    assert corr.articles["article-290"].prefer_article_unit is True
    assert corr.articles["article-294"].prefer_article_unit is True


def test_articles_283_300a_learning_units():
    units = _units()

    assert "***" not in units["article-283-clause-2"]["text"]
    assert units["article-284"].get("allows_letter_split")
    assert units["article-284"]["text"].startswith("All moneys received")
    assert "article-284-subclause-a" in units

    assert "article-286-clause-2" in units
    assert "1 [" not in units["article-286-clause-1"]["text"]

    assert units["article-287"].get("allows_letter_split")
    assert "railway" in units["article-287"]["text"]
    assert "substantial quantity of electricity" in units["article-287"]["text"]

    assert "Explanation" not in units["article-288-clause-1"]["text"]
    anns = json.loads(ANNOTATIONS.read_text())["units"]
    tip = anns["article-288-clause-1"][0]
    assert tip["target"] == "law of a State in force"
    assert "surfaces" not in tip  # Learn + Browse

    assert "290A" not in units["article-290"]["text"]
    assert units["article-290"].get("allows_letter_split")
    assert "Travancore Devaswom" in units["article-290a"]["text"]
    assert units["article-291"]["text"].strip() == "[Omitted.]"

    assert units["article-294"].get("allows_letter_split")
    assert "(a)" in units["article-295-clause-1"]["text"]

    assert "escheat" in units["article-296"]["text"].lower()
    assert "bona vacantia" in units["article-296"]["text"].lower()
    assert "exclusive economic" not in units["article-296"]["text"].lower()
    assert "297." not in units["article-296"]["text"]
    assert "298." not in units["article-296"]["text"]

    assert "article-297-clause-1" in units
    assert "territorial waters" in units["article-297-clause-1"]["text"]
    assert units["article-298"].get("allows_letter_split")
    assert "executive power of the Union" in units["article-298"]["text"]

    assert "***" not in units["article-299-clause-1"]["text"]
    assert "***" not in units["article-299-clause-2"]["text"]
    assert "article-300-clause-2-subclause-a" in units
    assert "article-300-clause-2-subclause-b" in units
    assert not units["article-300a"]["text"].rstrip().endswith("]")
