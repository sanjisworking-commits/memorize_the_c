"""Judicial Evolution notes on Browse (Article 326) — not on Learn."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from constitution_memorizer.web.app import create_app
from constitution_memorizer.web.judicial_evolution import load_judicial_evolution

ROOT = Path(__file__).resolve().parents[1]
UNITS = ROOT / "data" / "output" / "learning_units.json"
REVIEWED = ROOT / "data" / "output" / "constitution.reviewed.json"


def test_load_article_326_entries():
    catalog = load_judicial_evolution()
    je = catalog["326"]
    assert je.section_title == "Judicial Evolution"
    assert len(je.entries) == 4
    assert je.entries[0].heading.lower().startswith("early")
    assert "creature of statute" in je.entries[0].body
    assert "NOTA" in je.entries[3].body


def test_browse_article_326_shows_judicial_evolution(tmp_path: Path):
    app = create_app(
        units_path=UNITS,
        db_path=tmp_path / "progress.db",
        reviewed_path=REVIEWED if REVIEWED.exists() else tmp_path / "missing.json",
    )
    client = TestClient(app)
    response = client.get("/browse/article/326")
    # Browse needs reviewed corpus; skip soft if unavailable in CI without file.
    if not REVIEWED.exists():
        assert response.status_code in (404, 200)
        return
    assert response.status_code == 200
    html = response.text
    assert "Judicial Evolution" in html
    assert "judicial-evolution" in html
    assert "NOTA" in html
    assert "creature of statute" in html


def test_learn_article_326_omits_judicial_evolution(tmp_path: Path):
    app = create_app(
        units_path=UNITS,
        db_path=tmp_path / "progress.db",
        reviewed_path=tmp_path / "missing-reviewed.json",
    )
    client = TestClient(app)
    response = client.get("/learn/article-326?mode=read")
    assert response.status_code == 200
    assert "judicial-evolution" not in response.text
    assert "creature of statute" not in response.text


def test_browse_article_without_notes_omits_section(tmp_path: Path):
    if not REVIEWED.exists():
        return
    app = create_app(
        units_path=UNITS,
        db_path=tmp_path / "progress.db",
        reviewed_path=REVIEWED,
    )
    client = TestClient(app)
    response = client.get("/browse/article/2")
    assert response.status_code == 200
    assert "judicial-evolution" not in response.text
