"""Arts 353–359 Bare Act correction overlays."""

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


def test_overlays_353_359_present():
    corr = load_corrections(CORRECTIONS)
    for key in (
        "article-353",
        "article-354",
        "article-356",
        "article-357",
        "article-358",
        "article-359",
    ):
        assert key in corr.articles, key

    assert corr.articles["article-353"].prefer_article_unit is True
    assert corr.articles["article-353"].enable_letter_split is True
    assert (corr.articles["article-353"].body_text or "").startswith(
        "While a Proclamation of Emergency"
    )

    body_354 = corr.articles["article-354"].body_text or ""
    assert body_354.lstrip().startswith("(1)")
    assert "\n(2) " in body_354
    assert not (corr.articles["article-354"].title or "").startswith(
        "Application of provisions"
    ) or ".(1)" not in (corr.articles["article-354"].title or "")

    body_356 = corr.articles["article-356"].body_text or ""
    assert body_356.lstrip().startswith("(1)")
    assert "\n(5) " in body_356
    assert "***" not in body_356
    assert (corr.articles["article-356"].title or "").endswith("in States")

    body_357 = corr.articles["article-357"].body_text or ""
    assert body_357.lstrip().startswith("(1)")
    assert "\n(2) " in body_357
    assert ".(1)" not in (corr.articles["article-357"].title or "")

    body_358 = corr.articles["article-358"].body_text or ""
    assert "\n\nProvided that where such Proclamation" in body_358

    body_359 = corr.articles["article-359"].body_text or ""
    assert "\n(1A) " in body_359
    assert "\n(1B) " in body_359
    assert "\n(2) " in body_359
    assert "\n(3) " in body_359
    assert "1 [" not in body_359
    assert not body_359.rstrip().endswith("]")


def test_articles_353_359_learning_units():
    units = _units()

    assert "article-353" in units
    assert units["article-353"]["text"].startswith(
        "While a Proclamation of Emergency is in operation"
    )
    assert units["article-353"].get("allows_letter_split") is True
    assert "article-353-subclause-a" in units or "article-353-clause-a" in units

    assert "article-354-clause-1" in units
    assert "article-354-clause-2" in units
    assert not units["article-354-clause-1"]["text"].startswith("Application of provisions")
    assert units["article-354-clause-1"]["text"].lstrip().startswith("(1)")
    assert units["article-354-clause-2"]["text"].lstrip().startswith("(2)")

    assert "article-356-clause-1" in units
    assert "article-356-clause-2" in units
    assert "article-356-clause-5" in units
    assert "***" not in units["article-356-clause-1"]["text"]
    assert units["article-356-clause-1"]["text"].lstrip().startswith("(1)")

    assert "article-357-clause-1" in units
    assert "article-357-clause-2" in units
    assert "it shall be competent" in units["article-357-clause-1"]["text"]
    assert not units["article-357-clause-1"]["text"].startswith(
        "Exercise of legislative powers"
    )

    c1 = units["article-358-clause-1"]["text"]
    assert "\n\nProvided that where such Proclamation" in c1 or "\nProvided that where such Proclamation" in c1
    idx_colon = c1.find("have effect:")
    idx_prov = c1.find("Provided that where such Proclamation")
    assert idx_colon != -1 and idx_prov != -1 and idx_prov > idx_colon
    assert c1[idx_colon + len("have effect:") : idx_prov].strip() == ""

    assert "article-359-clause-1" in units
    assert "article-359-clause-1a" in units
    assert "article-359-clause-1b" in units
    assert "article-359-clause-2" in units
    assert "article-359-clause-3" in units
    assert "1 [" not in units["article-359-clause-1"]["text"]
    assert "(1A)" not in units["article-359-clause-1"]["text"]
    assert units["article-359-clause-1a"]["text"].lstrip().startswith("(1A)")
    assert units["article-359-clause-3"]["text"].lstrip().startswith("(3)")
