"""Restore Bare Act wording for Arts 249–263 diglot / Learn shape via corrections."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from constitution_memorizer.corrections.apply_corrections import load_corrections

ROOT = Path(__file__).resolve().parents[1]
CORRECTIONS = ROOT / "data" / "corrections" / "corrections.json"
UNITS = ROOT / "data" / "output" / "learning_units.json"

REQUIRED_KEYS = ('article-249', 'article-250', 'article-254', 'article-255', 'article-256', 'article-257', 'article-257a', 'article-258', 'article-258a', 'article-259', 'article-263')


def test_corrections_file_covers_keys():
    data = json.loads(CORRECTIONS.read_text())
    arts = data["articles"]
    for key in REQUIRED_KEYS:
        assert key in arts, key
    # touch loader for schema validity
    load_corrections(CORRECTIONS)


def test_committed_learning_units():
    if not UNITS.exists():
        pytest.skip("learning_units.json missing")
    payload = json.loads(UNITS.read_text())
    units = {u["id"]: u for u in payload["units"]}
    by_art: dict[str, list] = {}
    for u in payload["units"]:
        by_art.setdefault(str(u["article_number"]), []).append(u)


    if "article-258a" not in units:
        pytest.skip("units not regenerated for Art 258A")
    assert "1 [" not in units["article-249-clause-1"]["text"]
    assert "2 [" not in units["article-249-clause-1"]["text"]
    assert "goods and services tax provided under article 246A or" in units["article-249-clause-1"]["text"]
    assert "1 [" not in units["article-250-clause-1"]["text"]
    assert "***" not in units["article-254-clause-2"]["text"]
    assert "Provided that nothing in this clause shall prevent Parliament" in units["article-254-clause-2"]["text"]
    assert units["article-255"]["allows_letter_split"]
    assert units["article-255"]["text"].startswith("No Act of Parliament")
    assert units["article-256"]["text"].rstrip().endswith("purpose.")
    assert "257A" not in units["article-257-clause-4"]["text"]
    assert units["article-257a"]["text"].strip() == "[Omitted.]"
    assert "258A" not in units["article-258-clause-3"]["text"]
    assert "259." not in units["article-258-clause-3"]["text"]
    assert "article-258a" in units
    assert units["article-259"]["text"].strip() == "[Omitted.]"
    assert units["article-263"]["allows_letter_split"]
    assert "article-263-subclause-a" in units
    assert units["article-263"]["text"].startswith("If at any time it appears to the President")

