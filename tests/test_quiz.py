"""Deterministic quiz generation and grading (Test mode engine)."""

from __future__ import annotations

from constitution_memorizer.learning.schemas import LearningUnit, LearningUnitType
from constitution_memorizer.web.quiz import (
    QuizQuestion,
    build_quiz,
    grade_quiz,
    has_quiz,
    normalize_answer,
    quiz_seed,
)


def _article(num: int, title: str, text: str) -> LearningUnit:
    return LearningUnit(
        id=f"article-{num}",
        type=LearningUnitType.ARTICLE,
        article_number=str(num),
        display_title=f"Article {num}",
        title=title,
        text=text,
        estimated_learning_time=30,
        revision_order=num,
    )


RICH_TEXT = (
    "The State shall not deny to any person equality before the law or the "
    "equal protection of the laws within the territory of India on grounds "
    "only of religion, race, caste, sex or place of birth. Nothing shall "
    "prevent the State from making any special provision for women and "
    "children or for the advancement of any socially and educationally "
    "backward classes of citizens or for the Scheduled Castes and the "
    "Scheduled Tribes regarding their admission to educational institutions "
    "including private institutions, whether aided or unaided by the State."
)


def _units() -> dict[str, LearningUnit]:
    units = {
        "article-14": _article(14, "Equality before law", RICH_TEXT),
        "article-15": _article(
            15,
            "Prohibition of discrimination",
            "The State shall not discriminate against any citizen.",
        ),
        "article-16": _article(
            16,
            "Equality of opportunity in matters of public employment",
            "There shall be equality of opportunity for all citizens.",
        ),
        "article-17": _article(
            17, "Abolition of Untouchability", "Untouchability is abolished."
        ),
        "article-19": _article(
            19,
            "Protection of certain rights regarding freedom of speech",
            "All citizens shall have the right to freedom of speech.",
        ),
    }
    return units


def test_same_seed_gives_identical_quiz():
    units = _units()
    unit = units["article-14"]
    first = build_quiz(unit, units, cycle=3)
    second = build_quiz(unit, units, cycle=3)
    assert first == second  # identical questions AND identical option order


def test_cycles_rotate_question_selection():
    units = _units()
    unit = units["article-14"]
    assert build_quiz(unit, units, cycle=0) != build_quiz(unit, units, cycle=1)
    assert quiz_seed(unit.id, 0) != quiz_seed(unit.id, 1)


def test_full_quiz_mixes_mcq_and_fill():
    units = _units()
    quiz = build_quiz(units["article-14"], units, cycle=0)
    kinds = {q.kind for q in quiz}
    assert len(quiz) == 5
    assert kinds == {"mcq", "fill"}


def test_mcq_options_are_distinct_and_answer_appears_once():
    units = _units()
    for cycle in range(4):
        for q in build_quiz(units["article-14"], units, cycle=cycle):
            if q.kind != "mcq":
                continue
            norms = [normalize_answer(o) for o in q.options]
            assert len(norms) == len(set(norms)), q.options
            answer_norm = norms[q.answer_index]
            assert norms.count(answer_norm) == 1


def test_prompt_never_contains_its_own_answer():
    units = _units()
    for cycle in range(4):
        for q in build_quiz(units["article-14"], units, cycle=cycle):
            answer = q.options[q.answer_index] if q.kind == "mcq" else q.answer_text
            prompt_words = {normalize_answer(w) for w in q.prompt.split()}
            assert normalize_answer(answer) not in prompt_words, q.prompt


def test_public_dict_leaks_no_answers():
    units = _units()
    for q in build_quiz(units["article-14"], units, cycle=0):
        public = q.public_dict()
        assert set(public) == {"kind", "prompt", "options"}


def test_untitled_unit_degrades_to_keyword_questions():
    units = _units()
    clause = LearningUnit(
        id="article-14-clause-1",
        type=LearningUnitType.CLAUSE,
        article_number="14",
        display_title="Article 14(1)",
        title="Equality before law",
        text=RICH_TEXT,
        estimated_learning_time=30,
        revision_order=1,
    )
    units[clause.id] = clause
    quiz = build_quiz(clause, units, cycle=0)
    assert quiz  # keyword templates still work
    for q in quiz:
        assert "belongs to" not in q.prompt  # no structural MCQs for clauses


def test_sparse_text_degrades_count():
    units = _units()
    tiny = _article(99, "", "Short words about jurisdiction and territory here.")
    units[tiny.id] = tiny
    quiz = build_quiz(tiny, units, cycle=0)
    assert 0 < len(quiz) < 5


def test_empty_unit_has_no_quiz():
    units = _units()
    empty = LearningUnit(
        id="overview-1",
        type=LearningUnitType.PART_OVERVIEW,
        display_title="Part I",
        title=None,
        text="a b c",
        estimated_learning_time=30,
        revision_order=0,
    )
    units[empty.id] = empty
    assert not has_quiz(empty, units)
    assert build_quiz(empty, units, cycle=0) == []
    assert has_quiz(units["article-14"], units)


def test_grade_quiz_normalizes_fill_answers():
    q = QuizQuestion(kind="fill", prompt="p", answer_text="equality")
    graded = grade_quiz([q], ["  Equality, "])
    assert graded == {
        "correct": 1,
        "total": 1,
        "results": [{"correct": True, "expected": "equality"}],
    }


def test_grade_quiz_defensive_against_malformed_answers():
    mcq = QuizQuestion(
        kind="mcq", prompt="p", options=("a", "b", "c", "d"), answer_index=0
    )
    fill = QuizQuestion(kind="fill", prompt="p", answer_text="word")
    graded = grade_quiz([mcq, fill], [True, {"x": 1}])
    assert graded["correct"] == 0
    assert [r["correct"] for r in graded["results"]] == [False, False]
    # bool must not count as MCQ index 0/1
    assert grade_quiz([mcq], [0])["correct"] == 1
    assert grade_quiz([mcq], [False])["correct"] == 0
