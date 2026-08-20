"""Upload and rate-limit guards for the Learn speech route."""

from __future__ import annotations

import time
from collections import defaultdict

from fastapi import UploadFile

MAX_AUDIO_BYTES = 2 * 1024 * 1024
READ_CHUNK_BYTES = 64 * 1024
RATE_LIMIT_WINDOW_SECONDS = 60.0
RATE_LIMIT_MAX = 20

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

_MIME_PREFIXES = ("audio/webm", "audio/mp4", "audio/ogg", "audio/wav", "audio/mpeg")


class SpeechTooLarge(Exception):
    error_code = "too_large"


class SpeechUnsupportedType(Exception):
    error_code = "unsupported_type"


def mime_allowed(content_type: str | None) -> bool:
    raw = (content_type or "").split(";")[0].strip().lower()
    if not raw:
        return False
    if raw in ALLOWED_MIME_TYPES:
        return True
    return any(raw.startswith(prefix) for prefix in _MIME_PREFIXES)


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
    """Process-local sliding window. Multi-instance Railway is best-effort."""

    def __init__(
        self,
        *,
        window_seconds: float = RATE_LIMIT_WINDOW_SECONDS,
        max_hits: int = RATE_LIMIT_MAX,
    ) -> None:
        self._window = window_seconds
        self._max = max_hits
        self._hits: dict[str, list[float]] = defaultdict(list)

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        recent = [t for t in self._hits[key] if now - t < self._window]
        if len(recent) >= self._max:
            self._hits[key] = recent
            return False
        recent.append(now)
        self._hits[key] = recent
        return True
