# Speech transcription (V1)

Letters and Recite send short microphone recordings to Recall the C, not to
Deepgram from the browser.

```text
MediaRecorder
  → POST /learn/{unit_id}/speech/transcribe
  → unit + entitlement + size/MIME/rate limits
  → Deepgram Nova-3 (if DEEPGRAM_API_KEY is set)
  → Python word alignment (Letters)
  → JSON transcript (+ alignment for Letters)
```

Audio exists only in memory for that request. It is never written to disk or
the database.

## Why HTTP chunks, not WebSockets

Recite already scores on Stop. Letters V1 is Start → speak a short phrase →
Check phrase. One blob per check is enough. Automatic 700 ms silence slicing
can be added later on the same route.

## Deepgram

```text
model=nova-3
language=en-IN
smart_format=false
mip_opt_out=true
```

Keyterms are a jargon shortlist derived from `unit.text` (not `the` / `of` /
every word). Cap 100.

The browser never sends expected words. The server tokenizes the unit into
*speakable* targets: clause numbering such as `(1)` / `(a)` / `(iv)` and
punctuation-only tokens are ignored for alignment and completion.

Blue/correct requires an exact normalized match. Generic fuzzy edits
(`promulgation` ≈ `promulgaton`) do not count as correct.

## Entitlement

- `mode=letters` — guests allowed
- `mode=recite` — 403 `mode_locked` for guest / cap-reached

## Limits

- 2 MB streaming cap (chunked read; not an unbounded `read()`)
- Exact MIME allowlist (no filename or prefix fallback)
- Process-local rate limit (20 / 60s). Signed-in keys are `user:{id}`.
  Guests are keyed by the TCP peer IP — not a cookie and not
  `X-Forwarded-For`, which a client can spoof. Expired buckets are
  garbage-collected. Multi-instance Railway is best-effort.

Missing `DEEPGRAM_API_KEY`: the app still starts. The route returns
`unavailable` and the UI offers typed fallback. Typed fallback uses the same
route with `text` and does not call Deepgram.

Infrastructure errors must not paint a Letters cue red.
