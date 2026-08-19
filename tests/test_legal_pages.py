"""Public /terms, /privacy and /grievance pages for Google OAuth branding."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from constitution_memorizer.auth.fake_provider import FakeAuthProvider
from constitution_memorizer.auth.sessions import InMemorySessionStore
from constitution_memorizer.calendar_sync.routes import GCAL_SCOPE
from constitution_memorizer.multiuser.settings import MultiUserSettings, clear_settings_cache
from constitution_memorizer.web.app import create_app
from constitution_memorizer.web.legal import (
    DEFAULT_GRIEVANCE_EMAIL,
    DEFAULT_PRIVACY_EMAIL,
    DEFAULT_SUPPORT_EMAIL,
    GOOGLE_CALENDAR_SCOPE,
    LEGAL_PATHS,
)

MINI_UNITS = Path(__file__).parent / "fixtures" / "learning" / "mini_units.json"
GCAL_TOKEN_KEY = Fernet.generate_key().decode()


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


def _guest_client(tmp_path: Path, **overrides) -> TestClient:
    clear_settings_cache()
    return TestClient(
        create_app(
            units_path=MINI_UNITS,
            db_path=tmp_path / "progress.db",
            multiuser=True,
            multiuser_settings=_settings(**overrides),
            auth_provider=FakeAuthProvider(),
            session_store=InMemorySessionStore(),
        )
    )


def _signed_in_client(tmp_path: Path, **overrides) -> TestClient:
    provider = FakeAuthProvider()
    user_id = UUID("11111111-1111-4111-8111-111111111111")
    provider.seed_google_user(
        user_id=user_id,
        email="a@example.com",
        display_name="User A",
    )
    app = create_app(
        units_path=MINI_UNITS,
        db_path=tmp_path / "progress.db",
        multiuser=True,
        multiuser_settings=_settings(**overrides),
        auth_provider=provider,
        session_store=InMemorySessionStore(),
    )
    client = TestClient(app)
    start = client.get("/auth/google/start", follow_redirects=False)
    state = start.cookies.get("rtc_oauth_state")
    authed = client.get(
        f"/auth/callback?code=fake-google-code&state={state}",
        follow_redirects=False,
    )
    assert authed.status_code == 303
    return client


def test_legal_pages_are_public(tmp_path: Path) -> None:
    client = _guest_client(tmp_path)
    assert LEGAL_PATHS == ("/terms", "/privacy", "/grievance")
    for path, title in (
        ("/terms", "Terms &amp; Conditions"),
        ("/privacy", "Privacy Policy"),
        ("/grievance", "Grievance Redressal"),
    ):
        resp = client.get(path, follow_redirects=False)
        assert resp.status_code == 200
        html = resp.text
        assert title in html
        assert "Effective Date: 19 August 2026" in html
        assert "family=Fraunces" in html
        assert 'href="/terms"' in html
        assert 'href="/privacy"' in html
        assert 'href="/grievance"' in html
        assert "A study aid, not an official legal source" in html
        assert "{% extends" not in html


def test_legal_pages_work_without_multiuser(tmp_path: Path) -> None:
    client = TestClient(
        create_app(units_path=MINI_UNITS, db_path=tmp_path / "local.db", multiuser=False)
    )
    assert client.get("/privacy").status_code == 200
    assert client.get("/terms").status_code == 200
    assert client.get("/grievance").status_code == 200


def test_privacy_explains_google_user_data(tmp_path: Path) -> None:
    html = _guest_client(tmp_path).get("/privacy").text
    assert GOOGLE_CALENDAR_SCOPE in html
    assert GOOGLE_CALENDAR_SCOPE == GCAL_SCOPE
    assert "Google API Services User Data Policy" in html
    assert "Limited Use requirements" in html
    assert "does not receive your Google password" in html
    assert "does not sell Google user data" in html
    assert "does not use Google Calendar data to train general-purpose" in html
    assert "unrelated personal calendars" in html
    assert 'href="/profile"' in html
    assert DEFAULT_PRIVACY_EMAIL in html
    assert "aged 18 years" in html


def test_terms_keep_calendar_scope_narrow(tmp_path: Path) -> None:
    html = _guest_client(tmp_path).get("/terms").text
    assert "calendar.app.created" in html
    assert "not legal advice" in html.lower()
    assert "aged 18 years or above" in html
    assert DEFAULT_SUPPORT_EMAIL in html
    assert "not affiliated with" in html


def test_grievance_keeps_officer_placeholder(tmp_path: Path) -> None:
    html = _guest_client(tmp_path).get("/grievance").text
    assert "legal-placeholder" in html
    assert "[FULL NAME]" in html
    assert "[LEGAL ENTITY / PROPRIETOR NAME]" in html
    assert DEFAULT_GRIEVANCE_EMAIL in html
    assert "within 24 hours" in html
    assert "within seven days" in html


def test_operator_env_fills_placeholders(tmp_path: Path) -> None:
    html = _guest_client(
        tmp_path,
        LEGAL_ENTITY_NAME="Example Proprietor",
        LEGAL_BUSINESS_ADDRESS="1 Example Street, Example City",
        LEGAL_JURISDICTION="Mumbai, Maharashtra, India",
        LEGAL_GRIEVANCE_OFFICER="Asha Rao",
    ).get("/grievance").text
    assert "Example Proprietor" in html
    assert "1 Example Street, Example City" in html
    assert "Asha Rao" in html
    assert "[FULL NAME]" not in html
    assert "[LEGAL ENTITY / PROPRIETOR NAME]" not in html


def test_landing_and_login_link_legal_pages(tmp_path: Path) -> None:
    client = _guest_client(tmp_path)
    landing = client.get("/", follow_redirects=False).text
    assert 'aria-label="Legal"' in landing
    assert 'href="/terms"' in landing
    assert 'href="/privacy"' in landing
    assert 'href="/grievance"' in landing
    login = client.get("/login").text
    assert 'href="/terms"' in login
    assert 'href="/privacy"' in login
    assert "By continuing you agree" in login


def test_settings_calendar_disclosure_and_legal_links(tmp_path: Path) -> None:
    client = _signed_in_client(
        tmp_path,
        GCAL_CLIENT_ID="cid",
        GCAL_CLIENT_SECRET="csecret",
        GCAL_TOKEN_KEY=GCAL_TOKEN_KEY,
    )
    settings = client.get("/settings")
    assert settings.status_code == 200
    html = settings.text
    assert "Connect Google Calendar:" in html
    assert "It will not access your unrelated personal calendars." in html
    assert 'href="/terms"' in html
    assert 'href="/privacy"' in html
    assert 'href="/grievance"' in html


def test_in_app_footer_has_legal_nav(tmp_path: Path) -> None:
    html = _guest_client(tmp_path).get("/browse").text
    footer = html.split('aria-label="Legal"')[1].split("</nav>")[0]
    assert "/terms" in footer
    assert "/privacy" in footer
    assert "/grievance" in footer
    tools = html.split('aria-label="Tools"')[1].split("</nav>")[0]
    assert "/terms" not in tools
