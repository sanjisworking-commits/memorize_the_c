"""Sprint 27 — Full amendment history corpus."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from constitution_memorizer.web.amendments import load_amendments
from constitution_memorizer.web.app import create_app
from constitution_memorizer.web.browse import iter_articles, load_reviewed_document

ROOT = Path(__file__).resolve().parents[1]
SEED = ROOT / "data" / "reference" / "amendments.seed.json"
WIKI = ROOT / "data" / "reference" / "amendments.wikipedia.json"
REVIEWED = ROOT / "data" / "output" / "constitution.reviewed.json"
AMENDMENT_UNITS = Path(__file__).parent / "fixtures" / "learning" / "amendment_units.json"
AMENDMENT_REVIEWED = Path(__file__).parent / "fixtures" / "learning" / "amendment_reviewed.json"
MINI_UNITS = Path(__file__).parent / "fixtures" / "learning" / "mini_units.json"


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    app = create_app(
        units_path=AMENDMENT_UNITS,
        db_path=tmp_path / "progress.db",
        reviewed_path=AMENDMENT_REVIEWED,
        amendments_path=SEED,
    )
    return TestClient(app)


def test_wikipedia_catalog_has_106():
    data = json.loads(WIKI.read_text(encoding="utf-8"))
    assert data["amendment_count"] == 106
    assert len(data["amendments"]) == 106
    assert "wikipedia.org" in data["source"]["url"]
    assert data["amendments"][0]["no"] == "1st"
    assert data["amendments"][-1]["no"] == "106th"


def test_seed_preserves_sprint21_hand_notes():
    catalog = load_amendments(SEED)
    assert catalog["14"].amendments == []
    assert catalog["14"].learn_note is None
    assert len(catalog["15"].amendments) == 3
    assert "Inserted clause (4)" in catalog["15"].amendments[0].text
    assert "Amended thrice" in (catalog["15"].learn_note or "")
    assert catalog["19"].amendments[2].no == "44th"
    assert "property" in (catalog["19"].learn_note or "").lower()
    assert catalog["21"].amendments[0].no == "86th"


def test_seed_articles_exist_in_reviewed_corpus():
    catalog = load_amendments(SEED)
    reviewed = load_reviewed_document(REVIEWED)
    assert reviewed is not None
    corpus_ids = {a.article_number for a in iter_articles(reviewed)}
    missing = sorted(set(catalog) - corpus_ids, key=lambda x: (len(x), x))
    assert missing == [], f"Seed articles missing from corpus: {missing}"


def test_heavily_amended_articles_have_timelines():
    catalog = load_amendments(SEED)
    assert len(catalog["356"].amendments) >= 5
    assert {r.no for r in catalog["356"].amendments} >= {"38th", "42nd", "44th", "48th"}
    assert len(catalog["368"].amendments) >= 2
    assert {r.no for r in catalog["368"].amendments} >= {"24th", "42nd"}
    assert any(r.no == "61st" for r in catalog["326"].amendments)
    assert any(r.no == "73rd" for r in catalog["243"].amendments)


@pytest.fixture
def full_client(tmp_path: Path) -> TestClient:
    if not REVIEWED.exists():
        pytest.skip("reviewed corpus not present")
    # Prefer mini units if full units missing — Browse only needs reviewed + seed
    units = ROOT / "data" / "output" / "learning_units.json"
    if not units.exists():
        units = MINI_UNITS
    app = create_app(
        units_path=units,
        db_path=tmp_path / "progress.db",
        reviewed_path=REVIEWED,
        amendments_path=SEED,
    )
    return TestClient(app)


def test_browse_356_timeline(full_client: TestClient):
    html = full_client.get("/browse/article/356").text
    assert "Amendment history" in html
    assert "42nd Amdt" in html
    assert "48th Amdt" in html


def test_browse_368_timeline(full_client: TestClient):
    html = full_client.get("/browse/article/368").text
    assert "Amendment history" in html
    assert "24th Amdt" in html


def test_browse_15_regression(client: TestClient):
    html = client.get("/browse/article/15").text
    assert "1st Amdt" in html
    assert "103rd Amdt" in html
    assert "Inserted clause (4)" in html
