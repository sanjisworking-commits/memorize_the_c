"""Unit tests for TurnstileVerifier (httpx MockTransport) and settings."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx
import pytest

from constitution_memorizer.auth.exceptions import AuthConfigError
from constitution_memorizer.multiuser.settings import MultiUserSettings, clear_settings_cache
from datetime import datetime, timezone
from uuid import UUID

from constitution_memorizer.reports.notifier import build_plain_text_body
from constitution_memorizer.reports.repository import IssueReport
from constitution_memorizer.reports.schemas import ReportIssueRequest
from constitution_memorizer.reports.turnstile import (
    TURNSTILE_SITEVERIFY_URL,
    TurnstileRejectedError,
    TurnstileUnavailableError,
    TurnstileVerifier,
)


@pytest.fixture(autouse=True)
def _clear_settings():
    clear_settings_cache()
    yield
    clear_settings_cache()


def test_verify_posts_expected_url_and_fields() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["method"] = request.method
        captured["body"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(200, json={"success": True})

    verifier = TurnstileVerifier(
        "turnstile_secret_value",
        transport=httpx.MockTransport(handler),
    )
    asyncio.run(verifier.verify("token-abc"))

    assert captured["method"] == "POST"
    assert captured["url"] == TURNSTILE_SITEVERIFY_URL
    assert captured["body"] == {
        "secret": "turnstile_secret_value",
        "response": "token-abc",
    }
    assert "remoteip" not in captured["body"]


def test_success_true_accepted() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"success": True})

    verifier = TurnstileVerifier(
        "secret",
        transport=httpx.MockTransport(handler),
    )
    asyncio.run(verifier.verify("ok-token"))


def test_success_false_rejected_without_leaking_secrets() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "success": False,
                "error-codes": ["invalid-input-response"],
            },
        )

    secret = "super_secret_turnstile_key"
    token = "leaky-token-value"
    verifier = TurnstileVerifier(
        secret,
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(TurnstileRejectedError) as exc_info:
        asyncio.run(verifier.verify(token))

    message = str(exc_info.value)
    assert secret not in message
    assert token not in message
    assert "invalid-input-response" not in message


def test_network_failure_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    verifier = TurnstileVerifier(
        "secret",
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(TurnstileUnavailableError, match="request failed"):
        asyncio.run(verifier.verify("token"))


def test_non_2xx_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="upstream error body")

    verifier = TurnstileVerifier(
        "secret",
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(TurnstileUnavailableError) as exc_info:
        asyncio.run(verifier.verify("token"))
    assert "500" in str(exc_info.value)
    assert "upstream error body" not in str(exc_info.value)


def test_malformed_json_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="not-json")

    verifier = TurnstileVerifier(
        "secret",
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(TurnstileUnavailableError, match="invalid JSON"):
        asyncio.run(verifier.verify("token"))


def test_missing_success_key_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"challenge_ts": "2026-01-01"})

    verifier = TurnstileVerifier(
        "secret",
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(TurnstileUnavailableError, match="unexpected payload"):
        asyncio.run(verifier.verify("token"))


def test_custom_verify_url_for_tests() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        return httpx.Response(200, json={"success": True})

    verifier = TurnstileVerifier(
        "secret",
        transport=httpx.MockTransport(handler),
        verify_url="https://turnstile.test.example/siteverify",
    )
    asyncio.run(verifier.verify("token"))
    assert captured["url"] == "https://turnstile.test.example/siteverify"


def test_settings_helpers_and_independent_validation() -> None:
    disabled = MultiUserSettings(
        _env_file=None,
        REPORT_TURNSTILE_ENABLED="false",
        REPORT_TURNSTILE_SITE_KEY="",
        REPORT_TURNSTILE_SECRET_KEY="",
    )
    assert disabled.report_turnstile_enabled is False
    assert disabled.issue_report_turnstile_configured() is False
    disabled.validate_issue_report_turnstile()  # no-op

    partial = MultiUserSettings(
        _env_file=None,
        REPORT_TURNSTILE_ENABLED="true",
        REPORT_TURNSTILE_SITE_KEY="site",
        REPORT_TURNSTILE_SECRET_KEY="",
    )
    assert partial.issue_report_turnstile_configured() is False
    with pytest.raises(AuthConfigError, match="REPORT_TURNSTILE_SECRET_KEY"):
        partial.validate_issue_report_turnstile()

    only_secret = MultiUserSettings(
        _env_file=None,
        REPORT_TURNSTILE_ENABLED="true",
        REPORT_TURNSTILE_SITE_KEY="",
        REPORT_TURNSTILE_SECRET_KEY="secret",
    )
    with pytest.raises(AuthConfigError, match="REPORT_TURNSTILE_SITE_KEY"):
        only_secret.validate_issue_report_turnstile()

    full = MultiUserSettings(
        _env_file=None,
        REPORT_TURNSTILE_ENABLED="true",
        REPORT_TURNSTILE_SITE_KEY="site",
        REPORT_TURNSTILE_SECRET_KEY="secret",
    )
    assert full.issue_report_turnstile_configured() is True
    full.validate_issue_report_turnstile()


def test_turnstile_token_never_in_resend_email_body() -> None:
    report = IssueReport(
        id=UUID("aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"),
        status="new",
        created_at=datetime(2026, 8, 10, 12, 0, tzinfo=timezone.utc),
    )
    token = "XXXX.DUMMY.TOKEN.SHOULD.NOT.APPEAR"
    payload = ReportIssueRequest(
        issue_type="typo",
        description="A typo in the Bare Act quote.",
        page_url="/browse/article/21",
        turnstile_token=token,
    )
    text = build_plain_text_body(report=report, payload=payload)
    assert token not in text
    assert "turnstile" not in text.lower()
