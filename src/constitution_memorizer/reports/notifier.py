"""Resend HTTP notifier for new issue reports (plain text, no SDK)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from constitution_memorizer.reports.repository import IssueReport
    from constitution_memorizer.reports.schemas import ReportIssueRequest

RESEND_API_BASE = "https://api.resend.com"
DEFAULT_TIMEOUT_SECONDS = 10.0
EMAIL_SUBJECT = "New Recall the C issue report"


class IssueReportNotifyError(Exception):
    """Safe notification failure (no secrets or Resend body in message)."""


def _display(value: str | None) -> str:
    text = (value or "").strip()
    return text if text else "—"


def build_plain_text_body(
    *,
    report: IssueReport,
    payload: ReportIssueRequest,
) -> str:
    created = getattr(report.created_at, "isoformat", lambda: str(report.created_at))()
    lines = [
        "A new issue report was submitted.",
        "",
        f"Report ID: {report.id}",
        f"Status: {report.status}",
        f"Created: {created}",
        f"Issue type: {payload.issue_type}",
        f"Article number: {_display(payload.article_number)}",
        f"Section: {_display(payload.section)}",
        f"Page URL: {_display(payload.page_url)}",
        f"Reporter email: {_display(payload.reporter_email)}",
        f"Supporting source URL: {_display(payload.source_url)}",
        "",
        "Description:",
        _display(payload.description),
        "",
        "Selected text:",
        _display(payload.selected_text),
        "",
        "Suggested correction:",
        _display(payload.suggested_correction),
    ]
    return "\n".join(lines)


class ResendIssueReportNotifier:
    """Send admin email via Resend REST API using httpx."""

    def __init__(
        self,
        api_key: str,
        from_addr: str,
        to_addr: str,
        *,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        transport: httpx.AsyncBaseTransport | None = None,
        base_url: str = RESEND_API_BASE,
    ) -> None:
        self._api_key = api_key.strip()
        self._from = from_addr.strip()
        self._to = to_addr.strip()
        self._timeout = timeout
        self._transport = transport
        self._base_url = base_url.rstrip("/")

    async def send(
        self,
        *,
        report: IssueReport,
        payload: ReportIssueRequest,
    ) -> str | None:
        """POST plain-text email to Resend. Returns email id when present."""
        body = {
            "from": self._from,
            "to": [self._to],
            "subject": EMAIL_SUBJECT,
            "text": build_plain_text_body(report=report, payload=payload),
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "Idempotency-Key": f"issue-report-{report.id}",
        }
        async with httpx.AsyncClient(
            base_url=self._base_url,
            timeout=self._timeout,
            transport=self._transport,
        ) as client:
            try:
                response = await client.post("/emails", json=body, headers=headers)
            except httpx.HTTPError as exc:
                raise IssueReportNotifyError("Resend request failed") from exc

        if response.status_code < 200 or response.status_code >= 300:
            raise IssueReportNotifyError(
                f"Resend returned HTTP {response.status_code}"
            )

        try:
            data = response.json()
        except ValueError:
            return None
        email_id = data.get("id") if isinstance(data, dict) else None
        return str(email_id) if email_id else None
