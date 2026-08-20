"""Deepgram Nova-3 pre-recorded transcription (HTTP, no SDK)."""

from __future__ import annotations

import logging
from typing import Sequence

import httpx

from constitution_memorizer.speech.provider import (
    SpeechProviderError,
    SpeechTimeout,
    SpeechUnavailable,
    Transcript,
    TranscriptWord,
)

logger = logging.getLogger(__name__)

DEEPGRAM_LISTEN_URL = "https://api.deepgram.com/v1/listen"
DEFAULT_TIMEOUT_SECONDS = 15.0


class DeepgramSpeechProvider:
    def __init__(
        self,
        api_key: str,
        *,
        client: httpx.AsyncClient | None = None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._api_key = (api_key or "").strip()
        self._client = client
        self._timeout = timeout

    async def transcribe(
        self,
        audio: bytes,
        *,
        mime_type: str,
        keyterms: Sequence[str] = (),
    ) -> Transcript:
        if not self._api_key:
            raise SpeechUnavailable("Speech recognition is not configured")
        if not audio:
            return Transcript(text="", words=())

        params: list[tuple[str, str]] = [
            ("model", "nova-3"),
            ("language", "en-IN"),
            ("smart_format", "false"),
            ("mip_opt_out", "true"),
        ]
        for term in keyterms:
            cleaned = term.strip()
            if cleaned:
                params.append(("keyterm", cleaned))

        headers = {
            "Authorization": f"Token {self._api_key}",
            "Content-Type": mime_type or "application/octet-stream",
        }
        own_client = self._client is None
        client = self._client or httpx.AsyncClient(timeout=self._timeout)
        try:
            response = await client.post(
                DEEPGRAM_LISTEN_URL,
                params=params,
                content=audio,
                headers=headers,
            )
        except httpx.TimeoutException as exc:
            raise SpeechTimeout("Speech recognition timed out") from exc
        except httpx.HTTPError as exc:
            logger.warning("Deepgram request failed: %s", type(exc).__name__)
            raise SpeechProviderError("Speech recognition failed") from exc
        finally:
            if own_client:
                await client.aclose()

        if response.status_code >= 500:
            raise SpeechProviderError("Speech recognition failed")
        if response.status_code == 401 or response.status_code == 403:
            raise SpeechUnavailable("Speech recognition is not configured")
        if response.status_code >= 400:
            raise SpeechProviderError("Speech recognition failed")

        try:
            payload = response.json()
        except ValueError as exc:
            raise SpeechProviderError("Malformed speech response") from exc

        try:
            alternative = payload["results"]["channels"][0]["alternatives"][0]
        except (KeyError, IndexError, TypeError) as exc:
            raise SpeechProviderError("Malformed speech response") from exc

        text = str(alternative.get("transcript") or "").strip()
        words: list[TranscriptWord] = []
        raw_words = alternative.get("words") or []
        if isinstance(raw_words, list):
            for item in raw_words:
                if not isinstance(item, dict):
                    continue
                word = str(item.get("word") or "").strip()
                if not word:
                    continue
                confidence = item.get("confidence")
                conf: float | None
                try:
                    conf = float(confidence) if confidence is not None else None
                except (TypeError, ValueError):
                    conf = None
                words.append(TranscriptWord(word=word, confidence=conf))
        return Transcript(text=text, words=tuple(words))
