"""Line-oriented normalization including high-confidence hyphen joins."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from constitution_memorizer.normalization.text_cleaner import clean_text
from constitution_memorizer.schemas import NormalizationEvent

# Word ending with hyphen at end of line, next line starting with lowercase letter.
_HYPHEN_JOIN_RE = re.compile(
    r"^(?P<left>.*?\b[A-Za-z]{2,})-\s*$"
)
_NEXT_CONTINUATION_RE = re.compile(r"^(?P<right>[a-z][A-Za-z']*)(?P<rest>.*)$")


@dataclass
class NormalizedLine:
    """A single normalized line with optional page metadata."""

    index: int
    text: str
    page_number: int | None = None
    original_text: str | None = None
    kept: bool = True
    removal_reason: str | None = None


@dataclass
class NormalizationResult:
    """Result of line normalization."""

    lines: list[NormalizedLine] = field(default_factory=list)
    events: list[NormalizationEvent] = field(default_factory=list)
    text: str = ""


def _split_markdown_into_lines(text: str) -> list[str]:
    return text.split("\n")


def join_hyphenated_line_breaks(
    lines: list[str],
) -> tuple[list[str], list[NormalizationEvent]]:
    """
    Join words split across lines with a trailing hyphen when confidence is high.

    Only joins when the next line begins with a lowercase alphabetic token.
    Does not join when the next line looks like a new structural heading.
    """
    events: list[NormalizationEvent] = []
    if not lines:
        return [], events

    result: list[str] = []
    i = 0
    while i < len(lines):
        current = lines[i]
        match = _HYPHEN_JOIN_RE.match(current)
        if match and i + 1 < len(lines):
            nxt = lines[i + 1]
            nxt_match = _NEXT_CONTINUATION_RE.match(nxt)
            # Avoid joining into ALL-CAPS headings or PART/CHAPTER markers.
            if nxt_match and not nxt.strip().startswith(("PART ", "CHAPTER ", "SCHEDULE")):
                left = match.group("left")
                right = nxt_match.group("right")
                rest = nxt_match.group("rest")
                joined = f"{left}{right}{rest}"
                events.append(
                    NormalizationEvent(
                        event_type="joined_hyphenated_word",
                        original_text=f"{current}\\n{nxt}",
                        normalized_text=joined,
                        reason="High-confidence hyphenated line-break word join",
                        confidence=0.9,
                        line_index=i,
                    )
                )
                result.append(joined)
                i += 2
                continue
        result.append(current)
        i += 1

    return result, events


def normalize_markdown(text: str) -> NormalizationResult:
    """
    Clean text and produce a list of normalized lines.

    Does not remove headers/footers; that is handled by ``repetition_detector``.
    """
    cleaned, clean_events = clean_text(text)
    raw_lines = _split_markdown_into_lines(cleaned)
    joined_lines, join_events = join_hyphenated_line_breaks(raw_lines)

    lines = [
        NormalizedLine(index=i, text=line, original_text=line)
        for i, line in enumerate(joined_lines)
    ]
    result = NormalizationResult(
        lines=lines,
        events=[*clean_events, *join_events],
        text="\n".join(joined_lines),
    )
    return result


def lines_to_serializable(lines: list[NormalizedLine]) -> list[dict]:
    """Serialize normalized lines for intermediate JSON output."""
    return [
        {
            "index": line.index,
            "text": line.text,
            "page_number": line.page_number,
            "original_text": line.original_text,
            "kept": line.kept,
            "removal_reason": line.removal_reason,
        }
        for line in lines
    ]
