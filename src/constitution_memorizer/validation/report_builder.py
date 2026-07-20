"""Build machine-readable and human-readable extraction reports."""

from __future__ import annotations

import logging
from typing import Any

from constitution_memorizer.schemas import (
    ConstitutionDocument,
    ExtractionReport,
    Issue,
    ReportStatus,
)
from constitution_memorizer.validation.validator import (
    collect_counts,
    validate_against_expectations,
    validate_document,
)

logger = logging.getLogger(__name__)


def build_report(
    doc: ConstitutionDocument,
    *,
    source_file: str = "",
    page_count: int | None = None,
    duplicate_blocks_removed: int = 0,
    repeated_headers_removed: int = 0,
    extra_warnings: list[Issue] | None = None,
    extra_errors: list[Issue] | None = None,
    check_expectations: bool = True,
) -> ExtractionReport:
    """Validate ``doc`` and build an ``ExtractionReport``."""
    warnings, errors = validate_document(doc)
    if check_expectations:
        exp_warnings, exp_errors = validate_against_expectations(doc)
        warnings.extend(exp_warnings)
        errors.extend(exp_errors)
    if extra_warnings:
        warnings.extend(extra_warnings)
    if extra_errors:
        errors.extend(extra_errors)

    counts = collect_counts(doc)

    if errors:
        status = ReportStatus.FAILED
    elif warnings:
        status = ReportStatus.COMPLETED_WITH_WARNINGS
    else:
        status = ReportStatus.COMPLETED

    report = ExtractionReport(
        status=status,
        source_file=source_file or doc.document.source_filename,
        page_count=page_count if page_count is not None else doc.document.page_count,
        duplicate_blocks_removed=duplicate_blocks_removed,
        repeated_headers_removed=repeated_headers_removed,
        warnings=warnings,
        errors=errors,
        **counts,
    )
    return report


def format_report_summary(report: ExtractionReport) -> str:
    """Return a concise human-readable report summary for CLI output."""
    lines = [
        f"Status: {report.status.value}",
        f"Source: {report.source_file or '(unknown)'}",
        f"Pages: {report.page_count if report.page_count is not None else 'n/a'}",
        (
            f"Parts={report.parts_found} Chapters={report.chapters_found} "
            f"Articles={report.articles_found} Clauses={report.clauses_found} "
            f"Subclauses={report.subclauses_found}"
        ),
        (
            f"Provisos={report.provisos_found} Explanations={report.explanations_found} "
            f"Footnotes={report.footnotes_found} Schedules={report.schedules_found} "
            f"Tables={report.tables_found}"
        ),
        (
            f"Omitted={report.omitted_articles_found} Repealed={report.repealed_articles_found} "
            f"Unclassified={report.unclassified_blocks}"
        ),
        (
            f"Headers removed={report.repeated_headers_removed} "
            f"Duplicates removed={report.duplicate_blocks_removed}"
        ),
        f"Warnings: {len(report.warnings)}  Errors: {len(report.errors)}",
    ]
    if report.errors:
        lines.append("Errors:")
        for err in report.errors[:20]:
            lines.append(f"  - [{err.code}] {err.message}")
        if len(report.errors) > 20:
            lines.append(f"  ... and {len(report.errors) - 20} more")
    if report.warnings:
        lines.append("Warnings (first 20):")
        for warn in report.warnings[:20]:
            lines.append(f"  - [{warn.code}] {warn.message}")
        if len(report.warnings) > 20:
            lines.append(f"  ... and {len(report.warnings) - 20} more")
    return "\n".join(lines)


def report_to_dict(report: ExtractionReport) -> dict[str, Any]:
    """Serialize a report to a plain dictionary."""
    return report.model_dump(mode="json")
