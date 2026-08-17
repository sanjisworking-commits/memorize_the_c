"""Deterministic quiz generation and grading for Learn's Test mode.

Pure module, no I/O. The server builds a seeded quiz per (unit, revision
cycle), sends only the questions to the client (never the answers), and
regenerates the identical quiz to grade a submission — grading is stateless
because the same ``(unit_id, cycle)`` always yields the same questions.

Determinism rules: every candidate pool is sorted with a stable key before
any seeded operation, and all sampling/shuffling uses the one
``random.Random(quiz_seed(unit_id, cycle))`` instance.
"""

from __future__ import annotations

import random
import re
from dataclasses import dataclass
from hashlib import sha256
from typing import Mapping, Sequence

from constitution_memorizer.learning.schemas import LearningUnit, LearningUnitType

# Words need at least this many letters to become a keyword blank.
MIN_KEYWORD_LETTERS = 6
# Words of context shown on each side of a keyword blank.
CONTEXT_WORDS = 8
DEFAULT_QUESTION_COUNT = 5
MCQ_DISTRACTORS = 3

_KIND_MCQ = "mcq"
_KIND_FILL = "fill"


def normalize_answer(text: object) -> str:
    """Lowercase and strip non-alphanumerics — mirrors ``normWord`` in app.js."""
    return re.sub(r"[^a-z0-9]", "", str(text).lower())


def quiz_seed(unit_id: str, cycle: int) -> int:
    digest = sha256(f"{unit_id}:{cycle}".encode()).digest()
    return int.from_bytes(digest[:8], "big")


@dataclass(frozen=True)
class QuizQuestion:
    kind: str  # "mcq" | "fill"
    prompt: str
    options: tuple[str, ...] = ()  # mcq only
    answer_index: int = -1  # mcq only
    answer_text: str = ""  # fill only

    def public_dict(self) -> dict[str, object]:
        """Client-safe shape — never includes the answer."""
        return {
            "kind": self.kind,
            "prompt": self.prompt,
            "options": list(self.options),
        }


def _letter_len(word: str) -> int:
    return len(re.sub(r"[^A-Za-z]", "", word))


def _clean_word(word: str) -> str:
    return re.sub(r"^\W+|\W+$", "", word)


@dataclass(frozen=True)
class _KeywordCandidate:
    index: int
    surface: str  # cleaned word, the canonical answer form
    window: tuple[str, ...]  # context words with the target as "____"


def _keyword_candidates(text: str) -> list[_KeywordCandidate]:
    words = text.split()
    candidates: list[_KeywordCandidate] = []
    for i, raw in enumerate(words):
        clean = _clean_word(raw)
        if _letter_len(clean) < MIN_KEYWORD_LETTERS:
            continue
        lo = max(0, i - CONTEXT_WORDS)
        hi = min(len(words), i + CONTEXT_WORDS + 1)
        norm = normalize_answer(clean)
        # The answer must not leak: skip words that repeat inside the window.
        if any(
            j != i and normalize_answer(_clean_word(words[j])) == norm
            for j in range(lo, hi)
        ):
            continue
        window = tuple(
            "____" if j == i else words[j] for j in range(lo, hi)
        )
        prefix = ("…",) if lo > 0 else ()
        suffix = ("…",) if hi < len(words) else ()
        candidates.append(
            _KeywordCandidate(index=i, surface=clean, window=prefix + window + suffix)
        )
    return candidates


def _article_units(units: Mapping[str, LearningUnit]) -> list[LearningUnit]:
    return sorted(
        (
            u
            for u in units.values()
            if u.type == LearningUnitType.ARTICLE and u.article_number
        ),
        key=lambda u: u.id,
    )


def _is_article_unit(unit: LearningUnit) -> bool:
    return unit.type == LearningUnitType.ARTICLE and bool(unit.article_number)


def _dedupe_normalized(values: Sequence[str], *, exclude: str) -> list[str]:
    """Keep first surface form per normalized value; drop the answer's form."""
    excluded = normalize_answer(exclude)
    seen: set[str] = set()
    kept: list[str] = []
    for value in values:
        norm = normalize_answer(value)
        if not norm or norm == excluded or norm in seen:
            continue
        seen.add(norm)
        kept.append(value)
    return kept


def _make_mcq(
    prompt: str, answer: str, distractor_pool: list[str], rng: random.Random
) -> QuizQuestion | None:
    distractors = _dedupe_normalized(distractor_pool, exclude=answer)
    if len(distractors) < MCQ_DISTRACTORS:
        return None
    options = [answer] + rng.sample(distractors, MCQ_DISTRACTORS)
    rng.shuffle(options)
    return QuizQuestion(
        kind=_KIND_MCQ,
        prompt=prompt,
        options=tuple(options),
        answer_index=options.index(answer),
    )


def _title_mcq(
    unit: LearningUnit, units: Mapping[str, LearningUnit], rng: random.Random
) -> QuizQuestion | None:
    """Article-level only: the article number is the one safe identifier."""
    if not _is_article_unit(unit) or not unit.title:
        return None
    pool = [
        u.title
        for u in _article_units(units)
        if u.id != unit.id and u.title
    ]
    return _make_mcq(
        f"Which title belongs to Article {unit.article_number}?",
        unit.title,
        pool,
        rng,
    )


def _number_mcq(
    unit: LearningUnit, units: Mapping[str, LearningUnit], rng: random.Random
) -> QuizQuestion | None:
    if not _is_article_unit(unit) or not unit.title:
        return None
    pool = [
        f"Article {u.article_number}"
        for u in _article_units(units)
        if u.id != unit.id
    ]
    return _make_mcq(
        f"“{unit.title}” belongs to which Article?",
        f"Article {unit.article_number}",
        pool,
        rng,
    )


def _keyword_prompt(candidate: _KeywordCandidate) -> str:
    return "Fill in the missing word: “" + " ".join(candidate.window) + "”"


def _keyword_fill(candidate: _KeywordCandidate) -> QuizQuestion:
    return QuizQuestion(
        kind=_KIND_FILL,
        prompt=_keyword_prompt(candidate),
        answer_text=candidate.surface,
    )


def _keyword_distractor_pool(
    unit: LearningUnit, units: Mapping[str, LearningUnit]
) -> list[str]:
    """Own-text words first, then sibling texts; stable order, min length kept."""
    pool: list[str] = []
    for word in unit.text.split():
        clean = _clean_word(word)
        if _letter_len(clean) >= MIN_KEYWORD_LETTERS:
            pool.append(clean)
    for other in sorted(units.values(), key=lambda u: u.id):
        if other.id == unit.id:
            continue
        for word in other.text.split():
            clean = _clean_word(word)
            if _letter_len(clean) >= MIN_KEYWORD_LETTERS:
                pool.append(clean)
        if len(pool) >= 60:  # plenty for dedupe + sampling; keeps this cheap
            break
    return pool


def _keyword_mcq(
    candidate: _KeywordCandidate,
    unit: LearningUnit,
    units: Mapping[str, LearningUnit],
    rng: random.Random,
) -> QuizQuestion | None:
    question = _make_mcq(
        "Which word completes: “" + " ".join(candidate.window) + "”?",
        candidate.surface,
        _keyword_distractor_pool(unit, units),
        rng,
    )
    return question


def has_quiz(unit: LearningUnit, units: Mapping[str, LearningUnit]) -> bool:
    """Cycle-independent: can this unit produce at least one question?

    When False the Test mode is omitted from the unit's effective required
    modes — it must never be fake-completed just because nothing could be
    asked.
    """
    if _keyword_candidates(unit.text):
        return True
    rng = random.Random(0)  # availability probe only; result is discarded
    return _title_mcq(unit, units, rng) is not None


def build_quiz(
    unit: LearningUnit,
    units: Mapping[str, LearningUnit],
    *,
    cycle: int,
    count: int = DEFAULT_QUESTION_COUNT,
) -> list[QuizQuestion]:
    rng = random.Random(quiz_seed(unit.id, cycle))

    structural: list[QuizQuestion] = []
    for maker in (_title_mcq, _number_mcq):
        question = maker(unit, units, rng)
        if question is not None:
            structural.append(question)

    keywords = _keyword_candidates(unit.text)
    structural = structural[: max(0, count)]
    kw_needed = min(len(keywords), max(0, count - len(structural)))
    selected = rng.sample(keywords, kw_needed) if kw_needed else []

    total = len(structural) + len(selected)
    # Aim for about half MCQ overall; the rest of the keywords become fills.
    mcq_target = (total + 1) // 2
    kw_mcq_budget = max(0, mcq_target - len(structural))
    questions = list(structural)
    for candidate in selected:
        made_mcq = None
        if kw_mcq_budget > 0:
            made_mcq = _keyword_mcq(candidate, unit, units, rng)
        if made_mcq is not None:
            questions.append(made_mcq)
            kw_mcq_budget -= 1
        else:
            questions.append(_keyword_fill(candidate))
    rng.shuffle(questions)
    return questions


def grade_quiz(
    questions: Sequence[QuizQuestion], answers: Sequence[object]
) -> dict[str, object]:
    """Defensive grading: malformed answers simply grade as incorrect."""
    results: list[dict[str, object]] = []
    correct = 0
    for question, answer in zip(questions, answers):
        if question.kind == _KIND_MCQ:
            ok = (
                isinstance(answer, int)
                and not isinstance(answer, bool)
                and answer == question.answer_index
            )
            expected = question.options[question.answer_index]
        else:
            ok = (
                isinstance(answer, str)
                and normalize_answer(answer) != ""
                and normalize_answer(answer) == normalize_answer(question.answer_text)
            )
            expected = question.answer_text
        results.append({"correct": bool(ok), "expected": expected})
        if ok:
            correct += 1
    return {"correct": correct, "total": len(questions), "results": results}
