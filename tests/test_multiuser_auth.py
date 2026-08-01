"""Multi-user auth flows with FakeAuthProvider (no Google/SMS)."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from constitution_memorizer.auth.exceptions import AuthConfigError, InvalidCredentialsError
from constitution_memorizer.auth.fake_provider import FakeAuthProvider
from constitution_memorizer.auth.phone import mask_phone, normalize_e164
from constitution_memorizer.auth.sessions import (
    CSRF_COOKIE_NAME,
    SESSION_COOKIE_NAME,
    InMemorySessionStore,
)
from constitution_memorizer.multiuser.settings import MultiUserSettings, clear_settings_cache
from constitution_memorizer.web.app import create_app

MINI_UNITS = Path(__file__).parent / "fixtures" / "learning" / "mini_units.json"


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


def _multi_client(tmp_path: Path, provider: FakeAuthProvider | None = None) -> TestClient:
    provider = provider or FakeAuthProvider()
    provider.seed_google_user(
        user_id=UUID("11111111-1111-4111-8111-111111111111"),
        email="a@example.com",
        display_name="User A",
    )
    app = create_app(
        units_path=MINI_UNITS,
        db_path=tmp_path / "progress.db",
        multiuser=True,
        multiuser_settings=_settings(),
        auth_provider=provider,
        session_store=InMemorySessionStore(),
    )
    return TestClient(app)


def test_normalize_and_mask_phone():
    assert normalize_e164("+91 98765 43210") == "+919876543210"
    with pytest.raises(InvalidCredentialsError):
        normalize_e164("9876543210")
    assert mask_phone("+919876543210") == "+91******3210"


def test_staging_requires_auth_method():
    with pytest.raises(AuthConfigError):
        MultiUserSettings(
            _env_file=None,
            APP_ENV="staging",
            AUTH_GOOGLE_ENABLED="false",
            AUTH_PHONE_ENABLED="false",
            DATABASE_URL="postgresql://x",
            SUPABASE_URL="http://x",
            SUPABASE_ANON_KEY="x",
            SESSION_SECRET="x",
        ).validate_for_startup()


def test_login_page_feature_flags(tmp_path: Path):
    provider = FakeAuthProvider()
    app = create_app(
        units_path=MINI_UNITS,
        db_path=tmp_path / "p.db",
        multiuser=True,
        multiuser_settings=_settings(AUTH_GOOGLE_ENABLED="false"),
        auth_provider=provider,
        session_store=InMemorySessionStore(),
    )
    client = TestClient(app)
    html = client.get("/login").text
    assert 'href="/auth/google/start"' not in html
    assert "Phone number" in html


def test_google_oauth_callback_sets_session(tmp_path: Path):
    provider = FakeAuthProvider()
    client = _multi_client(tmp_path, provider)
    start = client.get("/auth/google/start", follow_redirects=False)
    assert start.status_code == 303
    state = start.cookies.get("rtc_oauth_state")
    assert state
    cb = client.get(
        f"/auth/callback?code=fake-google-code&state={state}",
        follow_redirects=False,
    )
    assert cb.status_code == 303
    assert cb.headers["location"] == "/dashboard"
    assert SESSION_COOKIE_NAME in cb.cookies
    dash = client.get("/dashboard")
    assert dash.status_code == 200
    assert "User A" in dash.text


def test_oauth_callback_rejects_bad_state(tmp_path: Path):
    client = _multi_client(tmp_path)
    resp = client.get("/auth/callback?code=fake-google-code&state=nope", follow_redirects=False)
    assert resp.status_code == 303
    assert "oauth_state" in resp.headers["location"]


def test_phone_otp_flow(tmp_path: Path):
    provider = FakeAuthProvider()
    client = _multi_client(tmp_path, provider)
    login = client.get("/login")
    csrf = login.cookies.get(CSRF_COOKIE_NAME)
    send = client.post(
        "/auth/phone/send",
        data={"phone": "+14155552671", "csrf_token": csrf},
        follow_redirects=False,
    )
    assert send.status_code == 303
    assert "otp=1" in send.headers["location"]
    assert provider.sent_otps == ["+14155552671"]

    login2 = client.get("/login?otp=1&phone=%2B14155552671")
    csrf2 = login2.cookies.get(CSRF_COOKIE_NAME)
    verify = client.post(
        "/auth/phone/verify",
        data={"phone": "+14155552671", "otp": "123456", "csrf_token": csrf2},
        follow_redirects=False,
    )
    assert verify.status_code == 303
    assert verify.headers["location"] == "/dashboard"


def test_invalid_otp(tmp_path: Path):
    provider = FakeAuthProvider()
    client = _multi_client(tmp_path, provider)
    login = client.get("/login")
    csrf = login.cookies.get(CSRF_COOKIE_NAME)
    client.post(
        "/auth/phone/send",
        data={"phone": "+14155552671", "csrf_token": csrf},
        follow_redirects=False,
    )
    bad = client.post(
        "/auth/phone/verify",
        data={"phone": "+14155552671", "otp": "000000", "csrf_token": csrf},
        follow_redirects=False,
    )
    assert "bad_otp" in bad.headers["location"]


def test_protected_route_redirects(tmp_path: Path):
    client = _multi_client(tmp_path)
    resp = client.get("/progress", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/login"


def test_logout_clears_session(tmp_path: Path):
    provider = FakeAuthProvider()
    client = _multi_client(tmp_path, provider)
    start = client.get("/auth/google/start", follow_redirects=False)
    state = start.cookies.get("rtc_oauth_state")
    client.get(f"/auth/callback?code=fake-google-code&state={state}", follow_redirects=False)
    assert client.get("/dashboard").status_code == 200
    out = client.post("/logout", follow_redirects=False)
    assert out.status_code == 303
    assert client.get("/dashboard", follow_redirects=False).headers["location"] == "/login"
