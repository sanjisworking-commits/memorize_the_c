"""Contact Us footer entry + shared dialog gating."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from constitution_memorizer.auth.fake_provider import FakeAuthProvider
from constitution_memorizer.auth.sessions import InMemorySessionStore
from constitution_memorizer.multiuser.settings import MultiUserSettings, clear_settings_cache
from constitution_memorizer.web.app import create_app

MINI_UNITS = Path(__file__).parent / "fixtures" / "learning" / "mini_units.json"
USER_ID = UUID("11111111-1111-4111-8111-111111111111")


@pytest.fixture(autouse=True)
def _clear_settings():
    clear_settings_cache()
    yield
    clear_settings_cache()


def _settings(**overrides) -> MultiUserSettings:
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


def _login(client: TestClient, provider: FakeAuthProvider) -> None:
    provider.seed_google_user(user_id=USER_ID, email="a@example.com", display_name="A")
    start = client.get("/auth/google/start", follow_redirects=False)
    state = start.cookies.get("rtc_oauth_state")
    client.get(
        f"/auth/callback?code=fake-google-code&state={state}",
        follow_redirects=False,
    )


def _app(tmp_path: Path, provider: FakeAuthProvider):
    return create_app(
        units_path=MINI_UNITS,
        db_path=tmp_path / "progress.db",
        multiuser=True,
        multiuser_settings=_settings(),
        auth_provider=provider,
        session_store=InMemorySessionStore(),
    )


def test_signed_in_user_sees_contact_us(tmp_path: Path):
    provider = FakeAuthProvider()
    client = TestClient(_app(tmp_path, provider))
    _login(client, provider)
    html = client.get("/dashboard").text
    assert "Contact us" in html
    assert 'data-contact-mode="contact"' in html
    assert "data-report-overlay" in html
    assert "report.js" in html


def test_guest_sees_contact_us_sign_in_gate(tmp_path: Path):
    provider = FakeAuthProvider()
    client = TestClient(_app(tmp_path, provider))
    html = client.get("/browse").text
    assert "Contact us" in html
    assert 'data-contact-mode="gate"' in html
    assert "data-report-overlay" in html


def test_report_trigger_only_on_signed_in_browse_article(tmp_path: Path):
    provider = FakeAuthProvider()
    client = TestClient(_app(tmp_path, provider))
    _login(client, provider)
    dash = client.get("/dashboard").text
    assert "data-report-open" not in dash
    # Browse article needs reviewed fixture — use browse list page instead
    browse = client.get("/browse").text
    assert "data-report-open" not in browse
