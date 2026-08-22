"""Normalization, speakable targets, exact match, and Needleman–Wunsch alignment."""

from __future__ import annotations

from constitution_memorizer.speech.align import (
    align_text,
    align_tokens,
    is_structural_token,
    keyterm_shortlist,
    norm_word,
    speakable_targets,
    tokenize,
    words_match,
)


def test_norm_word_strips_case_and_punctuation() -> None:
    assert norm_word("Citizens,") == "citizens"
    assert norm_word("CITIZENS") == "citizens"
    assert norm_word("citizens") == "citizens"


def test_words_match_rejects_synonyms() -> None:
    assert words_match("shall", "will") is False
    assert words_match("State", "government") is False
    assert words_match("shall", "shall") is True
    assert words_match("Legislature", "legislature") is True


def test_words_match_is_exact_only() -> None:
    assert words_match("promulgation", "promulgaton") is False
    assert words_match("the", "tha") is False
    assert words_match("citizens,", "citizens") is True


def test_structural_numbering_and_punctuation() -> None:
    for token in ("(1)", "(2)", "(a)", "(b)", "(i)", "(iv)", "(iii)", "1.", "(1)(a)", "—", ",", ";"):
        assert is_structural_token(token), token
    for token in ("No", "person", "shall", "Citizens,", "Article"):
        assert not is_structural_token(token), token


def test_speakable_targets_skip_clause_number() -> None:
    targets = speakable_targets(
        "(1) No person shall be convicted of any offence except for violation of a law in force."
    )
    assert targets[0] == (1, "No")
    assert 0 not in {index for index, _word in targets}
    assert "shall" in {word for _index, word in targets}


def test_align_exact_sentence() -> None:
    expected = tokenize("All citizens shall have the right")
    heard = tokenize("All citizens shall have the right")
    hits = align_tokens(expected, heard)
    assert [h.status for h in hits] == ["match"] * 6
    assert [h.index for h in hits] == list(range(6))


def test_align_substitution_shall_will() -> None:
    hits = align_text(
        "All citizens shall have the right",
        "All citizens will have the right",
    )
    by_index = {h.index: h.status for h in hits}
    assert by_index[0] == "match"
    assert by_index[1] == "match"
    assert by_index[2] == "substitute"
    assert by_index[3] == "match"
    assert by_index[4] == "match"
    assert by_index[5] == "match"


def test_align_ignores_leading_clause_number() -> None:
    hits = align_text(
        "(1) No person shall be convicted",
        "No person shall be convicted",
    )
    by_index = {h.index: h.status for h in hits}
    assert 0 not in by_index
    assert by_index[1] == "match"
    assert by_index[2] == "match"
    assert by_index[3] == "match"
    assert by_index[4] == "match"
    assert by_index[5] == "match"


def test_align_fuzzy_edit_is_substitute_not_match() -> None:
    hits = align_text("the promulgation of an ordinance", "the promulgaton of an ordinance")
    by_index = {h.index: h.status for h in hits}
    assert by_index[1] == "substitute"
    assert by_index[0] == "match"


def test_align_insertion_does_not_shift_later_matches() -> None:
    hits = align_text(
        "the right to freedom of speech",
        "the right extra to freedom of speech",
    )
    by_index = {h.index: h.status for h in hits}
    assert by_index[0] == "match"
    assert by_index[1] == "match"
    assert by_index[2] == "match"
    assert by_index[3] == "match"


def test_align_deletion_does_not_shift_later_matches() -> None:
    hits = align_text(
        "the right to freedom of speech",
        "the right freedom of speech",
    )
    by_index = {h.index: h.status for h in hits}
    assert by_index[0] == "match"
    assert by_index[1] == "match"
    assert 2 not in by_index or by_index[2] != "match"
    assert by_index[3] == "match"
    assert by_index[4] == "match"
    assert by_index[5] == "match"


def test_align_repeated_words_uses_from_index_window() -> None:
    expected = tokenize("the Union and the State")
    first = align_tokens(expected, tokenize("the Union"), from_index=0, window=3)
    assert [h.index for h in first if h.status == "match"] == [0, 1]
    second = align_tokens(expected, tokenize("the State"), from_index=3, window=3)
    assert [h.index for h in second if h.status == "match"] == [3, 4]


def test_align_short_utterance_stays_at_from_index() -> None:
    hits = align_text(
        "(1) No person shall be convicted of any offence except for violation of a law in force.",
        "will",
        from_index=3,
    )
    by_index = {h.index: h.status for h in hits}
    assert by_index == {3: "substitute"}


def test_align_prefix_delete_does_not_cascade() -> None:
    hits = align_text(
        "all citizens shall have the right",
        "citizens shall have the right",
    )
    by_index = {h.index: h.status for h in hits}
    assert 0 not in by_index
    assert by_index[1] == "match"
    assert by_index[2] == "match"
    assert by_index[3] == "match"
    assert by_index[4] == "match"
    assert by_index[5] == "match"


def test_keyterm_shortlist_caps_at_100() -> None:
    words = " ".join(f"terminology{i:03d}" for i in range(150))
    terms = keyterm_shortlist(words)
    assert len(terms) == 100
    assert terms[0] == "terminology000"
    assert "terminology099" in terms
    assert "terminology100" not in terms


def test_keyterm_shortlist_drops_function_words() -> None:
    terms = keyterm_shortlist(
        "Notwithstanding anything in this Constitution, the promulgation "
        "of an ordinance by the legislature after appropriation from the "
        "Consolidated Fund."
    )
    lowered = set(terms)
    assert "the" not in lowered
    assert "of" not in lowered
    assert "and" not in lowered
    assert "notwithstanding" in lowered
    assert "promulgation" in lowered
    assert "ordinance" in lowered
    assert "legislature" in lowered
    assert "appropriation" in lowered
    assert "consolidated" in lowered
    assert len(terms) <= 100
