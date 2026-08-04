"""Arts 264–280 Bare Act correction overlays."""

from __future__ import annotations

from pathlib import Path

import pytest

from constitution_memorizer.corrections.apply_corrections import load_corrections

ROOT = Path(__file__).resolve().parents[1]
CORRECTIONS = ROOT / "data" / "corrections" / "corrections.json"
UNITS = ROOT / "data" / "output" / "learning_units.json"


def _units():
    import json

    if not UNITS.exists():
        pytest.skip("learning_units.json not generated")
    data = json.loads(UNITS.read_text())
    return {u["id"]: u for u in data["units"]}


def test_overlays_264_280_present():
    corr = load_corrections(CORRECTIONS)
    for key in (
        "article-264",
        "article-267",
        "article-268",
        "article-268a",
        "article-269",
        "article-269a",
        "article-270",
        "article-271",
        "article-272",
        "article-273",
        "article-275",
        "article-276",
        "article-278",
        "article-280",
    ):
        assert key in corr.articles, key


def test_articles_264_280_learning_units():
    units = _units()

    assert units["article-264"]["text"].strip().endswith("article 280.")
    assert "]" not in units["article-264"]["text"]

    assert "Subs. by the Constitution" not in units["article-267-clause-1"]["text"]
    assert "Distribution of Revenues" not in units["article-267-clause-2"]["text"]
    assert "***" not in units["article-267-clause-2"]["text"]

    assert "(a)" in units["article-268-clause-1"]["text"]
    assert "268A" not in units["article-268-clause-1"]["text"]
    assert "268A" not in units.get("article-268-clause-2", {"text": ""}).get("text", "")
    assert units["article-268a"]["text"].strip() == "[Omitted.]"

    assert units["article-269-clause-1"]["text"].startswith("(1)")
    assert "269A." not in units["article-269-clause-1"]["text"]
    assert "except as provided in article 269A" in units["article-269-clause-1"]["text"]
    assert "article-269a-clause-1" in units
    assert "article-270-clause-1" in units
    assert "(1A)" in units["article-270-clause-1a"]["text"]

    assert "272." not in units["article-271"]["text"]
    assert "1 [" not in units["article-271"]["text"]
    assert units["article-272"]["text"].strip() == "[Omitted.]"

    assert "article 270" in units["article-273-clause-3"]["text"]
    assert "Odisha" in units["article-273-clause-1"]["text"]
    assert "2 [" not in units["article-273-clause-1"]["text"]

    assert "Provided that after a Finance Commission" in units["article-275-clause-2"]["text"]
    assert "(i)" in units["article-275-clause-1a"]["text"]
    assert "(ii)" in units["article-275-clause-1a"]["text"]

    assert "two thousand and five hundred" in units["article-276-clause-2"]["text"]
    assert "article-276-clause-3" in units

    assert units["article-278"]["text"].strip() == "[Omitted.]"

    clause3 = units["article-280-clause-3"]["text"]
    assert "(bb)" in clause3
    assert "(c)" in clause3
    assert "(d)" in clause3
    assert "3 [(" not in clause3
