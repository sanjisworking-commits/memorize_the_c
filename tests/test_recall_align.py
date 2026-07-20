"""Unit tests for recall LCS alignment (Sprint 18)."""

from __future__ import annotations

from constitution_memorizer.web.recall_align import (
    align_text,
    align_tokens,
    norm_word,
    tokenize,
)


def test_norm_word_strips_case_and_punctuation():
    assert norm_word("Himself.") == "himself"
    assert norm_word("(1)") == "1"
    assert norm_word("—") == ""


def test_tokenize_splits_on_whitespace():
    assert tokenize("  No person shall  ") == ["No", "person", "shall"]
    assert tokenize("") == []


def test_align_exact_match_all_hits():
    result = align_text("No person shall be convicted", "No person shall be convicted")
    assert result.hits == 5
    assert result.total == 5
    assert result.percent == 100
    assert result.extras == []
    assert result.stats_label() == "5 / 5 recalled · 100%"


def test_align_partial_and_out_of_order_gaps():
    # Spoken skips middle words; LCS still credits recalled tokens.
    source = ["No", "person", "shall", "be", "convicted", "of", "any", "offence"]
    spoken = ["No", "person", "convicted", "offence"]
    result = align_tokens(source, spoken)
    assert result.hits == 4
    assert 0 in result.hit_indices
    assert 1 in result.hit_indices
    assert 4 in result.hit_indices
    assert 7 in result.hit_indices
    assert result.extras == []


def test_align_extras_for_unmatched_spoken():
    result = align_text("No person shall", "No person hello shall world")
    assert result.hits == 3
    assert "hello" in result.extras
    assert "world" in result.extras


def test_align_punctuation_insensitive():
    result = align_text("No person shall be convicted.", "no person shall be convicted")
    assert result.hits == 5
    assert result.percent == 100
