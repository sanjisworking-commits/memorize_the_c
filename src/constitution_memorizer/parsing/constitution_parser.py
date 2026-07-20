"""State-machine parser for Constitution Bare Act Markdown/text."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable

from constitution_memorizer.normalization.line_normalizer import NormalizedLine
from constitution_memorizer.parsing.article_parser import (
    looks_like_article_title_line,
    looks_like_schedule_entry,
    parse_article_heading_line,
)
from constitution_memorizer.parsing.clause_parser import (
    append_text,
    make_clause_node,
    make_subclause_node,
    nesting_rank,
    parse_clause_line,
    parse_special_provision,
)
from constitution_memorizer.parsing.footnote_parser import (
    append_footnote_text,
    associate_footnotes,
    build_footnote,
    detect_footnote_start,
)
from constitution_memorizer.parsing.patterns import (
    APPENDIX_RE,
    CHAPTER_RE,
    CHAPTER_SUBSECTION_RE,
    CONTENTS_RE,
    ENACTMENT_DATE_RE,
    LIST_OF_ABBREVIATIONS_RE,
    PART_RE,
    PREAMBLE_RE,
    PREFACE_RE,
    SCHEDULE_PART_RE,
)
from constitution_memorizer.parsing.schedule_parser import (
    append_schedule_text,
    create_schedule,
    detect_list_heading,
    extract_article_references,
    parse_schedule_heading,
    start_schedule_list,
)
from constitution_memorizer.schemas import (
    Appendix,
    Article,
    ArticleStatus,
    Chapter,
    ConstitutionDocument,
    DocumentMetadata,
    ExtractionSummary,
    Footnote,
    NormalizationEvent,
    Part,
    Preamble,
    ProvisionNode,
    Schedule,
    SourceProvenance,
    UnclassifiedContent,
)
from constitution_memorizer.utils.identifiers import (
    article_id,
    chapter_id,
    part_id,
    roman_to_int,
    unclassified_id,
)

logger = logging.getLogger(__name__)


class ParserState(str, Enum):
    DOCUMENT_FRONT_MATTER = "document_front_matter"
    PREAMBLE = "preamble"
    PART = "part"
    CHAPTER = "chapter"
    ARTICLE = "article"
    CLAUSE = "clause"
    SUBCLAUSE = "subclause"
    PROVISO = "proviso"
    EXPLANATION = "explanation"
    FOOTNOTE_SECTION = "footnote_section"
    SCHEDULE = "schedule"
    APPENDIX = "appendix"
    UNKNOWN = "unknown"


@dataclass
class ParserContext:
    """Mutable parser context for the state machine."""

    state: ParserState = ParserState.DOCUMENT_FRONT_MATTER
    document: ConstitutionDocument = field(default_factory=ConstitutionDocument)
    current_part: Part | None = None
    current_chapter: Chapter | None = None
    current_article: Article | None = None
    current_clause: ProvisionNode | None = None
    provision_stack: list[ProvisionNode] = field(default_factory=list)
    current_schedule: Schedule | None = None
    current_footnote: Footnote | None = None
    current_appendix: Appendix | None = None
    awaiting_part_title: bool = False
    awaiting_chapter_title: bool = False
    awaiting_article_title: bool = False
    events: list[NormalizationEvent] = field(default_factory=list)
    unclassified_index: int = 0
    last_element_id: str | None = None
    front_matter_lines: list[str] = field(default_factory=list)
    # True once the operative Bare Act body begins (after TOC / preface).
    body_started: bool = False
    in_contents: bool = False
    schedules_region: bool = False
    seen_part_numbers: set[str] = field(default_factory=set)
    seen_article_numbers: set[str] = field(default_factory=set)
    chapter_subsections: list[str] = field(default_factory=list)


def _transition(ctx: ParserContext, new_state: ParserState, reason: str) -> None:
    if ctx.state != new_state:
        logger.debug("Parser transition %s → %s (%s)", ctx.state.value, new_state.value, reason)
        ctx.events.append(
            NormalizationEvent(
                event_type="parser_transition",
                original_text=ctx.state.value,
                normalized_text=new_state.value,
                reason=reason,
                confidence=1.0,
            )
        )
        ctx.state = new_state


def _attach_article(ctx: ParserContext, article: Article) -> None:
    if ctx.current_chapter is not None:
        ctx.current_chapter.articles.append(article)
    elif ctx.current_part is not None:
        ctx.current_part.articles.append(article)
    else:
        # Article before any Part — keep via unclassified? Better: invent anonymous part.
        # Retain as unclassified note plus still store under a synthetic container.
        _add_unclassified(
            ctx,
            text=f"Article {article.article_number} appeared before any Part heading",
            possible_type="article_without_part",
            confidence=0.4,
            reason="Article encountered before PART heading",
        )
        # Create a placeholder part so content is not lost from structured output.
        if ctx.current_part is None:
            part = Part(
                id="part-unknown",
                part_number="UNKNOWN",
                title="Unassigned",
                articles=[],
            )
            ctx.document.parts.append(part)
            ctx.current_part = part
        ctx.current_part.articles.append(article)
    ctx.current_article = article
    ctx.current_clause = None
    ctx.provision_stack = []
    ctx.last_element_id = article.id
    ctx.awaiting_article_title = False


def _add_unclassified(
    ctx: ParserContext,
    *,
    text: str,
    page_number: int | None = None,
    possible_type: str | None = None,
    confidence: float | None = None,
    reason: str = "",
) -> None:
    ctx.unclassified_index += 1
    item = UnclassifiedContent(
        id=unclassified_id(ctx.unclassified_index),
        text=text,
        page_number=page_number,
        preceding_element_id=ctx.last_element_id,
        following_element_id=None,
        possible_type=possible_type,
        confidence=confidence,
        reason=reason,
    )
    ctx.document.unclassified_content.append(item)
    ctx.events.append(
        NormalizationEvent(
            event_type="unclassified_content",
            original_text=text,
            reason=reason or "Could not confidently classify content",
            confidence=confidence,
            page_number=page_number,
        )
    )


def _finalize_article_body(article: Article) -> None:
    """Compose body_text from opening + clauses if body_text empty."""
    if article.body_text.strip():
        return
    parts: list[str] = []
    if article.opening_text.strip():
        parts.append(article.opening_text.strip())
    for clause in article.clauses:
        parts.append(f"{clause.label} {clause.text}".strip())
        for child in clause.children:
            parts.append(f"{child.label} {child.text}".strip())
    for proviso in article.provisos:
        parts.append(proviso)
    for expl in article.explanations:
        parts.append(expl)
    article.body_text = "\n".join(p for p in parts if p)


def _start_part(ctx: ParserContext, number: str, title: str | None, raw: str) -> bool:
    """
    Start a Constitution Part.

    Returns False when the heading should not create a new Part (duplicate or
    post-schedule/appendix territorial PART blocks).
    """
    normalized = number.upper().replace(" ", "")

    # After schedules begin, constitutional PART I–XXII headings should not
    # reopen the main Part list (appendix territorial PART I/II/III, etc.).
    if ctx.schedules_region or ctx.state == ParserState.APPENDIX:
        if ctx.current_appendix is not None:
            if ctx.current_appendix.body_text:
                ctx.current_appendix.body_text += f"\n{raw}"
            else:
                ctx.current_appendix.body_text = raw
        elif ctx.current_schedule is not None:
            append_schedule_text(ctx.current_schedule, raw)
        else:
            _add_unclassified(
                ctx,
                text=raw,
                possible_type="appendix_part",
                confidence=0.7,
                reason="PART heading after schedules/appendix retained outside main parts",
            )
        return False

    if normalized in ctx.seen_part_numbers:
        # Re-enter existing Part (rare TOC bleed) instead of duplicating.
        existing = next(
            (p for p in ctx.document.parts if p.part_number == normalized),
            None,
        )
        if existing is not None:
            ctx.current_part = existing
            ctx.current_chapter = None
            ctx.current_article = None
            ctx.current_clause = None
            ctx.provision_stack = []
            ctx.awaiting_part_title = title is None and not existing.title
            _transition(ctx, ParserState.PART, f"reenter PART {normalized}")
            return True
        _add_unclassified(
            ctx,
            text=raw,
            possible_type="duplicate_part",
            confidence=0.8,
            reason=f"Duplicate PART {normalized} demoted",
        )
        return False

    if ctx.current_article is not None:
        _finalize_article_body(ctx.current_article)
    part = Part(
        id=part_id(number),
        part_number=normalized,
        part_number_normalized=roman_to_int(number),
        title=title,
        source=SourceProvenance(raw_heading=raw),
    )
    ctx.document.parts.append(part)
    ctx.seen_part_numbers.add(normalized)
    ctx.current_part = part
    ctx.current_chapter = None
    ctx.current_article = None
    ctx.current_clause = None
    ctx.provision_stack = []
    ctx.awaiting_part_title = title is None
    ctx.last_element_id = part.id
    _transition(ctx, ParserState.PART, f"PART {part.part_number}")
    return True


def _start_chapter(ctx: ParserContext, number: str, title: str | None, raw: str) -> None:
    if ctx.current_part is None:
        _start_part(ctx, "UNKNOWN", "Unassigned", "synthetic")
    assert ctx.current_part is not None
    if ctx.current_article is not None:
        _finalize_article_body(ctx.current_article)
    chapter = Chapter(
        id=chapter_id(ctx.current_part.part_number, number),
        chapter_number=number.upper(),
        title=title,
        source=SourceProvenance(raw_heading=raw),
    )
    ctx.current_part.chapters.append(chapter)
    ctx.current_chapter = chapter
    ctx.current_article = None
    ctx.current_clause = None
    ctx.provision_stack = []
    ctx.awaiting_chapter_title = title is None
    ctx.last_element_id = chapter.id
    _transition(ctx, ParserState.CHAPTER, f"CHAPTER {chapter.chapter_number}")


def _start_article_from_heading(ctx: ParserContext, line: str) -> bool:
    heading = parse_article_heading_line(line)
    if heading is None:
        return False

    # Inside schedules, numbered entries are schedule items, not Articles.
    if ctx.state == ParserState.SCHEDULE:
        return False
    if ctx.schedules_region and looks_like_schedule_entry(line):
        return False

    parts = heading.number_parts
    # Keep first substantive occurrence; demote later collisions for review.
    if parts.article_number in ctx.seen_article_numbers:
        _add_unclassified(
            ctx,
            text=line,
            possible_type="duplicate_article",
            confidence=0.85,
            reason=(
                f"Duplicate Article {parts.article_number} demoted; "
                "first occurrence retained"
            ),
        )
        ctx.events.append(
            NormalizationEvent(
                event_type="demoted_duplicate_article",
                original_text=line,
                reason=f"Article {parts.article_number} already seen",
                confidence=0.9,
            )
        )
        return True

    if ctx.current_article is not None:
        _finalize_article_body(ctx.current_article)

    article = Article(
        id=article_id(parts.article_number),
        article_number=parts.article_number,
        numeric_component=parts.numeric_component,
        suffix=parts.suffix,
        title=heading.title,
        status=heading.status,
        part_number=ctx.current_part.part_number if ctx.current_part else None,
        chapter_number=ctx.current_chapter.chapter_number if ctx.current_chapter else None,
        opening_text=heading.opening_text,
        source=SourceProvenance(
            raw_heading=heading.raw_heading,
            raw_text=heading.opening_text or None,
        ),
    )
    if heading.footnote_marker:
        article.footnote_references.append(heading.footnote_marker)

    await_title = heading.title is None and not heading.opening_text

    _attach_article(ctx, article)
    ctx.seen_article_numbers.add(parts.article_number)
    ctx.awaiting_article_title = await_title
    _transition(ctx, ParserState.ARTICLE, f"Article {article.article_number}")
    return True


def _handle_clause(ctx: ParserContext, line: str) -> bool:
    parsed = parse_clause_line(line)
    if parsed is None or ctx.current_article is None:
        return False

    label, body, label_type = parsed
    rank = nesting_rank(label_type)

    if rank == 0:
        node = make_clause_node(ctx.current_article.article_number, label, body, label_type)
        ctx.current_article.clauses.append(node)
        ctx.current_clause = node
        ctx.provision_stack = [node]
        _transition(ctx, ParserState.CLAUSE, f"clause ({label})")
        return True

    # Nested provision: attach to deepest compatible parent.
    if not ctx.provision_stack:
        # No parent clause — treat as top-level clause anyway to avoid loss.
        node = make_clause_node(ctx.current_article.article_number, label, body, label_type)
        ctx.current_article.clauses.append(node)
        ctx.current_clause = node
        ctx.provision_stack = [node]
        _transition(ctx, ParserState.CLAUSE, f"orphan nested ({label}) promoted")
        return True

    while len(ctx.provision_stack) > 1:
        parent = ctx.provision_stack[-1]
        if nesting_rank(parent.label_type) < rank:
            break
        ctx.provision_stack.pop()

    parent = ctx.provision_stack[-1]
    child = make_subclause_node(parent.id, label, body, label_type)
    parent.children.append(child)
    ctx.provision_stack.append(child)
    _transition(ctx, ParserState.SUBCLAUSE, f"subclause ({label})")
    return True


def _handle_special(ctx: ParserContext, line: str) -> bool:
    special = parse_special_provision(line)
    if special is None:
        return False

    target_article = ctx.current_article
    target_clause = ctx.provision_stack[-1] if ctx.provision_stack else ctx.current_clause

    if special.kind == "proviso":
        if target_clause is not None:
            target_clause.provisos.append(special.text)
        elif target_article is not None:
            target_article.provisos.append(special.text)
        else:
            _add_unclassified(ctx, text=special.text, possible_type="proviso", confidence=0.5,
                              reason="Proviso without parent article")
        _transition(ctx, ParserState.PROVISO, "proviso")
        return True

    if special.kind == "explanation":
        if target_clause is not None:
            target_clause.explanations.append(special.text)
        elif target_article is not None:
            target_article.explanations.append(special.text)
        else:
            _add_unclassified(ctx, text=special.text, possible_type="explanation", confidence=0.5,
                              reason="Explanation without parent article")
        _transition(ctx, ParserState.EXPLANATION, "explanation")
        return True

    if special.kind == "exception" and target_article is not None:
        target_article.exceptions.append(special.text)
        return True

    if special.kind == "illustration" and target_article is not None:
        target_article.illustrations.append(special.text)
        return True

    _add_unclassified(
        ctx,
        text=special.text,
        possible_type=special.kind,
        confidence=0.45,
        reason=f"{special.kind} could not be associated",
    )
    return True


def _handle_footnote(ctx: ParserContext, line: str) -> bool:
    start = detect_footnote_start(line)
    if start is None:
        # Continuation of current footnote?
        if ctx.state == ParserState.FOOTNOTE_SECTION and ctx.current_footnote is not None:
            # Stop continuation on clear structural headings.
            if (
                PART_RE.match(line)
                or CHAPTER_RE.match(line)
                or parse_schedule_heading(line)
                or parse_article_heading_line(line)
            ):
                return False
            append_footnote_text(ctx.current_footnote, line)
            return True
        return False

    footnote = build_footnote(
        start.marker,
        start.text,
        context=ctx.current_article.article_number if ctx.current_article else None,
    )
    ctx.document.footnotes.append(footnote)
    ctx.current_footnote = footnote
    ctx.last_element_id = footnote.id
    _transition(ctx, ParserState.FOOTNOTE_SECTION, f"footnote {start.marker}")
    return True


def _append_article_text(ctx: ParserContext, text: str) -> None:
    assert ctx.current_article is not None
    if ctx.provision_stack:
        append_text(ctx.provision_stack[-1], text)
    elif ctx.current_article.opening_text:
        ctx.current_article.opening_text = f"{ctx.current_article.opening_text} {text}"
    else:
        ctx.current_article.opening_text = text
    if ctx.current_article.source.raw_text:
        ctx.current_article.source.raw_text += f"\n{text}"
    else:
        ctx.current_article.source.raw_text = text


def _strip_markdown_noise(text: str) -> str:
    """Remove common Docling Markdown wrappers without altering legal words."""
    working = re.sub(r"^#{1,6}\s*", "", text.strip())
    working = re.sub(r"^\*\*(.+)\*\*$", r"\1", working).strip()
    # Table cell lines from TOC: "| 1. | Name and territory |"
    if working.startswith("|"):
        cells = [c.strip() for c in working.strip("|").split("|")]
        cells = [c for c in cells if c and not re.fullmatch(r":?-{3,}:?", c)]
        working = " ".join(cells).strip()
    return working


def _process_line(ctx: ParserContext, line_obj: NormalizedLine) -> None:
    line = line_obj.text
    stripped = line.strip()

    # Preserve blank lines only as paragraph breaks inside preamble.
    if not stripped:
        if ctx.state == ParserState.PREAMBLE and ctx.document.preamble is not None:
            if ctx.document.preamble.paragraphs and ctx.document.preamble.paragraphs[-1]:
                ctx.document.preamble.paragraphs.append("")
        return

    working = _strip_markdown_noise(stripped)
    if not working:
        return

    if CONTENTS_RE.match(working) or PREFACE_RE.match(working) or LIST_OF_ABBREVIATIONS_RE.match(working):
        ctx.in_contents = True
        ctx.front_matter_lines.append(working)
        _transition(ctx, ParserState.DOCUMENT_FRONT_MATTER, "preface/contents")
        return

    # Body starts at the operative preamble text.
    if working.upper().startswith("WE, THE PEOPLE"):
        ctx.body_started = True
        ctx.in_contents = False

    # While inside CONTENTS/TOC, retain lines for review but do not build structure.
    if ctx.in_contents and not ctx.body_started:
        ctx.front_matter_lines.append(working)
        return

    # Editions/fixtures without a TOC: first operative structural marker opens the body.
    if not ctx.body_started and (
        PART_RE.match(working)
        or CHAPTER_RE.match(working)
        or parse_schedule_heading(working) is not None
        or parse_article_heading_line(working) is not None
    ):
        ctx.body_started = True

    # Inside schedules, never invent Articles / Parts from numbered list items.
    if ctx.state == ParserState.SCHEDULE and ctx.current_schedule is not None:
        schedule_heading = parse_schedule_heading(working)
        if schedule_heading:
            # Reuse schedule object if same number already created.
            existing = next(
                (
                    s
                    for s in ctx.document.schedules
                    if s.schedule_number == schedule_heading.schedule_number
                ),
                None,
            )
            if existing is None:
                schedule = create_schedule(schedule_heading)
                ctx.document.schedules.append(schedule)
            else:
                schedule = existing
            ctx.current_schedule = schedule
            ctx.schedules_region = True
            ctx.last_element_id = schedule.id
            return
        if APPENDIX_RE.match(working):
            pass  # fall through to appendix handling below
        else:
            # PART I/II/III inside schedules stay in schedule text.
            sched_part = SCHEDULE_PART_RE.match(working) or PART_RE.match(working)
            if sched_part:
                from constitution_memorizer.parsing.schedule_parser import add_section

                add_section(ctx.current_schedule, working)
                append_schedule_text(ctx.current_schedule, working)
                return
            list_name = detect_list_heading(working)
            if list_name:
                start_schedule_list(ctx.current_schedule, list_name)
                return
            if _handle_footnote(ctx, working):
                return
            if ctx.current_schedule.lists:
                ctx.current_schedule.lists[-1].items.append(working)
                if ctx.current_schedule.lists[-1].body_text:
                    ctx.current_schedule.lists[-1].body_text += f"\n{working}"
                else:
                    ctx.current_schedule.lists[-1].body_text = working
            append_schedule_text(ctx.current_schedule, working)
            return

    if ctx.state == ParserState.APPENDIX and ctx.current_appendix is not None:
        # Keep appendix-internal PART I/II/III territorial divisions out of
        # the Constitution Part list; only leave for a new Schedule heading.
        if parse_schedule_heading(working) is None and not PREAMBLE_RE.match(working):
            if APPENDIX_RE.match(working):
                pass  # fall through to start another appendix
            else:
                if ctx.current_appendix.body_text:
                    ctx.current_appendix.body_text += f"\n{working}"
                else:
                    ctx.current_appendix.body_text = working
                return

    # Awaited titles
    if ctx.awaiting_part_title and ctx.current_part is not None:
        if not PART_RE.match(working) and not CHAPTER_RE.match(working) and not parse_article_heading_line(working):
            ctx.current_part.title = working
            ctx.awaiting_part_title = False
            return

    if ctx.awaiting_chapter_title and ctx.current_chapter is not None:
        if not PART_RE.match(working) and not CHAPTER_RE.match(working) and not parse_article_heading_line(working):
            ctx.current_chapter.title = working
            ctx.awaiting_chapter_title = False
            return

    if ctx.awaiting_article_title and ctx.current_article is not None:
        if looks_like_article_title_line(working) and not parse_clause_line(working):
            # May include em-dash body.
            from constitution_memorizer.parsing.article_parser import split_title_and_body

            title, opening = split_title_and_body(working)
            if title:
                ctx.current_article.title = title
            if opening:
                ctx.current_article.opening_text = opening
            # Status from omitted/repealed title lines.
            from constitution_memorizer.parsing.article_parser import parse_article_heading_line as _pah

            # Direct omitted check:
            if re.search(r"\[?\s*Omitted\.?\s*\]?", working, re.I):
                ctx.current_article.status = ArticleStatus.OMITTED
                ctx.current_article.title = working.strip("[] ")
            elif re.search(r"\[?\s*Repealed\.?\s*\]?", working, re.I) or (
                re.match(r"^Repealed\.?$", working, re.I)
            ):
                ctx.current_article.status = ArticleStatus.REPEALED
                ctx.current_article.title = working.strip("[] ")
            ctx.awaiting_article_title = False
            if opening or title:
                return
            return

    # Structural detectors (order matters).
    if PREAMBLE_RE.match(working):
        if ctx.document.preamble is None:
            ctx.document.preamble = Preamble(source=SourceProvenance(raw_heading=working))
        _transition(ctx, ParserState.PREAMBLE, "PREAMBLE")
        return

    # Before the operative body, keep preface lines as front matter.
    # Footnotes may still appear in preface/endnotes regions — parse them.
    if not ctx.body_started:
        if PREAMBLE_RE.match(working):
            if ctx.document.preamble is None:
                ctx.document.preamble = Preamble(source=SourceProvenance(raw_heading=working))
            _transition(ctx, ParserState.PREAMBLE, "PREAMBLE")
            return
        if _handle_footnote(ctx, working):
            return
        ctx.front_matter_lines.append(working)
        _transition(ctx, ParserState.DOCUMENT_FRONT_MATTER, "front matter before body")
        return

    part_match = PART_RE.match(working)
    if part_match:
        number = part_match.group("number").replace(" ", "")
        title = part_match.group("title")
        ctx.current_schedule = None
        _start_part(ctx, number, title.strip() if title else None, working)
        return

    chapter_match = CHAPTER_RE.match(working)
    if chapter_match:
        number = chapter_match.group("number")
        title = chapter_match.group("title")
        # CHAPTER heading may include trailing article text on same Docling line.
        title_text = title.strip() if title else None
        if title_text and re.search(r"\b\d+[A-Za-z]{0,3}\.\s", title_text):
            # Split off trailing article-like content later via unclassified continuation.
            m = re.split(r"(?=\b\d+[A-Za-z]{0,3}\.\s)", title_text, maxsplit=1)
            title_text = m[0].strip() or None
            _start_chapter(ctx, number, title_text, working)
            if len(m) > 1 and m[1].strip():
                _process_line(
                    ctx,
                    NormalizedLine(index=line_obj.index, text=m[1].strip()),
                )
            return
        _start_chapter(ctx, number, title_text, working)
        return

    if CHAPTER_SUBSECTION_RE.match(working):
        if ctx.current_chapter is not None:
            # Store as editorial note on the chapter via source raw text trail.
            note = working
            if ctx.current_chapter.source.raw_text:
                ctx.current_chapter.source.raw_text += f"\n[subsection] {note}"
            else:
                ctx.current_chapter.source.raw_text = f"[subsection] {note}"
            ctx.chapter_subsections.append(note)
            ctx.events.append(
                NormalizationEvent(
                    event_type="chapter_subsection",
                    original_text=note,
                    reason="Classified chapter subsection heading",
                    confidence=0.9,
                )
            )
            return
        _add_unclassified(
            ctx,
            text=working,
            possible_type="chapter_subsection",
            confidence=0.7,
            reason="Chapter subsection without active chapter",
        )
        return

    schedule_heading = parse_schedule_heading(working)
    if schedule_heading:
        if ctx.current_article is not None:
            _finalize_article_body(ctx.current_article)
        existing = next(
            (
                s
                for s in ctx.document.schedules
                if s.schedule_number == schedule_heading.schedule_number
            ),
            None,
        )
        if existing is None:
            schedule = create_schedule(schedule_heading)
            refs = extract_article_references(working)
            if refs:
                schedule.references.extend(refs)
            ctx.document.schedules.append(schedule)
        else:
            schedule = existing
        ctx.current_schedule = schedule
        ctx.schedules_region = True
        ctx.current_article = None
        ctx.current_clause = None
        ctx.provision_stack = []
        ctx.last_element_id = schedule.id
        _transition(ctx, ParserState.SCHEDULE, f"Schedule {schedule.schedule_number}")
        return

    appendix_match = APPENDIX_RE.match(working)
    if appendix_match:
        label = (appendix_match.group("label") or "").strip() or str(
            len(ctx.document.appendices) + 1
        )
        appendix = Appendix(
            id=f"appendix-{label.lower()}",
            title=working,
            source=SourceProvenance(raw_heading=working),
        )
        ctx.document.appendices.append(appendix)
        ctx.current_appendix = appendix
        ctx.current_schedule = None
        ctx.schedules_region = True
        _transition(ctx, ParserState.APPENDIX, "appendix")
        return

    # Footnotes before articles so "1. Subs. by..." is not mistaken for Article 1.
    if _handle_footnote(ctx, working):
        return

    if _start_article_from_heading(ctx, working):
        return

    if _handle_clause(ctx, working):
        return

    if _handle_special(ctx, working):
        return

    # State-specific continuation.
    if ctx.state == ParserState.PREAMBLE and ctx.document.preamble is not None:
        preamble = ctx.document.preamble
        if ENACTMENT_DATE_RE.match(working):
            preamble.enactment_date_line = working
        if preamble.paragraphs and preamble.paragraphs[-1] == "":
            preamble.paragraphs[-1] = working
        elif preamble.paragraphs:
            # New sentence/paragraph line
            preamble.paragraphs.append(working)
        else:
            preamble.paragraphs.append(working)
        preamble.text = "\n\n".join(p for p in preamble.paragraphs if p)
        if preamble.source.raw_text:
            preamble.source.raw_text += f"\n{working}"
        else:
            preamble.source.raw_text = working
        return

    if ctx.state == ParserState.SCHEDULE and ctx.current_schedule is not None:
        list_name = detect_list_heading(working)
        if list_name:
            start_schedule_list(ctx.current_schedule, list_name)
            return
        if ctx.current_schedule.lists:
            ctx.current_schedule.lists[-1].items.append(working)
            if ctx.current_schedule.lists[-1].body_text:
                ctx.current_schedule.lists[-1].body_text += f"\n{working}"
            else:
                ctx.current_schedule.lists[-1].body_text = working
        append_schedule_text(ctx.current_schedule, working)
        return

    if ctx.state == ParserState.APPENDIX and ctx.current_appendix is not None:
        if ctx.current_appendix.body_text:
            ctx.current_appendix.body_text += f"\n{working}"
        else:
            ctx.current_appendix.body_text = working
        return

    if ctx.current_article is not None and ctx.state in {
        ParserState.ARTICLE,
        ParserState.CLAUSE,
        ParserState.SUBCLAUSE,
        ParserState.PROVISO,
        ParserState.EXPLANATION,
        ParserState.CHAPTER,
        ParserState.PART,
    }:
        _append_article_text(ctx, working)
        return

    if ctx.state == ParserState.DOCUMENT_FRONT_MATTER:
        ctx.front_matter_lines.append(working)
        # Heuristic: WE, THE PEOPLE... starts preamble without heading.
        if working.upper().startswith("WE, THE PEOPLE"):
            if ctx.document.preamble is None:
                ctx.document.preamble = Preamble(
                    paragraphs=[working],
                    text=working,
                    source=SourceProvenance(raw_text=working),
                )
            _transition(ctx, ParserState.PREAMBLE, "preamble text without heading")
        return

    # Unknown — retain.
    _add_unclassified(
        ctx,
        text=working,
        page_number=line_obj.page_number,
        possible_type="unknown",
        confidence=0.3,
        reason=f"No rule matched in state {ctx.state.value}",
    )
    _transition(ctx, ParserState.UNKNOWN, "unclassified line")


def _build_summary(doc: ConstitutionDocument) -> ExtractionSummary:
    chapters = sum(len(p.chapters) for p in doc.parts)
    articles = []
    for part in doc.parts:
        articles.extend(part.articles)
        for chapter in part.chapters:
            articles.extend(chapter.articles)
    omitted = sum(1 for a in articles if a.status == ArticleStatus.OMITTED)
    repealed = sum(1 for a in articles if a.status == ArticleStatus.REPEALED)
    return ExtractionSummary(
        parts_found=len(doc.parts),
        chapters_found=chapters,
        articles_found=len(articles),
        footnotes_found=len(doc.footnotes),
        schedules_found=len(doc.schedules),
        unclassified_blocks=len(doc.unclassified_content),
        omitted_articles_found=omitted,
        repealed_articles_found=repealed,
    )


def parse_lines(
    lines: Iterable[NormalizedLine] | Iterable[str],
    *,
    metadata: DocumentMetadata | None = None,
) -> tuple[ConstitutionDocument, list[NormalizationEvent]]:
    """
    Parse normalized lines into a ConstitutionDocument.

    ``lines`` may be ``NormalizedLine`` objects or plain strings.
    """
    ctx = ParserContext()
    if metadata is not None:
        ctx.document.document = metadata

    for item in lines:
        if isinstance(item, NormalizedLine):
            if not item.kept:
                continue
            _process_line(ctx, item)
        else:
            _process_line(ctx, NormalizedLine(index=0, text=str(item)))

    if ctx.current_article is not None:
        _finalize_article_body(ctx.current_article)

    # Front matter not consumed — keep as unclassified rather than drop.
    if ctx.front_matter_lines:
        # If preamble already captured WE THE PEOPLE, don't duplicate those lines.
        for text in ctx.front_matter_lines:
            if ctx.document.preamble and text in (ctx.document.preamble.text or ""):
                continue
            # Skip pure edition titles that are noise if preamble exists.
            _add_unclassified(
                ctx,
                text=text,
                possible_type="front_matter",
                confidence=0.55,
                reason="Document front matter retained for review",
            )

    # Best-effort footnote association (no invented links).
    associate_footnotes(ctx.document)

    ctx.document.extraction_summary = _build_summary(ctx.document)
    return ctx.document, ctx.events


def parse_markdown(
    text: str,
    *,
    metadata: DocumentMetadata | None = None,
) -> tuple[ConstitutionDocument, list[NormalizationEvent]]:
    """Parse a Markdown/text string into a ConstitutionDocument."""
    lines = [
        NormalizedLine(index=i, text=line)
        for i, line in enumerate(text.splitlines())
    ]
    return parse_lines(lines, metadata=metadata)
