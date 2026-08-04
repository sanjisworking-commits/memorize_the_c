"""Restore Bare Act wording for Arts 214–224A diglot / NJAC debris via corrections."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from constitution_memorizer.corrections.apply_corrections import load_corrections

ROOT = Path(__file__).resolve().parents[1]
CORRECTIONS = ROOT / "data" / "corrections" / "corrections.json"
UNITS = ROOT / "data" / "output" / "learning_units.json"

REQUIRED_KEYS = ('article-214', 'article-216', 'article-217', 'article-219', 'article-220', 'article-221', 'article-222', 'article-224a')


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


    if "article-214" not in units:
        pytest.skip("units not regenerated for Art 214")
    assert units["article-214"]["text"].strip() == "There shall be a High Court for each State."
    assert "*" not in units["article-216"]["text"]
    t217 = units["article-217-clause-1"]["text"]
    assert "National Judicial Appointments Commission" not in t217
    assert "Chief Justice of India" in t217
    texts_219 = " ".join(u["text"] for u in by_art["219"])
    assert "220." not in texts_219
    assert "***" not in texts_219
    assert "article-220" in units
    assert "article-221-clause-2" in units
    assert "1 [" not in units["article-221-clause-1"]["text"]
    assert "National Judicial Appointments Commission" not in units["article-222-clause-1"]["text"]
    assert "article-222-clause-2" in units
    assert "National Judicial Appointments Commission" not in units["article-224a"]["text"]
    assert "Chief Justice of a High Court" in units["article-224a"]["text"]

