"""Tests for conservative text cleaning."""

from __future__ import annotations

from constitution_memorizer.normalization.text_cleaner import clean_text


def test_soft_hyphen_removal() -> None:
    text = "edu\u00adcation"
    cleaned, events = clean_text(text)
    assert cleaned == "education"
    assert any(e.event_type == "removed_soft_hyphen" for e in events)


def test_nbsp_normalization() -> None:
    text = "equality\u00a0before\u202fthe law"
    cleaned, events = clean_text(text)
    assert "\u00a0" not in cleaned
    assert "\u202f" not in cleaned
    assert "equality before the law" in cleaned
    assert any(e.event_type == "normalized_nbsp" for e in events)


def test_line_ending_normalization() -> None:
    text = "line1\r\nline2\rline3\n"
    cleaned, events = clean_text(text)
    assert "\r" not in cleaned
    assert "line1\nline2\nline3" in cleaned
    assert any(e.event_type == "normalized_line_endings" for e in events)


def test_preserves_em_dash_and_brackets() -> None:
    text = "21A. Right to education.—The State [shall] provide."
    cleaned, _ = clean_text(text)
    assert "—" in cleaned
    assert "[shall]" in cleaned


def test_preserves_footnote_markers() -> None:
    text = "1[21A. Right to education.—Body"
    cleaned, _ = clean_text(text)
    assert cleaned.startswith("1[21A")


def test_does_not_rewrite_capitalization() -> None:
    text = "THE UNION AND ITS TERRITORY"
    cleaned, _ = clean_text(text)
    assert cleaned == text
