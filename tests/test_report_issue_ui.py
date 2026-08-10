"""Browse Article Report an Issue UI — trigger + dialog gating."""

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
MINI_REVIEWED = Path(__file__).parent / "fixtures" / "learning" / "mini_reviewed.json"
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
        "REPORT_TURNSTILE_ENABLED": "false",
        "REPORT_TURNSTILE_SITE_KEY": "",
        "REPORT_TURNSTILE_SECRET_KEY": "",
    }
    base.update({k: str(v) for k, v in overrides.items()})
    return MultiUserSettings(_env_file=None, **base)


def _login(client: TestClient, provider: FakeAuthProvider, email: str = "a@example.com") -> None:
    provider.seed_google_user(user_id=USER_ID, email=email, display_name="User A")
    start = client.get("/auth/google/start", follow_redirects=False)
    state = start.cookies.get("rtc_oauth_state")
    client.get(
        f"/auth/callback?code=fake-google-code&state={state}",
        follow_redirects=False,
    )


def _app(tmp_path: Path, provider: FakeAuthProvider, **settings_overrides):
    return create_app(
        units_path=MINI_UNITS,
        db_path=tmp_path / "progress.db",
        reviewed_path=MINI_REVIEWED,
        multiuser=True,
        multiuser_settings=_settings(**settings_overrides),
        auth_provider=provider,
        session_store=InMemorySessionStore(),
    )


def test_logged_in_browse_article_shows_report_button(tmp_path: Path):
    provider = FakeAuthProvider()
    client = TestClient(_app(tmp_path, provider))
    _login(client, provider)
    html = client.get("/browse/article/20").text
    assert 'data-report-open' in html
    assert "Report an issue" in html
    assert 'data-article-number="20"' in html
    assert 'data-report-overlay' in html
    assert "report.js" in html


def test_guest_browse_article_hides_report_button_and_dialog(tmp_path: Path):
    provider = FakeAuthProvider()
    client = TestClient(
        _app(
            tmp_path,
            provider,
            REPORT_TURNSTILE_ENABLED="true",
            REPORT_TURNSTILE_SITE_KEY="1x00000000000000000000AA",
            REPORT_TURNSTILE_SECRET_KEY="turnstile_secret_must_not_leak",
        )
    )
    html = client.get("/browse/article/20").text
    # Article report trigger stays signed-in only.
    assert "data-report-open" not in html
    assert "report-issue-link" not in html
    # Contact Us needs the shared dialog site-wide (guest gate).
    assert "data-report-overlay" in html
    assert "report.js" in html
    assert 'data-contact-mode="gate"' in html
    # Guests cannot submit — do not load Turnstile client/site key.
    assert "challenges.cloudflare.com/turnstile" not in html
    assert "1x00000000000000000000AA" not in html
    assert "turnstile_secret_must_not_leak" not in html
    assert 'data-turnstile-enabled="false"' in html


def test_turnstile_secret_never_in_html_when_enabled(tmp_path: Path):
    secret = "turnstile_secret_must_not_leak"
    site = "1x00000000000000000000AA"
    provider = FakeAuthProvider()
    client = TestClient(
        _app(
            tmp_path,
            provider,
            REPORT_TURNSTILE_ENABLED="true",
            REPORT_TURNSTILE_SITE_KEY=site,
            REPORT_TURNSTILE_SECRET_KEY=secret,
        )
    )
    _login(client, provider)
    html = client.get("/browse/article/20").text
    assert secret not in html
    assert site in html
    assert "challenges.cloudflare.com/turnstile" in html
    assert 'data-turnstile-enabled="true"' in html


def test_turnstile_site_key_omitted_when_disabled(tmp_path: Path):
    provider = FakeAuthProvider()
    client = TestClient(
        _app(
            tmp_path,
            provider,
            REPORT_TURNSTILE_ENABLED="false",
            REPORT_TURNSTILE_SITE_KEY="should-not-appear",
            REPORT_TURNSTILE_SECRET_KEY="",
        )
    )
    _login(client, provider)
    html = client.get("/browse/article/20").text
    assert "should-not-appear" not in html
    assert 'data-turnstile-enabled="false"' in html
    assert "challenges.cloudflare.com/turnstile" not in html


def test_authenticated_dashboard_has_contact_not_article_report(tmp_path: Path):
    site = "1x00000000000000000000AA"
    secret = "turnstile_secret_must_not_leak"
    provider = FakeAuthProvider()
    client = TestClient(
        _app(
            tmp_path,
            provider,
            REPORT_TURNSTILE_ENABLED="true",
            REPORT_TURNSTILE_SITE_KEY=site,
            REPORT_TURNSTILE_SECRET_KEY=secret,
        )
    )
    _login(client, provider)
    html = client.get("/dashboard").text
    # Contact Us is site-wide; Article report trigger is not.
    assert "data-report-overlay" in html
    assert "report.js" in html
    assert 'data-contact-mode="contact"' in html
    assert "data-report-open" not in html
    assert "report-issue-link" not in html
    assert secret not in html
    assert site in html
    assert "challenges.cloudflare.com/turnstile" in html


def test_report_dialog_hidden_overrides_display_flex():
    """display:flex on .rc-banner must not defeat HTML [hidden] after success."""
    css = Path(
        __file__
    ).resolve().parents[1] / "src/constitution_memorizer/web/static/styles.css"
    text = css.read_text(encoding="utf-8")
    assert ".rc-dialog [hidden]" in text
    assert "display: none !important" in text
