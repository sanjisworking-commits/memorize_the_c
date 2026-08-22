"""Speech transcription provider protocol and result types."""

from __future__ import annotations

from dataclasses import dataclass
from typing import AsyncIterator, Protocol, Sequence


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


@dataclass(frozen=True)
class LiveTranscriptEvent:
    """One streaming recognition result.

    ``is_final`` mirrors the provider's flag: True means this segment's text
    will not be revised again; False is an interim guess that the next event
    for the same segment replaces.
    """

    text: str
    is_final: bool


class LiveSession(Protocol):
    """A single live-recognition stream. Audio in, transcript events out."""

    async def send_audio(self, chunk: bytes) -> None: ...

    async def finish(self) -> None:
        """Signal end of audio so the provider flushes its final result."""
        ...

    async def close(self) -> None:
        """Tear the stream down unconditionally (idempotent)."""
        ...

    def events(self) -> AsyncIterator[LiveTranscriptEvent]: ...


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

    async def live_connect(
        self,
        *,
        keyterms: Sequence[str] = (),
    ) -> LiveSession:
        """Open a streaming recognition session (raises SpeechUnavailable
        when the provider cannot stream)."""
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

    async def live_connect(
        self,
        *,
        keyterms: Sequence[str] = (),
    ) -> LiveSession:
        raise SpeechUnavailable("Speech recognition is not configured")
