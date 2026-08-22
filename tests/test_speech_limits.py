"""MIME allowlist and process-local speech rate limiter."""

from __future__ import annotations

from constitution_memorizer.speech.limits import SpeechRateLimiter, mime_allowed


def test_mime_allows_exact_browser_types() -> None:
    assert mime_allowed("audio/webm")
    assert mime_allowed("audio/webm;codecs=opus")
    assert mime_allowed("audio/mp4")
    assert mime_allowed("video/webm")


def test_mime_rejects_prefix_and_empty() -> None:
    assert mime_allowed("audio/webm-evil") is False
    assert mime_allowed("application/octet-stream") is False
    assert mime_allowed("") is False
    assert mime_allowed(None) is False
    assert mime_allowed("audio/webm ") is True


def test_rate_limiter_gc_drops_expired_buckets() -> None:
    now = {"t": 0.0}

    def clock() -> float:
        return now["t"]

    limiter = SpeechRateLimiter(window_seconds=10, max_hits=5, clock=clock)
    assert limiter.allow("ip:a")
    assert limiter.allow("ip:b")
    assert limiter.bucket_count() == 2
    now["t"] = 10.5
    assert limiter.allow("ip:c")
    assert limiter.bucket_count() == 1
    assert "ip:c" in limiter._hits
