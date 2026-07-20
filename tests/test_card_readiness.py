"""Card readiness contract tests."""

from __future__ import annotations

from constitution_memorizer.learning.schemas import LearningUnit, LearningUnitType
from constitution_memorizer.web.browse import ArticleBrowseView
from constitution_memorizer.web.card_readiness import (
    check_browse_article,
    check_choose_unit,
    check_learn_unit,
    status_label,
    summarize_readiness,
    type_label,
)


def _unit(**kwargs) -> LearningUnit:
    defaults = dict(
        id="u1",
        type=LearningUnitType.CLAUSE,
        display_title="Article 243C(1)",
        title="Composition of Panchayats",
        text=(
            "(1) Subject to the provisions of this Part, the Legislature of a State "
            "may, by law, make provisions with respect to the composition of Panchayats:\n"
            "Provided that the ratio between the population of the territorial area "
            "of a Panchayat at any level and the number of seats in such Panchayat "
            "to be filled by election shall, so far as practicable, be the same "
            "throughout the State."
        ),
        estimated_learning_time=60,
    )
    defaults.update(kwargs)
    return LearningUnit(**defaults)


def test_type_label_is_plain_enum_value():
    assert type_label(_unit()) == "CLAUSE"


def test_complete_clause_with_proviso_passes():
    result = check_learn_unit(_unit())
    assert result.ok
    assert result.reasons == []


def test_truncated_open_clause_fails():
    result = check_learn_unit(
        _unit(
            text=(
                "(1) Subject to the provisions of this Part, the Legislature of a State "
                "may, by law, make provisions with respect to the composition of Panchayats:"
            )
        )
    )
    assert not result.ok
    assert "truncated_open_clause" in result.quality_flags


def test_garbage_article_one_fails():
    result = check_learn_unit(
        _unit(
            id="article-1",
            type=LearningUnitType.ARTICLE,
            display_title="Article 1",
            title='DEMOCRATIC REPUBLIC" (w.e.f. 3',
            text="1-1977).\n1-1977).",
        )
    )
    assert not result.ok
    assert "garbage_fragment" in result.quality_flags or "too_short" in result.quality_flags


def test_browse_flags_truncated_body():
    view = ArticleBrowseView(
        article_number="243C",
        title="Composition of Panchayats",
        part_number="IX",
        status="active",
        full_text="(1) make provisions with respect to the composition of Panchayats:",
        learn_units=[],
    )
    result = check_browse_article(view)
    assert not result.ok
    assert "truncated_open_clause" in result.quality_flags


def test_part_overview_short_title_passes():
    result = check_learn_unit(
        _unit(
            id="part-ix-overview",
            type=LearningUnitType.PART_OVERVIEW,
            display_title="Part IX overview",
            title="THE PANCHAYATS",
            text="THE PANCHAYATS",
            estimated_learning_time=30,
        )
    )
    assert result.ok


def test_choose_allows_short_letter_children():
    parent = _unit(
        id="clause-2",
        allows_letter_split=True,
        child_unit_ids=["clause-2-a", "clause-2-b"],
        text=(
            "(3) No person accused of any offence shall be compelled to be a "
            "witness against himself unless-"
        ),
    )
    children = [
        _unit(
            id="clause-2-a",
            type=LearningUnitType.SUBCLAUSE,
            display_title="Article 20(3)(a)",
            text="(a) the accusation is in writing;",
        ),
        _unit(
            id="clause-2-b",
            type=LearningUnitType.SUBCLAUSE,
            display_title="Article 20(3)(b)",
            text="(b) the person has counsel.",
        ),
    ]
    result = check_choose_unit(parent, children=children)
    assert result.ok
    assert all(check_learn_unit(child).ok for child in children)


def test_status_label_incomplete_when_not_ready():
    assert status_label(ready=False, raw_status="active") == "Incomplete extraction"
    assert status_label(ready=True, raw_status="UNKNOWN") == "Active"
    assert status_label(ready=True, raw_status="omitted") == "Omitted"


def test_summarize_readiness_counts_flags():
    units = [
        _unit(),
        _unit(
            id="bad",
            type=LearningUnitType.ARTICLE,
            display_title="Article 1",
            title='DEMOCRATIC REPUBLIC" (w.e.f. 3',
            text="1-1977).",
        ),
    ]
    summary = summarize_readiness(units)
    assert summary["ready"] == 1
    assert summary["unready"] == 1
    assert summary["flags"]
