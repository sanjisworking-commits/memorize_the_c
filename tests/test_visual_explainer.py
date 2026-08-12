"""Visual Explainer registry, resolver, and Browse/Learn wiring smoke tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from constitution_memorizer.web.app import create_app
from constitution_memorizer.web.explainers import (
    has_visual_explainer,
    normalise_ref,
    visual_explainer,
)

ROOT = Path(__file__).resolve().parents[1]
UNITS = ROOT / "data" / "output" / "learning_units.json"
SVG = ROOT / "src/constitution_memorizer/web/static/explainers/article-82.svg"


def test_normalise_ref_keeps_letter_suffixes():
    assert normalise_ref("Article 82(1)") == "82"
    assert normalise_ref("Article 21A") == "21A"
    assert normalise_ref("Article 21A(2)(b)") == "21A"
    assert normalise_ref("Article 239AA") == "239AA"
    assert normalise_ref("239AA") == "239AA"
    assert normalise_ref("Article 243ZG") == "243ZG"
    assert normalise_ref("243G") == "243G"
    assert normalise_ref("Clause (1) of Article 82") == "82"
    assert normalise_ref("31C") == "31C"


def test_visual_explainer_article_82_registered():
    ve = visual_explainer("82")
    assert ve is not None
    assert ve["article"] == "82"
    assert ve["src"].endswith("/static/explainers/article-82.svg")
    assert ve["title"] == "Readjustment after each census"
    assert ve["type"] == "flowchart"
    assert ve["label"] == "Visualise"
    assert "Prefer to see it?" in ve["band_title"]
    assert has_visual_explainer("Article 82(1)")
    assert SVG.is_file()


def test_visual_explainer_unknown_article_is_none():
    assert visual_explainer("999") is None
    assert visual_explainer("Article 999") is None
    assert not has_visual_explainer("1")


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    if not UNITS.exists():
        pytest.skip("learning_units.json missing")
    app = create_app(units_path=UNITS, db_path=tmp_path / "progress.db")
    return TestClient(app)


def test_browse_index_shows_visualise_only_for_article_82(client: TestClient):
    html = client.get("/browse").text
    assert 'data-ve-article="82"' in html
    assert "ve-card-cta" in html
    assert "visual-explainer.js" in html
    assert "ve-modal" in html
    # Article 1 has no explainer — no nested data-ve for 1 as a registered key
    assert 'data-ve-article="1"' not in html


def test_browse_article_82_actions_include_visualise(client: TestClient):
    html = client.get("/browse/article/82").text
    assert 'data-ve-open' in html
    assert 'data-ve-article="82"' in html
    assert "/static/explainers/article-82.svg" in html


def test_learn_article_82_shows_band(client: TestClient):
    html = client.get("/learn/article-82").text
    assert "ve-band" in html
    assert 'data-ve-article="82"' in html
    assert "Prefer to see it?" in html


def test_static_article_82_svg_served(client: TestClient):
    response = client.get("/static/explainers/article-82.svg")
    assert response.status_code == 200
    assert b"viewBox" in response.content
