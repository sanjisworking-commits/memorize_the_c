"""Bundled request bootstrap seeds caches and collapses Postgres round trips."""

from __future__ import annotations

import logging
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from constitution_memorizer.auth.fake_provider import FakeAuthProvider
from constitution_memorizer.auth.sessions import InMemorySessionStore
from constitution_memorizer.learning.schemas import LearningUnitsDocument
from constitution_memorizer.multiuser.settings import MultiUserSettings, clear_settings_cache
from constitution_memorizer.progress.db import open_progress_db
from constitution_memorizer.progress.postgres_repository import PostgresProgressRepository
from constitution_memorizer.progress.repository import (
    DEFAULT_NEWS_ARTICLES,
    DEFAULT_THEME,
    ProgressRepository,
)
from constitution_memorizer.progress.scheduler import ReminderEngine
from constitution_memorizer.utils.json_io import read_json
from constitution_memorizer.web.app import create_app

MINI_UNITS = Path(__file__).parent / "fixtures" / "learning" / "mini_units.json"
USER = UUID("11111111-1111-4111-8111-111111111111")
USER_EMAIL = "a@example.com"


class CountingProgressRepo:
    def __init__(self, inner: ProgressRepository) -> None:
        self.inner = inner
        self.reset_counts()

    def __getattr__(self, name: str):
        return getattr(self.inner, name)

    def reset_counts(self) -> None:
        self.get_progress_calls = 0
        self.list_all_progress_calls = 0
        self.list_due_calls = 0
        self.count_by_status_calls = 0
        self.get_profile_calls = 0
        self.list_split_preferences_calls = 0
        self.get_split_preference_calls = 0
        self.get_theme_calls = 0
        self.get_news_articles_raw_calls = 0
        self.get_setting_calls = 0
        self.modes_seen_calls = 0
        self.load_request_bootstrap_calls = 0

    def get_progress(self, user_id, unit_id: str):
        self.get_progress_calls += 1
        return self.inner.get_progress(user_id, unit_id)

    def list_all_progress(self, user_id):
        self.list_all_progress_calls += 1
        return self.inner.list_all_progress(user_id)

    def list_due(self, user_id, as_of, *, include_new: bool = False):
        self.list_due_calls += 1
        return self.inner.list_due(user_id, as_of, include_new=include_new)

    def count_by_status(self, user_id):
        self.count_by_status_calls += 1
        return self.inner.count_by_status(user_id)

    def get_profile(self, user_id):
        self.get_profile_calls += 1
        return self.inner.get_profile(user_id)

    def list_split_preferences(self, user_id):
        self.list_split_preferences_calls += 1
        return self.inner.list_split_preferences(user_id)

    def get_split_preference(self, user_id, parent_clause_id: str):
        self.get_split_preference_calls += 1
        return self.inner.get_split_preference(user_id, parent_clause_id)

    def get_theme(self, user_id):
        self.get_theme_calls += 1
        return self.inner.get_theme(user_id)

    def get_news_articles_raw(self, user_id):
        self.get_news_articles_raw_calls += 1
        return self.inner.get_news_articles_raw(user_id)

    def get_setting(self, user_id, key: str):
        self.get_setting_calls += 1
        return self.inner.get_setting(user_id, key)

    def modes_seen(self, user_id, unit_id: str):
        self.modes_seen_calls += 1
        return self.inner.modes_seen(user_id, unit_id)

    def load_request_bootstrap(self, user_id, *, include_profile=False, include_news=False):
        self.load_request_bootstrap_calls += 1
        return self.inner.load_request_bootstrap(
            user_id, include_profile=include_profile, include_news=include_news
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


def _catalog() -> dict:
    doc = LearningUnitsDocument.model_validate(read_json(MINI_UNITS))
    return {u.id: u for u in doc.units}


def _seeded_engine(tmp_path: Path) -> tuple[CountingProgressRepo, ReminderEngine]:
    conn = open_progress_db(tmp_path / "progress.db")
    repo = CountingProgressRepo(ProgressRepository(conn))
    engine = ReminderEngine.from_repository(repo, _catalog(), user_id=USER)
    engine.mark_all_modes_seen("clause-1")
    engine.mark_done("clause-1", as_of=date(2026, 7, 20))
    engine.set_split_preference("clause-2", "letters")
    engine.set_theme("dark")
    engine.set_news_articles_raw("14,21")
    engine._invalidate_progress_cache()
    engine._invalidate_split_cache()
    engine._invalidate_theme_cache()
    engine._invalidate_news_cache()
    repo.reset_counts()
    return repo, engine


def test_bootstrap_seeds_caches_and_matches_uncached(tmp_path: Path):
    repo, engine = _seeded_engine(tmp_path)
    as_of = date(2026, 7, 21)
    uncached = ReminderEngine.from_repository(repo.inner, engine.units, user_id=USER)
    expected_due = [row.learning_unit_id for row in uncached.due_today(as_of=as_of)]
    expected_stats = uncached.stats()
    expected_theme = uncached.get_theme()
    expected_news = uncached.get_news_articles_raw()
    repo.reset_counts()

    bundle = engine.bootstrap_request(include_news=True)
    assert repo.load_request_bootstrap_calls == 1
    repo.reset_counts()

    assert engine.get_theme() == expected_theme == "dark"
    assert engine.get_news_articles_raw() == expected_news == "14,21"
    assert engine.get_progress("clause-1") is not None
    assert engine.get_split_preference("clause-2") == "letters"
    assert [row.learning_unit_id for row in engine.due_today(as_of=as_of)] == expected_due
    assert engine.stats()["review"] == expected_stats["review"]
    assert engine.stats()["tracked"] == expected_stats["tracked"]
    assert bundle.theme == "dark"
    assert repo.get_theme_calls == 0
    assert repo.get_news_articles_raw_calls == 0
    assert repo.list_all_progress_calls == 0
    assert repo.list_split_preferences_calls == 0
    assert repo.list_due_calls == 0
    assert repo.count_by_status_calls == 0
    assert repo.get_split_preference_calls == 0
    assert repo.load_request_bootstrap_calls == 0


def test_empty_bootstrap_does_not_fallback(tmp_path: Path):
    conn = open_progress_db(tmp_path / "empty.db")
    repo = CountingProgressRepo(ProgressRepository(conn))
    engine = ReminderEngine.from_repository(repo, _catalog(), user_id=USER)
    engine.bootstrap_request(include_news=True)
    repo.reset_counts()
    assert engine._progress_cache == {}
    assert engine._split_cache == {}
    assert engine.get_theme() == DEFAULT_THEME
    assert engine.get_news_articles_raw() == DEFAULT_NEWS_ARTICLES
    assert engine.due_today(as_of=date(2026, 7, 21)) == []
    assert engine.stats()["tracked"] == 0
    assert repo.list_all_progress_calls == 0
    assert repo.list_due_calls == 0
    assert repo.count_by_status_calls == 0
    assert repo.get_theme_calls == 0
    assert repo.get_news_articles_raw_calls == 0


def test_loaded_empty_news_cache_does_not_query(tmp_path: Path):
    conn = open_progress_db(tmp_path / "news.db")
    repo = CountingProgressRepo(ProgressRepository(conn))
    engine = ReminderEngine.from_repository(repo, _catalog(), user_id=USER)
    engine._news_cache = ""
    assert engine.get_news_articles_raw() == ""
    assert repo.get_news_articles_raw_calls == 0
    assert repo.get_setting_calls == 0
    engine._news_cache = None
    assert engine.get_news_articles_raw() == DEFAULT_NEWS_ARTICLES
    assert repo.get_news_articles_raw_calls == 1


def _counting_client(tmp_path: Path) -> tuple[TestClient, CountingProgressRepo]:
    conn = open_progress_db(tmp_path / "progress.db")
    repo = CountingProgressRepo(ProgressRepository(conn))
    provider = FakeAuthProvider()
    provider.seed_google_user(
        user_id=USER,
        email=USER_EMAIL,
        display_name="Test User",
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
    cb = client.get(
        f"/auth/callback?code=fake-google-code&state={state}",
        follow_redirects=False,
    )
    assert cb.status_code == 303
    repo.reset_counts()
    return client, repo


def _breakdown_messages(caplog: logging.LogCaptureFixture) -> list[str]:
    return [
        record.getMessage()
        for record in caplog.records
        if record.getMessage().startswith("request_breakdown ")
    ]


def test_authenticated_dashboard_one_bootstrap(tmp_path: Path):
    client, repo = _counting_client(tmp_path)
    resp = client.get("/dashboard")
    assert resp.status_code == 200
    assert "Welcome, Test." in resp.text or "Good morning, Test." in resp.text
    assert repo.load_request_bootstrap_calls == 1
    assert repo.get_profile_calls == 0
    assert repo.list_all_progress_calls == 0
    assert repo.list_split_preferences_calls == 0
    assert repo.get_theme_calls == 0
    assert repo.list_due_calls == 0
    assert repo.modes_seen_calls <= 1


def test_authenticated_browse_one_bootstrap(tmp_path: Path):
    client, repo = _counting_client(tmp_path)
    resp = client.get("/browse")
    assert resp.status_code == 200
    assert repo.load_request_bootstrap_calls == 1
    assert repo.list_all_progress_calls == 0
    assert repo.list_split_preferences_calls == 0
    assert repo.get_news_articles_raw_calls == 0
    assert repo.get_theme_calls == 0
    assert repo.list_due_calls == 0


def test_guest_browse_does_not_bootstrap(tmp_path: Path):
    conn = open_progress_db(tmp_path / "progress.db")
    repo = CountingProgressRepo(ProgressRepository(conn))
    app = create_app(
        units_path=MINI_UNITS,
        db_path=tmp_path / "unused.db",
        multiuser=True,
        multiuser_settings=_settings(),
        auth_provider=FakeAuthProvider(),
        session_store=InMemorySessionStore(),
        progress_repo=repo,
    )
    client = TestClient(app)
    resp = client.get("/browse")
    assert resp.status_code == 200
    assert repo.load_request_bootstrap_calls == 0
    assert 'aria-label="' not in resp.text or "due or overdue" not in resp.text


def test_blank_profile_still_redirects_to_welcome(tmp_path: Path):
    client, repo = _counting_client(tmp_path)
    repo.inner.upsert_profile(USER, display_name="   ", avatar_url=None)
    repo.reset_counts()
    resp = client.get("/dashboard", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/welcome"
    assert repo.load_request_bootstrap_calls == 1


def test_dashboard_browse_breakdown_has_single_bootstrap(
    tmp_path: Path, caplog: logging.LogCaptureFixture
):
    client, _repo = _counting_client(tmp_path)
    with caplog.at_level(logging.INFO, logger="uvicorn.error"):
        caplog.clear()
        assert client.get("/dashboard").status_code == 200
        dash = _breakdown_messages(caplog)
        caplog.clear()
        assert client.get("/browse").status_code == 200
        browse = _breakdown_messages(caplog)
    assert len(dash) == 1
    assert "auth_session_n=1" in dash[0]
    assert "request_bootstrap_n=1" in dash[0]
    assert "progress_preload_" not in dash[0]
    assert "split_prefs_" not in dash[0]
    assert "theme_" not in dash[0]
    assert len(browse) == 1
    assert "request_bootstrap_n=1" in browse[0]
    assert "news_setting_" not in browse[0]
    assert "theme_" not in browse[0]


class _FakeCursor:
    def __init__(self, conn: "_FakeConnection") -> None:
        self.conn = conn
        self.closed = False
        self._kind: str | None = None

    def __enter__(self) -> "_FakeCursor":
        return self

    def __exit__(self, *exc: object) -> None:
        self.closed = True

    def execute(self, sql: str, params=None) -> None:
        self.conn.events.append(("execute", sql, params))
        text = " ".join(sql.split()).lower()
        if "learning_unit_progress" in text:
            self._kind = "progress"
        elif "split_preference" in text:
            self._kind = "split"
        elif "app_settings" in text and params and params[-1] == "theme":
            self._kind = "theme"
        elif "app_settings" in text:
            self._kind = "news"
        elif "user_profile" in text:
            self._kind = "profile"
        else:
            self._kind = "other"

    def fetchall(self):
        self.conn.events.append(("fetchall", self._kind))
        return list(self.conn.results.get(self._kind, []))

    def fetchone(self):
        self.conn.events.append(("fetchone", self._kind))
        rows = self.conn.results.get(self._kind, [])
        return rows[0] if rows else None


class _FakeConnection:
    def __init__(self, results: dict[str, list]) -> None:
        self.results = results
        self.events: list[tuple] = []
        self.cursors: list[_FakeCursor] = []
        self.pipeline_entries = 0

    def cursor(self, row_factory=None):
        cur = _FakeCursor(self)
        self.cursors.append(cur)
        return cur

    @contextmanager
    def pipeline(self):
        self.pipeline_entries += 1
        self.events.append(("pipeline_enter",))
        yield
        self.events.append(("pipeline_exit",))

    def __enter__(self) -> "_FakeConnection":
        return self

    def __exit__(self, *exc: object) -> None:
        return None


class _FakePool:
    def __init__(self, conn: _FakeConnection) -> None:
        self.conn = conn
        self.borrows = 0

    @contextmanager
    def connection(self):
        self.borrows += 1
        yield self.conn


def _progress_row() -> dict:
    return {
        "learning_unit_id": "clause-1",
        "status": "review",
        "times_completed": 1,
        "last_completed": date(2026, 7, 20),
        "next_revision": date(2026, 7, 21),
        "interval_days": 1,
        "ease_factor": 2.5,
        "created_at": "2026-07-20T00:00:00+00:00",
        "updated_at": "2026-07-20T00:00:00+00:00",
    }


def test_postgres_pipeline_queues_executes_before_fetch(monkeypatch: pytest.MonkeyPatch):
    conn = _FakeConnection(
        {
            "progress": [_progress_row()],
            "split": [{"parent_clause_id": "clause-2", "mode": "letters"}],
            "theme": [{"value": "dark"}],
            "news": [{"value": "14"}],
            "profile": [
                {
                    "user_id": USER,
                    "display_name": "Ada",
                    "avatar_url": None,
                    "created_at": "2026-07-20T00:00:00+00:00",
                    "updated_at": "2026-07-20T00:00:00+00:00",
                }
            ],
        }
    )
    pool = _FakePool(conn)
    monkeypatch.setattr(
        "constitution_memorizer.progress.postgres_repository._pipeline_supported",
        lambda: True,
    )
    repo = PostgresProgressRepository(pool)
    bundle = repo.load_request_bootstrap(USER, include_profile=True, include_news=True)
    assert pool.borrows == 1
    assert conn.pipeline_entries == 1
    kinds = [event[0] for event in conn.events]
    first_fetch = next(
        i for i, kind in enumerate(kinds) if kind in {"fetchall", "fetchone"}
    )
    assert kinds[:first_fetch].count("execute") == 5
    assert "fetchall" not in kinds[:first_fetch]
    assert "fetchone" not in kinds[:first_fetch]
    assert all(cur.closed for cur in conn.cursors)
    assert len(bundle.progress) == 1
    assert bundle.progress[0].learning_unit_id == "clause-1"
    assert bundle.split_preferences == {"clause-2": "letters"}
    assert bundle.theme == "dark"
    assert bundle.news_articles_raw == "14"
    assert bundle.profile is not None
    assert bundle.profile["display_name"] == "Ada"


def test_postgres_fallback_without_pipeline_preserves_semantics(
    monkeypatch: pytest.MonkeyPatch,
):
    conn = _FakeConnection(
        {
            "progress": [],
            "split": [],
            "theme": [],
            "news": [],
        }
    )
    pool = _FakePool(conn)
    monkeypatch.setattr(
        "constitution_memorizer.progress.postgres_repository._pipeline_supported",
        lambda: False,
    )
    repo = PostgresProgressRepository(pool)
    bundle = repo.load_request_bootstrap(USER, include_news=True)
    assert pool.borrows == 1
    assert conn.pipeline_entries == 0
    assert bundle.progress == []
    assert bundle.split_preferences == {}
    assert bundle.theme == DEFAULT_THEME
    assert bundle.news_articles_raw == DEFAULT_NEWS_ARTICLES
    assert bundle.profile is None
    assert all(cur.closed for cur in conn.cursors)
