"""Thin Google Calendar v3 client over httpx (calendar.app.created scope).

Follows the codebase's transport-injection idiom (reports/notifier.py):
tests pass an ``httpx.MockTransport``; production uses the default pool.
Only the five REST calls the sync needs — no Google SDK. Tokens are never
logged; errors surface as ``GoogleApiError`` with the status class only.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

import httpx

logger = logging.getLogger(__name__)

TOKEN_URL = "https://oauth2.googleapis.com/token"
REVOKE_URL = "https://oauth2.googleapis.com/revoke"
CALENDAR_API = "https://www.googleapis.com/calendar/v3"

CALENDAR_SUMMARY = "Recall the C — Revision Schedule"


class GoogleApiError(RuntimeError):
    def __init__(self, message: str, *, status_code: int = 0) -> None:
        super().__init__(message)
        self.status_code = status_code


class GoogleAuthRevoked(GoogleApiError):
    """Refresh token no longer valid (user revoked access / expired)."""


@dataclass
class GoogleCalendarClient:
    client_id: str
    client_secret: str
    refresh_token: str
    transport: httpx.AsyncBaseTransport | None = None
    _access_token: str | None = None
    _token_expiry: datetime | None = None

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(timeout=20.0, transport=self.transport)

    async def _ensure_access_token(self) -> str:
        now = datetime.now(timezone.utc)
        if (
            self._access_token
            and self._token_expiry
            and now < self._token_expiry - timedelta(seconds=60)
        ):
            return self._access_token
        async with self._client() as client:
            response = await client.post(
                TOKEN_URL,
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "refresh_token": self.refresh_token,
                    "grant_type": "refresh_token",
                },
            )
        if response.status_code >= 400:
            body = {}
            try:
                body = response.json()
            except Exception:
                pass
            if body.get("error") == "invalid_grant":
                raise GoogleAuthRevoked(
                    "Google authorization revoked", status_code=response.status_code
                )
            logger.error("Google token refresh failed: HTTP %s", response.status_code)
            raise GoogleApiError(
                "Google token refresh failed", status_code=response.status_code
            )
        payload = response.json()
        self._access_token = str(payload["access_token"])
        self._token_expiry = now + timedelta(seconds=int(payload.get("expires_in", 3600)))
        return self._access_token

    async def _request(
        self, method: str, path: str, *, json_body: dict | None = None
    ) -> httpx.Response:
        token = await self._ensure_access_token()
        async with self._client() as client:
            response = await client.request(
                method,
                f"{CALENDAR_API}{path}",
                headers={"Authorization": f"Bearer {token}"},
                json=json_body,
            )
        if response.status_code == 401:
            # Access token expired early — refresh once and retry.
            self._access_token = None
            token = await self._ensure_access_token()
            async with self._client() as client:
                response = await client.request(
                    method,
                    f"{CALENDAR_API}{path}",
                    headers={"Authorization": f"Bearer {token}"},
                    json=json_body,
                )
        return response

    # ------------------------------------------------------------------ #
    # Calendars                                                           #
    # ------------------------------------------------------------------ #
    async def get_calendar(self, calendar_id: str) -> bool:
        """True when the app-created calendar still exists."""
        response = await self._request("GET", f"/calendars/{calendar_id}")
        if response.status_code == 200:
            return True
        if response.status_code in (404, 410):
            return False
        raise GoogleApiError(
            "Calendar lookup failed", status_code=response.status_code
        )

    async def create_calendar(self, *, timezone_id: str) -> str:
        response = await self._request(
            "POST",
            "/calendars",
            json_body={"summary": CALENDAR_SUMMARY, "timeZone": timezone_id},
        )
        if response.status_code >= 400:
            raise GoogleApiError(
                "Calendar creation failed", status_code=response.status_code
            )
        return str(response.json()["id"])

    # ------------------------------------------------------------------ #
    # Events                                                              #
    # ------------------------------------------------------------------ #
    @staticmethod
    def _event_body(
        *,
        title: str,
        description: str,
        local_date: date,
        start_time: str,
        duration_minutes: int,
        timezone_id: str,
        reminder_minutes: tuple[int, ...] = (),
    ) -> dict:
        hour, minute = (int(part) for part in start_time.split(":", 1))
        start = datetime(
            local_date.year, local_date.month, local_date.day, hour, minute
        )
        end = start + timedelta(minutes=duration_minutes)
        body = {
            "summary": title,
            "description": description,
            "start": {
                "dateTime": start.strftime("%Y-%m-%dT%H:%M:%S"),
                "timeZone": timezone_id,
            },
            "end": {
                "dateTime": end.strftime("%Y-%m-%dT%H:%M:%S"),
                "timeZone": timezone_id,
            },
        }
        if reminder_minutes:
            # A fresh secondary calendar has NO default notifications, so
            # every event carries explicit popup overrides (Google caps 5).
            body["reminders"] = {
                "useDefault": False,
                "overrides": [
                    {"method": "popup", "minutes": m}
                    for m in reminder_minutes[:5]
                ],
            }
        return body

    async def insert_event(self, calendar_id: str, **event_kwargs) -> str:
        response = await self._request(
            "POST",
            f"/calendars/{calendar_id}/events",
            json_body=self._event_body(**event_kwargs),
        )
        if response.status_code >= 400:
            raise GoogleApiError(
                "Event creation failed", status_code=response.status_code
            )
        return str(response.json()["id"])

    async def patch_event(
        self, calendar_id: str, event_id: str, **event_kwargs
    ) -> str | None:
        """Update an event; returns None when Google says it no longer exists."""
        response = await self._request(
            "PATCH",
            f"/calendars/{calendar_id}/events/{event_id}",
            json_body=self._event_body(**event_kwargs),
        )
        if response.status_code in (404, 410):
            return None
        if response.status_code >= 400:
            raise GoogleApiError(
                "Event update failed", status_code=response.status_code
            )
        return event_id

    async def delete_event(self, calendar_id: str, event_id: str) -> None:
        """Delete an event; already-gone (404/410) is success."""
        response = await self._request(
            "DELETE", f"/calendars/{calendar_id}/events/{event_id}"
        )
        if response.status_code in (200, 204, 404, 410):
            return
        raise GoogleApiError(
            "Event deletion failed", status_code=response.status_code
        )


async def exchange_code(
    *,
    client_id: str,
    client_secret: str,
    code: str,
    redirect_uri: str,
    transport: httpx.AsyncBaseTransport | None = None,
) -> dict:
    """Authorization-code exchange. Returns the raw token payload."""
    async with httpx.AsyncClient(timeout=20.0, transport=transport) as client:
        response = await client.post(
            TOKEN_URL,
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
        )
    if response.status_code >= 400:
        logger.error("Google code exchange failed: HTTP %s", response.status_code)
        raise GoogleApiError(
            "Google authorization failed", status_code=response.status_code
        )
    return response.json()


async def revoke_token(
    token: str, *, transport: httpx.AsyncBaseTransport | None = None
) -> None:
    """Best-effort revocation — failures are logged, never raised."""
    try:
        async with httpx.AsyncClient(timeout=10.0, transport=transport) as client:
            await client.post(REVOKE_URL, params={"token": token})
    except httpx.HTTPError:
        logger.warning("Google token revocation request failed (ignored)")
