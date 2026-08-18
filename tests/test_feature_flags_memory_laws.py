"""MEMORY_LOG_ENABLED / RELEVANT_LAWS_ENABLED early 404 + UI gating."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from constitution_memorizer.auth.exceptions import AuthConfigError
from constitution_memorizer.auth.fake_provider import FakeAuthProvider
from constitution_memorizer.auth.sessions import InMemorySessionStore
from constitution_memorizer.multiuser.settings import MultiUserSettings, clear_settings_cache
from constitution_memorizer.progress.memory import MemoryEngine
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
        "MEMORY_LOG_ENABLED": "false",
        "RELEVANT_LAWS_ENABLED": "false",
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


def _client(tmp_path: Path, *, as_guest: bool = False, **overrides) -> TestClient:
    provider = FakeAuthProvider()
    app = create_app(
        units_path=MINI_UNITS,
        db_path=tmp_path / "progress.db",
        multiuser=True,
        multiuser_settings=_settings(**overrides),
        auth_provider=provider,
        session_store=InMemorySessionStore(),
    )
    client = TestClient(app)
    if not as_guest:
        _login(client, provider)
    return client


@pytest.mark.parametrize(
    "path",
    ["/memory", "/memory/foo", "/laws", "/laws/rti-2005"],
)
def test_disabled_prefixes_404_for_guest_without_login_redirect(
    tmp_path: Path, path: str
):
    client = _client(tmp_path, as_guest=True)
    resp = client.get(path, follow_redirects=False)
    assert resp.status_code == 404
    assert "/login" not in (resp.headers.get("location") or "")


@pytest.mark.parametrize(
    "path",
    ["/memory", "/memory/foo", "/laws", "/laws/rti-2005"],
)
def test_disabled_prefixes_404_for_signed_in_user(tmp_path: Path, path: str):
    client = _client(tmp_path, as_guest=False)
    resp = client.get(path, follow_redirects=False)
    assert resp.status_code == 404
    assert "/login" not in (resp.headers.get("location") or "")


def test_strict_prefix_does_not_match_memory_technique(tmp_path: Path):
    """Bare startswith('/memory') would incorrectly gate /memory-technique."""
    client = _client(tmp_path, as_guest=True)
    # No such route → still 404 from routing, but must not be feature-gated specially.
    # Ensure the gate only matches exact /memory or /memory/...
    app = create_app(
        units_path=MINI_UNITS,
        db_path=tmp_path / "progress2.db",
        multiuser=True,
        multiuser_settings=_settings(),
        auth_provider=FakeAuthProvider(),
        session_store=InMemorySessionStore(),
    )

    @app.get("/memory-technique")
    async def memory_technique():
        return {"ok": True}

    resp = TestClient(app).get("/memory-technique")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}


def test_no_memory_engine_when_flag_false(tmp_path: Path):
    app = create_app(
        units_path=MINI_UNITS,
        db_path=tmp_path / "progress.db",
        multiuser_settings=_settings(MEMORY_LOG_ENABLED="false"),
    )
    assert app.state.memory is None
    assert not isinstance(app.state.memory, MemoryEngine)


def test_memory_plus_postgres_fails_fast(tmp_path: Path):
    with pytest.raises(AuthConfigError, match="not supported with PostgreSQL"):
        create_app(
            units_path=MINI_UNITS,
            db_path=tmp_path / "progress.db",
            multiuser=True,
            multiuser_settings=_settings(
                MEMORY_LOG_ENABLED="true",
                DATABASE_URL="postgresql://user:pass@localhost:5432/db",
            ),
            auth_provider=FakeAuthProvider(),
            session_store=InMemorySessionStore(),
        )


def test_nav_and_footnote_gated_when_flags_false(tmp_path: Path):
    client = _client(tmp_path, as_guest=False)
    html = client.get("/dashboard").text
    assert 'href="/laws"' not in html
    assert 'href="/memory"' not in html
    assert "Memory log 1→3→7→14→30" not in html
    assert "Constitution 1→3→7→15→30→60" in html


def test_home_launcher_cards_gated(tmp_path: Path):
    # Single-user home with flags off
    app = create_app(
        units_path=MINI_UNITS,
        db_path=tmp_path / "progress.db",
        multiuser_settings=_settings(
            MULTIUSER_ENABLED="false",
            MEMORY_LOG_ENABLED="false",
            RELEVANT_LAWS_ENABLED="false",
        ),
    )
    html = TestClient(app).get("/").text
    assert "Relevant laws" not in html
    assert "Memory log" not in html.split("sheet-footnote")[0]
    assert 'href="/tables"' in html
