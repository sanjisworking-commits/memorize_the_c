"""Repeated header, footer and duplicate-line detection."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

from rapidfuzz import fuzz

from constitution_memorizer.config import PipelineConfig, default_config
from constitution_memorizer.normalization.line_normalizer import NormalizedLine
from constitution_memorizer.schemas import NormalizationEvent

_PAGE_NUMBER_RE = re.compile(r"^\s*\d{1,4}\s*$")
_PAGE_NUMBER_OF_RE = re.compile(
    r"^\s*(?:page\s+)?\d{1,4}\s*(?:/|of)\s*\d{1,4}\s*$",
    re.IGNORECASE,
)


@dataclass
class RepetitionDetectionResult:
    """Outcome of header/footer/duplicate detection."""

    lines: list[NormalizedLine]
    events: list[NormalizationEvent]
    repeated_headers_removed: int = 0
    duplicate_blocks_removed: int = 0
    page_numbers_removed: int = 0


def _compile_footer_patterns(config: PipelineConfig) -> list[re.Pattern[str]]:
    patterns: list[re.Pattern[str]] = []
    for raw in config.known_footer_patterns:
        try:
            patterns.append(re.compile(raw, re.IGNORECASE))
        except re.error:
            patterns.append(re.compile(re.escape(raw), re.IGNORECASE))
    return patterns


def _is_known_header(text: str, known_headers: list[str], threshold: float) -> bool:
    stripped = text.strip()
    if not stripped:
        return False
    for header in known_headers:
        if stripped == header:
            return True
        if fuzz.ratio(stripped, header) >= threshold * 100:
            return True
    return False


def _looks_like_page_number(text: str, max_digits: int) -> bool:
    stripped = text.strip()
    if not stripped:
        return False
    if _PAGE_NUMBER_OF_RE.match(stripped):
        return True
    if _PAGE_NUMBER_RE.match(stripped) and len(stripped) <= max_digits:
        return True
    return False


def detect_and_remove_repetitions(
    lines: list[NormalizedLine],
    config: PipelineConfig | None = None,
    *,
    estimated_page_count: int | None = None,
) -> RepetitionDetectionResult:
    """
    Remove repeated headers/footers and isolated page numbers carefully.

    A line is never deleted solely because it appears more than once. Removal
    requires a known header pattern, a configured footer pattern, a high
    cross-page frequency signal, or a reliable page-number shape.

    Consecutive exact duplicate lines (PDF extraction artefacts) are collapsed
    with an audit event; the removed copy is retained in the event trail.
    """
    config = config or default_config()
    events: list[NormalizationEvent] = []
    footer_patterns = _compile_footer_patterns(config)
    threshold = config.near_duplicate_threshold

    # Frequency among non-empty lines.
    non_empty = [ln.text.strip() for ln in lines if ln.text.strip()]
    counts = Counter(non_empty)
    unique_line_count = max(len(counts), 1)
    page_estimate = estimated_page_count or max(1, len(lines) // 40)

    auto_headers: set[str] = set()
    for text, count in counts.items():
        if len(text) < config.min_header_length:
            continue
        frequency = count / max(page_estimate, 1)
        if frequency >= config.minimum_header_page_frequency and count >= 3:
            # Prefer short-ish header-like lines (not long body paragraphs).
            if (len(text) <= 80 and text.upper() == text) or _is_known_header(
                text, config.known_headers, threshold
            ):
                auto_headers.add(text)

    repeated_headers_removed = 0
    page_numbers_removed = 0
    duplicate_blocks_removed = 0

    kept: list[NormalizedLine] = []
    previous_kept_text: str | None = None

    for line in lines:
        text = line.text
        stripped = text.strip()

        if not stripped:
            kept.append(line)
            previous_kept_text = ""
            continue

        # Consecutive exact duplicates.
        if previous_kept_text is not None and stripped == previous_kept_text.strip():
            line.kept = False
            line.removal_reason = "consecutive_duplicate"
            events.append(
                NormalizationEvent(
                    event_type="removed_duplicate_line",
                    original_text=stripped,
                    normalized_text="",
                    page_number=line.page_number,
                    reason="Consecutive exact duplicate line from PDF extraction",
                    confidence=0.92,
                    line_index=line.index,
                )
            )
            duplicate_blocks_removed += 1
            continue

        remove = False
        reason = ""
        event_type = ""
        confidence = 0.0

        if _is_known_header(stripped, config.known_headers, threshold):
            # Only remove if it appears often enough OR matches known list strongly.
            if counts[stripped] >= 2 or stripped in config.known_headers:
                remove = True
                reason = "Matched known removable header/footer pattern"
                event_type = "removed_repeated_header"
                confidence = 0.98
        elif stripped in auto_headers:
            remove = True
            reason = (
                f"Automatically detected repeated header "
                f"(count={counts[stripped]}, pages≈{page_estimate})"
            )
            event_type = "removed_repeated_header"
            confidence = min(0.99, counts[stripped] / max(page_estimate, 1))
        elif any(p.search(stripped) for p in footer_patterns):
            if counts[stripped] >= 2 or len(stripped) <= 60:
                remove = True
                reason = "Matched known footer/publisher pattern"
                event_type = "removed_repeated_footer"
                confidence = 0.9
        elif _looks_like_page_number(stripped, config.max_page_number_digits):
            # Isolated page numbers only — not Article numbers (those have trailing text).
            remove = True
            reason = "Isolated page number line"
            event_type = "removed_page_number"
            confidence = 0.85

        if remove:
            line.kept = False
            line.removal_reason = event_type
            events.append(
                NormalizationEvent(
                    event_type=event_type,
                    original_text=stripped,
                    normalized_text="",
                    page_number=line.page_number,
                    reason=reason,
                    confidence=confidence,
                    line_index=line.index,
                )
            )
            if event_type == "removed_page_number":
                page_numbers_removed += 1
            else:
                repeated_headers_removed += 1
            continue

        kept.append(line)
        previous_kept_text = text

    # Re-index kept lines for downstream consumers while preserving original index.
    return RepetitionDetectionResult(
        lines=kept,
        events=events,
        repeated_headers_removed=repeated_headers_removed,
        duplicate_blocks_removed=duplicate_blocks_removed,
        page_numbers_removed=page_numbers_removed,
    )


def normalize_document(
    text: str,
    config: PipelineConfig | None = None,
    *,
    estimated_page_count: int | None = None,
) -> tuple[list[NormalizedLine], list[NormalizationEvent], dict[str, int]]:
    """
    Full normalization pipeline: clean → hyphen-join → repetition removal.

    Returns kept lines, all events, and removal counters.
    """
    from constitution_memorizer.normalization.line_normalizer import normalize_markdown

    config = config or default_config()
    base = normalize_markdown(text)
    repetition = detect_and_remove_repetitions(
        base.lines,
        config,
        estimated_page_count=estimated_page_count,
    )
    events = [*base.events, *repetition.events]
    stats = {
        "repeated_headers_removed": repetition.repeated_headers_removed,
        "duplicate_blocks_removed": repetition.duplicate_blocks_removed,
        "page_numbers_removed": repetition.page_numbers_removed,
    }
    return repetition.lines, events, stats
