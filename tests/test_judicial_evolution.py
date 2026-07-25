"""Judicial Evolution notes on Learn (Article 326)."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from constitution_memorizer.web.app import create_app
from constitution_memorizer.web.judicial_evolution import load_judicial_evolution


def test_load_article_326_entries():
    catalog = load_judicial_evolution()
    je = catalog["326"]
    assert je.section_title == "Judicial Evolution"
    assert len(je.entries) == 4
    assert je.entries[0].heading.lower().startswith("early")
    assert "creature of statute" in je.entries[0].body
    assert "NOTA" in je.entries[3].body


def test_learn_article_326_shows_judicial_evolution(tmp_path: Path):
    app = create_app(
        units_path=Path("data/output/learning_units.json"),
        db_path=tmp_path / "progress.db",
        reviewed_path=tmp_path / "missing-reviewed.json",
    )
    client = TestClient(app)
    response = client.get("/learn/article-326?mode=read")
    assert response.status_code == 200
    html = response.text
    assert "Judicial Evolution" in html
    assert "judicial-evolution" in html
    assert "ADR vs Union of India" in html or "ADR VS UNION OF INDIA" in html
    assert "NOTA" in html
    assert "creature of statute" in html
    # Must not replace Bare Act body.
    assert "adult suffrage" in html


def test_learn_article_without_notes_omits_section(tmp_path: Path):
    app = create_app(
        units_path=Path("data/output/learning_units.json"),
        db_path=tmp_path / "progress.db",
        reviewed_path=tmp_path / "missing-reviewed.json",
    )
    client = TestClient(app)
    response = client.get("/learn/article-2?mode=read")
    assert response.status_code == 200
    assert "judicial-evolution" not in response.text
