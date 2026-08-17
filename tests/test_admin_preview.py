"""Admin Entitlement Preview: Article-aware states, persistence safety."""

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
from tests.quiz_helpers import complete_all_modes

MINI_UNITS = Path(__file__).parent / "fixtures" / "learning" / "mini_units.json"
ADMIN = UUID("88888888-8888-4888-8888-888888888888")


@pytest.fixture(autouse=True)
def _fresh_settings():
    clear_settings_cache()
    yield
    clear_settings_cache()


def _settings() -> MultiUserSettings:
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
        ARTICLE_ENTITLEMENTS_ENABLED="true",
        ADMIN_ENABLED="true",
    )


def _client(
    tmp_path: Path, *, make_admin: bool = True
) -> tuple[TestClient, ProgressRepository]:
    conn = open_progress_db(tmp_path / "progress.db")
    repo = ProgressRepository(conn)
    provider = FakeAuthProvider()
    provider.seed_google_user(
        user_id=ADMIN, email="admin@recall.app", display_name="Admin"
    )
    app = create_app(
        units_path=MINI_UNITS,
        db_path=tmp_path / "unused.db",
        multiuser=True,
        multiuser_settings=_settings(),
        auth_provider=provider,
        session_store=InMemorySessionStore(),
        progress_repo=repo,
    )
    client = TestClient(app)
    start = client.get("/auth/google/start", follow_redirects=False)
    state = start.cookies.get("rtc_oauth_state")
    client.get(
        f"/auth/callback?code=fake-google-code&state={state}",
        follow_redirects=False,
    )
    if make_admin:
        repo.conn.execute(
            "INSERT INTO user_roles (user_id, role, created_at) VALUES (?, 'admin', ?)",
            (str(ADMIN), datetime.now(timezone.utc).isoformat()),
        )
        repo.conn.commit()
    return client, repo


def _enter_preview(client: TestClient, state: str) -> None:
    csrf = client.cookies.get("rtc_csrf")
    resp = client.post(
        "/admin/preview",
        data={"csrf_token": csrf, "state": state},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert client.cookies.get("rtc_admin_preview") == state


def test_preview_page_shows_four_states(tmp_path: Path) -> None:
    client, _repo = _client(tmp_path)
    page = client.get("/admin/preview")
    assert page.status_code == 200
    for code in ("free_claimable", "free_claimed", "free_cap", "subscribed"):
        assert code in page.text
    assert "use a private window" in page.text


def test_unknown_state_rejected(tmp_path: Path) -> None:
    client, _repo = _client(tmp_path)
    csrf = client.cookies.get("rtc_csrf")
    resp = client.post(
        "/admin/preview", data={"csrf_token": csrf, "state": "guest"}
    )
    assert resp.status_code == 400


def test_forged_cookie_does_nothing_for_non_admin(tmp_path: Path) -> None:
    client, _repo = _client(tmp_path, make_admin=False)
    client.cookies.set("rtc_admin_preview", "free_cap")
    page = client.get("/learn/clause-1")
    assert page.status_code == 200
    # A real free user with slots sees no locks; the forged cookie would
    # have shown Type/Recite locked.
    assert 'data-locked-modes=""' in page.text
    assert "ADMIN PREVIEW" not in page.text


def test_free_cap_preview_locks_and_banner(tmp_path: Path) -> None:
    client, _repo = _client(tmp_path)
    _enter_preview(client, "free_cap")
    page = client.get("/learn/clause-1")
    assert "ADMIN PREVIEW" in page.text
    assert "Free — 3/3 used" in page.text
    assert 'data-locked-modes="type,recite"' in page.text
    assert "Type 🔒" in page.text and "Recite 🔒" in page.text
    assert "Exit preview" in page.text


def test_free_claimed_preview_all_modes_no_prompt(tmp_path: Path) -> None:
    client, _repo = _client(tmp_path)
    _enter_preview(client, "free_claimed")
    page = client.get("/learn/clause-1")
    assert 'data-locked-modes=""' in page.text
    assert "ADMIN PREVIEW" in page.text


def test_subscribed_preview_everything_open(tmp_path: Path) -> None:
    client, _repo = _client(tmp_path)
    _enter_preview(client, "subscribed")
    page = client.get("/learn/clause-1")
    assert 'data-locked-modes=""' in page.text


def test_claim_confirm_while_previewing_writes_nothing(tmp_path: Path) -> None:
    client, repo = _client(tmp_path)
    _enter_preview(client, "free_claimable")
    complete_all_modes(client, MINI_UNITS, "clause-1")
    done = client.post(
        "/learn/clause-1/done",
        data={"claim_article": "1", "modes": "read,cloze,letters,type,recite,test"},
        headers={"accept": "application/json"},
    )
    assert done.status_code == 200
    payload = done.json()
    assert payload.get("persisted") is False
    # Nothing was claimed and no Done cycle persisted.
    assert repo.claimed_articles(ADMIN) == set()
    progress = repo.get_progress(ADMIN, "clause-1")
    assert progress is None or progress.times_completed == 0


def test_done_while_previewing_subscribed_writes_nothing(tmp_path: Path) -> None:
    client, repo = _client(tmp_path)
    _enter_preview(client, "subscribed")
    complete_all_modes(client, MINI_UNITS, "clause-1")
    done = client.post(
        "/learn/clause-1/done", headers={"accept": "application/json"}
    )
    assert done.status_code == 200
    assert done.json().get("persisted") is False
    progress = repo.get_progress(ADMIN, "clause-1")
    assert progress is None or progress.times_completed == 0


def test_exit_preview_restores_real_access(tmp_path: Path) -> None:
    client, _repo = _client(tmp_path)
    _enter_preview(client, "free_cap")
    assert 'data-locked-modes="type,recite"' in client.get("/learn/clause-1").text
    csrf = client.cookies.get("rtc_csrf")
    resp = client.post(
        "/admin/preview/clear",
        data={"csrf_token": csrf},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    page = client.get("/learn/clause-1")
    assert 'data-locked-modes=""' in page.text
    assert "ADMIN PREVIEW" not in page.text


def test_preview_enter_writes_audit(tmp_path: Path) -> None:
    client, repo = _client(tmp_path)
    _enter_preview(client, "free_cap")
    row = repo.conn.execute(
        "SELECT before_state, after_state FROM admin_audit_log WHERE action = 'preview_enter'"
    ).fetchone()
    assert row is not None
    assert '"state": "free_cap"' in row["after_state"]
