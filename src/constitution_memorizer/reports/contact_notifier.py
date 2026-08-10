"""Resend HTTP notifier for Contact Us messages (plain text, no SDK)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from constitution_memorizer.reports.contact_repository import ContactMessage
    from constitution_memorizer.reports.contact_schemas import ContactMessageRequest

RESEND_API_BASE = "https://api.resend.com"
DEFAULT_TIMEOUT_SECONDS = 10.0
EMAIL_SUBJECT = "New Recall the C contact message"


class ContactMessageNotifyError(Exception):
    """Safe notification failure (no secrets or Resend body in message)."""


def _display(value: str | None) -> str:
    text = (value or "").strip()
    return text if text else "—"


def build_contact_plain_text_body(
    *,
    message: ContactMessage,
    payload: ContactMessageRequest,
) -> str:
    created = getattr(message.created_at, "isoformat", lambda: str(message.created_at))()
    lines = [
        "A new Contact Us message was submitted.",
        "",
        f"Message ID: {message.id}",
        f"Status: {message.status}",
        f"Created: {created}",
        f"Topic: {payload.topic}",
        f"Page URL: {_display(payload.page_url)}",
        f"Reporter email: {_display(payload.reporter_email)}",
        "",
        "Message:",
        _display(payload.message),
    ]
    return "\n".join(lines)


class ResendContactMessageNotifier:
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
        message: ContactMessage,
        payload: ContactMessageRequest,
    ) -> str | None:
        """POST plain-text email to Resend. Returns email id when present."""
        body = {
            "from": self._from,
            "to": [self._to],
            "subject": EMAIL_SUBJECT,
            "text": build_contact_plain_text_body(message=message, payload=payload),
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "Idempotency-Key": f"contact-message-{message.id}",
        }
        async with httpx.AsyncClient(
            base_url=self._base_url,
            timeout=self._timeout,
            transport=self._transport,
        ) as client:
            try:
                response = await client.post("/emails", json=body, headers=headers)
            except httpx.HTTPError as exc:
                raise ContactMessageNotifyError("Resend request failed") from exc

        if response.status_code < 200 or response.status_code >= 300:
            raise ContactMessageNotifyError(
                f"Resend returned HTTP {response.status_code}"
            )

        try:
            data = response.json()
        except ValueError:
            return None
        email_id = data.get("id") if isinstance(data, dict) else None
        return str(email_id) if email_id else None
