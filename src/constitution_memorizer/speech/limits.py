"""Upload and rate-limit guards for the Learn speech route."""

from __future__ import annotations

import time
from collections.abc import Callable

from fastapi import UploadFile

MAX_AUDIO_BYTES = 2 * 1024 * 1024
READ_CHUNK_BYTES = 64 * 1024
RATE_LIMIT_WINDOW_SECONDS = 60.0
RATE_LIMIT_MAX = 20

# Exact types only (parameters like codecs=opus are stripped first).
ALLOWED_MIME_TYPES = frozenset(
    {
        "audio/webm",
        "audio/mp4",
        "audio/ogg",
        "audio/wav",
        "audio/mpeg",
        "audio/mp3",
        "audio/x-wav",
        "audio/wave",
        "video/webm",  # some browsers tag MediaRecorder webm this way
    }
)


class SpeechTooLarge(Exception):
    error_code = "too_large"


class SpeechUnsupportedType(Exception):
    error_code = "unsupported_type"


def mime_allowed(content_type: str | None) -> bool:
    """Allow only exact listed MIME types. No prefix or filename fallback."""
    raw = (content_type or "").split(";")[0].strip().lower()
    if not raw:
        return False
    return raw in ALLOWED_MIME_TYPES


async def read_upload_limited(
    upload: UploadFile, *, limit: int = MAX_AUDIO_BYTES
) -> bytes:
    """Read an upload in chunks and abort if it exceeds ``limit``."""
    chunks: list[bytes] = []
    total = 0
    while True:
        piece = await upload.read(READ_CHUNK_BYTES)
        if not piece:
            break
        total += len(piece)
        if total > limit:
            raise SpeechTooLarge("Audio is too large")
        chunks.append(piece)
    return b"".join(chunks)


class SpeechRateLimiter:
    """Process-local sliding window. Multi-instance Railway is best-effort.

    Expired keys are garbage-collected so guest IP buckets cannot grow
    without bound.
    """

    def __init__(
        self,
        *,
        window_seconds: float = RATE_LIMIT_WINDOW_SECONDS,
        max_hits: int = RATE_LIMIT_MAX,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._window = window_seconds
        self._max = max_hits
        self._clock = clock
        self._hits: dict[str, list[float]] = {}
        self._last_gc = clock()

    def bucket_count(self) -> int:
        return len(self._hits)

    def allow(self, key: str) -> bool:
        now = self._clock()
        self._gc(now)
        recent = [t for t in self._hits.get(key, []) if now - t < self._window]
        if len(recent) >= self._max:
            self._hits[key] = recent
            return False
        recent.append(now)
        self._hits[key] = recent
        return True

    def _gc(self, now: float) -> None:
        if now - self._last_gc < self._window:
            return
        self._last_gc = now
        stale = [
            key
            for key, times in self._hits.items()
            if not times or now - times[-1] >= self._window
        ]
        for key in stale:
            self._hits.pop(key, None)
