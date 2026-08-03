"""PKCE helpers for Supabase OAuth (server-side)."""

from __future__ import annotations

import base64
import hashlib
import secrets


def new_code_verifier() -> str:
    """Return a high-entropy PKCE code_verifier (43–128 chars)."""
    return secrets.token_urlsafe(64)[:128]


def code_challenge_s256(verifier: str) -> str:
    """S256 code_challenge for a verifier."""
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
