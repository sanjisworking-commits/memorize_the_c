"""Browse Part segregation without constitution.reviewed.json."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from constitution_memorizer.web.app import create_app
from constitution_memorizer.web.browse import browse_parts_from_units
from constitution_memorizer.progress.scheduler import ReminderEngine

MINI_UNITS = Path(__file__).parent / "fixtures" / "learning" / "mini_units.json"
FULL_UNITS = Path(__file__).resolve().parents[1] / "data" / "output" / "learning_units.json"


def test_browse_parts_from_mini_units_tags(tmp_path: Path):
    engine = ReminderEngine.from_paths(tmp_path / "p.db", MINI_UNITS)
    sections = browse_parts_from_units(engine)
    assert sections
    romans = [s.part_number for s in sections]
    assert "III" in romans or any(c.article_number == "20" for s in sections for c in s.cards)
    # Mini fixture tags Part III on clause units
    part_iii = next((s for s in sections if s.part_number == "III"), None)
    assert part_iii is not None
    assert any(c.article_number == "20" for c in part_iii.cards)


def test_browse_html_parts_without_reviewed(tmp_path: Path):
    if not FULL_UNITS.exists():
        import pytest
        pytest.skip("full learning_units.json missing")
    client = TestClient(
        create_app(
            units_path=FULL_UNITS,
            db_path=tmp_path / "progress.db",
            reviewed_path=tmp_path / "missing-reviewed.json",
        )
    )
    html = client.get("/browse").text
    assert "browse-part-roman" in html
    assert "Part I" in html
    assert "Part II" in html
    assert "Part III" in html
    assert "The Union And Its Territory" in html or "Union" in html
    assert "Articles 1–4" in html or "Articles 1" in html
    # Must not collapse to a single flat Part —
    assert html.count("browse-part-roman") >= 10
    assert "Part —" not in html or html.count("browse-part-roman") > 1
    css = client.get("/static/styles.css?v=main2").text
    untracked_block = css.split(".browse-article-card.is-untracked")[1][:280]
    assert "browse-untracked-fg" not in untracked_block
