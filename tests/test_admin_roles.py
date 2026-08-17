"""Admin console authorization: authoritative role checks, 404 semantics."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from constitution_memorizer.auth.fake_provider import FakeAuthProvider
from constitution_memorizer.auth.sessions import InMemorySessionStore
from constitution_memorizer.multiuser.settings import (
    MultiUserSettings,
    clear_settings_cache,
)
from constitution_memorizer.progress.db import open_progress_db
from constitution_memorizer.progress.repository import ProgressRepository
from constitution_memorizer.web.app import create_app

MINI_UNITS = Path(__file__).parent / "fixtures" / "learning" / "mini_units.json"
USER = UUID("44444444-4444-4444-8444-444444444444")


@pytest.fixture(autouse=True)
def _fresh_settings():
    clear_settings_cache()
    yield
    clear_settings_cache()


def _settings(admin: bool = True, entitlements: bool = True) -> MultiUserSettings:
    return MultiUserSettings(
        _env_file=None,
        APP_ENV="test",
        MULTIUSER_ENABLED="true",
        AUTH_GOOGLE_ENABLED="true",
        AUTH_PHONE_ENABLED="true",
        SESSION_SECRET="test-secret",
        SUPABASE_URL="http://example.invalid",
        SUPABASE_ANON_KEY="anon",
        DATABASE_URL="",
        COOKIE_SECURE="false",
        ARTICLE_ENTITLEMENTS_ENABLED="true" if entitlements else "false",
        ADMIN_ENABLED="true" if admin else "false",
    )


def _client(
    tmp_path: Path, *, admin_enabled: bool = True, entitlements: bool = True
) -> tuple[TestClient, ProgressRepository]:
    conn = open_progress_db(tmp_path / "progress.db")
    repo = ProgressRepository(conn)
    provider = FakeAuthProvider()
    provider.seed_google_user(
        user_id=USER, email="admin@example.com", display_name="Sanjana"
    )
    app = create_app(
        units_path=MINI_UNITS,
        db_path=tmp_path / "unused.db",
        multiuser=True,
        multiuser_settings=_settings(admin_enabled, entitlements),
        auth_provider=provider,
        session_store=InMemorySessionStore(),
        progress_repo=repo,
    )
    client = TestClient(app)
    start = client.get("/auth/google/start", follow_redirects=False)
    state = start.cookies.get("rtc_oauth_state")
    cb = client.get(
        f"/auth/callback?code=fake-google-code&state={state}",
        follow_redirects=False,
    )
    assert cb.status_code == 303
    return client, repo


def _seed_admin(repo: ProgressRepository, user_id: UUID = USER) -> None:
    repo.conn.execute(
        "INSERT INTO user_roles (user_id, role, created_at) VALUES (?, 'admin', ?)",
        (str(user_id), datetime.now(timezone.utc).isoformat()),
    )
    repo.conn.commit()


def _revoke_admin(repo: ProgressRepository, user_id: UUID = USER) -> None:
    repo.conn.execute(
        "DELETE FROM user_roles WHERE user_id = ? AND role = 'admin'",
        (str(user_id),),
    )
    repo.conn.commit()


GET_ROUTES = ("/admin", "/admin/users", "/admin/admins", "/admin/access", "/admin/audit")


def test_guest_get_admin_redirects_to_login(tmp_path: Path) -> None:
    conn = open_progress_db(tmp_path / "progress.db")
    app = create_app(
        units_path=MINI_UNITS,
        db_path=tmp_path / "unused.db",
        multiuser=True,
        multiuser_settings=_settings(),
        auth_provider=FakeAuthProvider(),
        session_store=InMemorySessionStore(),
        progress_repo=ProgressRepository(conn),
    )
    client = TestClient(app)
    resp = client.get("/admin", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"].startswith("/login?")


@pytest.mark.parametrize("path", GET_ROUTES)
def test_signed_in_non_admin_gets_404(tmp_path: Path, path: str) -> None:
    client, _repo = _client(tmp_path)
    assert client.get(path).status_code == 404


def test_non_admin_post_routes_404(tmp_path: Path) -> None:
    client, _repo = _client(tmp_path)
    csrf = client.cookies.get("rtc_csrf")
    resp = client.post(
        f"/admin/users/{USER}/grants",
        data={"csrf_token": csrf, "source": "admin_grant", "reason": "x"},
        follow_redirects=False,
    )
    assert resp.status_code == 404


@pytest.mark.parametrize("path", GET_ROUTES)
def test_admin_gets_200(tmp_path: Path, path: str) -> None:
    client, repo = _client(tmp_path)
    _seed_admin(repo)
    assert client.get(path).status_code == 200


def test_console_flag_off_404s_but_bypass_survives(tmp_path: Path) -> None:
    # ADMIN_ENABLED gates the console only: the paywall bypass follows the
    # user_roles row, so a deploy toggle can never push the owner's account
    # into the 3-Article gate.
    client, repo = _client(tmp_path, admin_enabled=False)
    _seed_admin(repo)
    assert client.get("/admin").status_code == 404
    dash = client.get("/dashboard")
    assert dash.status_code == 200
    assert "Administrator access" in dash.text
    # Nav link is hidden too — it targets the disabled console.
    assert "Admin console" not in dash.text


def test_single_user_mode_admin_404s(tmp_path: Path) -> None:
    conn = open_progress_db(tmp_path / "progress.db")
    app = create_app(
        units_path=MINI_UNITS,
        db_path=tmp_path / "unused.db",
        multiuser=False,
        multiuser_settings=_settings(),
        progress_repo=ProgressRepository(conn),
    )
    client = TestClient(app)
    assert client.get("/admin").status_code == 404
    # The local owner keeps full access (legacy behavior).
    assert client.get("/learn").status_code == 200


def test_revoked_role_404s_immediately_despite_hint_cache(tmp_path: Path) -> None:
    client, repo = _client(tmp_path)
    _seed_admin(repo)
    # Warm both the console and the nav hint cache.
    assert client.get("/admin").status_code == 200
    dash = client.get("/dashboard")
    assert "Admin console" in dash.text
    _revoke_admin(repo)
    # Authorization is authoritative per request — no cache stands in its way.
    assert client.get("/admin").status_code == 404


def test_nav_hint_visibility(tmp_path: Path) -> None:
    client, repo = _client(tmp_path)
    dash = client.get("/dashboard")
    assert "Admin console" not in dash.text
    _seed_admin(repo)
    # The hint cache may hold the negative result for up to its TTL; clear it
    # the way a fresh process would start.
    client.app.state.admin_hint_cache.clear()
    dash = client.get("/dashboard")
    assert "Admin console" in dash.text
    assert "/admin" in dash.text


def test_admins_roster_lists_and_stays_read_only(tmp_path: Path) -> None:
    client, repo = _client(tmp_path)
    _seed_admin(repo)
    page = client.get("/admin/admins")
    assert page.status_code == 200
    assert str(USER) in page.text
    assert "Roles change from the command line, not here." in page.text
    assert "grant_admin.py" in page.text and "revoke_admin.py" in page.text
    # No role-mutation forms on the page.
    assert "Make admin" not in page.text
