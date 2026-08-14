"""PKCE helpers and Supabase authorize URL shape."""

from __future__ import annotations

from constitution_memorizer.auth.pkce import code_challenge_s256, new_code_verifier
from constitution_memorizer.auth.supabase_provider import SupabaseAuthProvider


def test_code_challenge_is_s256_urlsafe():
    verifier = new_code_verifier()
    challenge = code_challenge_s256(verifier)
    assert 43 <= len(verifier) <= 128
    assert len(challenge) >= 43
    assert "+" not in challenge and "/" not in challenge


def test_supabase_authorize_url_includes_pkce_and_state():
    provider = SupabaseAuthProvider(
        supabase_url="https://example.supabase.co",
        anon_key="anon",
    )
    verifier = new_code_verifier()
    challenge = code_challenge_s256(verifier)
    url = provider.get_google_authorization_url(
        "http://127.0.0.1:8010/auth/callback",
        state="abc",
        code_challenge=challenge,
    )
    assert url.startswith("https://example.supabase.co/auth/v1/authorize?")
    assert "provider=google" in url
    assert "code_challenge=" in url
    assert "code_challenge_method=S256" in url
    assert "state%3Dabc" in url
