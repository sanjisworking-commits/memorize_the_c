"""Arts 334–338 Bare Act correction overlays."""

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


def test_overlays_334_338_present():
    corr = load_corrections(CORRECTIONS)
    for key in (
        "article-334",
        "article-334a",
        "article-335",
        "article-336",
        "article-337",
        "article-338",
    ):
        assert key in corr.articles, key
    assert corr.articles["article-334"].prefer_article_unit is True
    assert corr.articles["article-334"].enable_letter_split is True
    assert corr.articles["article-334"].title.startswith("Reservation of seats")


def test_articles_334_338_learning_units():
    units = _units()

    assert units["article-334"].get("allows_letter_split")
    assert units["article-334"]["text"].startswith(
        "Notwithstanding anything in the foregoing provisions of this Part"
    )
    assert "1 [" not in units["article-334"]["text"]
    assert "eighty years" in units["article-334"]["text"]
    assert "seventy years" in units["article-334"]["text"]
    assert "Provided that nothing in this article shall affect any representation" in units[
        "article-334"
    ]["text"]
    assert "article-334-subclause-a" in units
    assert "article-334-subclause-b" in units

    assert not units["article-334a-clause-4"]["text"].rstrip().endswith("]")

    assert "Provided that nothing in this article shall prevent" in units["article-335"][
        "text"
    ]
    assert "relaxation in qualifying marks" in units["article-335"]["text"]

    assert "Provided that at the end of ten years" in units["article-336-clause-1"][
        "text"
    ]
    assert "Provided that" not in units["article-336-clause-2"]["text"]

    assert "***" not in units["article-337"]["text"]
    assert "Anglo-Indian community" in units["article-337"]["text"]

    assert "article-338-clause-1" in units
    assert units["article-338-clause-1"]["text"].startswith(
        "(1) There shall be a Commission for the Scheduled Castes"
    )
    assert "1 [" not in units["article-338-clause-1"]["text"]
    assert "***" not in units["article-338-clause-5"]["text"]
    assert "article-338-clause-5-subclause-c" in units
    assert "article-338-clause-5-subclause-d" in units
    assert "article-338-clause-5-subclause-f" in units
    for n in range(6, 11):
        assert f"article-338-clause-{n}" in units, n
    assert "Anglo-Indian community" in units["article-338-clause-10"]["text"]
