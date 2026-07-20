"""Tests for normalization (hyphen joins, headers, page numbers) and validation."""

from __future__ import annotations

from constitution_memorizer.config import PipelineConfig
from constitution_memorizer.normalization.line_normalizer import (
    join_hyphenated_line_breaks,
    normalize_markdown,
)
from constitution_memorizer.normalization.repetition_detector import (
    detect_and_remove_repetitions,
    normalize_document,
)
from constitution_memorizer.normalization.text_cleaner import clean_text
from constitution_memorizer.schemas import (
    Article,
    ArticleStatus,
    ConstitutionDocument,
    DocumentMetadata,
    Footnote,
    Part,
    SourceProvenance,
)
from constitution_memorizer.utils.identifiers import article_id
from constitution_memorizer.validation.report_builder import build_report
from constitution_memorizer.validation.validator import validate_document


def test_broken_line_word_joins() -> None:
    lines = [
        "The State shall provide free and compulsory edu-",
        "cation to all children.",
    ]
    joined, events = join_hyphenated_line_breaks(lines)
    assert len(joined) == 1
    assert "education" in joined[0]
    assert any(e.event_type == "joined_hyphenated_word" for e in events)


def test_does_not_join_into_headings() -> None:
    lines = [
        "something-",
        "PART III",
    ]
    joined, events = join_hyphenated_line_breaks(lines)
    assert joined == lines
    assert not events


def test_repeated_header_removal() -> None:
    text = "\n".join(
        [
            "THE CONSTITUTION OF INDIA",
            "14. Equality before law.—The State shall not deny equality.",
            "THE CONSTITUTION OF INDIA",
            "15. Prohibition of discrimination.—The State shall not discriminate.",
            "THE CONSTITUTION OF INDIA",
        ]
    )
    lines, events, stats = normalize_document(text, estimated_page_count=3)
    kept_text = "\n".join(ln.text for ln in lines)
    assert "Equality before law" in kept_text
    assert stats["repeated_headers_removed"] >= 1
    assert any(e.event_type == "removed_repeated_header" for e in events)
    # Audit trail retains original header text.
    assert any(e.original_text == "THE CONSTITUTION OF INDIA" for e in events)


def test_page_number_removal() -> None:
    base = normalize_markdown("14. Equality.\n42\n15. Prohibition.")
    result = detect_and_remove_repetitions(base.lines, PipelineConfig())
    kept = [ln.text for ln in result.lines if ln.kept]
    assert "42" not in [k.strip() for k in kept]
    assert result.page_numbers_removed >= 1


def test_preserves_legal_punctuation() -> None:
    cleaned, _ = clean_text("Provided that—nothing herein shall apply; see Art. 14.")
    assert "—" in cleaned
    assert ";" in cleaned


def test_prevention_of_false_duplicate_removal() -> None:
    """Repeated body phrases that are not consecutive must not be deleted."""
    text = "\n".join(
        [
            "The State shall not deny equality.",
            "Another line about liberty.",
            "The State shall not deny equality.",
        ]
    )
    lines, events, stats = normalize_document(text)
    kept = [ln.text for ln in lines]
    assert kept.count("The State shall not deny equality.") == 2
    assert stats["duplicate_blocks_removed"] == 0


def test_consecutive_duplicate_removal() -> None:
    text = "Same line\nSame line\nDifferent"
    lines, events, stats = normalize_document(text)
    kept = [ln.text for ln in lines]
    assert kept.count("Same line") == 1
    assert stats["duplicate_blocks_removed"] == 1


def _sample_doc_with_issues() -> ConstitutionDocument:
    art14 = Article(
        id=article_id("14"),
        article_number="14",
        numeric_component=14,
        title="Equality before law",
        body_text="The State shall not deny equality before the law.",
        footnote_references=["9"],
        source=SourceProvenance(page_start=10, page_end=9),
    )
    art14_dup = Article(
        id=article_id("14"),
        article_number="14",
        numeric_component=14,
        title=None,
        body_text="",
        status=ArticleStatus.ACTIVE,
    )
    empty = Article(
        id=article_id("99"),
        article_number="99",
        numeric_component=99,
        title=None,
        body_text="",
    )
    part = Part(id="part-iii", part_number="III", articles=[art14, art14_dup, empty])
    return ConstitutionDocument(
        document=DocumentMetadata(source_filename="test.pdf"),
        parts=[part],
        footnotes=[
            Footnote(id="footnote-1", marker="1", text="Ins. by amendment."),
        ],
        unclassified_content=[],
    )


def test_duplicate_article_detection() -> None:
    doc = _sample_doc_with_issues()
    warnings, errors = validate_document(doc)
    assert any(e.code == "duplicate_article_id" for e in errors)
    assert any(e.code == "duplicate_article_number" for e in errors)


def test_empty_article_detection() -> None:
    doc = _sample_doc_with_issues()
    warnings, _ = validate_document(doc)
    assert any(w.code == "empty_article" for w in warnings)


def test_broken_source_range() -> None:
    doc = _sample_doc_with_issues()
    _, errors = validate_document(doc)
    assert any(e.code == "broken_source_range" for e in errors)


def test_missing_footnote_target() -> None:
    doc = _sample_doc_with_issues()
    warnings, _ = validate_document(doc)
    assert any(w.code == "missing_footnote_target" for w in warnings)


def test_unclassified_content_warning() -> None:
    from constitution_memorizer.schemas import UnclassifiedContent

    doc = ConstitutionDocument(
        unclassified_content=[
            UnclassifiedContent(id="unclassified-0001", text="???", reason="test"),
        ]
    )
    warnings, _ = validate_document(doc)
    assert any(w.code == "unclassified_content" for w in warnings)


def test_report_status_with_warnings() -> None:
    doc = _sample_doc_with_issues()
    report = build_report(doc, source_file="test.pdf")
    assert report.status.value in {"completed_with_warnings", "failed"}
    assert report.articles_found == 3
