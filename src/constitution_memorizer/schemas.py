"""Pydantic schemas for Constitution Bare Act structured output."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ArticleStatus(str, Enum):
    """Lifecycle status of an Article as evidenced by the Bare Act text."""

    ACTIVE = "active"
    OMITTED = "omitted"
    REPEALED = "repealed"
    SUBSTITUTED = "substituted"
    HISTORICAL = "historical"
    UNKNOWN = "unknown"


class PartStatus(str, Enum):
    """Lifecycle status of a Part."""

    ACTIVE = "active"
    OMITTED = "omitted"
    REPEALED = "repealed"
    UNKNOWN = "unknown"


class FootnoteOperation(str, Enum):
    """Structured amendment operation inferred from a footnote, when confident."""

    INSERTED = "inserted"
    SUBSTITUTED = "substituted"
    OMITTED = "omitted"
    REPEALED = "repealed"
    AMENDED = "amended"
    RENUMBERED = "renumbered"
    UNKNOWN = "unknown"


class LabelType(str, Enum):
    """Classification of a provision label."""

    NUMERIC = "numeric"
    ALPHANUMERIC = "alphanumeric"
    ALPHABETIC = "alphabetic"
    ROMAN = "roman"
    UPPER_ALPHA = "upper_alpha"
    UNKNOWN = "unknown"


class ReportStatus(str, Enum):
    """Overall extraction/validation report status."""

    COMPLETED = "completed"
    COMPLETED_WITH_WARNINGS = "completed_with_warnings"
    FAILED = "failed"


class SourceProvenance(BaseModel):
    """Source traceability for a structural element."""

    model_config = ConfigDict(extra="forbid")

    page_start: int | None = None
    page_end: int | None = None
    bounding_boxes: list[dict[str, Any]] = Field(default_factory=list)
    raw_heading: str | None = None
    raw_text: str | None = None
    docling_reference: str | None = None


class ProvisionNode(BaseModel):
    """Recursive provision node for clauses and nested subclauses."""

    model_config = ConfigDict(extra="forbid")

    id: str
    label: str
    label_type: LabelType = LabelType.UNKNOWN
    text: str = ""
    children: list[ProvisionNode] = Field(default_factory=list)
    provisos: list[str] = Field(default_factory=list)
    explanations: list[str] = Field(default_factory=list)
    footnote_references: list[str] = Field(default_factory=list)
    source: SourceProvenance = Field(default_factory=SourceProvenance)


class EditorialNote(BaseModel):
    """Editorial or amendment note preserved verbatim with optional metadata."""

    model_config = ConfigDict(extra="forbid")

    text: str
    operation: FootnoteOperation | None = None
    amendment_name: str | None = None
    year: int | None = None
    source: SourceProvenance = Field(default_factory=SourceProvenance)


class Article(BaseModel):
    """A Constitution Article with nested provisions."""

    model_config = ConfigDict(extra="forbid")

    id: str
    article_number: str
    numeric_component: int
    suffix: str = ""
    title: str | None = None
    status: ArticleStatus = ArticleStatus.ACTIVE
    part_number: str | None = None
    chapter_number: str | None = None
    body_text: str = ""
    opening_text: str = ""
    clauses: list[ProvisionNode] = Field(default_factory=list)
    provisos: list[str] = Field(default_factory=list)
    explanations: list[str] = Field(default_factory=list)
    exceptions: list[str] = Field(default_factory=list)
    illustrations: list[str] = Field(default_factory=list)
    editorial_notes: list[EditorialNote] = Field(default_factory=list)
    amendment_notes: list[EditorialNote] = Field(default_factory=list)
    footnote_references: list[str] = Field(default_factory=list)
    cross_references: list[str] = Field(default_factory=list)
    source: SourceProvenance = Field(default_factory=SourceProvenance)
    manual_review_status: str | None = None


class Chapter(BaseModel):
    """A Chapter within a Part."""

    model_config = ConfigDict(extra="forbid")

    id: str
    chapter_number: str
    title: str | None = None
    articles: list[Article] = Field(default_factory=list)
    source: SourceProvenance = Field(default_factory=SourceProvenance)


class Part(BaseModel):
    """A Part of the Constitution."""

    model_config = ConfigDict(extra="forbid")

    id: str
    part_number: str
    part_number_normalized: int | None = None
    title: str | None = None
    status: PartStatus = PartStatus.ACTIVE
    chapters: list[Chapter] = Field(default_factory=list)
    articles: list[Article] = Field(default_factory=list)
    source: SourceProvenance = Field(default_factory=SourceProvenance)


class TableCell(BaseModel):
    """A single table cell."""

    model_config = ConfigDict(extra="forbid")

    text: str = ""
    row_index: int = 0
    col_index: int = 0


class TableData(BaseModel):
    """A table preserved from extraction."""

    model_config = ConfigDict(extra="forbid")

    id: str | None = None
    caption: str | None = None
    headers: list[str] = Field(default_factory=list)
    rows: list[list[str]] = Field(default_factory=list)
    cells: list[TableCell] = Field(default_factory=list)
    source: SourceProvenance = Field(default_factory=SourceProvenance)


class ScheduleSection(BaseModel):
    """A named section within a Schedule."""

    model_config = ConfigDict(extra="forbid")

    id: str | None = None
    title: str | None = None
    body_text: str = ""
    source: SourceProvenance = Field(default_factory=SourceProvenance)


class ScheduleList(BaseModel):
    """A list within a Schedule (e.g. Union / State / Concurrent)."""

    model_config = ConfigDict(extra="forbid")

    id: str | None = None
    name: str | None = None
    items: list[str] = Field(default_factory=list)
    body_text: str = ""
    source: SourceProvenance = Field(default_factory=SourceProvenance)


class Schedule(BaseModel):
    """A Schedule of the Constitution."""

    model_config = ConfigDict(extra="forbid")

    id: str
    schedule_number: str
    schedule_number_normalized: int | None = None
    title: str | None = None
    references: list[str] = Field(default_factory=list)
    sections: list[ScheduleSection] = Field(default_factory=list)
    lists: list[ScheduleList] = Field(default_factory=list)
    tables: list[TableData] = Field(default_factory=list)
    body_text: str = ""
    footnote_references: list[str] = Field(default_factory=list)
    source: SourceProvenance = Field(default_factory=SourceProvenance)


class Appendix(BaseModel):
    """An appendix or annexure attached to the Bare Act edition."""

    model_config = ConfigDict(extra="forbid")

    id: str
    title: str | None = None
    body_text: str = ""
    source: SourceProvenance = Field(default_factory=SourceProvenance)


class Footnote(BaseModel):
    """A footnote with exact original text and optional structured metadata."""

    model_config = ConfigDict(extra="forbid")

    id: str
    marker: str
    text: str
    operation: FootnoteOperation = FootnoteOperation.UNKNOWN
    amendment_name: str | None = None
    amendment_number: int | None = None
    year: int | None = None
    effective_date: str | None = None
    affected_article: str | None = None
    source: SourceProvenance = Field(default_factory=SourceProvenance)


class Preamble(BaseModel):
    """The Preamble, kept separate from Articles."""

    model_config = ConfigDict(extra="forbid")

    text: str = ""
    paragraphs: list[str] = Field(default_factory=list)
    enactment_date_line: str | None = None
    footnote_references: list[str] = Field(default_factory=list)
    amendment_notes: list[EditorialNote] = Field(default_factory=list)
    source: SourceProvenance = Field(default_factory=SourceProvenance)


class UnclassifiedContent(BaseModel):
    """Content retained because classification was uncertain."""

    model_config = ConfigDict(extra="forbid")

    id: str
    text: str
    page_number: int | None = None
    preceding_element_id: str | None = None
    following_element_id: str | None = None
    possible_type: str | None = None
    confidence: float | None = None
    reason: str = ""


class DocumentMetadata(BaseModel):
    """Metadata about the source Bare Act document and extraction run."""

    model_config = ConfigDict(extra="forbid")

    title: str = "The Constitution of India"
    edition: str | None = None
    publication_date: str | None = None
    publisher: str | None = None
    language: str = "English"
    source_filename: str = ""
    source_path: str | None = None
    source_sha256: str = ""
    page_count: int | None = None
    extracted_at: str = ""
    schema_version: str = "1.0.0"
    file_size_bytes: int | None = None
    docling_version: str | None = None
    ocr_used: bool | None = None


class ExtractionSummary(BaseModel):
    """Lightweight summary embedded in the main constitution JSON."""

    model_config = ConfigDict(extra="forbid")

    parts_found: int = 0
    chapters_found: int = 0
    articles_found: int = 0
    footnotes_found: int = 0
    schedules_found: int = 0
    unclassified_blocks: int = 0
    omitted_articles_found: int = 0
    repealed_articles_found: int = 0
    warnings: list[str] = Field(default_factory=list)


class NormalizationEvent(BaseModel):
    """Audit event for a normalization or parsing decision."""

    model_config = ConfigDict(extra="forbid")

    event_type: str
    original_text: str | None = None
    normalized_text: str | None = None
    page_number: int | None = None
    reason: str = ""
    confidence: float | None = None
    line_index: int | None = None


class ExtractionMetadata(BaseModel):
    """Metadata produced by the Docling extraction stage."""

    model_config = ConfigDict(extra="forbid")

    source_filename: str
    source_path: str
    file_size_bytes: int
    source_sha256: str
    extracted_at: str
    page_count: int | None = None
    docling_version: str | None = None
    ocr_used: bool | None = None
    output_paths: dict[str, str] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class Issue(BaseModel):
    """A validation warning or error."""

    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    element_id: str | None = None
    severity: str = "warning"


class ExtractionReport(BaseModel):
    """Machine-readable extraction and validation report."""

    model_config = ConfigDict(extra="forbid")

    status: ReportStatus = ReportStatus.COMPLETED
    source_file: str = ""
    page_count: int | None = None
    parts_found: int = 0
    chapters_found: int = 0
    articles_found: int = 0
    clauses_found: int = 0
    subclauses_found: int = 0
    provisos_found: int = 0
    explanations_found: int = 0
    footnotes_found: int = 0
    schedules_found: int = 0
    tables_found: int = 0
    omitted_articles_found: int = 0
    repealed_articles_found: int = 0
    unclassified_blocks: int = 0
    duplicate_blocks_removed: int = 0
    repeated_headers_removed: int = 0
    warnings: list[Issue] = Field(default_factory=list)
    errors: list[Issue] = Field(default_factory=list)
    generated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class ConstitutionDocument(BaseModel):
    """Root structured output for the Constitution Bare Act."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0.0"
    document: DocumentMetadata = Field(default_factory=DocumentMetadata)
    preamble: Preamble | None = None
    parts: list[Part] = Field(default_factory=list)
    schedules: list[Schedule] = Field(default_factory=list)
    appendices: list[Appendix] = Field(default_factory=list)
    footnotes: list[Footnote] = Field(default_factory=list)
    unclassified_content: list[UnclassifiedContent] = Field(default_factory=list)
    extraction_summary: ExtractionSummary = Field(default_factory=ExtractionSummary)


# Rebuild forward refs for recursive model
ProvisionNode.model_rebuild()
