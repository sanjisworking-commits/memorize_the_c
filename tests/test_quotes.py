"""Curated quotes catalog and deterministic selection."""

from __future__ import annotations

from pathlib import Path

from constitution_memorizer.web.quotes import get_quote_for, load_quotes

QUOTES_PATH = Path(__file__).resolve().parents[1] / "data" / "reference" / "quotes.json"


def test_quotes_json_loads_with_schema():
    quotes = load_quotes(QUOTES_PATH)
    assert quotes
    for row in quotes:
        assert set(row.keys()) == {"text", "author"}
        assert isinstance(row["text"], str) and row["text"].strip()
        assert isinstance(row["author"], str) and row["author"].strip()
        assert 40 <= len(row["text"]) <= 220


def test_get_quote_for_is_deterministic():
    quotes = load_quotes(QUOTES_PATH)
    seed = "00000000-0000-4000-8000-000000000001:clause-1:2026-08-14:2"
    first = get_quote_for(quotes, seed)
    second = get_quote_for(quotes, seed)
    assert first == second
    other = get_quote_for(quotes, seed + ":x")
    assert other is not None
    # Different seed may collide but almost always differs on this catalog.
    assert first != other or len(quotes) == 1


def test_get_quote_for_empty_catalog():
    assert get_quote_for([], "anything") is None
