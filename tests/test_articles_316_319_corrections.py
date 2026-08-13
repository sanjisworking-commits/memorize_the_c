"""Arts 316–319 Bare Act correction overlays."""

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


def test_overlays_316_319_present():
    corr = load_corrections(CORRECTIONS)
    for key in ("article-316", "article-317", "article-318", "article-319"):
        assert key in corr.articles, key
    assert corr.articles["article-318"].prefer_article_unit is True
    assert corr.articles["article-318"].enable_letter_split is True
    assert corr.articles["article-319"].prefer_article_unit is True
    assert corr.articles["article-319"].enable_letter_split is True


def test_articles_316_319_learning_units():
    units = _units()

    assert units["article-316-clause-1"]["text"].startswith("(1)")
    assert "(1A)" not in units["article-316-clause-1"]["text"]
    assert not units["article-316-clause-1"]["text"].rstrip().endswith("]")
    assert "one-half of the members" in units["article-316-clause-1"]["text"]
    assert "article-316-clause-1a" in units
    assert units["article-316-clause-1a"]["text"].startswith("(1A)")
    assert "***" not in units["article-316-clause-2"]["text"]
    assert "2 [" not in units["article-316-clause-2"]["text"]
    assert "sixty-two years" in units["article-316-clause-2"]["text"]

    assert "article-317-clause-1" in units
    assert units["article-317-clause-1"]["text"].startswith("(1) Subject")
    assert "Commission .-(" not in units["article-317-clause-1"]["text"]
    assert "***" not in units["article-317-clause-2"]["text"]
    assert "article-317-clause-3-subclause-c" in units

    assert units["article-318"].get("allows_letter_split")
    assert units["article-318"]["text"].startswith("In the case of the Union Commission")
    assert "***" not in units["article-318"]["text"]
    assert "varied to his disadvantage" in units["article-318"]["text"]
    assert "article-318-subclause-a" in units
    assert "article-318-subclause-b" in units

    assert units["article-319"].get("allows_letter_split")
    assert units["article-319"]["text"].startswith("On ceasing to hold office")
    assert "article-319-subclause-a" in units
    assert "article-319-subclause-b" in units
    assert "article-319-subclause-c" in units
    assert "article-319-subclause-d" in units
