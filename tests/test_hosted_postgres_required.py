"""Hosted multi-user must fail closed without a PostgreSQL DATABASE_URL."""

from __future__ import annotations

from pathlib import Path

import pytest

from constitution_memorizer.auth.exceptions import AuthConfigError
from constitution_memorizer.auth.fake_provider import FakeAuthProvider
from constitution_memorizer.auth.sessions import InMemorySessionStore
from constitution_memorizer.multiuser.settings import MultiUserSettings, clear_settings_cache
from constitution_memorizer.progress.postgres_repository import PostgresProgressRepository
from constitution_memorizer.web.app import create_app

MINI_UNITS = Path(__file__).parent / "fixtures" / "learning" / "mini_units.json"


@pytest.fixture(autouse=True)
def _clear_settings():
    clear_settings_cache()
    yield
    clear_settings_cache()


def _settings(**overrides) -> MultiUserSettings:
    base = {
        "APP_ENV": "production",
        "MULTIUSER_ENABLED": "true",
        "AUTH_GOOGLE_ENABLED": "true",
        "AUTH_PHONE_ENABLED": "true",
        "SESSION_SECRET": "test-secret",
        "SUPABASE_URL": "http://example.invalid",
        "SUPABASE_ANON_KEY": "anon",
        "DATABASE_URL": "postgresql://user:pass@localhost:5432/db",
        "COOKIE_SECURE": "true",
        "MEMORY_LOG_ENABLED": "false",
    }
    base.update({k: str(v) for k, v in overrides.items()})
    return MultiUserSettings(_env_file=None, **base)


def test_production_multiuser_postgresql_allowed(tmp_path: Path):
    app = create_app(
        units_path=MINI_UNITS,
        db_path=tmp_path / "progress.db",
        multiuser=True,
        multiuser_settings=_settings(
            APP_ENV="production",
            DATABASE_URL="postgresql://user:pass@localhost:5432/db",
        ),
        auth_provider=FakeAuthProvider(),
        session_store=InMemorySessionStore(),
    )
    assert isinstance(app.state.engine.repo, PostgresProgressRepository)
    assert app.state.use_postgres_progress is True


def test_production_multiuser_sqlite_url_fails(tmp_path: Path):
    with pytest.raises(AuthConfigError, match="PostgreSQL"):
        create_app(
            units_path=MINI_UNITS,
            db_path=tmp_path / "progress.db",
            multiuser=True,
            multiuser_settings=_settings(
                APP_ENV="production",
                DATABASE_URL="sqlite:///tmp/progress.db",
            ),
            auth_provider=FakeAuthProvider(),
            session_store=InMemorySessionStore(),
        )


@pytest.mark.parametrize(
    "url",
    ["", "mysql://user:pass@localhost/db", "postgres://user:pass@localhost/db", "not-a-url"],
)
def test_production_multiuser_non_postgres_url_fails(tmp_path: Path, url: str):
    with pytest.raises(AuthConfigError, match="PostgreSQL"):
        create_app(
            units_path=MINI_UNITS,
            db_path=tmp_path / "progress.db",
            multiuser=True,
            multiuser_settings=_settings(APP_ENV="production", DATABASE_URL=url),
            auth_provider=FakeAuthProvider(),
            session_store=InMemorySessionStore(),
        )


def test_staging_multiuser_empty_database_url_fails(tmp_path: Path):
    with pytest.raises(AuthConfigError, match="PostgreSQL"):
        create_app(
            units_path=MINI_UNITS,
            db_path=tmp_path / "progress.db",
            multiuser=True,
            multiuser_settings=_settings(APP_ENV="staging", DATABASE_URL=""),
            auth_provider=FakeAuthProvider(),
            session_store=InMemorySessionStore(),
        )


def test_development_single_user_sqlite_still_allowed(tmp_path: Path):
    app = create_app(
        units_path=MINI_UNITS,
        db_path=tmp_path / "progress.db",
        multiuser=False,
        multiuser_settings=_settings(
            APP_ENV="development",
            MULTIUSER_ENABLED="false",
            DATABASE_URL="",
        ),
    )
    assert app.state.use_postgres_progress is False
    assert app.state.engine.repo is not None
