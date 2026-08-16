"""Learn/Choose reuse request bootstrap; POST Choose is one lean write."""

from __future__ import annotations

import logging
from pathlib import Path
from uuid import UUID

from fastapi.testclient import TestClient

from constitution_memorizer.auth.fake_provider import FakeAuthProvider
from constitution_memorizer.auth.sessions import InMemorySessionStore
from constitution_memorizer.learning.schemas import LearningUnitsDocument
from constitution_memorizer.multiuser.settings import MultiUserSettings, clear_settings_cache
from constitution_memorizer.progress.db import open_progress_db
from constitution_memorizer.progress.repository import ProgressRepository
from constitution_memorizer.progress.scheduler import ReminderEngine
from constitution_memorizer.utils.json_io import read_json
from constitution_memorizer.web.app import create_app

MINI_UNITS = Path(__file__).parent / "fixtures" / "learning" / "mini_units.json"
USER = UUID("11111111-1111-4111-8111-111111111111")
USER_EMAIL = "a@example.com"


class CountingProgressRepo:
    def __init__(self, inner: ProgressRepository) -> None:
        self.inner = inner
        self.load_request_bootstrap_calls = 0
        self.list_all_progress_calls = 0
        self.list_split_preferences_calls = 0
        self.get_split_preference_calls = 0
        self.set_split_preference_calls = 0
        self.get_theme_calls = 0
        self.mark_mode_seen_calls = 0
        self.get_progress_calls = 0

    def __getattr__(self, name: str):
        return getattr(self.inner, name)

    def load_request_bootstrap(self, user_id, *, include_profile=False, include_news=False):
        self.load_request_bootstrap_calls += 1
        return self.inner.load_request_bootstrap(
            user_id, include_profile=include_profile, include_news=include_news
        )

    def list_all_progress(self, user_id):
        self.list_all_progress_calls += 1
        return self.inner.list_all_progress(user_id)

    def list_split_preferences(self, user_id):
        self.list_split_preferences_calls += 1
        return self.inner.list_split_preferences(user_id)

    def get_split_preference(self, user_id, parent_clause_id: str):
        self.get_split_preference_calls += 1
        return self.inner.get_split_preference(user_id, parent_clause_id)

    def set_split_preference(self, user_id, parent_clause_id: str, mode: str):
        self.set_split_preference_calls += 1
        return self.inner.set_split_preference(user_id, parent_clause_id, mode)

    def get_theme(self, user_id):
        self.get_theme_calls += 1
        return self.inner.get_theme(user_id)

    def mark_mode_seen(self, user_id, unit_id: str, mode: str):
        self.mark_mode_seen_calls += 1
        return self.inner.mark_mode_seen(user_id, unit_id, mode)

    def get_progress(self, user_id, unit_id: str):
        self.get_progress_calls += 1
        return self.inner.get_progress(user_id, unit_id)

    def reset_counts(self) -> None:
        self.load_request_bootstrap_calls = 0
        self.list_all_progress_calls = 0
        self.list_split_preferences_calls = 0
        self.get_split_preference_calls = 0
        self.set_split_preference_calls = 0
        self.get_theme_calls = 0
        self.mark_mode_seen_calls = 0
        self.get_progress_calls = 0


def _catalog() -> dict:
    doc = LearningUnitsDocument.model_validate(read_json(MINI_UNITS))
    return {u.id: u for u in doc.units}


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
    )


def _app(tmp_path: Path, repo: CountingProgressRepo, *, login: bool) -> TestClient:
    clear_settings_cache()
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
    if login:
        start = client.get("/auth/google/start", follow_redirects=False)
        state = start.cookies.get("rtc_oauth_state")
        cb = client.get(
            f"/auth/callback?code=fake-google-code&state={state}",
            follow_redirects=False,
        )
        assert cb.status_code == 303
    repo.reset_counts()
    return client


def _authed(tmp_path: Path) -> tuple[TestClient, CountingProgressRepo]:
    conn = open_progress_db(tmp_path / "progress.db")
    repo = CountingProgressRepo(ProgressRepository(conn))
    return _app(tmp_path, repo, login=True), repo


def _guest(tmp_path: Path) -> tuple[TestClient, CountingProgressRepo]:
    conn = open_progress_db(tmp_path / "progress.db")
    repo = CountingProgressRepo(ProgressRepository(conn))
    return _app(tmp_path, repo, login=False), repo


def _engine(tmp_path: Path) -> tuple[CountingProgressRepo, ReminderEngine]:
    conn = open_progress_db(tmp_path / "progress.db")
    repo = CountingProgressRepo(ProgressRepository(conn))
    return repo, ReminderEngine.from_repository(repo, _catalog())


def _breakdown_messages(caplog: logging.LogCaptureFixture) -> list[str]:
    return [
        record.getMessage()
        for record in caplog.records
        if record.getMessage().startswith("request_breakdown ")
    ]


def test_authenticated_learn_get_bootstraps_once(tmp_path: Path, caplog):
    client, repo = _authed(tmp_path)
    with caplog.at_level(logging.INFO, logger="uvicorn.error"):
        caplog.clear()
        resp = client.get("/learn/clause-1")
    assert resp.status_code == 200
    assert "Article 20(1)" in resp.text
    assert repo.load_request_bootstrap_calls == 1
    assert repo.mark_mode_seen_calls == 1
    assert repo.list_all_progress_calls == 0
    assert repo.list_split_preferences_calls == 0
    assert repo.get_theme_calls == 0
    messages = _breakdown_messages(caplog)
    assert len(messages) == 1
    line = messages[0]
    assert "request_bootstrap_n=1" in line
    assert "mode_seen_write_n=1" in line
    assert "learn_build_n=1" in line
    assert "template_n=1" in line
    assert "progress_preload_n=" not in line
    assert "split_prefs_n=" not in line
    assert "theme_n=" not in line


def test_authenticated_learn_split_redirect_unchanged(tmp_path: Path, caplog):
    client, repo = _authed(tmp_path)
    with caplog.at_level(logging.INFO, logger="uvicorn.error"):
        caplog.clear()
        resp = client.get("/learn/clause-2", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/learn/clause-2/choose"
    assert repo.load_request_bootstrap_calls == 1
    assert repo.mark_mode_seen_calls == 0
    messages = _breakdown_messages(caplog)
    assert len(messages) == 1
    line = messages[0]
    assert "request_bootstrap_n=1" in line
    assert "learn_build_" not in line
    assert "mode_seen_write_" not in line


def test_authenticated_choose_get_bootstraps_once(tmp_path: Path, caplog):
    client, repo = _authed(tmp_path)
    with caplog.at_level(logging.INFO, logger="uvicorn.error"):
        caplog.clear()
        resp = client.get("/learn/clause-2/choose")
    assert resp.status_code == 200
    assert "Learn whole clause" in resp.text
    assert "Split into letters" in resp.text
    assert repo.load_request_bootstrap_calls == 1
    assert repo.list_split_preferences_calls == 0
    assert repo.list_all_progress_calls == 0
    assert repo.get_theme_calls == 0
    assert repo.mark_mode_seen_calls == 0
    messages = _breakdown_messages(caplog)
    assert len(messages) == 1
    line = messages[0]
    assert "request_bootstrap_n=1" in line
    assert "completion_n=1" in line
    assert "template_n=1" in line
    assert "split_prefs_n=" not in line
    assert "progress_preload_n=" not in line
    assert "theme_n=" not in line
    assert "mode_seen_write_" not in line


def test_guest_learn_get_does_not_bootstrap(tmp_path: Path):
    client, repo = _guest(tmp_path)
    resp = client.get("/learn/clause-1")
    assert resp.status_code == 200
    assert "learning as a guest" in resp.text.lower()
    assert "guest-signin-modal" in resp.text
    assert repo.load_request_bootstrap_calls == 0
    assert repo.mark_mode_seen_calls == 0


def test_guest_choose_get_does_not_bootstrap(tmp_path: Path):
    client, repo = _guest(tmp_path)
    resp = client.get("/learn/clause-2/choose")
    assert resp.status_code == 200
    assert "Learn whole clause" in resp.text
    assert repo.load_request_bootstrap_calls == 0


def test_lean_set_split_preference_leaves_cold_cache(tmp_path: Path):
    repo, engine = _engine(tmp_path)
    assert engine._split_cache is None
    engine.set_split_preference("clause-2", "letters")
    assert engine._split_cache is None
    assert repo.set_split_preference_calls == 1
    assert repo.list_split_preferences_calls == 0


def test_lean_set_split_preference_updates_warm_cache(tmp_path: Path):
    repo, engine = _engine(tmp_path)
    engine._split_cache = {"another-clause": "whole"}
    engine.set_split_preference("clause-2", "letters")
    assert engine._split_cache == {
        "another-clause": "whole",
        "clause-2": "letters",
    }
    assert repo.set_split_preference_calls == 1
    assert repo.list_split_preferences_calls == 0


def test_explicit_mode_navigation_does_not_read_prefs(tmp_path: Path):
    repo, engine = _engine(tmp_path)
    assert engine.next_to_learn_from_clause("clause-2", mode="whole") == "clause-2"
    assert engine.next_to_learn_from_clause("clause-2", mode="letters") == "clause-2-a"
    assert repo.list_split_preferences_calls == 0
    assert repo.get_split_preference_calls == 0


def test_no_override_next_to_learn_from_clause_unchanged(tmp_path: Path):
    repo, engine = _engine(tmp_path)
    assert engine.next_to_learn_from_clause("clause-2") == "clause-2"
    engine.set_split_preference("clause-2", "letters")
    assert engine.next_to_learn_from_clause("clause-2") == "clause-2-a"
    assert repo.set_split_preference_calls == 1


def test_choose_post_whole_is_one_write(tmp_path: Path, caplog):
    client, repo = _authed(tmp_path)
    with caplog.at_level(logging.INFO, logger="uvicorn.error"):
        caplog.clear()
        resp = client.post(
            "/learn/clause-2/choose",
            data={"mode": "whole"},
            follow_redirects=False,
        )
    assert resp.status_code == 303
    assert resp.headers["location"] == "/learn/clause-2"
    assert repo.set_split_preference_calls == 1
    assert repo.load_request_bootstrap_calls == 0
    assert repo.list_split_preferences_calls == 0
    assert repo.get_split_preference_calls == 0
    messages = _breakdown_messages(caplog)
    assert len(messages) == 1
    line = messages[0]
    assert "split_write_n=1" in line
    assert "request_bootstrap_n=" not in line
    assert "split_prefs_n=" not in line


def test_choose_post_letters_is_one_write(tmp_path: Path, caplog):
    client, repo = _authed(tmp_path)
    with caplog.at_level(logging.INFO, logger="uvicorn.error"):
        caplog.clear()
        resp = client.post(
            "/learn/clause-2/choose",
            data={"mode": "letters"},
            follow_redirects=False,
        )
    assert resp.status_code == 303
    assert resp.headers["location"] == "/learn/clause-2-a"
    assert repo.set_split_preference_calls == 1
    assert repo.load_request_bootstrap_calls == 0
    assert repo.list_split_preferences_calls == 0
    messages = _breakdown_messages(caplog)
    assert len(messages) == 1
    line = messages[0]
    assert "split_write_n=1" in line
    assert "request_bootstrap_n=" not in line
    assert "split_prefs_n=" not in line
