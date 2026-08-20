"""Deepgram provider with a mocked HTTP transport. Never hits the live API."""

from __future__ import annotations

import asyncio

import httpx
import pytest

from constitution_memorizer.speech.deepgram import DeepgramSpeechProvider
from constitution_memorizer.speech.provider import (
    SpeechProviderError,
    SpeechTimeout,
    SpeechUnavailable,
    UnavailableSpeechProvider,
)


def _run(coro):
    return asyncio.run(coro)


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def test_unavailable_provider_raises() -> None:
    async def go() -> None:
        with pytest.raises(SpeechUnavailable):
            await UnavailableSpeechProvider().transcribe(b"x", mime_type="audio/webm")

    _run(go())


def test_missing_api_key_raises() -> None:
    async def go() -> None:
        provider = DeepgramSpeechProvider("")
        with pytest.raises(SpeechUnavailable):
            await provider.transcribe(b"x", mime_type="audio/webm")

    _run(go())


def test_successful_transcription() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["model"] == "nova-3"
        assert request.url.params["language"] == "en"
        assert request.url.params["smart_format"] == "false"
        assert request.url.params["mip_opt_out"] == "true"
        assert "the" not in request.url.params.get_list("keyterm")
        assert "notwithstanding" in request.url.params.get_list("keyterm")
        return httpx.Response(
            200,
            json={
                "results": {
                    "channels": [
                        {
                            "alternatives": [
                                {
                                    "transcript": "all citizens shall have",
                                    "words": [
                                        {"word": "all", "confidence": 0.98},
                                        {"word": "citizens", "confidence": 0.9},
                                    ],
                                }
                            ]
                        }
                    ]
                }
            },
        )

    async def go() -> None:
        provider = DeepgramSpeechProvider("dg-test", client=_client(handler))
        result = await provider.transcribe(
            b"fake-audio",
            mime_type="audio/webm",
            keyterms=["notwithstanding"],
        )
        assert result.text == "all citizens shall have"
        assert result.words[0].word == "all"
        assert result.words[0].confidence == pytest.approx(0.98)

    _run(go())


def test_timeout() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("slow")

    async def go() -> None:
        provider = DeepgramSpeechProvider("dg-test", client=_client(handler))
        with pytest.raises(SpeechTimeout):
            await provider.transcribe(b"x", mime_type="audio/webm")

    _run(go())


def test_provider_http_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(502, json={"error": "nope"})

    async def go() -> None:
        provider = DeepgramSpeechProvider("dg-test", client=_client(handler))
        with pytest.raises(SpeechProviderError):
            await provider.transcribe(b"x", mime_type="audio/webm")

    _run(go())


def test_malformed_payload() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"results": {}})

    async def go() -> None:
        provider = DeepgramSpeechProvider("dg-test", client=_client(handler))
        with pytest.raises(SpeechProviderError):
            await provider.transcribe(b"x", mime_type="audio/webm")

    _run(go())
