"""Conservative character-level text cleaning for PDF extraction artefacts."""

from __future__ import annotations

import re
import unicodedata

from constitution_memorizer.schemas import NormalizationEvent

SOFT_HYPHEN = "\u00ad"
NBSP = "\u00a0"
NARROW_NBSP = "\u202f"
ZERO_WIDTH_SPACE = "\u200b"
ZERO_WIDTH_NON_JOINER = "\u200c"
ZERO_WIDTH_JOINER = "\u200d"
BOM = "\ufeff"

# Collapse runs of spaces/tabs but preserve newlines for line-oriented processing.
_HORIZONTAL_WS_RE = re.compile(r"[^\S\n\r]+")
_MULTI_BLANK_RE = re.compile(r"\n{3,}")


def clean_text(text: str, *, emit_events: bool = True) -> tuple[str, list[NormalizationEvent]]:
    """
    Apply conservative cleaning that does not rewrite legal meaning.

    Allowed operations: soft-hyphen removal, NBSP normalization, excessive
    whitespace collapse, CRLF→LF, and removal of BOM / zero-width characters.
    Em dashes, editorial brackets and footnote markers are preserved.
    """
    events: list[NormalizationEvent] = []
    original = text

    if BOM in text:
        text = text.replace(BOM, "")
        if emit_events:
            events.append(
                NormalizationEvent(
                    event_type="removed_bom",
                    original_text=BOM,
                    normalized_text="",
                    reason="Removed UTF-8 BOM",
                    confidence=1.0,
                )
            )

    for char, name in (
        (SOFT_HYPHEN, "removed_soft_hyphen"),
        (ZERO_WIDTH_SPACE, "removed_zero_width_space"),
        (ZERO_WIDTH_NON_JOINER, "removed_zwnj"),
        (ZERO_WIDTH_JOINER, "removed_zwj"),
    ):
        if char in text:
            count = text.count(char)
            text = text.replace(char, "")
            if emit_events:
                events.append(
                    NormalizationEvent(
                        event_type=name,
                        original_text=char,
                        normalized_text="",
                        reason=f"Removed {count} occurrence(s) of U+{ord(char):04X}",
                        confidence=1.0,
                    )
                )

    if NBSP in text or NARROW_NBSP in text:
        text = text.replace(NBSP, " ").replace(NARROW_NBSP, " ")
        if emit_events:
            events.append(
                NormalizationEvent(
                    event_type="normalized_nbsp",
                    original_text="\\u00a0/\\u202f",
                    normalized_text=" ",
                    reason="Converted non-breaking spaces to regular spaces",
                    confidence=1.0,
                )
            )

    if "\r\n" in text or "\r" in text:
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        if emit_events:
            events.append(
                NormalizationEvent(
                    event_type="normalized_line_endings",
                    original_text="CRLF/CR",
                    normalized_text="LF",
                    reason="Standardized line endings to LF",
                    confidence=1.0,
                )
            )

    collapsed = _HORIZONTAL_WS_RE.sub(" ", text)
    collapsed = _MULTI_BLANK_RE.sub("\n\n", collapsed)
    # Strip trailing spaces on each line without removing blank lines entirely.
    collapsed = "\n".join(line.rstrip() for line in collapsed.split("\n"))

    if collapsed != text and emit_events:
        events.append(
            NormalizationEvent(
                event_type="normalized_whitespace",
                original_text=None,
                normalized_text=None,
                reason="Collapsed excessive horizontal whitespace and blank lines",
                confidence=0.95,
            )
        )
        text = collapsed
    else:
        text = collapsed

    # NFC normalization only (composing form); does not rewrite legal text.
    nfc = unicodedata.normalize("NFC", text)
    if nfc != text and emit_events:
        events.append(
            NormalizationEvent(
                event_type="unicode_nfc",
                original_text=None,
                normalized_text=None,
                reason="Applied Unicode NFC normalization",
                confidence=1.0,
            )
        )
        text = nfc
    else:
        text = nfc

    if text != original and not events and emit_events:
        events.append(
            NormalizationEvent(
                event_type="cleaned_text",
                reason="Text cleaned with conservative rules",
                confidence=0.9,
            )
        )

    return text, events
