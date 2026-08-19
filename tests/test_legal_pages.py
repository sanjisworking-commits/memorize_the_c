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
    GOOGLE_CALENDAR_SCOPE,
    LEGAL_PATHS,
    UNCONFIGURED,
    missing_legal_configuration,
)

MINI_UNITS = Path(__file__).parent / "fixtures" / "learning" / "mini_units.json"
GCAL_TOKEN_KEY = Fernet.generate_key().decode()
CALENDAR_DISCLOSURE = (
    "Recall the C will create and manage a separate revision calendar for "
    "your Recall the C study schedule. It will not access your unrelated "
    "personal calendars."
)


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
    provider.seed_google_user(
        user_id=UUID("11111111-1111-4111-8111-111111111111"),
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


def test_missing_legal_configuration_lists_empty_fields() -> None:
    empty = _settings()
    missing = missing_legal_configuration(empty)
    assert "LEGAL_ENTITY_NAME" in missing
    assert "LEGAL_SUPPORT_EMAIL" in missing
    assert "LEGAL_GRIEVANCE_OFFICER" in missing
    filled = _settings(
        LEGAL_ENTITY_NAME="Example",
        LEGAL_BUSINESS_ADDRESS="1 Street",
        LEGAL_JURISDICTION="Mumbai, Maharashtra, India",
        LEGAL_SUPPORT_EMAIL="support@example.test",
        LEGAL_PRIVACY_EMAIL="privacy@example.test",
        LEGAL_GRIEVANCE_EMAIL="grievance@example.test",
        LEGAL_GRIEVANCE_OFFICER="Asha Rao",
    )
    assert missing_legal_configuration(filled) == []


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
        assert "Effective 20 August 2026" in html
        assert "Last updated 20 August 2026" in html
        assert 'href="/terms"' in html
        assert 'href="/privacy"' in html
        assert 'href="/grievance"' in html
        assert "noindex" not in html.lower()
        assert UNCONFIGURED in html
        assert "support@recall-the-c.in" not in html


def test_privacy_does_not_redirect_to_login(tmp_path: Path) -> None:
    resp = _guest_client(tmp_path).get("/privacy", follow_redirects=False)
    assert resp.status_code == 200
    assert "/login" not in (resp.headers.get("location") or "")


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
    assert "calendar" != GCAL_SCOPE.split("/")[-1]
    assert "does not receive the user’s Google password" in html
    assert "does not sell Google user data" in html
    assert "Google Calendar access is optional" in html
    assert "Managing your Google data" in html
    assert "Google Workspace APIs" in html
    assert "Limited Use requirements" in html
    assert "use and transfer to any other app" not in html
    assert 'href="/profile"' in html
    assert "aged 18 years" in html
    assert "extends base.html" not in html


def test_terms_keep_calendar_scope_narrow(tmp_path: Path) -> None:
    html = _guest_client(tmp_path).get("/terms").text
    assert "calendar.app.created" in html
    assert "not legal advice" in html.lower()
    assert "study aid" in html.lower()
    assert "not affiliated with" in html
    assert "1 → 3 → 7 → 14 → 30 → 60" in html


def test_grievance_uses_aims_not_statutory_deadline(tmp_path: Path) -> None:
    html = _guest_client(tmp_path).get("/grievance").text
    assert "Grievance" in html
    assert "aims to acknowledge a valid grievance within 24 hours" in html
    assert "Under the DPDP Act" not in html
    assert "Never send us passwords" in html
    assert UNCONFIGURED in html


def test_operator_fields_are_escaped(tmp_path: Path) -> None:
    payload = "<script>alert(1)</script>"
    html = _guest_client(
        tmp_path,
        LEGAL_ENTITY_NAME=payload,
        LEGAL_BUSINESS_ADDRESS="1 Example Street",
        LEGAL_JURISDICTION="Mumbai, Maharashtra, India",
        LEGAL_GRIEVANCE_OFFICER="Asha Rao",
        LEGAL_SUPPORT_EMAIL="support@example.test",
        LEGAL_PRIVACY_EMAIL="privacy@example.test",
        LEGAL_GRIEVANCE_EMAIL="grievance@example.test",
        LEGAL_PRIVACY_CONTACT="Privacy Contact",
    ).get("/grievance").text
    assert payload not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "Asha Rao" in html
    assert UNCONFIGURED not in html


def test_landing_login_and_browse_link_legal_pages(tmp_path: Path) -> None:
    client = _guest_client(tmp_path)
    landing = client.get("/", follow_redirects=False).text
    assert 'href="/terms"' in landing
    assert 'href="/privacy"' in landing
    login = client.get("/login").text
    assert 'href="/terms"' in login
    assert 'href="/privacy"' in login
    assert "By continuing, you agree to the" in login
    assert "acknowledge the" in login
    legal_nav = login.split('aria-label="Legal"')[1].split("</nav>")[0]
    assert "/terms" in legal_nav
    assert "/privacy" in legal_nav
    assert "/grievance" in legal_nav
    assert "/tables" not in legal_nav
    browse = client.get("/browse").text
    footer = browse.split('aria-label="Legal"')[1].split("</nav>")[0]
    assert "/terms" in footer
    tools = browse.split('aria-label="Tools"')[1].split("</nav>")[0]
    assert "/terms" not in tools


def test_signed_in_privacy_uses_app_chrome(tmp_path: Path) -> None:
    client = _signed_in_client(tmp_path)
    resp = client.get("/privacy", follow_redirects=False)
    assert resp.status_code == 200
    html = resp.text
    assert "Privacy Policy" in html
    assert "is-authed" in html
    assert "Learning as guest" not in html
    assert 'href="/dashboard"' in html


def test_settings_calendar_disclosure_precedes_connect(tmp_path: Path) -> None:
    client = _signed_in_client(
        tmp_path,
        GCAL_CLIENT_ID="cid",
        GCAL_CLIENT_SECRET="csecret",
        GCAL_TOKEN_KEY=GCAL_TOKEN_KEY,
    )
    html = client.get("/settings").text
    assert CALENDAR_DISCLOSURE in html
    assert "/privacy#google-calendar" in html
    assert "Learn how we use Google data" in html
    disc = html.index(CALENDAR_DISCLOSURE)
    btn = html.index("Connect Google Calendar")
    learn = html.index("/privacy#google-calendar")
    assert disc < learn < btn
