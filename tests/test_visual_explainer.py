"""Visual Explainer registry, resolver, wiring, and auth-gated SVG tests."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from constitution_memorizer.auth.fake_provider import FakeAuthProvider
from constitution_memorizer.auth.sessions import InMemorySessionStore
from constitution_memorizer.multiuser.settings import MultiUserSettings, clear_settings_cache
from constitution_memorizer.web.app import create_app
from constitution_memorizer.web.explainers import (
    ASSETS_DIR,
    explainer_asset_path,
    has_visual_explainer,
    normalise_ref,
    visual_explainer,
)

ROOT = Path(__file__).resolve().parents[1]
UNITS = ROOT / "data" / "output" / "learning_units.json"
SVG = ASSETS_DIR / "article-82.svg"
STATIC_JS = ROOT / "src/constitution_memorizer/web/static/visual-explainer.js"
AUTH_JS = ROOT / "src/constitution_memorizer/web/static/auth.js"


@pytest.fixture(autouse=True)
def _clear_settings():
    clear_settings_cache()
    yield
    clear_settings_cache()


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
    assert ve["src"] == "/api/explainers/82"
    assert ve["title"] == "Readjustment after each census"
    assert ve["type"] == "flowchart"
    assert ve["label"] == "Visualise"
    assert "Prefer to see it?" in ve["band_title"]
    assert has_visual_explainer("Article 82(1)")
    assert SVG.is_file()
    assert explainer_asset_path("82") == SVG.resolve()


def test_visual_explainer_unknown_article_is_none():
    assert visual_explainer("999") is None
    assert visual_explainer("Article 999") is None
    assert not has_visual_explainer("1")
    assert explainer_asset_path("999") is None
    assert explainer_asset_path("../etc/passwd") is None


def test_pending_intent_and_dismiss_hooks_in_js():
    ve_js = STATIC_JS.read_text()
    assert 'PENDING_KEY = "rtc_pending_ve"' in ve_js
    assert "function savePending(article, source)" in ve_js
    assert 'pending = { article: String(article) }' in ve_js
    assert "rtc:guest-modal-dismiss" in ve_js
    # Intent must not stash src/title/type from the trigger.
    save_body = ve_js.split("function savePending")[1].split("function readPending")[0]
    assert "data-ve-src" not in save_body
    assert "title" not in save_body
    assert "type" not in save_body
    auth_js = AUTH_JS.read_text()
    assert 'CustomEvent("rtc:guest-modal-dismiss")' in auth_js


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    if not UNITS.exists():
        pytest.skip("learning_units.json missing")
    app = create_app(units_path=UNITS, db_path=tmp_path / "progress.db")
    return TestClient(app)


def test_browse_index_shows_visualise_mark_only_for_article_82(client: TestClient):
    html = client.get("/browse").text
    assert "browse-mark-visualise" in html
    assert 'data-browse-filter="visualise"' in html
    assert "ve-card-cta" not in html
    assert "data-ve-open" not in html
    assert "visual-explainer.js" in html
    assert "ve-modal" in html
    assert "browse-legend" in html
    assert "Visualise" in html
    card = html[html.find("Article 82") : html.find("Article 82") + 1200]
    assert "browse-mark-visualise" in card
    assert ">Visualise<" not in card
    assert "data-ve-open" not in card
    assert 'data-browse-marks="' in html
    assert html.count('data-ve-article="82"') == 0
    assert 'data-browse-filter="visualise"' in html
    # Marks are not VE triggers: guest auth is attached only to data-ve-open.


def test_browse_article_82_actions_include_visualise(client: TestClient):
    html = client.get("/browse/article/82").text
    assert "data-ve-open" in html
    assert 'data-ve-article="82"' in html
    assert "Visualise" in html
    assert "/api/explainers/82" in html
    assert "/static/explainers/" not in html


def test_learn_article_82_shows_band(client: TestClient):
    html = client.get("/learn/article-82").text
    assert "ve-band" in html
    assert 'data-ve-article="82"' in html
    assert "Prefer to see it?" in html


def test_single_user_api_serves_svg(client: TestClient):
    response = client.get("/api/explainers/82")
    assert response.status_code == 200
    assert "svg" in response.headers.get("content-type", "")
    assert b"viewBox" in response.content


def test_public_static_explainer_path_gone(client: TestClient):
    assert client.get("/static/explainers/article-82.svg").status_code == 404


def test_unknown_explainer_api_404(client: TestClient):
    assert client.get("/api/explainers/999").status_code == 404


def _multi_settings(**overrides) -> MultiUserSettings:
    base = {
        "APP_ENV": "test",
        "MULTIUSER_ENABLED": "true",
        "AUTH_GOOGLE_ENABLED": "true",
        "AUTH_PHONE_ENABLED": "true",
        "SESSION_SECRET": "test-secret",
        "SUPABASE_URL": "http://example.invalid",
        "SUPABASE_ANON_KEY": "anon",
        "DATABASE_URL": "",
        "COOKIE_SECURE": "false",
    }
    base.update({k: str(v) for k, v in overrides.items()})
    return MultiUserSettings(_env_file=None, **base)


def test_guest_cannot_fetch_explainer_svg(tmp_path: Path):
    if not UNITS.exists():
        pytest.skip("learning_units.json missing")
    provider = FakeAuthProvider()
    app = create_app(
        units_path=UNITS,
        db_path=tmp_path / "progress.db",
        multiuser=True,
        multiuser_settings=_multi_settings(),
        auth_provider=provider,
        session_store=InMemorySessionStore(),
    )
    client = TestClient(app)
    response = client.get("/api/explainers/82")
    assert response.status_code == 403


def test_signed_in_user_can_fetch_explainer_svg(tmp_path: Path):
    if not UNITS.exists():
        pytest.skip("learning_units.json missing")
    provider = FakeAuthProvider()
    provider.seed_google_user(
        user_id=UUID("11111111-1111-4111-8111-111111111111"),
        email="a@example.com",
        display_name="User A",
    )
    app = create_app(
        units_path=UNITS,
        db_path=tmp_path / "progress.db",
        multiuser=True,
        multiuser_settings=_multi_settings(),
        auth_provider=provider,
        session_store=InMemorySessionStore(),
    )
    client = TestClient(app)
    start = client.get("/auth/google/start", follow_redirects=False)
    state = start.cookies.get("rtc_oauth_state")
    client.get(
        f"/auth/callback?code=fake-google-code&state={state}",
        follow_redirects=False,
    )
    response = client.get("/api/explainers/82")
    assert response.status_code == 200
    assert b"viewBox" in response.content
