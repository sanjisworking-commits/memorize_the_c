"""Phase 2 regression tests cut from diglot Bare Act failure cases."""

from __future__ import annotations

from pathlib import Path

from constitution_memorizer.corrections.apply_corrections import (
    CorrectionsFile,
    ArticleCorrection,
    apply_corrections,
)
from constitution_memorizer.parsing.article_parser import parse_article_heading_line
from constitution_memorizer.parsing.constitution_parser import parse_markdown
from constitution_memorizer.parsing.schedule_parser import parse_schedule_heading
from constitution_memorizer.schemas import ArticleStatus, ConstitutionDocument
from constitution_memorizer.validation.validator import (
    validate_against_expectations,
    validate_document,
)

REGRESSION = Path(__file__).parent / "fixtures" / "regression"


def _article_map(doc: ConstitutionDocument) -> dict[str, object]:
    result = {}
    for part in doc.parts:
        for article in part.articles:
            result[article.article_number] = article
        for chapter in part.chapters:
            for article in chapter.articles:
                result[article.article_number] = article
    return result


def test_toc_contents_does_not_create_articles() -> None:
    text = (REGRESSION / "toc_contents.md").read_text(encoding="utf-8")
    # Ensure body marker exists so TOC is skipped until WE THE PEOPLE if present.
    # This fixture is TOC-only; without body start, structural markers stay front matter.
    doc, _ = parse_markdown(text)
    articles = _article_map(doc)
    # TOC rows like "1. Name and territory..." must not become Articles alone.
    assert "1" not in articles or doc.parts == []


def test_footnote_prefixed_schedule_headings() -> None:
    assert parse_schedule_heading("1 [FOURTH SCHEDULE") is not None
    assert parse_schedule_heading("## 1 [NINTH SCHEDULE") is not None
    assert parse_schedule_heading("1 [TWELFTH SCHEDULE") is not None


def test_glued_schedule_headings_recovered() -> None:
    text = (REGRESSION / "glued_schedule_headings.md").read_text(encoding="utf-8")
    doc, _ = parse_markdown(text)
    numbers = {s.schedule_number for s in doc.schedules}
    assert {"SEVENTH", "EIGHTH", "NINTH", "TENTH", "ELEVENTH", "TWELFTH"} <= numbers
    seventh = next(s for s in doc.schedules if s.schedule_number == "SEVENTH")
    assert seventh.lists
    # Schedule list items must not become Articles.
    articles = _article_map(doc)
    assert articles.get("1") is None or articles["1"].part_number == "XXII"


def test_schedule_entries_not_articles() -> None:
    assert parse_schedule_heading("EIGHTH SCHEDULELanguages.") is not None
    assert parse_schedule_heading("SEVENTH SCHEDULE-") is not None
    text = (REGRESSION / "seventh_schedule_body.md").read_text(encoding="utf-8")
    # Wrap with a schedule start if needed
    if "SCHEDULE" not in text.upper().split("\n", 1)[0]:
        text = "SEVENTH SCHEDULE\n" + text
    doc, _ = parse_markdown("PART XXII\nSHORT TITLE\n395. Short title.—x\n" + text)
    articles = _article_map(doc)
    # Defence of India style entries should not create Article 1 in main parts.
    art1 = articles.get("1")
    if art1 is not None:
        assert "Defence" not in (art1.title or "")


def test_omitted_diglot_article_31() -> None:
    heading = parse_article_heading_line(
        "31. [ Compulsory acquisition of property. ]. -Omitted by the Constitution "
        "( Forty-fourth Amendment ) Act, 1978, s. 6 ( w.e.f. 20-6-1979)."
    )
    assert heading is not None
    assert heading.status == ArticleStatus.OMITTED
    assert heading.title is not None
    assert "Compulsory acquisition" in heading.title

    text = (
        "PART III\nFUNDAMENTAL RIGHTS\n"
        + (REGRESSION / "omitted_article_31.md").read_text(encoding="utf-8")
    )
    doc, _ = parse_markdown(text)
    articles = _article_map(doc)
    assert "31" in articles
    assert articles["31"].status == ArticleStatus.OMITTED


def test_chapter_subheads_classified() -> None:
    text = (REGRESSION / "chapter_subheads.md").read_text(encoding="utf-8")
    doc, events = parse_markdown(text)
    assert any(e.event_type == "chapter_subsection" for e in events)
    unclassified_unknown = [
        u for u in doc.unclassified_content if u.text.strip() == "General"
    ]
    assert not unclassified_unknown
    articles = _article_map(doc)
    assert "52" in articles
    assert "53" in articles


def test_appendix_territorial_parts_not_main_parts() -> None:
    text = (
        "PART XXII\nSHORT TITLE\n395. Short title.—This Constitution may be called X.\n"
        "APPENDICES\n"
        + (REGRESSION / "appendix_territorial_parts.md").read_text(encoding="utf-8")
    )
    doc, _ = parse_markdown(text)
    part_numbers = [p.part_number for p in doc.parts]
    # Should not create multiple main-body PART I/II/III after schedules/appendices.
    assert part_numbers.count("I") <= 1
    assert part_numbers.count("II") <= 1
    assert part_numbers.count("III") <= 1


def test_footnote_marker_association() -> None:
    text = (REGRESSION / "footnote_markers.md").read_text(encoding="utf-8")
    doc, _ = parse_markdown(text)
    articles = _article_map(doc)
    assert "21A" in articles
    assert "1" in articles["21A"].footnote_references
    assert doc.footnotes
    markers = {f.marker for f in doc.footnotes}
    assert "1" in markers


def test_duplicate_article_demotion() -> None:
    text = """PART I
UNION

1. Name and territory of the Union.—India shall be a Union of States.

PART III
RIGHTS

14. Equality before law.—The State shall not deny equality.

1. Defence of India.
"""
    doc, events = parse_markdown(text)
    articles = _article_map(doc)
    assert articles["1"].title is not None
    assert "Name and territory" in (articles["1"].title or "")
    assert any(e.event_type == "demoted_duplicate_article" for e in events)
    warnings, errors = validate_document(doc)
    assert not any(e.code == "duplicate_article_number" for e in errors)


def test_corrections_overlay_does_not_mutate_source() -> None:
    text = """PART III
RIGHTS

21A. Right to education.—The State shall provide free and compulsory education.
"""
    doc, _ = parse_markdown(text)
    original_title = _article_map(doc)["21A"].title
    corrections = CorrectionsFile(
        articles={
            "article-21a": ArticleCorrection(
                title="Right to education",
                manual_review_status="approved",
            )
        }
    )
    reviewed, changes = apply_corrections(doc, corrections)
    assert _article_map(doc)["21A"].title == original_title
    assert _article_map(reviewed)["21A"].manual_review_status == "approved"
    assert changes


def test_structure_expectations_helper() -> None:
    text = (REGRESSION / "glued_schedule_headings.md").read_text(encoding="utf-8")
    doc, _ = parse_markdown(text)
    expectations = {
        "required_parts_core": ["XXII"],
        "article_count_min": 1,
        "article_count_max": 50,
        "required_schedules": ["SEVENTH", "EIGHTH"],
        "optional_schedules": ["NINTH"],
        "max_main_parts": 30,
    }
    warnings, errors = validate_against_expectations(doc, expectations)
    assert not errors
