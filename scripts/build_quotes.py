#!/usr/bin/env python3
"""Curate civic quotes for the Recall the C interaction layer.

Filter, dedupe, normalize, and canonicalize only. Quote wording is never
paraphrased or rewritten. ``--source`` is required (no hardcoded path).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "data" / "reference" / "quotes.json"

MIN_LEN = 40
MAX_LEN = 220

# Conservative off-tone fragments — scholarly civic register only.
OFF_TONE = (
    "kiss slowly",
    "road trip",
    "hit the road",
    "best road",
    "motivate you",
    "with images",
    "stoic leadership",
    "moonlit garden",
    "hyenas of hate",
    "jackals of hypocrisy",
)

AUTHOR_CANON = (
    (
        re.compile(
            r"gandhi",
            re.I,
        ),
        "Mahatma Gandhi",
    ),
    (
        re.compile(r"ambedkar", re.I),
        "B. R. Ambedkar",
    ),
    (
        re.compile(r"\bobama\b", re.I),
        "Barack Obama",
    ),
)

_DATE_LIKE = re.compile(
    r"\b(?:\d{1,2}\s+)?(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|"
    r"may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|"
    r"nov(?:ember)?|dec(?:ember)?)[a-z]*\.?\s+\d{4}\b"
    r"|\b(?:17|18|19|20)\d{2}\b",
    re.I,
)
_URL = re.compile(r"https?://|www\.", re.I)
_VOLUME = re.compile(r"\bvolume\b|\bvol\.?\b", re.I)
_JUNK_WORD = re.compile(
    r"\bquotes?\b|\bimages?\b|\bcollected works\b|\bmemo \d+",
    re.I,
)


def _norm_space(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").replace("\u00a0", " ")).strip()


def _canonicalize_author(author: str) -> str:
    compact = _norm_space(author)
    for pattern, canon in AUTHOR_CANON:
        if pattern.search(compact):
            return canon
    return compact


def _is_all_caps_title(text: str) -> bool:
    letters = [c for c in text if c.isalpha()]
    if len(letters) < 12:
        return False
    upper = sum(1 for c in letters if c.isupper())
    return upper / len(letters) >= 0.85


def _author_is_fragment(author: str) -> bool:
    if not author or len(author) < 2:
        return True
    if len(author) > 60:
        return True
    if re.search(r"\d", author):
        return True
    if ";" in author or ")." in author:
        return True
    if _VOLUME.search(author) or _DATE_LIKE.search(author):
        return True
    if _JUNK_WORD.search(author) or _URL.search(author):
        return True
    return False


def _text_is_junk(text: str) -> bool:
    if _is_all_caps_title(text):
        return True
    if _JUNK_WORD.search(text) or _URL.search(text) or _VOLUME.search(text):
        return True
    # Bibliographic date fragments ("11 April, 1910"), not years inside a sentence.
    if re.match(r"^\(?\d{1,2}\s+\w+,\s+\d{4}", text):
        return True
    lowered = text.lower()
    return any(frag in lowered for frag in OFF_TONE)


def curate(rows: list[dict]) -> tuple[list[dict[str, str]], Counter]:
    stats: Counter = Counter()
    stats["source"] = len(rows)
    kept: list[dict[str, str]] = []
    seen: set[str] = set()

    for row in rows:
        stats["seen"] += 1
        if not isinstance(row, dict):
            stats["not_object"] += 1
            continue
        text = _norm_space(str(row.get("text") or ""))
        author = _canonicalize_author(str(row.get("author") or ""))
        n = len(text)
        if n < MIN_LEN:
            stats["too_short"] += 1
            continue
        if n > MAX_LEN:
            stats["too_long"] += 1
            continue
        if _text_is_junk(text):
            stats["junk_text"] += 1
            continue
        if _author_is_fragment(author):
            stats["junk_author"] += 1
            continue
        key = text.casefold()
        if key in seen:
            stats["duplicate"] += 1
            continue
        seen.add(key)
        kept.append({"text": text, "author": author})

    stats["kept"] = len(kept)
    return kept, stats


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        required=True,
        type=Path,
        help="Path to the raw civic quotes JSON array",
    )
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)

    source = args.source.expanduser().resolve()
    if not source.is_file():
        print(f"error: source not found: {source}", file=sys.stderr)
        return 1

    raw = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        print("error: source must be a JSON array", file=sys.stderr)
        return 1

    kept, stats = curate(raw)
    out = args.out.expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(kept, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print("quotes build audit")
    print(f"  source count     {stats['source']}")
    print(f"  too short (<{MIN_LEN}) {stats['too_short']}")
    print(f"  too long (>{MAX_LEN})  {stats['too_long']}")
    print(f"  junk text        {stats['junk_text']}")
    print(f"  junk author      {stats['junk_author']}")
    print(f"  duplicate        {stats['duplicate']}")
    print(f"  kept             {stats['kept']}")
    print(f"  wrote            {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
