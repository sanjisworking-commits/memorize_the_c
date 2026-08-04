"""Restore Bare Act wording for Arts 233–243R diglot / missing stems via corrections."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from constitution_memorizer.corrections.apply_corrections import load_corrections

ROOT = Path(__file__).resolve().parents[1]
CORRECTIONS = ROOT / "data" / "corrections" / "corrections.json"
UNITS = ROOT / "data" / "output" / "learning_units.json"

REQUIRED_KEYS = ('article-233', 'article-236', 'article-239', 'article-239a', 'article-239aa', 'article-239ab', 'article-241', 'article-242', 'article-243', 'article-243c', 'article-243g', 'article-243h', 'article-243l', 'article-243o', 'article-243p', 'article-243q', 'article-243r')


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


    if "article-239-clause-1" not in units:
        pytest.skip("units not regenerated for Art 239")
    assert "Appointments of persons to be, and the posting" in units["article-233-clause-1"]["text"]
    assert "article-233-clause-2" in units
    assert "article-236" in units and units["article-236"]["allows_letter_split"]
    assert "article-239-clause-1" in units and "article-239a-clause-1" in units
    assert "article-239aa-clause-1" in units
    texts_239ab = " ".join(u["text"] for u in by_art["239AB"])
    assert "in pursuance of that article" in texts_239ab or "article 239AA" in texts_239ab
    assert "article-241-clause-1" in units
    assert "article-241-clause-3" in units
    assert not units["article-241-clause-4"]["text"].rstrip().endswith("]")
    assert units["article-242"]["text"].strip() == "[Omitted.]"
    assert "article-243c-clause-2" in units
    assert units["article-243h"]["allows_letter_split"]
    assert units["article-243p"]["allows_letter_split"]
    assert units["article-243q"]["allows_letter_split"]
    assert "\n\nProvided" in json.loads(CORRECTIONS.read_text())["articles"]["article-243l"]["body_text"]
    assert "(i)" in " ".join(u["text"] for u in by_art["243R"])

