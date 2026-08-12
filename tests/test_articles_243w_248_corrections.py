"""Restore Bare Act wording for Arts 243W–248 diglot / missing stems via corrections."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from constitution_memorizer.corrections.apply_corrections import load_corrections

ROOT = Path(__file__).resolve().parents[1]
CORRECTIONS = ROOT / "data" / "corrections" / "corrections.json"
UNITS = ROOT / "data" / "output" / "learning_units.json"

REQUIRED_KEYS = ('article-243w', 'article-243x', 'article-243y', 'article-243zb', 'article-243zd', 'article-243ze', 'article-243zg', 'article-243zh', 'article-243zi', 'article-243zj', 'article-243zl', 'article-243zm', 'article-243zp', 'article-243zq', 'article-243zs', 'article-243zt', 'article-244', 'article-244a', 'article-245', 'article-246', 'article-246a', 'article-248')


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


    if "article-243zi" not in units:
        pytest.skip("units not regenerated for Art 243ZI")
    assert units["article-243w"]["allows_letter_split"]
    assert units["article-243x"]["allows_letter_split"]
    texts_y = " ".join(u["text"] for u in by_art["243Y"])
    assert "any other matter referred to the Finance Commission" in texts_y
    assert "\n\nProvided" in json.loads(CORRECTIONS.read_text())["articles"]["article-243zb"]["body_text"]
    texts_zd = " ".join(u["text"] for u in by_art["243ZD"])
    assert "filled:" not in texts_zd.replace("shall be filled:", "")
    assert "(i)" in texts_zd
    texts_ze = " ".join(u["text"] for u in by_art["243ZE"])
    assert "(c)" in texts_ze and "(d)" in texts_ze
    texts_zg = " ".join(u["text"] for u in by_art["243ZG"])
    assert "PART IXB" not in texts_zg and not texts_zg.rstrip().endswith("]")
    assert units["article-243zh"]["allows_letter_split"]
    assert "article-243zi" in units
    assert "article-243zj-clause-1" in units
    assert "Provided that the board may be superseded" in units["article-243zl-clause-1"]["text"]
    assert "Provided that such auditors" in units["article-243zm-clause-3"]["text"]
    assert units["article-243zp"]["allows_letter_split"]
    texts_zq = " ".join(u["text"] for u in by_art["243ZQ"])
    assert "(c)" in texts_zq and "(d)" in texts_zq
    assert "\n\nProvided" in json.loads(CORRECTIONS.read_text())["articles"]["article-243zs"]["body_text"]
    assert not units["article-243zt"]["text"].rstrip().endswith("]")
    t244 = " ".join(u["text"] for u in by_art["244"])
    assert "Meghalaya" in t244 and "244A" not in t244 and "***" not in t244
    assert "article-244a-clause-1" in units
    assert "article-245-clause-1" in units
    texts_246 = " ".join(u["text"] for u in by_art["246"])
    assert "***" not in texts_246 and "246A" not in texts_246
    assert "article-246a-clause-1" in units
    assert "1 [" not in units["article-248-clause-1"]["text"]
    assert "Subject to article 246A, Parliament" in units["article-248-clause-1"]["text"]

