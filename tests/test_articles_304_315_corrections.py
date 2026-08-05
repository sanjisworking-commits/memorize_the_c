"""Arts 304–315 Bare Act correction overlays."""

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


def test_overlays_304_315_present():
    corr = load_corrections(CORRECTIONS)
    for key in (
        "article-304",
        "article-305",
        "article-306",
        "article-308",
        "article-309",
        "article-310",
        "article-311",
        "article-312",
        "article-312a",
        "article-314",
        "article-315",
    ):
        assert key in corr.articles, key
    assert corr.articles["article-304"].prefer_article_unit is True
    assert corr.articles["article-304"].enable_letter_split is True
    assert corr.articles["article-305"].create is True
    assert corr.articles["article-312a"].create is True


def test_articles_304_315_learning_units():
    units = _units()

    assert units["article-304"].get("allows_letter_split")
    assert units["article-304"]["text"].startswith("Notwithstanding anything in article 301")
    assert "previous sanction of the President" in units["article-304"]["text"]
    assert "1 [" not in units["article-304"]["text"]
    assert "or the Union territories" in units["article-304"]["text"]
    assert "article-304-subclause-a" in units
    assert "article-304-subclause-b" in units

    assert "article-305" in units
    assert "State monopolies" not in units["article-305"]["text"]  # title not body
    assert "existing law" in units["article-305"]["text"]

    assert units["article-306"]["text"].strip() == "[Omitted.]"
    assert "1 [" not in units["article-308"]["text"]
    assert "Jammu and Kashmir" in units["article-308"]["text"]

    assert "\n\nProvided that" in units["article-309"]["text"]
    assert "***" not in units["article-309"]["text"]
    assert "***" not in units["article-310-clause-1"]["text"]
    assert "***" not in units["article-310-clause-2"]["text"]

    assert "article-311-clause-2" in units
    assert units["article-311-clause-1"]["text"].startswith("(1)")
    assert "(2)" not in units["article-311-clause-1"]["text"]
    assert "\n\nProvided that" in units["article-311-clause-2"]["text"]
    assert "article-311-clause-2-subclause-c" in units
    assert "shall not apply-]" not in units["article-311-clause-2"]["text"]
    assert "shall not apply-]" not in units["article-311-clause-3"]["text"]
    assert not units["article-311-clause-3"]["text"].rstrip().endswith("]")

    clause1_ids = [uid for uid in units if uid == "article-312-clause-1"]
    assert len(clause1_ids) == 1
    assert "Council of States" in units["article-312-clause-1"]["text"]
    assert "vary or revoke" not in units["article-312-clause-1"]["text"].lower()
    assert "1 [" not in units["article-312-clause-1"]["text"]
    assert units["article-312-clause-2"]["text"].startswith("(2)")
    assert "(3)" not in units["article-312-clause-2"]["text"]
    assert units["article-312-clause-3"]["text"].startswith("(3)")
    assert "312A" not in units["article-312-clause-4"]["text"]

    assert "article-312a-clause-1" in units
    assert "vary or revoke" in units["article-312a-clause-1"]["text"].lower()
    assert "article-312a-clause-1-subclause-a" in units
    assert "article-312a-clause-1-subclause-b" in units
    assert "article-312a-clause-4" in units

    assert units["article-314"]["text"].strip() == "[Omitted.]"
    assert "***" not in units["article-315-clause-4"]["text"]
