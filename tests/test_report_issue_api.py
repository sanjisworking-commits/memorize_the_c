"""V1 Report Issue API — validation + insert via injected fake repository."""

from __future__ import annotations

import inspect
import re
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from constitution_memorizer.auth.fake_provider import FakeAuthProvider
from constitution_memorizer.auth.sessions import InMemorySessionStore
from constitution_memorizer.multiuser.settings import MultiUserSettings, clear_settings_cache
from constitution_memorizer.reports.repository import (
    IssueReport,
    PostgresIssueReportRepository,
)
from constitution_memorizer.web.app import create_app

MINI_UNITS = Path(__file__).parent / "fixtures" / "learning" / "mini_units.json"
FIXED_ID = UUID("aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee")


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


class FakeIssueReportRepository:
    """In-memory stand-in; records create_report kwargs."""

    def __init__(self, *, fail: bool = False, status: str = "new") -> None:
        self.calls: list[dict] = []
        self.fail = fail
        self.status = status

    def create_report(self, **kwargs) -> IssueReport:
        self.calls.append(kwargs)
        if self.fail:
            raise RuntimeError("simulated database failure: connection refused")
        return IssueReport(
            id=FIXED_ID,
            status=self.status,
            created_at=datetime(2026, 8, 10, 12, 0, tzinfo=timezone.utc),
        )


def _client(
    tmp_path: Path,
    *,
    repo: FakeIssueReportRepository | None | object = ...,
    multiuser: bool = True,
) -> TestClient:
    kwargs: dict = {
        "units_path": MINI_UNITS,
        "db_path": tmp_path / "progress.db",
        "multiuser": multiuser,
        "multiuser_settings": _settings(),
        "auth_provider": FakeAuthProvider(),
        "session_store": InMemorySessionStore(),
    }
    if repo is not ...:
        kwargs["issue_report_repo"] = repo
    return TestClient(create_app(**kwargs))


def _valid_body(**overrides) -> dict:
    body = {
        "article_number": "55",
        "section": "Explanation",
        "selected_text": "Population means...",
        "issue_type": "incorrect_fact",
        "description": "This appears to use the wrong census reference.",
        "suggested_correction": "Suggested wording...",
        "source_url": "https://example.com/source",
        "reporter_email": "reader@example.com",
        "page_url": "/browse/article/55",
    }
    body.update(overrides)
    return body


def test_valid_report_returns_201_with_uuid_and_new_status(tmp_path: Path):
    repo = FakeIssueReportRepository()
    client = _client(tmp_path, repo=repo)
    resp = client.post("/api/report-issue", json=_valid_body())
    assert resp.status_code == 201
    data = resp.json()
    assert data["success"] is True
    assert data["report_id"] == str(FIXED_ID)
    assert data["status"] == "new"
    UUID(data["report_id"])  # valid UUID
    assert len(repo.calls) == 1
    assert repo.calls[0]["issue_type"] == "incorrect_fact"
    assert repo.calls[0]["description"].startswith("This appears")


def test_optional_fields_can_be_omitted(tmp_path: Path):
    repo = FakeIssueReportRepository()
    client = _client(tmp_path, repo=repo)
    resp = client.post(
        "/api/report-issue",
        json={
            "issue_type": "typo",
            "description": "Missing hyphen in Bare Act quote.",
            "page_url": "/browse/article/21",
        },
    )
    assert resp.status_code == 201
    call = repo.calls[0]
    assert call["article_number"] is None
    assert call["section"] is None
    assert call["selected_text"] is None
    assert call["suggested_correction"] is None
    assert call["source_url"] is None
    assert call["reporter_email"] is None
    assert call["page_url"] == "/browse/article/21"


def test_invalid_issue_type_rejected(tmp_path: Path):
    repo = FakeIssueReportRepository()
    client = _client(tmp_path, repo=repo)
    resp = client.post(
        "/api/report-issue",
        json=_valid_body(issue_type="not_a_real_type"),
    )
    assert resp.status_code == 422
    assert repo.calls == []


def test_missing_description_rejected(tmp_path: Path):
    repo = FakeIssueReportRepository()
    client = _client(tmp_path, repo=repo)
    body = _valid_body()
    del body["description"]
    resp = client.post("/api/report-issue", json=body)
    assert resp.status_code == 422
    assert repo.calls == []


def test_blank_description_rejected(tmp_path: Path):
    repo = FakeIssueReportRepository()
    client = _client(tmp_path, repo=repo)
    resp = client.post(
        "/api/report-issue",
        json=_valid_body(description="   "),
    )
    assert resp.status_code == 422
    assert repo.calls == []


def test_missing_page_url_rejected(tmp_path: Path):
    repo = FakeIssueReportRepository()
    client = _client(tmp_path, repo=repo)
    body = _valid_body()
    del body["page_url"]
    resp = client.post("/api/report-issue", json=body)
    assert resp.status_code == 422
    assert repo.calls == []


def test_invalid_reporter_email_rejected(tmp_path: Path):
    repo = FakeIssueReportRepository()
    client = _client(tmp_path, repo=repo)
    resp = client.post(
        "/api/report-issue",
        json=_valid_body(reporter_email="not-an-email"),
    )
    assert resp.status_code == 422
    assert repo.calls == []


def test_empty_reporter_email_treated_as_absent(tmp_path: Path):
    repo = FakeIssueReportRepository()
    client = _client(tmp_path, repo=repo)
    resp = client.post(
        "/api/report-issue",
        json=_valid_body(reporter_email="  "),
    )
    assert resp.status_code == 201
    assert repo.calls[0]["reporter_email"] is None


def test_repository_unavailable_returns_503(tmp_path: Path):
    client = _client(tmp_path, repo=None)
    resp = client.post("/api/report-issue", json=_valid_body())
    assert resp.status_code == 503
    assert resp.json()["detail"] == "Unable to submit report right now."


def test_database_failure_returns_generic_503(tmp_path: Path):
    repo = FakeIssueReportRepository(fail=True)
    client = _client(tmp_path, repo=repo)
    resp = client.post("/api/report-issue", json=_valid_body())
    assert resp.status_code == 503
    detail = resp.json()["detail"]
    assert detail == "Unable to submit report right now."
    assert "psycopg" not in detail.lower()
    assert "connection refused" not in detail.lower()
    assert "simulated" not in detail.lower()


def test_guest_can_submit_without_authentication(tmp_path: Path):
    repo = FakeIssueReportRepository()
    client = _client(tmp_path, repo=repo, multiuser=True)
    # No session cookies — guest.
    resp = client.post("/api/report-issue", json=_valid_body(), follow_redirects=False)
    assert resp.status_code == 201
    assert resp.json()["success"] is True
    assert len(repo.calls) == 1


def test_repository_sql_is_parameterized():
    source = inspect.getsource(PostgresIssueReportRepository.create_report)
    assert "%s" in source
    assert "RETURNING id, status, created_at" in source
    # No f-string / format interpolation of user fields into SQL.
    assert 'f"' not in source
    assert ".format(" not in source
    # Nine placeholders for the nine inserted columns.
    assert source.count("%s") >= 9
    assert re.search(
        r"INSERT INTO issue_reports\s*\(",
        source,
        re.IGNORECASE,
    )


def test_create_app_wires_postgres_repo_from_database_url(tmp_path: Path):
    from unittest.mock import MagicMock, patch

    dsn = "postgresql://user:pass@localhost:5432/testdb"
    sentinel = MagicMock(name="issue_report_repo")
    with patch(
        "constitution_memorizer.web.app.PostgresIssueReportRepository",
        return_value=sentinel,
    ) as ctor:
        app = create_app(
            units_path=MINI_UNITS,
            db_path=tmp_path / "progress.db",
            multiuser=False,
            multiuser_settings=_settings(DATABASE_URL=dsn),
            auth_provider=FakeAuthProvider(),
            session_store=InMemorySessionStore(),
        )
    ctor.assert_called_once_with(dsn)
    assert app.state.issue_report_repo is sentinel


def test_create_app_leaves_repo_none_without_database_url(tmp_path: Path):
    app = create_app(
        units_path=MINI_UNITS,
        db_path=tmp_path / "progress.db",
        multiuser=False,
        multiuser_settings=_settings(DATABASE_URL=""),
        auth_provider=FakeAuthProvider(),
        session_store=InMemorySessionStore(),
    )
    assert app.state.issue_report_repo is None
