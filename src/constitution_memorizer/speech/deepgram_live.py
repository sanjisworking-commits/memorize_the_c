"""Deepgram Nova-3 live (streaming) transcription over WebSocket.

The browser never talks to Deepgram: audio flows browser → our WS route →
this session → Deepgram, and interim/final transcript events flow back the
same way. Uses the ``websockets`` package, which ships with
``uvicorn[standard]`` (already a pinned runtime dependency).

Audio exists only in transit; nothing is persisted.
"""

from __future__ import annotations

import json
import logging
from typing import AsyncIterator, Sequence
from urllib.parse import urlencode

from constitution_memorizer.speech.provider import (
    LiveTranscriptEvent,
    SpeechProviderError,
    SpeechUnavailable,
)

logger = logging.getLogger(__name__)

DEEPGRAM_LIVE_URL = "wss://api.deepgram.com/v1/listen"
CONNECT_TIMEOUT_SECONDS = 10.0


class DeepgramLiveSession:
    """One live stream. ``send_audio`` in, ``events()`` out."""

    def __init__(self, ws) -> None:
        self._ws = ws
        self._closed = False

    async def send_audio(self, chunk: bytes) -> None:
        if self._closed or not chunk:
            return
        await self._ws.send(chunk)

    async def finish(self) -> None:
        if self._closed:
            return
        try:
            await self._ws.send(json.dumps({"type": "CloseStream"}))
        except Exception:  # noqa: BLE001 — already closing
            pass

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            await self._ws.close()
        except Exception:  # noqa: BLE001
            pass

    async def events(self) -> AsyncIterator[LiveTranscriptEvent]:
        """Yield transcript events until Deepgram closes the stream."""
        import websockets

        try:
            async for message in self._ws:
                if isinstance(message, (bytes, bytearray)):
                    continue
                try:
                    payload = json.loads(message)
                except ValueError:
                    continue
                if payload.get("type") != "Results":
                    continue
                try:
                    alternative = payload["channel"]["alternatives"][0]
                except (KeyError, IndexError, TypeError):
                    continue
                text = str(alternative.get("transcript") or "").strip()
                is_final = bool(payload.get("is_final"))
                if not text and not is_final:
                    continue
                yield LiveTranscriptEvent(text=text, is_final=is_final)
        except websockets.exceptions.ConnectionClosedOK:
            return
        except websockets.exceptions.ConnectionClosedError as exc:
            logger.warning("Deepgram live stream closed abnormally: %s", exc.code)
            return


async def deepgram_live_connect(
    api_key: str,
    *,
    keyterms: Sequence[str] = (),
) -> DeepgramLiveSession:
    """Open a Deepgram live session (mirrors the pre-recorded params)."""
    import websockets

    key = (api_key or "").strip()
    if not key:
        raise SpeechUnavailable("Speech recognition is not configured")

    params: list[tuple[str, str]] = [
        ("model", "nova-3"),
        ("language", "en-IN"),
        ("smart_format", "false"),
        ("mip_opt_out", "true"),
        ("interim_results", "true"),
        ("punctuate", "false"),
    ]
    for term in keyterms:
        cleaned = term.strip()
        if cleaned:
            params.append(("keyterm", cleaned))
    url = f"{DEEPGRAM_LIVE_URL}?{urlencode(params)}"
    try:
        ws = await websockets.connect(
            url,
            additional_headers={"Authorization": f"Token {key}"},
            open_timeout=CONNECT_TIMEOUT_SECONDS,
            max_size=1 << 20,
        )
    except Exception as exc:  # noqa: BLE001 — one boundary, one error type
        logger.warning("Deepgram live connect failed: %s", type(exc).__name__)
        raise SpeechProviderError("Speech recognition failed") from exc
    return DeepgramLiveSession(ws)
