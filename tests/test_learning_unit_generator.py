"""Sprint 1 tests for Learning Unit generation."""

from __future__ import annotations

from pathlib import Path

import pytest

from constitution_memorizer.learning.learning_unit_generator import (
    generate_learning_units,
    generate_learning_units_from_path,
    summarize_units,
)
from constitution_memorizer.learning.schemas import LearningUnitType
from constitution_memorizer.learning.time_difficulty import (
    count_words,
    estimate_difficulty,
    estimate_learning_time_seconds,
)
from constitution_memorizer.schemas import ConstitutionDocument
from constitution_memorizer.utils.json_io import read_json

FIXTURE = Path(__file__).parent / "fixtures" / "learning" / "sample_reviewed.json"


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


def test_numbered_clauses_become_clause_units(sample_doc):
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
    # Sprint 1: alphabetic children are inlined, not emitted as SUBCLAUSE.
    assert not any(u.type == LearningUnitType.SUBCLAUSE for u in result.units)
    clause3 = next(u for u in result.units if u.id == "article-20-clause-3")
    assert "Nested alphabetic text" in clause3.text
    assert clause3.display_title == "Article 20(3)"


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


def test_revision_chain_links_units(sample_doc):
    result = generate_learning_units(sample_doc)
    units = result.units
    assert result.unit_count == len(units)
    assert units[0].previous_unit is None
    assert units[-1].next_unit is None
    for index, unit in enumerate(units):
        assert unit.revision_order == index + 1
        if index > 0:
            assert unit.previous_unit == units[index - 1].id
        if index + 1 < len(units):
            assert unit.next_unit == units[index + 1].id


def test_generate_learning_units_from_path_writes_files(tmp_path, sample_doc):
    out = tmp_path / "learning_units.json"
    result = generate_learning_units_from_path(FIXTURE, out, force=True)
    assert out.exists()
    assert (tmp_path / "learning_units.min.json").exists()
    loaded = read_json(out)
    assert loaded["unit_count"] == result.unit_count
    stats = summarize_units(result)
    assert stats["by_type"][LearningUnitType.ARTICLE.value] == 1
    assert stats["by_type"][LearningUnitType.CLAUSE.value] == 3
    assert stats["by_type"][LearningUnitType.PART_OVERVIEW.value] == 1
    assert stats["by_type"][LearningUnitType.SCHEDULE_ENTRY.value] == 2


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
