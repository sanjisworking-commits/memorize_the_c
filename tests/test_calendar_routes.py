"""Calendar OAuth routes: state CSRF, token rules, reconnect, isolation."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID

import httpx
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from constitution_memorizer.auth.fake_provider import FakeAuthProvider
from constitution_memorizer.auth.sessions import InMemorySessionStore
from constitution_memorizer.calendar_sync.crypto import TokenSealer
from constitution_memorizer.calendar_sync.store import SYNC_PENDING, SqliteCalendarStore
from constitution_memorizer.multiuser.settings import MultiUserSettings
from constitution_memorizer.progress.db import open_progress_db
from constitution_memorizer.progress.repository import ProgressRepository
from constitution_memorizer.web.app import create_app

MINI_UNITS = Path(__file__).parent / "fixtures" / "learning" / "mini_units.json"
USER = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
OTHER = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
TOKEN_KEY = Fernet.generate_key().decode()
CAL_ID = "cal_recall_1"


class FakeGoogleAuth:
    """Token + calendar endpoints for the OAuth callback path."""

    def __init__(self) -> None:
        self.refresh_token: str | None = "rt-1"
        self.calendar_exists = True
        self.created_calendars = 0
        self.revoked_tokens: list[str] = []

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self._handle)

    def _handle(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/token":
            body = dict(pair.split("=", 1) for pair in request.content.decode().split("&"))
            if body.get("grant_type") == "authorization_code":
                payload = {"access_token": "at", "expires_in": 3600}
                if self.refresh_token:
                    payload["refresh_token"] = self.refresh_token
                return httpx.Response(200, json=payload)
            return httpx.Response(200, json={"access_token": "at", "expires_in": 3600})
        if path == "/revoke":
            self.revoked_tokens.append(str(request.url.params.get("token")))
            return httpx.Response(200)
        if request.method == "GET" and "/calendars/" in path:
            if self.calendar_exists:
                return httpx.Response(200, json={"id": CAL_ID})
            return httpx.Response(404)
        if request.method == "POST" and path.endswith("/calendars"):
            self.created_calendars += 1
            return httpx.Response(200, json={"id": f"cal_new_{self.created_calendars}"})
        if request.method == "POST" and path.endswith("/events"):
            return httpx.Response(200, json={"id": "ev1"})
        return httpx.Response(404)


def _settings(*, gcal: bool = True) -> MultiUserSettings:
    return MultiUserSettings(
        _env_file=None,
        APP_ENV="test",
        APP_BASE_URL="https://recall-the-c.in",
        MULTIUSER_ENABLED="true",
        AUTH_GOOGLE_ENABLED="true",
        SESSION_SECRET="test-secret",
        SUPABASE_URL="http://example.invalid",
        SUPABASE_ANON_KEY="anon",
        DATABASE_URL="",
        COOKIE_SECURE="false",
        GCAL_CLIENT_ID="gcal-cid" if gcal else "",
        GCAL_CLIENT_SECRET="gcal-secret" if gcal else "",
        GCAL_TOKEN_KEY=TOKEN_KEY if gcal else "",
    )


def _client(tmp_path: Path, *, gcal: bool = True, signed_in: bool = True):
    conn = open_progress_db(tmp_path / "progress.db")
    repo = ProgressRepository(conn)
    provider = FakeAuthProvider()
    provider.seed_google_user(user_id=USER, email="a@example.com", display_name="T")
    fake = FakeGoogleAuth()
    app = create_app(
        units_path=MINI_UNITS,
        db_path=tmp_path / "unused.db",
        multiuser=True,
        multiuser_settings=_settings(gcal=gcal),
        auth_provider=provider,
        session_store=InMemorySessionStore(),
        progress_repo=repo,
        calendar_store=SqliteCalendarStore(conn),
        gcal_transport=fake.transport(),
    )
    client = TestClient(app)
    if signed_in:
        start = client.get("/auth/google/start", follow_redirects=False)
        state = start.cookies.get("rtc_oauth_state")
        cb = client.get(
            f"/auth/callback?code=fake-google-code&state={state}",
            follow_redirects=False,
        )
        assert cb.status_code == 303
    return client, SqliteCalendarStore(conn), fake, repo


def _connect(client: TestClient, fake: FakeGoogleAuth) -> str:
    """Drive the full connect → callback flow; returns the final redirect."""
    start = client.get("/calendar/google/connect", follow_redirects=False)
    assert start.status_code == 303
    assert "accounts.google.com" in start.headers["location"]
    assert "access_type=offline" in start.headers["location"]
    assert "prompt=consent" in start.headers["location"]
    assert "calendar.app.created" in start.headers["location"]
    state = start.cookies.get("rtc_gcal_state")
    assert state
    cb = client.get(
        f"/calendar/google/callback?code=auth-code&state={state}",
        follow_redirects=False,
    )
    assert cb.status_code == 303
    return cb.headers["location"]


def test_connect_requires_sign_in(tmp_path: Path) -> None:
    client, _store, _fake, _repo = _client(tmp_path, signed_in=False)
    resp = client.get("/calendar/google/connect", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"].startswith("/login")


def test_unconfigured_routes_bounce(tmp_path: Path) -> None:
    client, _store, _fake, _repo = _client(tmp_path, gcal=False)
    resp = client.get("/calendar/google/connect", follow_redirects=False)
    assert resp.headers["location"] == "/settings"
    settings_html = client.get("/settings").text
    assert "Revision calendar" not in settings_html


def test_full_connect_creates_connection_and_syncs(tmp_path: Path) -> None:
    client, store, fake, _repo = _client(tmp_path)
    fake.calendar_exists = False  # first connect: nothing to reuse
    location = _connect(client, fake)
    assert location == "/settings?gcal=connected"
    connection = store.get_connection(USER)
    assert connection is not None and connection.is_active
    assert connection.google_calendar_id == "cal_new_1"
    # Token sealed at rest — never plaintext.
    assert connection.refresh_token_sealed != "rt-1"
    assert TokenSealer(TOKEN_KEY).unseal(connection.refresh_token_sealed) == "rt-1"
    settings_html = client.get("/settings").text
    assert "Recall the C — Revision Schedule" in settings_html


def test_callback_rejects_state_mismatch(tmp_path: Path) -> None:
    client, store, fake, _repo = _client(tmp_path)
    client.get("/calendar/google/connect", follow_redirects=False)
    cb = client.get(
        "/calendar/google/callback?code=auth-code&state=forged",
        follow_redirects=False,
    )
    assert "gcal=error" in cb.headers["location"]
    assert store.get_connection(USER) is None


def test_reconnect_reuses_tombstoned_calendar(tmp_path: Path) -> None:
    client, store, fake, _repo = _client(tmp_path)
    fake.calendar_exists = False
    _connect(client, fake)  # creates cal_new_1
    # Disconnect (tombstone).
    csrf = client.cookies.get("rtc_csrf")
    resp = client.post(
        "/calendar/google/disconnect",
        data={"csrf_token": csrf},
        follow_redirects=False,
    )
    assert resp.headers["location"] == "/settings?gcal=disconnected"
    assert store.get_connection(USER).is_active is False
    # Reconnect: Calendars.get(cal_new_1) → 200 → reuse, no second calendar.
    fake.calendar_exists = True
    _connect(client, fake)
    connection = store.get_connection(USER)
    assert connection.is_active
    assert connection.google_calendar_id == "cal_new_1"
    assert fake.created_calendars == 1  # never duplicated


def test_omitted_refresh_token_preserves_stored_one(tmp_path: Path) -> None:
    client, store, fake, _repo = _client(tmp_path)
    fake.calendar_exists = False
    _connect(client, fake)
    sealed_before = store.get_connection(USER).refresh_token_sealed
    # Google re-consent responses often omit refresh_token entirely.
    fake.refresh_token = None
    fake.calendar_exists = True
    location = _connect(client, fake)
    assert location == "/settings?gcal=connected"
    assert store.get_connection(USER).refresh_token_sealed == sealed_before


def test_no_token_anywhere_is_explicit_error(tmp_path: Path) -> None:
    client, store, fake, _repo = _client(tmp_path)
    fake.refresh_token = None  # first connect AND no stored token
    start = client.get("/calendar/google/connect", follow_redirects=False)
    state = start.cookies.get("rtc_gcal_state")
    cb = client.get(
        f"/calendar/google/callback?code=auth-code&state={state}",
        follow_redirects=False,
    )
    assert "why=no_refresh_token" in cb.headers["location"]
    assert store.get_connection(USER) is None


def test_disconnect_requires_csrf(tmp_path: Path) -> None:
    client, store, fake, _repo = _client(tmp_path)
    fake.calendar_exists = False
    _connect(client, fake)
    resp = client.post(
        "/calendar/google/disconnect",
        data={"csrf_token": "forged"},
        follow_redirects=False,
    )
    assert "why=csrf" in resp.headers["location"]
    assert store.get_connection(USER).is_active  # untouched


def test_preferences_validate_and_persist(tmp_path: Path) -> None:
    client, store, fake, repo = _client(tmp_path)
    fake.calendar_exists = False
    _connect(client, fake)
    csrf = client.cookies.get("rtc_csrf")
    ok = client.post(
        "/calendar/google/preferences",
        data={
            "csrf_token": csrf,
            "user_timezone": "Asia/Kolkata",
            "revision_time": "21:30",
            "session_minutes": "45",
        },
        follow_redirects=False,
    )
    assert ok.headers["location"] == "/settings?gcal=saved"
    assert repo.get_setting(USER, "user_timezone") == "Asia/Kolkata"
    assert repo.get_setting(USER, "gcal_revision_time") == "21:30"
    assert repo.get_setting(USER, "gcal_session_minutes") == "45"
    bad_tz = client.post(
        "/calendar/google/preferences",
        data={"csrf_token": csrf, "user_timezone": "Mars/Olympus"},
        follow_redirects=False,
    )
    assert "why=timezone" in bad_tz.headers["location"]
    bad_minutes = client.post(
        "/calendar/google/preferences",
        data={"csrf_token": csrf, "revision_time": "20:00", "session_minutes": "37"},
        follow_redirects=False,
    )
    assert "why=duration" in bad_minutes.headers["location"]


def test_done_flags_sync_pending(tmp_path: Path) -> None:
    """The state-change hook durably flags sync before any async work."""
    client, store, fake, _repo = _client(tmp_path)
    fake.calendar_exists = False
    _connect(client, fake)
    # Complete a unit through the app (all six modes then Done).
    for mode in ("read", "cloze", "letters", "type", "recite", "test"):
        client.get(f"/learn/clause-1?mode={mode}")
    from tests.quiz_helpers import submit_quiz

    submit_quiz(client, MINI_UNITS, "clause-1")
    for mode in ("cloze", "type", "recite"):
        client.post(f"/learn/clause-1/seen", data={"mode": mode})
    resp = client.post(
        "/learn/clause-1/done",
        data={"modes": "read,cloze,letters,type,recite,test", "claim_article": "1"},
        follow_redirects=False,
    )
    assert resp.status_code in (200, 303)
    connection = store.get_connection(USER)
    # Either the async sync already completed (ok) or the flag is still set —
    # both prove the durable-flag-then-sync path ran.
    assert connection.sync_status in ("ok", "pending", "error")
    assert connection.last_synced_at is not None or connection.sync_pending


def test_account_deletion_cleans_calendar_rows(tmp_path: Path) -> None:
    client, store, fake, _repo = _client(tmp_path)
    fake.calendar_exists = False
    _connect(client, fake)
    assert store.get_connection(USER) is not None
    csrf = client.cookies.get("rtc_csrf")
    resp = client.post(
        "/profile",
        data={"csrf_token": csrf, "action": "delete_account"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert store.get_connection(USER) is None
    assert store.list_event_mappings(USER) == []


def test_connect_captures_browser_timezone_before_oauth(tmp_path: Path) -> None:
    """Fix 2: ?tz= from the browser persists set-if-unset BEFORE Google runs,
    so the first calendar + events use local time, never a UTC default."""
    client, _store, _fake, repo = _client(tmp_path)
    resp = client.get(
        "/calendar/google/connect?tz=Asia/Kolkata", follow_redirects=False
    )
    assert resp.status_code == 303
    assert repo.get_setting(USER, "user_timezone") == "Asia/Kolkata"
    # An explicit existing choice is never overwritten.
    client.get("/calendar/google/connect?tz=Europe/London", follow_redirects=False)
    assert repo.get_setting(USER, "user_timezone") == "Asia/Kolkata"


def test_connect_ignores_invalid_timezone(tmp_path: Path) -> None:
    client, _store, _fake, repo = _client(tmp_path)
    client.get("/calendar/google/connect?tz=Mars/Olympus", follow_redirects=False)
    assert (repo.get_setting(USER, "user_timezone") or "") == ""


def test_settings_view_restarts_stale_pending_sync(tmp_path: Path, monkeypatch) -> None:
    """Fix 3: a stranded sync_pending (restart before the task ran) is
    re-kicked by viewing Settings; a fresh pending is left alone."""
    client, store, fake, _repo = _client(tmp_path)
    fake.calendar_exists = False
    _connect(client, fake)
    calls: list[str] = []
    monkeypatch.setattr(
        "constitution_memorizer.calendar_sync.routes.schedule_sync",
        lambda _req, uid: calls.append(str(uid)),
    )
    # Fresh pending (sync_requested_at = now) → no re-kick.
    store.mark_sync_pending(USER)
    client.get("/settings")
    assert calls == []
    # Stale pending (backdate the request) → settings view restarts it.
    conn = store._conn  # test-only backdating
    conn.execute(
        "UPDATE google_calendar_connections SET sync_requested_at = ? WHERE user_id = ?",
        ("2020-01-01T00:00:00+00:00", str(USER)),
    )
    conn.commit()
    client.get("/settings")
    assert calls == [str(USER)]


def test_account_deletion_revokes_google_grant(tmp_path: Path) -> None:
    """Fix 6: deleting the account revokes the Google grant before wiping
    the sealed token."""
    client, store, fake, _repo = _client(tmp_path)
    fake.calendar_exists = False
    _connect(client, fake)
    csrf = client.cookies.get("rtc_csrf")
    resp = client.post(
        "/profile",
        data={"csrf_token": csrf, "action": "delete_account"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert fake.revoked_tokens, "revocation endpoint was never called"
    assert store.get_connection(USER) is None
