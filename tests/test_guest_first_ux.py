"""Guest-first multi-user UX: browse/learn without account; gate personal writes."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from constitution_memorizer.auth.exceptions import InvalidCredentialsError
from constitution_memorizer.auth.fake_provider import FakeAuthProvider
from constitution_memorizer.auth.phone import normalize_e164, normalize_india_mobile
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


def _client(tmp_path: Path, provider: FakeAuthProvider | None = None) -> TestClient:
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


def test_india_mobile_to_e164():
    assert normalize_india_mobile("9876543210") == "+919876543210"
    assert normalize_e164("9876543210") == "+919876543210"
    assert normalize_e164("+91 98765 43210") == "+919876543210"
    with pytest.raises(InvalidCredentialsError):
        normalize_india_mobile("5876543210")
    with pytest.raises(InvalidCredentialsError):
        normalize_e164("12345")


def test_guest_landing_and_browse_learn(tmp_path: Path):
    client = _client(tmp_path)
    home = client.get("/", follow_redirects=False)
    assert home.status_code == 200
    html = home.text
    assert "Recall the C" in html
    assert "Memorize the C" not in html
    assert "Start remembering" in html
    assert 'href="/login"' in html
    assert "data-landing-demo" in html
    assert "Check" in html
    assert "landing.js" in html
    assert "family=Fraunces" in html or "@keyframes recallFade" in html
    assert "@keyframes floatC" in html
    # Gap panel: recognition vs recall with Art 21 demo line
    assert "On the page" in html
    assert "From memory" in html
    assert "No person shall be deprived of his life or personal liberty" in html
    assert "landing-gap-blank" in html
    assert "day 1, 3, 7, 14, 30" in html
    assert "Day 30" in html
    assert "Toward mastered" in html
    assert "landing-close .landing-actions" in html
    assert "justify-content: center" in html
    # Standalone page: no app chrome from base.html
    assert "Learning as guest" not in html
    assert 'class="nav-link">Home' not in html
    assert 'class="nav-link">Browse' not in html
    assert "Explore the Constitution" not in html
    assert "Articles" not in html
    assert "{% extends" not in html

    browse = client.get("/browse")
    assert browse.status_code == 200
    assert "Browse the Constitution" in browse.text
    assert "Learning as guest" in browse.text
    assert "guest-signin-modal" in browse.text
    assert 'href="/" class="nav-link">Home' in browse.text
    assert 'href="/browse" class="nav-link is-active">Browse' in browse.text

    learn = client.get("/learn/clause-1")
    assert learn.status_code == 200
    assert "learning as a guest" in learn.text.lower()
    assert "guest-signin-modal" in learn.text


def test_authed_logo_and_root_go_to_dashboard(tmp_path: Path):
    client = _client(tmp_path)
    start = client.get("/auth/google/start", follow_redirects=False)
    state = start.cookies.get("rtc_oauth_state")
    client.get(
        f"/auth/callback?code=fake-google-code&state={state}",
        follow_redirects=False,
    )
    dash = client.get("/dashboard")
    assert dash.status_code == 200
    assert 'class="brand" href="/dashboard"' in dash.text
    assert "main_logo.png" in dash.text
    root = client.get("/", follow_redirects=False)
    assert root.status_code == 303
    assert root.headers["location"] == "/dashboard"


def test_guest_post_done_redirects_to_login(tmp_path: Path):
    client = _client(tmp_path)
    resp = client.post("/learn/clause-1/done", follow_redirects=False)
    assert resp.status_code == 303
    loc = resp.headers["location"]
    assert loc.startswith("/login")
    assert "reason=mastered" in loc


def test_guest_dashboard_and_progress_gates(tmp_path: Path):
    client = _client(tmp_path)
    dash = client.get("/dashboard")
    assert dash.status_code == 200
    assert "Sign in to save your learning" in dash.text
    assert "Create a personal learning record" in dash.text
    prog = client.get("/progress")
    assert prog.status_code == 200
    assert "Sign in to save your learning" in prog.text
    assert "Create a personal learning record" in prog.text
    assert "Progress and mastery are private" not in prog.text


def test_login_ui_india_phone_and_otp_states(tmp_path: Path):
    client = _client(tmp_path)
    html = client.get("/login").text
    assert "+91" in html
    assert 'name="national_number"' in html
    assert "Continue with Google" in html

    login = client.get("/login")
    csrf = login.cookies.get(CSRF_COOKIE_NAME)
    send = client.post(
        "/auth/phone/send",
        data={
            "national_number": "9876543210",
            "country_code": "+91",
            "csrf_token": csrf,
            "next": "/dashboard",
        },
        follow_redirects=False,
    )
    assert send.status_code == 303
    assert "otp=1" in send.headers["location"]
    assert "+919876543210" in send.headers["location"] or "%2B919876543210" in send.headers[
        "location"
    ]

    otp_page = client.get("/login?otp=1&phone=%2B919876543210")
    assert otp_page.status_code == 200
    assert 'name="otp0"' in otp_page.text
    assert "Enter the code" in otp_page.text

    bad_phone = client.post(
        "/auth/phone/send",
        data={
            "national_number": "1234567890",
            "country_code": "+91",
            "csrf_token": csrf,
        },
        follow_redirects=False,
    )
    assert "phone_format" in bad_phone.headers["location"]
    assert "invalid-phone" in bad_phone.headers["location"]


def test_phone_otp_welcome_then_dashboard(tmp_path: Path):
    provider = FakeAuthProvider()
    client = _client(tmp_path, provider)
    login = client.get("/login")
    csrf = login.cookies.get(CSRF_COOKIE_NAME)
    client.post(
        "/auth/phone/send",
        data={
            "national_number": "9876543210",
            "country_code": "+91",
            "csrf_token": csrf,
        },
        follow_redirects=False,
    )
    verify = client.post(
        "/auth/phone/verify",
        data={
            "phone": "+919876543210",
            "otp": "123456",
            "csrf_token": csrf,
            "otp0": "1",
            "otp1": "2",
            "otp2": "3",
            "otp3": "4",
            "otp4": "5",
            "otp5": "6",
        },
        follow_redirects=False,
    )
    assert verify.status_code == 303
    assert verify.headers["location"] == "/welcome"
    assert SESSION_COOKIE_NAME in verify.cookies

    welcome = client.get("/welcome")
    assert welcome.status_code == 200
    assert "What should we call you" in welcome.text
    csrf2 = client.cookies.get(CSRF_COOKIE_NAME) or csrf
    saved = client.post(
        "/welcome",
        data={"display_name": "Priya", "csrf_token": csrf2},
        follow_redirects=False,
    )
    assert saved.headers["location"] == "/dashboard"
    dash = client.get("/dashboard")
    assert dash.status_code == 200
    assert "Priya" in dash.text


def test_logout_signed_out_page(tmp_path: Path):
    client = _client(tmp_path)
    start = client.get("/auth/google/start", follow_redirects=False)
    state = start.cookies.get("rtc_oauth_state")
    client.get(f"/auth/callback?code=fake-google-code&state={state}", follow_redirects=False)
    out = client.post("/logout", follow_redirects=False)
    assert out.status_code == 303
    assert out.headers["location"] == "/signed-out"
    page = client.get("/signed-out")
    assert page.status_code == 200
    assert "signed out" in page.text.lower()
    gate = client.get("/dashboard")
    assert gate.status_code == 200
    assert "Sign in to save your learning" in gate.text


def test_auth_transition_and_profile_pages(tmp_path: Path):
    client = _client(tmp_path)
    start = client.get("/auth/google/start", follow_redirects=False)
    state = start.cookies.get("rtc_oauth_state")
    cb = client.get(
        f"/auth/callback?code=fake-google-code&state={state}",
        follow_redirects=False,
    )
    assert cb.status_code == 303
    assert cb.headers["location"].startswith("/auth/transition")
    # Follow transition destination
    trans = client.get(cb.headers["location"])
    assert trans.status_code == 200
    assert "Opening your learning space" in trans.text
    dash = client.get("/dashboard")
    assert dash.status_code == 200
    assert "Welcome, User." in dash.text or "Good morning, User." in dash.text
    profile = client.get("/profile")
    assert profile.status_code == 200
    assert "Profile" in profile.text
    assert "Learning preferences → Settings" in profile.text
    assert 'name="notification_frequency"' not in profile.text
    assert 'name="theme"' not in profile.text


def test_dashboard_recent_activity_uses_display_title(tmp_path: Path):
    client = _client(tmp_path)
    start = client.get("/auth/google/start", follow_redirects=False)
    state = start.cookies.get("rtc_oauth_state")
    client.get(
        f"/auth/callback?code=fake-google-code&state={state}",
        follow_redirects=False,
    )
    # Mark modes seen then done so a progress row exists.
    for mode in ("read", "cloze", "letters", "type", "recite", "card"):
        client.post("/learn/clause-1/seen", data={"mode": mode})
    client.post("/learn/clause-1/done", follow_redirects=False)
    dash = client.get("/dashboard")
    assert dash.status_code == 200
    assert "Article 20(1)" in dash.text
    assert 'href="/learn/clause-1"' in dash.text
    assert "Mastered Article 20(1)" in dash.text or "Reviewed Article 20(1)" in dash.text


def test_dashboard_multiuser_layout(tmp_path: Path):
    client = _client(tmp_path)
    start = client.get("/auth/google/start", follow_redirects=False)
    state = start.cookies.get("rtc_oauth_state")
    client.get(
        f"/auth/callback?code=fake-google-code&state={state}",
        follow_redirects=False,
    )
    dash = client.get("/dashboard")
    assert dash.status_code == 200
    html = dash.text
    assert 'class="eyebrow"' not in html
    assert "Welcome, User." in html or "Good morning, User." in html
    assert "Due today" in html
    assert "Continue learning" in html
    assert "Articles started" in html
    assert "Units completed" in html
    assert "Units mastered" in html
    assert "Day streak" in html
    assert "Revisions done" in html
    assert "Explore the Constitution" in html
    assert "Browse Parts &amp; Articles" in html
    assert "→" in html
    assert "dash-progress-summary" not in html
    assert "Progress summary" in html  # aria-label on strip
    # Top-row Progress card (old 3-col) is gone — no started/review/mastered trio labels.
    assert ">Started<" not in html
    assert "Recent activity" in html
    assert "dash-card-head" in html
    assert "dash-card-body" in html
    assert "Nothing is due today" in html
    assert "dash-btn-outline" in html
    assert 'dash-btn-full" href="/browse">Browse the Constitution' not in html
    # Account dropdown identity header + menu order
    assert "account-menu-identity" in html
    assert "account-menu-name" in html
    assert "User A" in html
    assert "a@example.com" in html
    assert "account-provider-badge is-google" in html
    profile_i = html.index('href="/profile"')
    settings_i = html.index('href="/settings"')
    calendar_i = html.index('href="/calendar"')
    assert profile_i < settings_i < calendar_i
    # Memory log is feature-flagged off for V1 production.
    assert 'href="/memory"' not in html
    assert "Sign out" in html


def test_dashboard_data_error_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from constitution_memorizer.web import dashboard as dash_mod

    client = _client(tmp_path)
    start = client.get("/auth/google/start", follow_redirects=False)
    state = start.cookies.get("rtc_oauth_state")
    client.get(
        f"/auth/callback?code=fake-google-code&state={state}",
        follow_redirects=False,
    )

    def boom(*args, **kwargs):
        raise RuntimeError("forced dashboard failure")

    monkeypatch.setattr(dash_mod, "build_dashboard_context", boom)
    dash = client.get("/dashboard")
    assert dash.status_code == 200
    assert "We couldn't load your dashboard" in dash.text
    assert "Try again" in dash.text
