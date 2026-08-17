"""Admin Reports/Contact inboxes: filters, transitions, audit, degradation."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from constitution_memorizer.admin.service import AdminService
from constitution_memorizer.auth.fake_provider import FakeAuthProvider
from constitution_memorizer.auth.sessions import InMemorySessionStore
from constitution_memorizer.multiuser.settings import (
    MultiUserSettings,
    clear_settings_cache,
)
from constitution_memorizer.progress.db import open_progress_db
from constitution_memorizer.progress.repository import ProgressRepository
from constitution_memorizer.reports.contact_repository import ContactMessage
from constitution_memorizer.reports.repository import IssueReportRow
from constitution_memorizer.web.app import create_app

MINI_UNITS = Path(__file__).parent / "fixtures" / "learning" / "mini_units.json"
ADMIN = UUID("77777777-7777-4777-8777-777777777777")


@pytest.fixture(autouse=True)
def _fresh_settings():
    clear_settings_cache()
    yield
    clear_settings_cache()


class FakeIssueReportInbox:
    """Insert-free fake with the admin-inbox surface of the Postgres repo."""

    def __init__(self, rows: list[IssueReportRow] | None = None) -> None:
        self.rows = {r.id: r for r in (rows or [])}
        self.audits: list = []

    def list_reports(self, *, status=None, limit=50, offset=0):
        items = [r for r in self.rows.values() if status is None or r.status == status]
        return items[offset : offset + limit]

    def get_report(self, report_id: str):
        return self.rows.get(report_id)

    def count_by_status(self, status: str) -> int:
        return sum(1 for r in self.rows.values() if r.status == status)

    def update_status(self, report_id, status, *, audit=None):
        row = self.rows.get(report_id)
        if row is None:
            return None
        before = row.status
        self.rows[report_id] = IssueReportRow(
            **{**row.__dict__, "status": status}
        )
        if audit is not None:
            self.audits.append(audit)
        return (before, status)


class FakeContactInbox:
    def __init__(self, rows: list[ContactMessage] | None = None) -> None:
        self.rows = {str(r.id): r for r in (rows or [])}
        self.audits: list = []

    def list_messages(self, *, status=None, limit=50, offset=0):
        items = [r for r in self.rows.values() if status is None or r.status == status]
        return items[offset : offset + limit]

    def get_message(self, message_id: str):
        return self.rows.get(message_id)

    def count_by_status(self, status: str) -> int:
        return sum(1 for r in self.rows.values() if r.status == status)

    def update_status(self, message_id, status, *, audit=None):
        row = self.rows.get(message_id)
        if row is None:
            return None
        before = row.status
        self.rows[message_id] = ContactMessage(
            id=row.id,
            status=status,
            created_at=row.created_at,
            topic=row.topic,
            message=row.message,
            page_url=row.page_url,
            reporter_email=row.reporter_email,
        )
        if audit is not None:
            self.audits.append(audit)
        return (before, status)


def _report(status: str = "new") -> IssueReportRow:
    return IssueReportRow(
        id=str(uuid4()),
        article_number="19",
        section="19(1)(a)",
        selected_text=None,
        issue_type="text_error",
        description="Cloze blanks the wrong clause.",
        suggested_correction=None,
        source_url=None,
        reporter_email="a@example.com",
        page_url="/learn/x",
        status=status,
        created_at=datetime(2026, 8, 17, 8, 12, tzinfo=timezone.utc).isoformat(),
    )


def _contact(status: str = "new") -> ContactMessage:
    return ContactMessage(
        id=uuid4(),
        status=status,
        created_at=datetime(2026, 8, 17, 7, 55, tzinfo=timezone.utc),
        topic="general_feedback",
        message="Bought the 30-day pass twice by mistake.",
        page_url=None,
        reporter_email="v@example.com",
    )


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
        ADMIN_ENABLED="true",
    )


def _admin_client(
    tmp_path: Path,
    *,
    report_repo=None,
    contact_repo=None,
) -> TestClient:
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
        issue_report_repo=report_repo,
        contact_message_repo=contact_repo,
    )
    client = TestClient(app)
    start = client.get("/auth/google/start", follow_redirects=False)
    state = start.cookies.get("rtc_oauth_state")
    client.get(
        f"/auth/callback?code=fake-google-code&state={state}",
        follow_redirects=False,
    )
    repo.conn.execute(
        "INSERT INTO user_roles (user_id, role, created_at) VALUES (?, 'admin', ?)",
        (str(ADMIN), datetime.now(timezone.utc).isoformat()),
    )
    repo.conn.commit()
    return client


def test_reports_inbox_lists_and_filters(tmp_path: Path) -> None:
    inbox = FakeIssueReportInbox([_report("new"), _report("reviewing"), _report("fixed")])
    client = _admin_client(tmp_path, report_repo=inbox)
    page = client.get("/admin/reports")
    assert page.status_code == 200
    assert "Cloze blanks the wrong clause." in page.text
    filtered = client.get("/admin/reports", params={"status": "resolved"})
    assert filtered.text.count("Reopen") == 1
    # Contact has no dismissed chip; reports does.
    assert 'status=dismissed' in page.text


def test_valid_transition_writes_audit(tmp_path: Path) -> None:
    row = _report("new")
    inbox = FakeIssueReportInbox([row])
    client = _admin_client(tmp_path, report_repo=inbox)
    csrf = client.cookies.get("rtc_csrf")
    resp = client.post(
        f"/admin/reports/{row.id}/status",
        data={"csrf_token": csrf, "status": "reviewing"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert inbox.rows[row.id].status == "reviewing"
    assert len(inbox.audits) == 1
    audit = inbox.audits[0]
    assert audit.action == "report_status_change"
    assert audit.before_state == {"status": "new"}
    assert audit.after_state == {"status": "reviewing"}


def test_reopen_terminal_to_new_allowed(tmp_path: Path) -> None:
    row = _report("rejected")
    inbox = FakeIssueReportInbox([row])
    client = _admin_client(tmp_path, report_repo=inbox)
    csrf = client.cookies.get("rtc_csrf")
    resp = client.post(
        f"/admin/reports/{row.id}/status",
        data={"csrf_token": csrf, "status": "new"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert inbox.rows[row.id].status == "new"


def test_invalid_transition_400(tmp_path: Path) -> None:
    row = _report("fixed")
    inbox = FakeIssueReportInbox([row])
    client = _admin_client(tmp_path, report_repo=inbox)
    csrf = client.cookies.get("rtc_csrf")
    resp = client.post(
        f"/admin/reports/{row.id}/status",
        data={"csrf_token": csrf, "status": "reviewing"},
    )
    assert resp.status_code == 400
    assert inbox.rows[row.id].status == "fixed"
    assert inbox.audits == []


def test_contact_dismiss_refused(tmp_path: Path) -> None:
    # Contact has no "rejected" value — the service refuses it with a 400
    # (and the UI never renders that button for contact rows).
    msg = _contact("new")
    inbox = FakeContactInbox([msg])
    client = _admin_client(tmp_path, contact_repo=inbox)
    csrf = client.cookies.get("rtc_csrf")
    resp = client.post(
        f"/admin/contact/{msg.id}/status",
        data={"csrf_token": csrf, "status": "rejected"},
    )
    assert resp.status_code == 400
    page = client.get("/admin/contact")
    assert ">Dismiss</button>" not in page.text


def test_contact_resolve_and_reopen(tmp_path: Path) -> None:
    msg = _contact("new")
    inbox = FakeContactInbox([msg])
    client = _admin_client(tmp_path, contact_repo=inbox)
    csrf = client.cookies.get("rtc_csrf")
    ok = client.post(
        f"/admin/contact/{msg.id}/status",
        data={"csrf_token": csrf, "status": "resolved"},
        follow_redirects=False,
    )
    assert ok.status_code == 303
    assert inbox.rows[str(msg.id)].status == "resolved"
    reopen = client.post(
        f"/admin/contact/{msg.id}/status",
        data={"csrf_token": csrf, "status": "new"},
        follow_redirects=False,
    )
    assert reopen.status_code == 303
    assert inbox.rows[str(msg.id)].status == "new"
    assert [a.action for a in inbox.audits] == [
        "contact_status_change",
        "contact_status_change",
    ]


def test_unknown_id_404(tmp_path: Path) -> None:
    client = _admin_client(tmp_path, report_repo=FakeIssueReportInbox())
    csrf = client.cookies.get("rtc_csrf")
    resp = client.post(
        f"/admin/reports/{uuid4()}/status",
        data={"csrf_token": csrf, "status": "reviewing"},
    )
    assert resp.status_code == 404


def test_repo_none_degrades(tmp_path: Path) -> None:
    client = _admin_client(tmp_path)
    page = client.get("/admin/reports")
    assert page.status_code == 200
    assert "Inbox requires the hosted database." in page.text
    csrf = client.cookies.get("rtc_csrf")
    resp = client.post(
        f"/admin/reports/{uuid4()}/status",
        data={"csrf_token": csrf, "status": "reviewing"},
    )
    assert resp.status_code == 503


def test_home_counts_render_inbox_numbers(tmp_path: Path) -> None:
    inbox = FakeIssueReportInbox([_report("new"), _report("new")])
    contact = FakeContactInbox([_contact("new")])
    client = _admin_client(tmp_path, report_repo=inbox, contact_repo=contact)
    home = client.get("/admin")
    assert home.status_code == 200
    assert "New reports" in home.text and "New messages" in home.text
    assert "No payment metrics exist yet." in home.text


def test_service_validates_before_touching_repo() -> None:
    service = AdminService(None, None)
    with pytest.raises(LookupError):
        service.update_report_status(
            admin_user_id="x", report_id="y", status="reviewing"
        )
