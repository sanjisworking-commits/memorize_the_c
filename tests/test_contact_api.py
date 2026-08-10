"""POST /api/contact — auth, Turnstile, DB, Resend reliability."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from constitution_memorizer.auth.fake_provider import FakeAuthProvider
from constitution_memorizer.auth.sessions import InMemorySessionStore
from constitution_memorizer.multiuser.settings import MultiUserSettings, clear_settings_cache
from constitution_memorizer.reports.contact_repository import ContactMessage
from constitution_memorizer.reports.turnstile import (
    TurnstileRejectedError,
    TurnstileUnavailableError,
)
from constitution_memorizer.web.app import create_app

MINI_UNITS = Path(__file__).parent / "fixtures" / "learning" / "mini_units.json"
FIXED_ID = UUID("cccccccc-bbbb-4ccc-8ddd-eeeeeeeeeeee")


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


class FakeContactRepo:
    def __init__(self, *, fail: bool = False) -> None:
        self.calls: list[dict] = []
        self.fail = fail

    def create_message(self, **kwargs) -> ContactMessage:
        self.calls.append(kwargs)
        if self.fail:
            raise RuntimeError("simulated database failure")
        return ContactMessage(
            id=FIXED_ID,
            status="new",
            created_at=datetime(2026, 8, 10, 12, 0, tzinfo=timezone.utc),
            topic=kwargs["topic"],
            message=kwargs["message"],
            page_url=kwargs.get("page_url"),
            reporter_email=kwargs.get("reporter_email"),
        )


class FakeContactNotifier:
    def __init__(self, *, fail: bool = False) -> None:
        self.calls: list[dict] = []
        self.fail = fail

    async def send(self, *, message, payload) -> str | None:
        self.calls.append({"message": message, "payload": payload})
        if self.fail:
            raise RuntimeError("simulated Resend failure")
        return "email_fake"


class FakeTurnstileVerifier:
    def __init__(self, *, outcome: str = "ok") -> None:
        self.calls: list[dict] = []
        self.outcome = outcome

    async def verify(self, token: str, **kwargs) -> None:
        self.calls.append({"token": token, **kwargs})
        if self.outcome == "reject":
            raise TurnstileRejectedError("Turnstile verification failed")
        if self.outcome == "unavailable":
            raise TurnstileUnavailableError("Turnstile verification request failed")


def _login(client: TestClient, provider: FakeAuthProvider, email: str = "a@example.com"):
    provider.seed_google_user(email=email, display_name="User")
    start = client.get("/auth/google/start", follow_redirects=False)
    state = start.cookies.get("rtc_oauth_state")
    client.get(
        f"/auth/callback?code=fake-google-code&state={state}",
        follow_redirects=False,
    )


def _client(
    tmp_path: Path,
    *,
    repo=...,
    notifier=...,
    turnstile=...,
    settings=None,
    as_guest: bool = False,
    email: str = "a@example.com",
) -> TestClient:
    provider = FakeAuthProvider()
    kwargs = {
        "units_path": MINI_UNITS,
        "db_path": tmp_path / "progress.db",
        "multiuser": True,
        "multiuser_settings": settings or _settings(),
        "auth_provider": provider,
        "session_store": InMemorySessionStore(),
    }
    if repo is not ...:
        kwargs["contact_message_repo"] = repo
    if notifier is not ...:
        kwargs["contact_message_notifier"] = notifier
    if turnstile is not ...:
        kwargs["issue_report_turnstile_verifier"] = turnstile
    client = TestClient(create_app(**kwargs))
    if not as_guest:
        _login(client, provider, email=email)
    return client


def _body(**overrides) -> dict:
    body = {
        "topic": "technical_issue",
        "message": "The settings page feels slow on mobile.",
        "page_url": "/settings",
    }
    body.update(overrides)
    return body


def test_unauthenticated_contact_401_skips_side_effects(tmp_path: Path):
    repo = FakeContactRepo()
    notifier = FakeContactNotifier()
    turnstile = FakeTurnstileVerifier()
    client = _client(
        tmp_path,
        repo=repo,
        notifier=notifier,
        turnstile=turnstile,
        settings=_settings(
            REPORT_TURNSTILE_ENABLED="true",
            REPORT_TURNSTILE_SITE_KEY="site",
            REPORT_TURNSTILE_SECRET_KEY="secret",
        ),
        as_guest=True,
    )
    resp = client.post("/api/contact", json=_body(turnstile_token="tok"))
    assert resp.status_code == 401
    assert repo.calls == []
    assert notifier.calls == []
    assert turnstile.calls == []


def test_authenticated_valid_contact_201(tmp_path: Path):
    repo = FakeContactRepo()
    notifier = FakeContactNotifier()
    client = _client(tmp_path, repo=repo, notifier=notifier, email="reader@example.com")
    resp = client.post("/api/contact", json=_body())
    assert resp.status_code == 201
    data = resp.json()
    assert data["success"] is True
    assert data["message_id"] == str(FIXED_ID)
    assert data["status"] == "new"
    assert len(repo.calls) == 1
    assert repo.calls[0]["reporter_email"] == "reader@example.com"
    assert len(notifier.calls) == 1


def test_browser_email_spoof_ignored(tmp_path: Path):
    repo = FakeContactRepo()
    client = _client(tmp_path, repo=repo, email="real@example.com")
    resp = client.post(
        "/api/contact",
        json=_body(reporter_email="spoof@evil.example"),
    )
    assert resp.status_code == 201
    assert repo.calls[0]["reporter_email"] == "real@example.com"


def test_wrong_topic_rejected(tmp_path: Path):
    repo = FakeContactRepo()
    client = _client(tmp_path, repo=repo)
    resp = client.post("/api/contact", json=_body(topic="spam"))
    assert resp.status_code == 422
    assert repo.calls == []


def test_missing_message_rejected(tmp_path: Path):
    repo = FakeContactRepo()
    client = _client(tmp_path, repo=repo)
    resp = client.post("/api/contact", json=_body(message="   "))
    assert resp.status_code == 422
    assert repo.calls == []


def test_turnstile_failure_blocks_db_and_email(tmp_path: Path):
    repo = FakeContactRepo()
    notifier = FakeContactNotifier()
    turnstile = FakeTurnstileVerifier(outcome="reject")
    client = _client(
        tmp_path,
        repo=repo,
        notifier=notifier,
        turnstile=turnstile,
        settings=_settings(
            REPORT_TURNSTILE_ENABLED="true",
            REPORT_TURNSTILE_SITE_KEY="site",
            REPORT_TURNSTILE_SECRET_KEY="secret",
        ),
    )
    resp = client.post("/api/contact", json=_body(turnstile_token="bad"))
    assert resp.status_code == 400
    assert repo.calls == []
    assert notifier.calls == []
    assert turnstile.calls


def test_db_failure_blocks_email(tmp_path: Path):
    repo = FakeContactRepo(fail=True)
    notifier = FakeContactNotifier()
    client = _client(tmp_path, repo=repo, notifier=notifier)
    resp = client.post("/api/contact", json=_body())
    assert resp.status_code == 503
    assert notifier.calls == []


def test_resend_failure_still_201(tmp_path: Path):
    repo = FakeContactRepo()
    notifier = FakeContactNotifier(fail=True)
    client = _client(tmp_path, repo=repo, notifier=notifier)
    resp = client.post("/api/contact", json=_body())
    assert resp.status_code == 201
    assert len(repo.calls) == 1


def test_production_requires_contact_us_action(tmp_path: Path):
    repo = FakeContactRepo()
    turnstile = FakeTurnstileVerifier()
    client = _client(
        tmp_path,
        repo=repo,
        turnstile=turnstile,
        settings=_settings(
            APP_ENV="production",
            REPORT_TURNSTILE_ENABLED="true",
            REPORT_TURNSTILE_SITE_KEY="site",
            REPORT_TURNSTILE_SECRET_KEY="secret",
            APP_BASE_URL="https://recall-the-c.in",
        ),
    )
    resp = client.post("/api/contact", json=_body(turnstile_token="tok"))
    assert resp.status_code == 201
    assert turnstile.calls[0]["expected_action"] == "contact_us"


def test_turnstile_secret_never_rendered(tmp_path: Path):
    secret = "turnstile_secret_must_not_leak"
    client = _client(
        tmp_path,
        repo=FakeContactRepo(),
        settings=_settings(
            REPORT_TURNSTILE_ENABLED="true",
            REPORT_TURNSTILE_SITE_KEY="1x00000000000000000000AA",
            REPORT_TURNSTILE_SECRET_KEY=secret,
        ),
    )
    html = client.get("/dashboard").text
    assert secret not in html
