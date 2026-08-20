"""Unit-scoped /learn/{unit}/speech/transcribe: entitlement, limits, alignment."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from uuid import UUID

from fastapi.testclient import TestClient

from constitution_memorizer.auth.fake_provider import FakeAuthProvider
from constitution_memorizer.auth.sessions import InMemorySessionStore
from constitution_memorizer.multiuser.settings import MultiUserSettings, clear_settings_cache
from constitution_memorizer.speech.limits import MAX_AUDIO_BYTES, SpeechRateLimiter
from constitution_memorizer.speech.provider import (
    SpeechUnavailable,
    Transcript,
    TranscriptWord,
)
from constitution_memorizer.web.app import create_app

MINI_UNITS = Path(__file__).parent / "fixtures" / "learning" / "mini_units.json"


class FakeSpeechProvider:
    def __init__(self, text: str = "all citizens shall have the right") -> None:
        self.text = text
        self.calls: list[dict] = []

    async def transcribe(self, audio: bytes, *, mime_type: str, keyterms=()) -> Transcript:
        self.calls.append(
            {"nbytes": len(audio), "mime_type": mime_type, "keyterms": list(keyterms)}
        )
        words = tuple(TranscriptWord(word=w) for w in self.text.split())
        return Transcript(text=self.text, words=words)


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
        ARTICLE_ENTITLEMENTS_ENABLED="true",
    )


def _guest_client(tmp_path: Path, provider=None) -> TestClient:
    clear_settings_cache()
    app = create_app(
        units_path=MINI_UNITS,
        db_path=tmp_path / "progress.db",
        multiuser=True,
        multiuser_settings=_settings(),
        auth_provider=FakeAuthProvider(),
        session_store=InMemorySessionStore(),
        speech_provider=provider or FakeSpeechProvider(),
    )
    return TestClient(app)


def _signed_in_client(tmp_path: Path, provider=None) -> TestClient:
    clear_settings_cache()
    store = InMemorySessionStore()
    fake = FakeAuthProvider()
    fake.seed_google_user(
        user_id=UUID("11111111-1111-4111-8111-111111111111"),
        email="a@example.com",
        display_name="User A",
    )
    app = create_app(
        units_path=MINI_UNITS,
        db_path=tmp_path / "progress.db",
        multiuser=True,
        multiuser_settings=_settings(),
        auth_provider=fake,
        session_store=store,
        speech_provider=provider or FakeSpeechProvider(),
    )
    client = TestClient(app)
    start = client.get("/auth/google/start", follow_redirects=False)
    state = start.cookies.get("rtc_oauth_state")
    client.get(
        f"/auth/callback?code=fake-google-code&state={state}",
        follow_redirects=False,
    )
    return client


def test_missing_unit_404(tmp_path: Path) -> None:
    client = _guest_client(tmp_path)
    resp = client.post(
        "/learn/no-such/speech/transcribe",
        data={"mode": "letters", "text": "hello"},
    )
    assert resp.status_code == 404
    assert resp.json()["error"] == "not_found"


def test_guest_letters_typed_alignment(tmp_path: Path) -> None:
    provider = FakeSpeechProvider()
    client = _guest_client(tmp_path, provider)
    resp = client.post(
        "/learn/clause-1/speech/transcribe",
        data={"mode": "letters", "text": "No person shall be", "from_index": 0},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["transcript"] == "No person shall be"
    hits = {row["index"]: row["status"] for row in body["alignment"]}
    assert 0 not in hits
    assert hits[1] == "match"
    assert hits[2] == "match"
    assert hits[3] == "match"
    assert hits[4] == "match"
    assert provider.calls == []  # typed fallback skips Deepgram
    assert "expected" not in body


def test_expected_form_field_is_ignored(tmp_path: Path) -> None:
    client = _guest_client(tmp_path)
    resp = client.post(
        "/learn/clause-1/speech/transcribe",
        data={
            "mode": "letters",
            "text": "will",
            "from_index": 3,
            "expected": "shall never be used",
        },
    )
    assert resp.status_code == 200
    hits = {row["index"]: row["status"] for row in resp.json()["alignment"]}
    # clause-1: "(1) No person shall …" — shall is index 3.
    assert 3 in hits
    assert hits[3] == "substitute"


def test_guest_recite_locked(tmp_path: Path) -> None:
    client = _guest_client(tmp_path)
    resp = client.post(
        "/learn/clause-1/speech/transcribe",
        data={"mode": "recite", "text": "No person shall be deprived"},
    )
    assert resp.status_code == 403
    assert resp.json()["error"] == "mode_locked"


def test_audio_success_uses_provider(tmp_path: Path) -> None:
    provider = FakeSpeechProvider("No person shall")
    client = _signed_in_client(tmp_path, provider)
    resp = client.post(
        "/learn/clause-1/speech/transcribe",
        data={"mode": "letters", "from_index": 0},
        files={"audio": ("utt.webm", BytesIO(b"fake-bytes"), "audio/webm")},
    )
    assert resp.status_code == 200
    assert provider.calls
    assert provider.calls[0]["nbytes"] == 10
    assert "the" not in provider.calls[0]["keyterms"]
    assert resp.json()["alignment"]


def test_unsupported_mime(tmp_path: Path) -> None:
    client = _guest_client(tmp_path)
    resp = client.post(
        "/learn/clause-1/speech/transcribe",
        data={"mode": "letters"},
        files={"audio": ("utt.bin", BytesIO(b"fake-bytes"), "application/octet-stream")},
    )
    assert resp.status_code == 400
    assert resp.json()["error"] == "unsupported_type"


def test_filename_suffix_does_not_bypass_mime(tmp_path: Path) -> None:
    client = _guest_client(tmp_path)
    resp = client.post(
        "/learn/clause-1/speech/transcribe",
        data={"mode": "letters"},
        files={"audio": ("utt.webm", BytesIO(b"fake-bytes"), "")},
    )
    assert resp.status_code == 400
    assert resp.json()["error"] == "unsupported_type"


def test_mime_prefix_is_rejected(tmp_path: Path) -> None:
    client = _guest_client(tmp_path)
    resp = client.post(
        "/learn/clause-1/speech/transcribe",
        data={"mode": "letters"},
        files={"audio": ("utt.webm", BytesIO(b"fake-bytes"), "audio/webm-evil")},
    )
    assert resp.status_code == 400
    assert resp.json()["error"] == "unsupported_type"


def test_too_large(tmp_path: Path) -> None:
    client = _guest_client(tmp_path)
    payload = b"x" * (MAX_AUDIO_BYTES + 1)
    resp = client.post(
        "/learn/clause-1/speech/transcribe",
        data={"mode": "letters"},
        files={"audio": ("utt.webm", BytesIO(payload), "audio/webm")},
    )
    assert resp.status_code == 413
    assert resp.json()["error"] == "too_large"


def test_unavailable_provider(tmp_path: Path) -> None:
    class Boom:
        async def transcribe(self, audio, *, mime_type, keyterms=()):
            raise SpeechUnavailable("no key")

    client = _guest_client(tmp_path, Boom())
    resp = client.post(
        "/learn/clause-1/speech/transcribe",
        data={"mode": "letters"},
        files={"audio": ("utt.webm", BytesIO(b"fake-bytes"), "audio/webm")},
    )
    assert resp.status_code == 503
    assert resp.json()["error"] == "unavailable"


def test_rate_limited(tmp_path: Path) -> None:
    client = _guest_client(tmp_path)
    client.app.state.speech_rate_limiter = SpeechRateLimiter(
        window_seconds=60, max_hits=1
    )
    first = client.post(
        "/learn/clause-1/speech/transcribe",
        data={"mode": "letters", "text": "No"},
    )
    assert first.status_code == 200
    second = client.post(
        "/learn/clause-1/speech/transcribe",
        data={"mode": "letters", "text": "person"},
    )
    assert second.status_code == 429
    assert second.json()["error"] == "rate_limited"


def test_guest_rate_limit_ignores_spoofed_cookie_and_forwarded_for(
    tmp_path: Path,
) -> None:
    client = _guest_client(tmp_path)
    client.app.state.speech_rate_limiter = SpeechRateLimiter(
        window_seconds=60, max_hits=1
    )
    first = client.post(
        "/learn/clause-1/speech/transcribe",
        data={"mode": "letters", "text": "No"},
        headers={"X-Forwarded-For": "203.0.113.10"},
        cookies={"rtc_session": "forged-one"},
    )
    assert first.status_code == 200
    second = client.post(
        "/learn/clause-1/speech/transcribe",
        data={"mode": "letters", "text": "person"},
        headers={"X-Forwarded-For": "198.51.100.20"},
        cookies={"rtc_session": "forged-two"},
    )
    assert second.status_code == 429
    assert second.json()["error"] == "rate_limited"


def test_guest_recite_audio_does_not_call_provider(tmp_path: Path) -> None:
    provider = FakeSpeechProvider()
    client = _guest_client(tmp_path, provider)
    resp = client.post(
        "/learn/clause-1/speech/transcribe",
        data={"mode": "recite"},
        files={"audio": ("utt.webm", BytesIO(b"fake-bytes"), "audio/webm")},
    )
    assert resp.status_code == 403
    assert resp.json()["error"] == "mode_locked"
    assert provider.calls == []


def test_signed_in_claimable_recite_omits_alignment(tmp_path: Path) -> None:
    """Free accounts with remaining slots may Recite; alignment is Letters-only."""
    provider = FakeSpeechProvider()
    client = _signed_in_client(tmp_path, provider)
    resp = client.post(
        "/learn/clause-1/speech/transcribe",
        data={"mode": "recite", "text": "No person shall"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert "alignment" not in body
    assert provider.calls == []


def test_recite_typed_omits_alignment_and_skips_provider(tmp_path: Path) -> None:
    provider = FakeSpeechProvider()
    app = create_app(
        units_path=MINI_UNITS,
        db_path=tmp_path / "progress.db",
        speech_provider=provider,
    )
    client = TestClient(app)
    resp = client.post(
        "/learn/clause-1/speech/transcribe",
        data={"mode": "recite", "text": "No person shall be convicted"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["transcript"] == "No person shall be convicted"
    assert "alignment" not in body
    assert provider.calls == []


def test_recite_audio_omits_alignment(tmp_path: Path) -> None:
    provider = FakeSpeechProvider("No person shall")
    app = create_app(
        units_path=MINI_UNITS,
        db_path=tmp_path / "progress.db",
        speech_provider=provider,
    )
    client = TestClient(app)
    resp = client.post(
        "/learn/clause-1/speech/transcribe",
        data={"mode": "recite"},
        files={"audio": ("utt.webm", BytesIO(b"fake-bytes"), "audio/webm")},
    )
    assert resp.status_code == 200
    assert provider.calls
    assert "alignment" not in resp.json()


def test_app_starts_without_deepgram_key(tmp_path: Path) -> None:
    from constitution_memorizer.speech.provider import UnavailableSpeechProvider

    app = create_app(units_path=MINI_UNITS, db_path=tmp_path / "progress.db")
    assert isinstance(app.state.speech_provider, UnavailableSpeechProvider)


def test_speech_align_js_is_not_shipped() -> None:
    root = Path(__file__).resolve().parents[1]
    assert not (
        root / "src" / "constitution_memorizer" / "web" / "static" / "speech_align.js"
    ).exists()
