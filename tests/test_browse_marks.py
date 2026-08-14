"""Generic Browse mark tray, legend, and tokens."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from constitution_memorizer.progress.scheduler import ReminderEngine
from constitution_memorizer.web.app import create_app
from constitution_memorizer.web.browse import (
    BROWSE_MARKS,
    browse_parts_sections,
    marks_for_article,
    present_browse_marks,
)

ROOT = Path(__file__).resolve().parents[1]
UNITS = ROOT / "data" / "output" / "learning_units.json"
MINI_UNITS = Path(__file__).parent / "fixtures" / "learning" / "mini_units.json"
CSS = ROOT / "src" / "constitution_memorizer" / "web" / "static" / "styles.css"
APP_JS = ROOT / "src" / "constitution_memorizer" / "web" / "static" / "app.js"


def test_browse_mark_registry_keys():
    assert [m.key for m in BROWSE_MARKS] == ["news", "visualise"]


def test_marks_for_article_news_only():
    assert marks_for_article("1", in_news=True) == ("news",)
    assert marks_for_article("1", in_news=False) == ()


def test_marks_for_article_visualise():
    assert marks_for_article("82", in_news=False) == ("visualise",)
    assert marks_for_article("82", in_news=True) == ("news", "visualise")


def test_present_browse_marks_registry_order(tmp_path: Path):
    engine = ReminderEngine.from_paths(tmp_path / "p.db", MINI_UNITS)
    engine.set_news_articles_raw("20")
    sections = browse_parts_sections(engine, None)
    present = present_browse_marks(sections)
    assert [m.key for m in present] == ["news"]
    assert present[0].legend_label == "In news"


def test_browse_legend_and_card_marks_split(tmp_path: Path):
    if not UNITS.exists():
        pytest.skip("learning_units.json missing")
    client = TestClient(create_app(units_path=UNITS, db_path=tmp_path / "progress.db"))
    html = client.get("/browse").text
    css = CSS.read_text(encoding="utf-8")
    js = APP_JS.read_text(encoding="utf-8")
    assert "browse-legend-caption" in html
    assert "In news" in html
    assert "Visualise" in html
    assert "--browse-mark-visualise" in css
    assert ".browse-mark-tray" in css
    assert "function initBrowseIndex" in js
    assert "data-browse-marks" in html
    assert "data-ve-open" not in html
    news_card = html[html.find("Article 19") : html.find("Article 19") + 900]
    assert "browse-mark-news" in news_card
    assert ">In news<" not in news_card
    vis_card = html[html.find("Article 82") : html.find("Article 82") + 1200]
    assert "browse-mark-visualise" in vis_card
    assert ">Visualise<" not in vis_card
