"""Cloudflare Turnstile Siteverify client for issue reports (no SDK)."""

from __future__ import annotations

import httpx

TURNSTILE_SITEVERIFY_URL = (
    "https://challenges.cloudflare.com/turnstile/v0/siteverify"
)
DEFAULT_TIMEOUT_SECONDS = 10.0


class TurnstileRejectedError(Exception):
    """Token was rejected by Cloudflare (success: false). Safe message only."""


class TurnstileUnavailableError(Exception):
    """Siteverify could not be completed. Safe message only."""


class TurnstileVerifier:
    """Verify a Turnstile token via Cloudflare Siteverify using httpx."""

    def __init__(
        self,
        secret: str,
        *,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        transport: httpx.AsyncBaseTransport | None = None,
        verify_url: str = TURNSTILE_SITEVERIFY_URL,
    ) -> None:
        self._secret = secret.strip()
        self._timeout = timeout
        self._transport = transport
        self._verify_url = verify_url

    async def verify(self, token: str) -> None:
        """
        POST secret + response to Siteverify.

        Raises TurnstileRejectedError when success is false.
        Raises TurnstileUnavailableError on network/non-2xx/malformed responses.
        Never includes secret, token, or Cloudflare body in exception messages.
        """
        body = {"secret": self._secret, "response": token}
        async with httpx.AsyncClient(
            timeout=self._timeout,
            transport=self._transport,
        ) as client:
            try:
                response = await client.post(self._verify_url, json=body)
            except httpx.HTTPError as exc:
                raise TurnstileUnavailableError(
                    "Turnstile verification request failed"
                ) from exc

        if response.status_code < 200 or response.status_code >= 300:
            raise TurnstileUnavailableError(
                f"Turnstile verification returned HTTP {response.status_code}"
            )

        try:
            data = response.json()
        except ValueError as exc:
            raise TurnstileUnavailableError(
                "Turnstile verification returned invalid JSON"
            ) from exc

        if not isinstance(data, dict):
            raise TurnstileUnavailableError(
                "Turnstile verification returned unexpected payload"
            )

        success = data.get("success")
        if success is True:
            return
        if success is False:
            raise TurnstileRejectedError("Turnstile verification failed")
        raise TurnstileUnavailableError(
            "Turnstile verification returned unexpected payload"
        )
