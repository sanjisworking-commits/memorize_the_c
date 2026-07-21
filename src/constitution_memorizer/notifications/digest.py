"""Build today's study reminder digest from ReminderEngine (Home parity)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from constitution_memorizer.progress.scheduler import ReminderEngine
from constitution_memorizer.web.service import continue_unit_id, due_checklist


@dataclass(frozen=True)
class ReminderDigest:
    as_of: date
    titles: list[str] = field(default_factory=list)
    unit_ids: list[str] = field(default_factory=list)
    continue_title: str | None = None
    continue_id: str | None = None
    base_url: str = "http://127.0.0.1:8001/"

    @property
    def due_count(self) -> int:
        return len(self.titles)

    @property
    def is_empty(self) -> bool:
        return self.due_count == 0

    def notification_title(self) -> str:
        if self.is_empty:
            return "Recall the C — all caught up"
        n = self.due_count
        return f"Recall the C — {n} due today"

    def notification_body(self) -> str:
        lines = [self.as_of.strftime("%d %b %Y")]
        if self.titles:
            for title in self.titles:
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
) -> ReminderDigest:
    """Build digest using the same due list as the Home page."""
    today = as_of or date.today()
    due_units = due_checklist(engine, as_of=today)
    titles = [u.display_title for u in due_units]
    ids = [u.id for u in due_units]
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
        continue_title=cont_title,
        continue_id=cont_id,
        base_url=base_url,
    )
