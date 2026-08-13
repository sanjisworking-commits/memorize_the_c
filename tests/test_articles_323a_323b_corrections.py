"""Arts 323A / 323B — restore missing clause (1) and letter formatting."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from constitution_memorizer.corrections.apply_corrections import load_corrections
from constitution_memorizer.learning.text_fallback_splitter import split_flat_article_body
from constitution_memorizer.schemas import LabelType

ROOT = Path(__file__).resolve().parents[1]
CORRECTIONS = ROOT / "data" / "corrections" / "corrections.json"
UNITS = ROOT / "data" / "output" / "learning_units.json"


def _units():
    if not UNITS.exists():
        pytest.skip("learning_units.json not generated")
    data = json.loads(UNITS.read_text())
    return {u["id"]: u for u in data["units"]}


def test_overlays_323a_323b_present():
    corr = load_corrections(CORRECTIONS)
    assert "article-323a" in corr.articles
    assert "article-323b" in corr.articles
    assert corr.articles["article-323a"].part_number == "XIVA"
    assert corr.articles["article-323b"].part_number == "XIVA"
    assert corr.articles["article-323a"].title == "Administrative tribunals"
    assert corr.articles["article-323b"].title == "Tribunals for other matters"


def test_articles_323a_323b_learning_units():
    units = _units()

    c1a = units["article-323a-clause-1"]["text"]
    assert c1a.startswith(
        "(1) Parliament may, by law, provide for the adjudication or trial "
        "by administrative tribunals"
    )
    assert "article-323a-clause-3" in units
    assert "article-323a-clause-2-subclause-c" in units
    assert "article-323a-clause-2-subclause-d" in units
    assert "1 [" not in units["article-323a-clause-2"]["text"]
    assert "***" not in units["article-323a-clause-2"]["text"]

    c1b = units["article-323b-clause-1"]["text"]
    assert c1b.startswith(
        "(1) The appropriate Legislature may, by law, provide for the "
        "adjudication or trial by tribunals"
    )
    assert "article-323b-clause-3" in units
    assert "article-323b-clause-4" in units
    assert "Explanation" in units["article-323b-clause-4"]["text"]

    clause2 = units["article-323b-clause-2"]["text"]
    assert "\n(h) rent" in clause2
    assert "\n(i) offences" in clause2
    assert "\n(j) any matter" in clause2
    assert "1 [" not in clause2
    assert "***" not in clause2

    assert "article-323b-clause-2-subclause-h" in units
    assert "article-323b-clause-2-subclause-i" in units
    assert "article-323b-clause-2-subclause-j" in units
    assert "(i)" not in units["article-323b-clause-2-subclause-h"]["text"]
    assert units["article-323b-clause-2-subclause-i"]["text"].startswith("(i) offences")

    children = units["article-323b-clause-2"]["child_unit_ids"]
    assert "article-323b-clause-2-subclause-i" in children

    assert units["part-xiva-overview"]["title"] == "TRIBUNALS"


def test_splitter_i_before_j_is_alphabetic():
    body = (
        "(2) The matters are the following, namely:—\n"
        "(h) rent and tenancy issues;\n"
        "(i) offences against laws with respect to sub-clauses (a) to (h);\n"
        "(j) any matter incidental to sub-clauses (a) to (i)."
    )
    roots = split_flat_article_body("323B", body)
    assert len(roots) == 1
    kids = {c.label: c for c in roots[0].children}
    assert kids["(i)"].label_type == LabelType.ALPHABETIC
    assert kids["(j)"].label_type == LabelType.ALPHABETIC
    assert not kids["(h)"].children


def test_splitter_i_before_ii_stays_roman():
    body = (
        "(b) he has been ordinarily resident in the territory of India—\n"
        "(i) for not less than five years; or\n"
        "(ii) permanently."
    )
    roots = split_flat_article_body("6", body)
    assert len(roots) == 1
    parent = roots[0]
    assert parent.label == "(b)"
    assert parent.label_type == LabelType.ALPHABETIC
    romans = [(c.label, c.label_type) for c in parent.children]
    assert ("(i)", LabelType.ROMAN) in romans
    assert ("(ii)", LabelType.ROMAN) in romans
