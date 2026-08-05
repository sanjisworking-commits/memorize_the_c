"""Arts 348–352 Bare Act correction overlays."""

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


def test_overlays_348_352_present():
    corr = load_corrections(CORRECTIONS)
    for key in (
        "article-348",
        "article-350",
        "article-350a",
        "article-350b",
        "article-352",
    ):
        assert key in corr.articles, key
    assert corr.articles["article-350a"].create is True
    body_348 = corr.articles["article-348"].body_text or ""
    assert "shall be in the English language" in body_348
    assert "\n(3) " in body_348 or body_348.startswith("(3)") or "\n(3) Notwithstanding" in body_348
    assert "***" not in body_348
    body_350 = corr.articles["article-350"].body_text or ""
    assert "350A" not in body_350
    assert "mother-tongue" not in body_350
    body_350b = corr.articles["article-350b"].body_text or ""
    assert not body_350b.rstrip().endswith("]")
    body_352 = corr.articles["article-352"].body_text or ""
    assert "\nExplanation" in body_352
    assert "\n(2) " in body_352
    assert "\n(5) " in body_352
    assert "\n(9) " in body_352
    assert "1 [" not in body_352
    assert "Provided that if any such Proclamation" in body_352


def test_articles_348_352_learning_units():
    units = _units()

    assert "article-348-clause-1" in units
    assert "article-348-clause-1-subclause-b" in units
    assert "article-348-clause-1-subclause-b-subclause-i" in units or any(
        uid.startswith("article-348-clause-1-subclause-b") and "subclause-i" in uid
        for uid in units
    ) or "Bills to be introduced" in units["article-348-clause-1-subclause-b"]["text"]
    # (b) must not be truncated to stem only
    assert "authoritative texts" in units["article-348-clause-1-subclause-b"]["text"]
    assert "article-348-clause-2" in units
    assert "Provided that nothing in this clause" in units["article-348-clause-2"]["text"]
    assert "***" not in units["article-348-clause-2"]["text"]
    assert "article-348-clause-3" in units

    assert "article-350" in units
    assert "350A" not in units["article-350"]["text"]
    assert "mother-tongue" not in units["article-350"]["text"]

    assert "article-350a" in units
    assert "mother-tongue" in units["article-350a"]["text"]

    assert "article-350b-clause-1" in units
    assert "article-350b-clause-2" in units
    assert not units["article-350b-clause-2"]["text"].rstrip().endswith("]")

    assert "article-352-clause-1" in units
    c1 = units["article-352-clause-1"]["text"]
    assert "armed rebellion" in c1
    assert "1 [" not in c1
    assert "Explanation" in c1
    # Explanation starts on its own line within clause (1) card or as separate trailing text
    assert "\nExplanation" in c1 or c1.strip().startswith("Explanation")
    assert "(2)" not in c1.split("Explanation")[0] or c1.index("Explanation") < c1.find("(2)") if "(2)" in c1 else True
    # (2) must be its own unit, not glued only inside (1)
    assert "article-352-clause-2" in units
    assert units["article-352-clause-2"]["text"].lstrip().startswith("(2)")
    assert "article-352-clause-4" in units
    assert "Provided that if any such Proclamation" in units["article-352-clause-4"]["text"]
    for n in (5, 6, 7, 8, 9):
        assert f"article-352-clause-{n}" in units, n
    assert "armed rebellion" in units["article-352-clause-9"]["text"]
    assert "1 [" not in units["article-352-clause-9"]["text"]
