"""Tests for Learning Unit generation (Sprint 1–2)."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from constitution_memorizer.learning.learning_unit_generator import (
    generate_learning_units,
    generate_learning_units_from_path,
    summarize_units,
)
from constitution_memorizer.learning.schemas import LearningUnitType
from constitution_memorizer.learning.text_fallback_splitter import (
    has_provision_markers,
    split_flat_article_body,
)
from constitution_memorizer.learning.time_difficulty import (
    count_words,
    estimate_difficulty,
    estimate_learning_time_seconds,
)
from constitution_memorizer.schemas import ConstitutionDocument, LabelType
from constitution_memorizer.utils.json_io import read_json

FIXTURE = Path(__file__).parent / "fixtures" / "learning" / "sample_reviewed.json"
REVIEWED = Path("data/output/constitution.reviewed.json")


@pytest.fixture
def sample_doc() -> ConstitutionDocument:
    return ConstitutionDocument.model_validate(read_json(FIXTURE))


def test_article_without_clauses_becomes_single_article_unit(sample_doc):
    result = generate_learning_units(sample_doc)
    by_id = {u.id: u for u in result.units}

    unit = by_id["article-14"]
    assert unit.type == LearningUnitType.ARTICLE
    assert unit.article_number == "14"
    assert unit.display_title == "Article 14"
    assert "equality before the law" in unit.text.lower()
    assert unit.estimated_learning_time >= 30
    assert 1 <= unit.difficulty <= 5
    assert "Fundamental Rights" in unit.tags


def test_numbered_clauses_and_alphabetic_dual_units(sample_doc):
    result = generate_learning_units(sample_doc)
    clause_ids = [
        u.id
        for u in result.units
        if u.article_number == "20" and u.type == LearningUnitType.CLAUSE
    ]
    assert clause_ids == [
        "article-20-clause-1",
        "article-20-clause-2",
        "article-20-clause-3",
    ]

    parent = next(u for u in result.units if u.id == "article-20-clause-3")
    assert parent.allows_letter_split is True
    assert parent.child_unit_ids == [
        "article-20-clause-3-subclause-a",
        "article-20-clause-3-subclause-b",
    ]
    assert "the accusation is in writing" in parent.text
    assert "filed before a court" in parent.text  # roman inlined into whole clause

    letters = [
        u
        for u in result.units
        if u.article_number == "20" and u.type == LearningUnitType.SUBCLAUSE
    ]
    assert [u.id for u in letters] == [
        "article-20-clause-3-subclause-a",
        "article-20-clause-3-subclause-b",
    ]
    assert letters[0].parent_clause_id == "article-20-clause-3"
    assert letters[0].letter_sequence_next == "article-20-clause-3-subclause-b"
    assert letters[1].letter_sequence_prev == "article-20-clause-3-subclause-a"
    assert letters[0].display_title == "Article 20(3)(a)"
    # Roman nested under (a) stays inside SUBCLAUSE; no deeper units.
    assert "filed before a court" in letters[0].text
    assert "served on the accused" in letters[0].text
    assert not any(
        u.type == LearningUnitType.SUBCLAUSE and "(i)" in u.display_title
        for u in result.units
    )


def test_text_fallback_splits_flat_article_19(sample_doc):
    result = generate_learning_units(sample_doc)
    art19 = [u for u in result.units if u.article_number == "19"]
    assert not any(u.type == LearningUnitType.ARTICLE for u in art19)
    clause_ids = [u.id for u in art19 if u.type == LearningUnitType.CLAUSE]
    assert clause_ids == ["article-19-clause-1", "article-19-clause-2"]

    clause1 = next(u for u in art19 if u.id == "article-19-clause-1")
    assert clause1.allows_letter_split is True
    assert set(clause1.child_unit_ids) == {
        "article-19-clause-1-subclause-a",
        "article-19-clause-1-subclause-b",
    }
    letters = [u for u in art19 if u.type == LearningUnitType.SUBCLAUSE]
    assert {u.id for u in letters} == {
        "article-19-clause-1-subclause-a",
        "article-19-clause-1-subclause-b",
    }


def test_part_overview_and_schedule_entries(sample_doc):
    result = generate_learning_units(sample_doc)
    by_id = {u.id: u for u in result.units}

    overview = by_id["part-iii-overview"]
    assert overview.type == LearningUnitType.PART_OVERVIEW
    assert "FUNDAMENTAL RIGHTS" in overview.text

    section = by_id["schedule-1-section-1"]
    assert section.type == LearningUnitType.SCHEDULE_ENTRY
    assert "Andhra Pradesh" in section.display_title

    body_fallback = by_id["schedule-body-only"]
    assert body_fallback.type == LearningUnitType.SCHEDULE_ENTRY
    assert "Whole-schedule fallback" in body_fallback.text


def test_global_chain_is_clause_level(sample_doc):
    result = generate_learning_units(sample_doc)
    chain = [u for u in result.units if u.type != LearningUnitType.SUBCLAUSE]
    subclauses = [u for u in result.units if u.type == LearningUnitType.SUBCLAUSE]

    assert chain[0].previous_unit is None
    assert chain[-1].next_unit is None
    for index, unit in enumerate(chain):
        assert unit.revision_order == index + 1
        if index > 0:
            assert unit.previous_unit == chain[index - 1].id
        if index + 1 < len(chain):
            assert unit.next_unit == chain[index + 1].id

    # Letter units are present but off the default revision path.
    assert subclauses
    for unit in subclauses:
        assert unit.revision_order == 0
        assert unit.previous_unit is None
        assert unit.next_unit is None


def test_generate_learning_units_from_path_writes_files(tmp_path, sample_doc):
    out = tmp_path / "learning_units.json"
    result = generate_learning_units_from_path(FIXTURE, out, force=True)
    assert out.exists()
    assert (tmp_path / "learning_units.min.json").exists()
    loaded = read_json(out)
    assert loaded["unit_count"] == result.unit_count
    stats = summarize_units(result)
    assert stats["by_type"][LearningUnitType.ARTICLE.value] == 1
    assert stats["by_type"][LearningUnitType.CLAUSE.value] == 5  # 19×2 + 20×3
    assert stats["by_type"][LearningUnitType.SUBCLAUSE.value] == 4  # 19×2 + 20×2
    assert stats["by_type"][LearningUnitType.PART_OVERVIEW.value] == 1
    assert stats["by_type"][LearningUnitType.SCHEDULE_ENTRY.value] == 2
    assert stats["allows_letter_split"] == 2


def test_time_and_difficulty_heuristics():
    assert count_words("one two three") == 3
    assert estimate_learning_time_seconds("word " * 20) == 30
    assert estimate_learning_time_seconds("word " * 100) == 60
    assert estimate_learning_time_seconds("word " * 200) == 120
    assert estimate_learning_time_seconds("word " * 400) >= 180

    short = estimate_difficulty(text="Short text only.", clause_count=0)
    assert short in {1, 2}
    nested = estimate_difficulty(
        text="word " * 100,
        clause_count=3,
        has_nested_children=True,
    )
    assert nested >= 4


def test_split_flat_article_body_builds_tree():
    body = (
        "(1) Rights-\n"
        "(a) speech;\n"
        "(b) assembly with-\n"
        "(i) notice; and\n"
        "(ii) permission;\n"
        "(2) Reasonable restrictions."
    )
    assert has_provision_markers(body)
    roots = split_flat_article_body("19", body)
    assert [r.label for r in roots] == ["(1)", "(2)"]
    assert [c.label for c in roots[0].children] == ["(a)", "(b)"]
    assert roots[0].children[0].label_type == LabelType.ALPHABETIC
    assert [c.label for c in roots[0].children[1].children] == ["(i)", "(ii)"]
    assert roots[0].children[1].children[0].label_type == LabelType.ROMAN


@pytest.mark.skipif(not REVIEWED.exists(), reason="reviewed corpus not present")
def test_generate_real_units_does_not_modify_reviewed_corpus(tmp_path):
    before = hashlib.sha256(REVIEWED.read_bytes()).hexdigest()
    out = tmp_path / "learning_units.json"
    result = generate_learning_units_from_path(REVIEWED, out, force=True)
    after = hashlib.sha256(REVIEWED.read_bytes()).hexdigest()
    assert before == after
    assert result.unit_count > 0
    assert LearningUnitType.SUBCLAUSE.value in summarize_units(result)["by_type"]
