"""Arts 338A–342 Bare Act correction overlays."""

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


def test_overlays_338a_342_present():
    corr = load_corrections(CORRECTIONS)
    for key in (
        "article-338a",
        "article-338b",
        "article-339",
        "article-341",
        "article-342",
    ):
        assert key in corr.articles, key
    assert corr.articles["article-338a"].create is True
    assert corr.articles["article-338b"].create is True


def test_articles_338a_342_learning_units():
    units = _units()

    assert "article-338a-clause-1" in units
    assert "Scheduled Tribes" in units["article-338a-clause-1"]["text"]
    assert "article-338a-clause-9" in units
    assert "article-338a-clause-5-subclause-a" in units

    assert "article-338b-clause-1" in units
    assert "Backward Classes" in units["article-338b-clause-1"]["text"]
    assert "article-338b-clause-9" in units
    assert "article 342A" in units["article-338b-clause-9"]["text"]

    assert "***" not in units["article-339-clause-1"]["text"]
    assert "3 [" not in units["article-339-clause-2"]["text"]
    assert "directions to a State" in units["article-339-clause-2"]["text"]

    assert "article-341-clause-1" in units
    assert "article-341-clause-2" in units
    assert not units["article-341-clause-1"]["text"].startswith("Scheduled Castes")
    assert "***" not in units["article-341-clause-1"]["text"]
    assert "1 [" not in units["article-341-clause-1"]["text"]
    assert "Union territory" in units["article-341-clause-1"]["text"]

    assert "article-342-clause-1" in units
    assert "article-342-clause-2" in units
    assert not units["article-342-clause-1"]["text"].rstrip().endswith("]")
    assert "***" not in units["article-342-clause-1"]["text"]
    assert "1 [" not in units["article-342-clause-1"]["text"]
