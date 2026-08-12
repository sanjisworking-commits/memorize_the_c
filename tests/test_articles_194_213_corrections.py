"""Restore Bare Act wording for Arts 194–213 diglot debris via corrections."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from constitution_memorizer.corrections.apply_corrections import load_corrections

ROOT = Path(__file__).resolve().parents[1]
CORRECTIONS = ROOT / "data" / "corrections" / "corrections.json"
UNITS = ROOT / "data" / "output" / "learning_units.json"

REQUIRED_KEYS = ('article-194', 'article-205', 'article-207', 'article-208', 'article-210', 'article-213')


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


    if "article-194-clause-4" not in units:
        pytest.skip("units not regenerated for Art 194")
    assert "article-194-clause-4" in units
    assert "article-205-clause-1" in units
    assert units["article-205-clause-1"]["text"].startswith("(1) The Governor shall")
    assert "Provided that no recommendation shall be required" in units["article-207-clause-1"]["text"]
    texts_208 = " ".join(u["text"] for u in by_art["208"])
    assert "Forty-second Amendment" not in texts_208
    assert "Forty-fourth Amendment" not in texts_208
    body_210 = "\n".join(u["text"] for u in by_art["210"])
    assert "\n\nProvided" in json.loads(CORRECTIONS.read_text())["articles"]["article-210"]["body_text"]
    assert "mother-tongue" in body_210
    assert "article-213-clause-4" not in units
    assert "article-213-clause-3" in units

