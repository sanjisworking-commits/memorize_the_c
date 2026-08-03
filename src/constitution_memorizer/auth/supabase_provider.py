"""Supabase Auth provider implementation."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import httpx

from constitution_memorizer.auth.exceptions import AuthConfigError, InvalidCredentialsError
from constitution_memorizer.auth.models import AuthenticatedSession, AuthenticatedUser
from constitution_memorizer.auth.phone import normalize_e164

logger = logging.getLogger(__name__)


class SupabaseAuthProvider:
    """Talks to Supabase Auth HTTP APIs using the anon key (server-side only)."""

    def __init__(self, *, supabase_url: str, anon_key: str) -> None:
        if not supabase_url or not anon_key:
            raise AuthConfigError("SUPABASE_URL and SUPABASE_ANON_KEY are required")
        self.base_url = supabase_url.rstrip("/")
        self.anon_key = anon_key
        self._headers = {
            "apikey": anon_key,
            "Authorization": f"Bearer {anon_key}",
            "Content-Type": "application/json",
        }

    def get_google_authorization_url(
        self,
        redirect_url: str,
        *,
        state: str,
        code_challenge: str | None = None,
        code_challenge_method: str = "S256",
    ) -> str:
        """Build Supabase /auth/v1/authorize URL (PKCE when challenge provided)."""
        from urllib.parse import urlencode

        # Carry our CSRF state on redirect_to so it returns in the query string.
        separator = "&" if "?" in redirect_url else "?"
        redirect_with_state = f"{redirect_url}{separator}state={state}"
        params: dict[str, str] = {
            "provider": "google",
            "redirect_to": redirect_with_state,
            "scopes": "openid email profile",
        }
        if code_challenge:
            params["code_challenge"] = code_challenge
            params["code_challenge_method"] = code_challenge_method or "S256"
        return f"{self.base_url}/auth/v1/authorize?{urlencode(params)}"

    def exchange_oauth_callback(
        self,
        *,
        code: str | None,
        access_token: str | None,
        refresh_token: str | None,
        redirect_url: str,
        code_verifier: str | None = None,
    ) -> AuthenticatedSession:
        if access_token and refresh_token:
            user = self.verify_access_token(access_token)
            return AuthenticatedSession(
                user=user,
                access_token=access_token,
                refresh_token=refresh_token,
            )
        if not code:
            raise InvalidCredentialsError("Missing OAuth credentials")
        if code_verifier:
            data = self._post(
                "/auth/v1/token?grant_type=pkce",
                {
                    "auth_code": code,
                    "code_verifier": code_verifier,
                },
            )
        else:
            # Legacy / non-PKCE authorization_code (rarely used with hosted Supabase).
            data = self._post(
                "/auth/v1/token?grant_type=authorization_code",
                {
                    "auth_code": code,
                    "redirect_to": redirect_url,
                },
            )
        return self._session_from_token_payload(data)

    def send_phone_otp(self, phone_number: str) -> None:
        phone = normalize_e164(phone_number)
        self._post("/auth/v1/otp", {"phone": phone})

    def verify_phone_otp(self, phone_number: str, otp: str) -> AuthenticatedSession:
        phone = normalize_e164(phone_number)
        data = self._post(
            "/auth/v1/verify",
            {"phone": phone, "token": otp, "type": "sms"},
        )
        return self._session_from_token_payload(data)

    def verify_access_token(self, access_token: str) -> AuthenticatedUser:
        data = self._get("/auth/v1/user", access_token=access_token)
        return self._user_from_payload(data)

    def refresh_session(self, refresh_token: str) -> AuthenticatedSession:
        data = self._post(
            "/auth/v1/token?grant_type=refresh_token",
            {"refresh_token": refresh_token},
        )
        return self._session_from_token_payload(data)

    def _session_from_token_payload(self, data: dict[str, Any]) -> AuthenticatedSession:
        access = str(data.get("access_token") or "")
        refresh = str(data.get("refresh_token") or "")
        if not access or not refresh:
            raise InvalidCredentialsError("Auth provider returned an incomplete session")
        user_payload = data.get("user") or {}
        if not user_payload:
            user = self.verify_access_token(access)
        else:
            user = self._user_from_payload(user_payload)
        expires_at = None
        if data.get("expires_at"):
            try:
                expires_at = datetime.fromtimestamp(int(data["expires_at"]), tz=timezone.utc)
            except (TypeError, ValueError):
                expires_at = None
        return AuthenticatedSession(
            user=user,
            access_token=access,
            refresh_token=refresh,
            expires_at=expires_at,
        )

    def _user_from_payload(self, data: dict[str, Any]) -> AuthenticatedUser:
        try:
            user_id = UUID(str(data["id"]))
        except (KeyError, ValueError) as exc:
            raise InvalidCredentialsError("Auth provider user id missing") from exc
        meta = data.get("user_metadata") or {}
        identities = data.get("identities") or []
        provider = "supabase"
        if identities:
            provider = str(identities[0].get("provider") or provider)
        elif data.get("phone"):
            provider = "phone"
        elif data.get("email"):
            provider = "email"
        return AuthenticatedUser(
            id=user_id,
            email=data.get("email"),
            phone=data.get("phone"),
            display_name=meta.get("full_name") or meta.get("name"),
            avatar_url=meta.get("avatar_url") or meta.get("picture"),
            provider=provider,
        )

    def _post(self, path: str, json_body: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        with httpx.Client(timeout=20.0) as client:
            response = client.post(url, headers=self._headers, json=json_body)
        if response.status_code >= 400:
            logger.info(
                "Supabase auth POST %s failed status=%s body=%s",
                path,
                response.status_code,
                (response.text or "")[:300],
            )
            raise InvalidCredentialsError("Authentication request failed")
        payload = response.json()
        if not isinstance(payload, dict):
            return {}
        return payload

    def _get(self, path: str, *, access_token: str) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        headers = {
            **self._headers,
            "Authorization": f"Bearer {access_token}",
        }
        with httpx.Client(timeout=20.0) as client:
            response = client.get(url, headers=headers)
        if response.status_code >= 400:
            raise InvalidCredentialsError("Invalid or expired access token")
        payload = response.json()
        if not isinstance(payload, dict):
            raise InvalidCredentialsError("Invalid auth user payload")
        return payload
