"""Build today's study reminder digest (Constitution + Memory log)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from constitution_memorizer.progress.memory import MemoryEngine, MemoryEntry
from constitution_memorizer.progress.scheduler import ReminderEngine
from constitution_memorizer.web.service import continue_unit_id, due_checklist


def memory_due_entries(
    memory: MemoryEngine | None,
    *,
    as_of: date | None = None,
) -> list[MemoryEntry]:
    """Memory log entries due today or overdue (not mastered)."""
    if memory is None:
        return []
    today = as_of or date.today()
    due: list[MemoryEntry] = []
    for entry in memory.repo.list_all():
        if entry.status == "mastered":
            continue
        if entry.next_revision is None:
            continue
        if entry.next_revision <= today:
            due.append(entry)
    due.sort(
        key=lambda e: (
            e.next_revision or today,
            e.title.lower(),
            e.id,
        )
    )
    return due


def memory_entry_label(entry: MemoryEntry) -> str:
    title = entry.title.strip() or entry.id
    acronym = entry.acronym.strip()
    if acronym:
        return f"{title} ({acronym})"
    return title


@dataclass(frozen=True)
class ReminderDigest:
    as_of: date
    titles: list[str] = field(default_factory=list)
    unit_ids: list[str] = field(default_factory=list)
    memory_titles: list[str] = field(default_factory=list)
    memory_ids: list[str] = field(default_factory=list)
    continue_title: str | None = None
    continue_id: str | None = None
    base_url: str = "http://127.0.0.1:8001/"

    @property
    def constitution_due_count(self) -> int:
        return len(self.titles)

    @property
    def memory_due_count(self) -> int:
        return len(self.memory_titles)

    @property
    def due_count(self) -> int:
        return self.constitution_due_count + self.memory_due_count

    @property
    def is_empty(self) -> bool:
        return self.due_count == 0

    def notification_title(self) -> str:
        if self.is_empty:
            return "Recall the C — all caught up"
        n = self.due_count
        return f"Recall the C — {n} due"

    def notification_body(self) -> str:
        lines = [self.as_of.strftime("%d %b %Y")]
        if self.titles or self.memory_titles:
            if self.titles:
                if self.memory_titles:
                    lines.append("Constitution:")
                for title in self.titles:
                    lines.append(f"• {title}")
            if self.memory_titles:
                if self.titles:
                    lines.append("Memory log:")
                for title in self.memory_titles:
                    lines.append(f"• {title}")
        elif self.continue_title:
            lines.append(f"Nothing due — continue with {self.continue_title}")
        else:
            lines.append("Nothing due today.")
        lines.append(f"Open {self.base_url.rstrip('/')}/")
        return "\n".join(lines)


def build_study_digest(
    engine: ReminderEngine,
    *,
    as_of: date | None = None,
    base_url: str = "http://127.0.0.1:8001/",
    include_continue: bool = True,
    memory: MemoryEngine | None = None,
) -> ReminderDigest:
    """Build digest using Home due list + Memory log dues."""
    today = as_of or date.today()
    due_units = due_checklist(engine, as_of=today)
    titles = [u.display_title for u in due_units]
    ids = [u.id for u in due_units]
    mem_entries = memory_due_entries(memory, as_of=today)
    mem_titles = [memory_entry_label(e) for e in mem_entries]
    mem_ids = [e.id for e in mem_entries]
    cont_title = None
    cont_id = None
    if include_continue:
        cont_id = continue_unit_id(engine, as_of=today)
        if cont_id:
            unit = engine.get_unit(cont_id)
            cont_title = unit.display_title if unit else cont_id
    return ReminderDigest(
        as_of=today,
        titles=titles,
        unit_ids=ids,
        memory_titles=mem_titles,
        memory_ids=mem_ids,
        continue_title=cont_title,
        continue_id=cont_id,
        base_url=base_url,
    )
