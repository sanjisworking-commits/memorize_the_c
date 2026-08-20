"""Speech transcription provider protocol and result types."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence


class SpeechError(Exception):
    """Base class for transcription failures."""

    error_code = "provider_error"


class SpeechUnavailable(SpeechError):
    error_code = "unavailable"


class SpeechTimeout(SpeechError):
    error_code = "timeout"


class SpeechProviderError(SpeechError):
    error_code = "provider_error"


@dataclass(frozen=True)
class TranscriptWord:
    word: str
    confidence: float | None = None


@dataclass(frozen=True)
class Transcript:
    text: str
    words: tuple[TranscriptWord, ...] = ()


class SpeechProvider(Protocol):
    async def transcribe(
        self,
        audio: bytes,
        *,
        mime_type: str,
        keyterms: Sequence[str] = (),
    ) -> Transcript:
        """Return a transcript for ``audio``. Never persist the bytes."""
        ...


class UnavailableSpeechProvider:
    """Installed when DEEPGRAM_API_KEY is missing. App still starts."""

    async def transcribe(
        self,
        audio: bytes,
        *,
        mime_type: str,
        keyterms: Sequence[str] = (),
    ) -> Transcript:
        raise SpeechUnavailable("Speech recognition is not configured")
