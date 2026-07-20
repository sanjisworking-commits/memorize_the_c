"""Schedule parsing helpers."""

from __future__ import annotations

import re
from dataclasses import dataclass

from constitution_memorizer.parsing.patterns import LIST_HEADING_RE, SCHEDULE_RE
from constitution_memorizer.schemas import (
    Schedule,
    ScheduleList,
    ScheduleSection,
    SourceProvenance,
    TableData,
)
from constitution_memorizer.utils.identifiers import (
    schedule_id,
    schedule_number_normalized,
)


@dataclass
class ParsedScheduleHeading:
    """Detected Schedule heading."""

    schedule_number: str
    title: str | None
    raw_heading: str


def parse_schedule_heading(line: str) -> ParsedScheduleHeading | None:
    """Detect a Schedule heading line, including glued Docling variants."""
    stripped = line.strip()
    stripped = re.sub(r"^[-*]\s+", "", stripped)
    stripped = re.sub(r"^#{1,6}\s*", "", stripped)
    # Diglot body headings often look like: "1 [FOURTH SCHEDULE" / "1[NINTH SCHEDULE"
    stripped = re.sub(r"^\d+\s*\[\s*", "", stripped)
    stripped = stripped.rstrip("]").strip()
    # Normalize odd spacing: "THIRD  SCHEDULE", "FOURTH  SCHEDULE -Allocation"
    stripped = re.sub(r"\s+", " ", stripped)

    match = SCHEDULE_RE.match(stripped)
    if not match:
        # Fallback for glued forms already mostly handled by SCHEDULE_RE.
        loose = re.match(
            r"^(?:THE\s+)?"
            r"(FIRST|SECOND|THIRD|FOURTH|FIFTH|SIXTH|SEVENTH|EIGHTH|NINTH|"
            r"TENTH|ELEVENTH|TWELFTH)\s*SCHEDULE\b(.*)$",
            stripped,
            re.I,
        )
        if not loose:
            return None
        number = loose.group(1).upper()
        rest = loose.group(2).strip(" -—–⎯−:.")
        return ParsedScheduleHeading(
            schedule_number=number,
            title=rest or None,
            raw_heading=stripped,
        )

    number = match.group("number").strip().upper()
    title = match.group("title")
    if title:
        title = title.strip(" -—–⎯−:.") or None
    return ParsedScheduleHeading(
        schedule_number=number,
        title=title,
        raw_heading=stripped,
    )


def create_schedule(heading: ParsedScheduleHeading) -> Schedule:
    """Create a Schedule model from a heading."""
    return Schedule(
        id=schedule_id(heading.schedule_number),
        schedule_number=heading.schedule_number,
        schedule_number_normalized=schedule_number_normalized(heading.schedule_number),
        title=heading.title,
        source=SourceProvenance(raw_heading=heading.raw_heading),
    )


def detect_list_heading(line: str) -> str | None:
    """Detect Union/State/Concurrent list headings in the Seventh Schedule."""
    stripped = re.sub(r"^#{1,6}\s*", "", line.strip())
    stripped = re.sub(r"^[-*]\s+", "", stripped)
    match = LIST_HEADING_RE.match(stripped)
    if not match:
        return None
    return match.group("name").strip()


def append_schedule_text(schedule: Schedule, text: str) -> None:
    """Append body text to a schedule."""
    text = text.strip()
    if not text:
        return
    if schedule.body_text:
        schedule.body_text = f"{schedule.body_text}\n{text}"
    else:
        schedule.body_text = text
    if schedule.source.raw_text:
        schedule.source.raw_text = f"{schedule.source.raw_text}\n{text}"
    else:
        schedule.source.raw_text = text


def start_schedule_list(schedule: Schedule, name: str) -> ScheduleList:
    """Start a new named list within a schedule."""
    list_obj = ScheduleList(
        id=f"{schedule.id}-list-{len(schedule.lists) + 1}",
        name=name,
        source=SourceProvenance(raw_heading=name),
    )
    schedule.lists.append(list_obj)
    return list_obj


def add_table_from_rows(
    schedule: Schedule,
    rows: list[list[str]],
    *,
    caption: str | None = None,
) -> TableData:
    """Preserve a table under a schedule without losing cell content."""
    headers = rows[0] if rows else []
    body_rows = rows[1:] if len(rows) > 1 else []
    table = TableData(
        id=f"{schedule.id}-table-{len(schedule.tables) + 1}",
        caption=caption,
        headers=headers,
        rows=body_rows,
    )
    schedule.tables.append(table)
    return table


def add_section(schedule: Schedule, title: str, body: str = "") -> ScheduleSection:
    """Add a named section to a schedule."""
    section = ScheduleSection(
        id=f"{schedule.id}-section-{len(schedule.sections) + 1}",
        title=title,
        body_text=body,
        source=SourceProvenance(raw_heading=title, raw_text=body or None),
    )
    schedule.sections.append(section)
    return section


def extract_article_references(text: str) -> list[str]:
    """Extract 'Articles 246 and 248' style references from schedule intros."""
    refs: list[str] = []
    for match in re.finditer(
        r"Articles?\s+([\dA-Za-z,\s]+(?:\s+and\s+[\dA-Za-z]+)?)",
        text,
        re.I,
    ):
        refs.append(match.group(0).strip())
    return refs
