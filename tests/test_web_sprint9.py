"""Sprint 9 Choose + incomplete panel tests."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from jinja2 import Environment, FileSystemLoader
from starlette.requests import Request

from constitution_memorizer.web.app import TEMPLATES_DIR, create_app

MINI_UNITS = Path(__file__).parent / "fixtures" / "learning" / "mini_units.json"


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    app = create_app(
        units_path=MINI_UNITS,
        db_path=tmp_path / "progress.db",
    )
    return TestClient(app)


def test_choose_matches_prototype_copy(client: TestClient):
    response = client.get("/learn/clause-2/choose")
    assert response.status_code == 200
    assert "Split choice" in response.text
    assert "Learn whole clause" in response.text
    assert "Split into letters" in response.text
    assert "btn-accent" in response.text
    assert "btn-accent-outline" in response.text
    assert "your choice is remembered for this clause" in response.text
    assert "letter unit" in response.text
    assert "btn-green" not in response.text


def test_incomplete_template_renders_reasons():
    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/learn/garbage",
        "raw_path": b"/learn/garbage",
        "query_string": b"",
        "headers": [],
        "client": ("test", 50000),
        "server": ("test", 80),
    }
    request = Request(scope)
    body = env.get_template("incomplete.html").render(
        request=request,
        title="Article 1",
        readiness=SimpleNamespace(reasons=["garbage_fragment", "too_short"], ok=False),
        unit=SimpleNamespace(article_number="1", text="1-1977).", display_title="Article 1"),
        type_label="ARTICLE",
        part_label="Part I",
    )
    assert "Incomplete extraction" in body
    assert "garbage_fragment" in body
    assert "Browse article" in body
    assert "Part I" in body
    assert "ARTICLE" in body
    assert 'href="/"' in body
