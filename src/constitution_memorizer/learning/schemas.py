"""Schemas for the Learning Unit learning layer (Sprint 1+)."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class LearningUnitType(str, Enum):
    """Supported learning unit kinds for Version 1."""

    ARTICLE = "ARTICLE"
    CLAUSE = "CLAUSE"
    SUBCLAUSE = "SUBCLAUSE"
    SCHEDULE_ENTRY = "SCHEDULE_ENTRY"
    PART_OVERVIEW = "PART_OVERVIEW"


class LearningUnit(BaseModel):
    """A single schedulable learning chunk derived from the Bare Act JSON."""

    model_config = ConfigDict(extra="forbid")

    id: str
    type: LearningUnitType
    parent_id: str | None = None
    article_number: str | None = None
    display_title: str
    title: str | None = None
    text: str = ""
    difficulty: int = Field(ge=1, le=5, default=2)
    estimated_learning_time: int = Field(
        ge=1,
        description="Estimated learning time in seconds",
    )
    revision_order: int = 0
    next_unit: str | None = None
    previous_unit: str | None = None
    tags: list[str] = Field(default_factory=list)

    # Sprint 2 fields reserved here with safe defaults so schema stays stable.
    allows_letter_split: bool = False
    child_unit_ids: list[str] = Field(default_factory=list)
    parent_clause_id: str | None = None
    letter_sequence_next: str | None = None
    letter_sequence_prev: str | None = None


class LearningUnitsDocument(BaseModel):
    """Root document written to learning_units.json."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0.0"
    source_document: str = "constitution.reviewed.json"
    unit_count: int = 0
    units: list[LearningUnit] = Field(default_factory=list)
