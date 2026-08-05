"""Arts 360–364 Bare Act correction overlays."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from constitution_memorizer.corrections.apply_corrections import load_corrections

ROOT = Path(__file__).resolve().parents[1]
CORRECTIONS = ROOT / "data" / "corrections" / "corrections.json"
UNITS = ROOT / "data" / "output" / "learning_units.json"


def _units():
    if not UNITS.exists():
        pytest.skip("learning_units.json not generated")
    data = json.loads(UNITS.read_text())
    return {u["id"]: u for u in data["units"]}


def test_overlays_360_364_present():
    corr = load_corrections(CORRECTIONS)
    for key in (
        "article-360",
        "article-361",
        "article-361a",
        "article-362",
        "article-363",
        "article-363a",
        "article-364",
    ):
        assert key in corr.articles, key

    assert corr.articles["article-360"].title == "Provisions as to financial emergency"
    body_360 = corr.articles["article-360"].body_text or ""
    assert body_360.lstrip().startswith("(1)")
    assert "\n(2) " in body_360
    assert "\n(3) " in body_360
    assert "\n(4) " in body_360
    assert "4 [" not in body_360

    assert corr.articles["article-361"].title == (
        "Protection of President and Governors and Rajpramukhs"
    )
    assert ".(1)" not in (corr.articles["article-361"].title or "")
    body_361 = corr.articles["article-361"].body_text or ""
    assert body_361.lstrip().startswith("(1)")
    assert "***" not in body_361
    assert "1 [" not in body_361

    assert corr.articles["article-361a"].create is True
    body_361a = corr.articles["article-361a"].body_text or ""
    assert body_361a.lstrip().startswith("(1)")
    assert "\n(2) " in body_361a
    assert "Explanation" in body_361a

    assert corr.articles["article-362"].status == "omitted"
    assert corr.articles["article-362"].body_text == "[Omitted.]"

    assert (corr.articles["article-363"].title or "").startswith("Bar to interference")
    body_363 = corr.articles["article-363"].body_text or ""
    assert body_363.lstrip().startswith("(1)")
    assert "363A" not in body_363
    assert "privy purse" not in body_363

    assert corr.articles["article-363a"].create is True
    assert "privy purse" in (corr.articles["article-363a"].body_text or "")

    assert corr.articles["article-364"].title == (
        "Special provisions as to major ports and aerodromes"
    )
    body_364 = corr.articles["article-364"].body_text or ""
    assert body_364.lstrip().startswith("(1)")
    assert "\n(2) " in body_364


def test_articles_360_364_learning_units():
    units = _units()

    assert "article-360-clause-1" in units
    assert "article-360-clause-2" in units
    assert "article-360-clause-3" in units
    assert "article-360-clause-4" in units
    assert units["article-360-clause-1"]["text"].lstrip().startswith("(1)")
    assert not units["article-360-clause-1"]["text"].startswith("Provisions as to")

    assert "article-361-clause-1" in units
    assert "article-361-clause-2" in units
    assert "article-361-clause-4" in units
    assert "***" not in units["article-361-clause-2"]["text"]
    assert units["article-361-clause-1"]["text"].lstrip().startswith("(1)")
    assert "Provided that the conduct of the President" in units["article-361-clause-1"]["text"]

    assert "article-361a-clause-1" in units
    assert "article-361a-clause-2" in units
    assert "newspaper" in units["article-361a-clause-1"]["text"]

    assert "article-362" in units
    assert units["article-362"]["text"].strip() == "[Omitted.]"

    assert "article-363-clause-1" in units
    assert "article-363-clause-2" in units
    assert "363A" not in units["article-363-clause-1"]["text"]
    assert "privy purse" not in units["article-363-clause-2"]["text"]

    assert "article-363a" in units or "article-363a-subclause-a" in units
    blob = " ".join(u["text"] for uid, u in units.items() if uid.startswith("article-363a"))
    assert "privy purse" in blob

    assert "article-364-clause-1" in units
    assert "article-364-clause-2" in units
    assert units["article-364-clause-1"]["text"].lstrip().startswith("(1)")
    assert "Notwithstanding anything in this Constitution" in units["article-364-clause-1"]["text"]
    assert not units["article-364-clause-1"]["text"].startswith("Special provisions")
