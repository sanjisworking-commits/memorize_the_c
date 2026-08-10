"""Unit tests for ResendIssueReportNotifier (httpx MockTransport)."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import httpx
import pytest

from constitution_memorizer.multiuser.settings import MultiUserSettings, clear_settings_cache
from constitution_memorizer.reports.notifier import (
    IssueReportNotifyError,
    ResendIssueReportNotifier,
)
from constitution_memorizer.reports.repository import IssueReport
from constitution_memorizer.reports.schemas import ReportIssueRequest

FIXED_ID = UUID("aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee")


@pytest.fixture(autouse=True)
def _clear_settings():
    clear_settings_cache()
    yield
    clear_settings_cache()


def _report(**overrides: Any) -> IssueReport:
    base = {
        "id": FIXED_ID,
        "status": "new",
        "created_at": datetime(2026, 8, 10, 12, 0, tzinfo=timezone.utc),
    }
    base.update(overrides)
    return IssueReport(**base)


def _payload(**overrides: Any) -> ReportIssueRequest:
    base = {
        "issue_type": "incorrect_fact",
        "description": "This appears to use the wrong census reference.",
        "page_url": "/browse/article/55",
        "article_number": "55",
        "section": "Explanation",
        "selected_text": "Population means...",
        "suggested_correction": "Suggested wording...",
        "source_url": "https://example.com/source",
        "reporter_email": "reader@example.com",
    }
    base.update(overrides)
    return ReportIssueRequest(**base)


def test_send_posts_expected_payload_and_headers() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["method"] = request.method
        captured["authorization"] = request.headers.get("Authorization")
        captured["idempotency"] = request.headers.get("Idempotency-Key")
        captured["content_type"] = request.headers.get("Content-Type")
        captured["body"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(200, json={"id": "email_123"})

    notifier = ResendIssueReportNotifier(
        "re_test_secret_key",
        "Recall the C <reports@example.com>",
        "inbox@example.com",
        transport=httpx.MockTransport(handler),
    )
    email_id = asyncio.run(notifier.send(report=_report(), payload=_payload()))

    assert email_id == "email_123"
    assert captured["method"] == "POST"
    assert captured["url"] == "https://api.resend.com/emails"
    assert captured["authorization"] == "Bearer re_test_secret_key"
    assert captured["idempotency"] == f"issue-report-{FIXED_ID}"
    assert captured["content_type"] == "application/json"
    assert captured["body"]["from"] == "Recall the C <reports@example.com>"
    assert captured["body"]["to"] == ["inbox@example.com"]
    assert captured["body"]["subject"] == "New Recall the C issue report"
    text = captured["body"]["text"]
    assert f"Report ID: {FIXED_ID}" in text
    assert "Status: new" in text
    assert "Issue type: incorrect_fact" in text
    assert "Article number: 55" in text
    assert "Section: Explanation" in text
    assert "Page URL: /browse/article/55" in text
    assert "Reporter email: reader@example.com" in text
    assert "Supporting source URL: https://example.com/source" in text
    assert "This appears to use the wrong census reference." in text
    assert "Population means..." in text
    assert "Suggested wording..." in text


def test_send_uses_em_dash_for_absent_optional_fields() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(200, json={"id": "email_ok"})

    notifier = ResendIssueReportNotifier(
        "re_test",
        "from@example.com",
        "to@example.com",
        transport=httpx.MockTransport(handler),
    )
    asyncio.run(
        notifier.send(
            report=_report(),
            payload=_payload(
                article_number=None,
                section=None,
                selected_text=None,
                suggested_correction=None,
                source_url=None,
                reporter_email=None,
            ),
        )
    )
    text = captured["body"]["text"]
    assert "Article number: —" in text
    assert "Section: —" in text
    assert "Reporter email: —" in text
    assert "Supporting source URL: —" in text
    assert "Selected text:\n—" in text
    assert "Suggested correction:\n—" in text


def test_non_2xx_raises_safe_error_without_secrets_or_body() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            401,
            json={"message": "API key is invalid", "name": "validation_error"},
        )

    notifier = ResendIssueReportNotifier(
        "re_should_not_leak",
        "from@example.com",
        "to@example.com",
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(IssueReportNotifyError) as exc_info:
        asyncio.run(notifier.send(report=_report(), payload=_payload()))

    message = str(exc_info.value)
    assert "401" in message
    assert "re_should_not_leak" not in message
    assert "API key is invalid" not in message
    assert "validation_error" not in message
    assert "Authorization" not in message


def test_transport_error_raises_notify_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    notifier = ResendIssueReportNotifier(
        "re_test",
        "from@example.com",
        "to@example.com",
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(IssueReportNotifyError, match="Resend request failed"):
        asyncio.run(notifier.send(report=_report(), payload=_payload()))


def test_custom_base_url_used_when_provided() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        return httpx.Response(200, json={"id": "email_x"})

    notifier = ResendIssueReportNotifier(
        "re_test",
        "from@example.com",
        "to@example.com",
        transport=httpx.MockTransport(handler),
        base_url="https://resend.test.example",
    )
    asyncio.run(notifier.send(report=_report(), payload=_payload()))
    assert captured["url"] == "https://resend.test.example/emails"


def test_partial_settings_leave_notify_unconfigured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RESEND_API_KEY", "re_only_key")
    monkeypatch.delenv("REPORT_EMAIL_FROM", raising=False)
    monkeypatch.delenv("REPORT_EMAIL_TO", raising=False)
    assert MultiUserSettings(_env_file=None).issue_report_notify_configured() is False

    monkeypatch.setenv("RESEND_API_KEY", "re_key")
    monkeypatch.setenv("REPORT_EMAIL_FROM", "from@example.com")
    monkeypatch.delenv("REPORT_EMAIL_TO", raising=False)
    assert MultiUserSettings(_env_file=None).issue_report_notify_configured() is False

    monkeypatch.setenv("REPORT_EMAIL_FROM", "")
    monkeypatch.setenv("REPORT_EMAIL_TO", "to@example.com")
    assert MultiUserSettings(_env_file=None).issue_report_notify_configured() is False

    monkeypatch.setenv("RESEND_API_KEY", "re_key")
    monkeypatch.setenv("REPORT_EMAIL_FROM", "from@example.com")
    monkeypatch.setenv("REPORT_EMAIL_TO", "to@example.com")
    assert MultiUserSettings(_env_file=None).issue_report_notify_configured() is True
