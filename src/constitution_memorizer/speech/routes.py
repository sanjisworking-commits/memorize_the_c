"""Unit-scoped speech transcription for Letters and Recite."""

from __future__ import annotations

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import JSONResponse

from constitution_memorizer.speech.align import (
    AlignmentHit,
    align_text,
    keyterm_shortlist,
    tokenize,
)
from constitution_memorizer.speech.limits import (
    SpeechRateLimiter,
    SpeechTooLarge,
    mime_allowed,
    read_upload_limited,
)
from constitution_memorizer.speech.provider import (
    SpeechError,
    SpeechUnavailable,
    Transcript,
)
from constitution_memorizer.web.entitlements import resolve_learn_access
from constitution_memorizer.web.request_context import bound_engine

router = APIRouter()

_ALLOWED_MODES = frozenset({"letters", "recite"})


def _engine(request: Request):
    bound = getattr(request.state, "bound_engine", None) or bound_engine.get()
    if bound is not None:
        return bound
    return request.app.state.engine


def _rate_key(request: Request) -> str:
    """Guest buckets are the TCP peer IP, not a cookie or X-Forwarded-For.

    A client-supplied session cookie or spoofed forwarded header must not
    mint a fresh limiter bucket.
    """
    user = getattr(request.state, "current_user", None)
    if user is not None:
        return f"user:{user.id}"
    host = request.client.host if request.client is not None else "unknown"
    return f"ip:{host}"


def _error(code: str, status: int) -> JSONResponse:
    return JSONResponse({"ok": False, "error": code}, status_code=status)


def _alignment_payload(hits: list[AlignmentHit]) -> list[dict[str, object]]:
    return [{"index": hit.index, "status": hit.status} for hit in hits]


@router.post("/learn/{unit_id}/speech/transcribe")
async def transcribe_utterance(
    request: Request,
    unit_id: str,
    mode: str = Form(...),
    from_index: int = Form(0),
    text: str = Form(""),
    audio: UploadFile | None = File(None),
    expected: str = Form(""),
) -> JSONResponse:
    # ``expected`` is accepted so a client cannot smuggle it as a surprise
    # field that we then *use*. It is ignored; the unit text is authoritative.
    del expected

    mode = (mode or "").strip().lower()
    if mode not in _ALLOWED_MODES:
        return _error("invalid_mode", 400)

    eng = _engine(request)
    unit = eng.get_unit(unit_id)
    if unit is None:
        return _error("not_found", 404)

    access = resolve_learn_access(request, eng, unit.article_number)
    if access.is_locked(mode):
        return JSONResponse(
            {"ok": False, "error": "mode_locked", "mode": mode},
            status_code=403,
        )

    limiter: SpeechRateLimiter = request.app.state.speech_rate_limiter
    if not limiter.allow(_rate_key(request)):
        return _error("rate_limited", 429)

    typed = (text or "").strip()
    transcript_text = ""
    words_payload: list[dict[str, object]] = []

    if typed:
        transcript_text = typed
    else:
        if audio is None:
            return _error("empty", 400)
        content_type = audio.content_type or ""
        if not mime_allowed(content_type):
            return _error("unsupported_type", 400)
        try:
            audio_bytes = await read_upload_limited(audio)
        except SpeechTooLarge:
            return _error("too_large", 413)
        if not audio_bytes:
            return _error("empty", 400)

        provider = request.app.state.speech_provider
        keyterms = keyterm_shortlist(unit.text)
        try:
            result: Transcript = await provider.transcribe(
                audio_bytes,
                mime_type=content_type.split(";")[0].strip() or "audio/webm",
                keyterms=keyterms,
            )
        except SpeechUnavailable:
            return _error("unavailable", 503)
        except SpeechError as exc:
            return _error(getattr(exc, "error_code", "provider_error"), 502)

        transcript_text = result.text.strip()
        words_payload = [
            {"word": item.word, "confidence": item.confidence}
            for item in result.words
        ]
        if not transcript_text:
            return _error("empty", 400)

    payload: dict[str, object] = {
        "ok": True,
        "transcript": transcript_text,
        "words": words_payload,
    }
    if mode == "letters":
        try:
            start = max(0, int(from_index))
        except (TypeError, ValueError):
            start = 0
        if start > len(tokenize(unit.text)):
            start = 0
        payload["alignment"] = _alignment_payload(
            align_text(unit.text, transcript_text, from_index=start)
        )
    return JSONResponse(payload)
