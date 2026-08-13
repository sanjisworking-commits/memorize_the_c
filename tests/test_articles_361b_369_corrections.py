"""Arts 361B / 366 / 367 / 368 / 369 Bare Act correction overlays."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from constitution_memorizer.corrections.apply_corrections import load_corrections

ROOT = Path(__file__).resolve().parents[1]
CORRECTIONS = ROOT / "data" / "corrections" / "corrections.json"
UNITS = ROOT / "data" / "output" / "learning_units.json"
ANNOTATIONS = ROOT / "data" / "reference" / "text_annotations.json"


def _units():
    if not UNITS.exists():
        pytest.skip("learning_units.json not generated")
    data = json.loads(UNITS.read_text())
    return {u["id"]: u for u in data["units"]}


def test_overlays_361b_369_present():
    corr = load_corrections(CORRECTIONS)
    for key in (
        "article-361b",
        "article-366",
        "article-367",
        "article-368",
        "article-369",
    ):
        assert key in corr.articles, key

    assert corr.articles["article-361b"].create is True
    assert "remunerative political post" in (corr.articles["article-361b"].body_text or "")

    body_366 = corr.articles["article-366"].body_text or ""
    assert "6. (a)" not in body_366
    assert "7. (b)" not in body_366
    assert "* * *" not in body_366
    assert "1 [" not in body_366
    assert "2 [" not in body_366
    assert "\n(29A) " in body_366
    assert "(e) a tax on the supply of goods by any unincorporated" in body_366
    assert "\n(30) " in body_366
    idx_29a = body_366.index("(29A)")
    idx_30 = body_366.index("\n(30) ")
    assert idx_30 > idx_29a
    # no footnote gap between 29A(d) and (e)
    chunk = body_366[idx_29a:idx_30]
    assert "Ins. by the Constitution" not in chunk
    assert "\n(e) " in chunk
    assert "\n(f) " in chunk

    body_367 = corr.articles["article-367"].body_text or ""
    assert "C.O. 272" not in body_367
    assert "Added by the Constitution" not in body_367
    assert "order 4 declare" not in body_367
    assert "by order declare" in body_367
    assert "***" not in body_367

    body_368 = corr.articles["article-368"].body_text or ""
    assert body_368.rstrip().endswith("under this article.")
    assert "\n(3) " in body_368
    assert "(4)" not in body_368
    assert "(5)" not in body_368
    assert "3 [" not in body_368

    body_369 = corr.articles["article-369"].body_text or ""
    assert body_369.startswith("Notwithstanding anything in this Constitution")
    assert "\n(a) " in body_369
    assert "clause (a)" in body_369
    assert "clause ( a )" not in body_369
    assert corr.articles["article-369"].prefer_article_unit is True


def test_articles_361b_369_learning_units():
    units = _units()

    assert "article-361b" in units
    assert "Tenth Schedule" in units["article-361b"]["text"]
    assert units["article-361b"].get("allows_letter_split") is True

    assert "article-366-clause-20" in units
    assert "6. (a)" not in units["article-366-clause-20"]["text"]
    assert "(a) a tramway" in units["article-366-clause-20"]["text"]
    assert "article-366-clause-29a" in units
    assert "article-366-clause-30" in units
    assert units["article-366-clause-30"]["text"].lstrip().startswith("(30)")
    assert "1 [" not in units["article-366-clause-30"]["text"]
    # 29A continuous through (f)
    t29 = units["article-366-clause-29a"]["text"]
    assert "(e)" in t29 and "(f)" in t29
    assert "Ins. by the Constitution" not in t29

    assert "article-367-clause-1" in units
    assert "article-367-clause-3" in units
    assert "C.O. 272" not in units["article-367-clause-3"]["text"]
    assert "Added by the Constitution" not in units["article-367-clause-3"]["text"]

    assert "article-368-clause-3" in units
    assert "(4)" not in units["article-368-clause-3"]["text"]
    assert "article-368-clause-4" not in units
    assert "article-368-clause-5" not in units

    assert "article-369" in units
    assert units["article-369"]["text"].startswith("Notwithstanding anything in this Constitution")
    assert not units["article-369"]["text"].lstrip().startswith("(a)")
    assert "article-369-subclause-a" in units or "article-369-clause-a" in units


def test_article_368_minerva_tip_present():
    data = json.loads(ANNOTATIONS.read_text())
    tips = data["units"].get("article-368-clause-3") or []
    assert tips, "expected Minerva tip on 368(3)"
    blob = json.dumps(tips)
    assert "Minerva" in blob
    assert "invalid" in blob.lower() or "declared invalid" in blob
