"""Memory log — personal list/acronym scheduler (separate from Constitution)."""

from __future__ import annotations

import secrets
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

# Memory log ladder stops at 30 (no 60 rung).
MEMORY_INTERVAL_LADDER: tuple[int, ...] = (1, 3, 7, 14, 30)


def advance_memory_interval(current_interval_days: int) -> int | None:
    """Next Memory log rung, or None when the entry should be mastered."""
    if current_interval_days <= 0:
        return MEMORY_INTERVAL_LADDER[0]
    if current_interval_days in MEMORY_INTERVAL_LADDER:
        index = MEMORY_INTERVAL_LADDER.index(current_interval_days)
        if index + 1 >= len(MEMORY_INTERVAL_LADDER):
            return None
        return MEMORY_INTERVAL_LADDER[index + 1]
    for rung in MEMORY_INTERVAL_LADDER:
        if rung > current_interval_days:
            return rung
    return None


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass(frozen=True)
class MemoryEntry:
    id: str
    title: str
    acronym: str
    notes: str
    logged_date: date
    status: str
    interval_days: int
    last_completed: date | None
    next_revision: date | None
    times_completed: int
    created_at: str
    updated_at: str
    photo_path: str | None = None


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    return date.fromisoformat(value)


def _row_to_entry(row: sqlite3.Row, photo_path: str | None = None) -> MemoryEntry:
    return MemoryEntry(
        id=row["id"],
        title=row["title"],
        acronym=row["acronym"] or "",
        notes=row["notes"] or "",
        logged_date=date.fromisoformat(row["logged_date"]),
        status=row["status"],
        interval_days=int(row["interval_days"]),
        last_completed=_parse_date(row["last_completed"]),
        next_revision=_parse_date(row["next_revision"]),
        times_completed=int(row["times_completed"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        photo_path=photo_path,
    )


class MemoryRepository:
    """CRUD for memory_entry / memory_media on the shared progress connection."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def get(self, entry_id: str) -> MemoryEntry | None:
        row = self.conn.execute(
            "SELECT * FROM memory_entry WHERE id = ?", (entry_id,)
        ).fetchone()
        if row is None:
            return None
        media = self.conn.execute(
            "SELECT path FROM memory_media WHERE entry_id = ?", (entry_id,)
        ).fetchone()
        return _row_to_entry(row, media["path"] if media else None)

    def list_all(self) -> list[MemoryEntry]:
        rows = self.conn.execute(
            "SELECT * FROM memory_entry ORDER BY logged_date DESC, created_at DESC"
        ).fetchall()
        photos = {
            r["entry_id"]: r["path"]
            for r in self.conn.execute("SELECT entry_id, path FROM memory_media")
        }
        return [_row_to_entry(row, photos.get(row["id"])) for row in rows]

    def create(
        self,
        *,
        title: str,
        acronym: str = "",
        logged_date: date | None = None,
    ) -> MemoryEntry:
        entry_id = f"mem-{secrets.token_hex(6)}"
        today = logged_date or date.today()
        now = _utc_now()
        # First review due tomorrow (+1).
        next_rev = today + timedelta(days=1)
        self.conn.execute(
            """
            INSERT INTO memory_entry (
                id, title, acronym, notes, logged_date, status, interval_days,
                last_completed, next_revision, times_completed, created_at, updated_at
            ) VALUES (?, ?, ?, '', ?, 'review', 1, NULL, ?, 0, ?, ?)
            """,
            (
                entry_id,
                title.strip(),
                (acronym or "").strip(),
                today.isoformat(),
                next_rev.isoformat(),
                now,
                now,
            ),
        )
        self.conn.commit()
        entry = self.get(entry_id)
        assert entry is not None
        return entry

    def update_notes(self, entry_id: str, notes: str) -> MemoryEntry:
        now = _utc_now()
        self.conn.execute(
            "UPDATE memory_entry SET notes = ?, updated_at = ? WHERE id = ?",
            (notes, now, entry_id),
        )
        self.conn.commit()
        entry = self.get(entry_id)
        if entry is None:
            raise KeyError(entry_id)
        return entry

    def set_photo(self, entry_id: str, relative_path: str) -> MemoryEntry:
        now = _utc_now()
        self.conn.execute(
            """
            INSERT INTO memory_media (entry_id, path, uploaded_at)
            VALUES (?, ?, ?)
            ON CONFLICT(entry_id) DO UPDATE SET
                path = excluded.path,
                uploaded_at = excluded.uploaded_at
            """,
            (entry_id, relative_path, now),
        )
        self.conn.execute(
            "UPDATE memory_entry SET updated_at = ? WHERE id = ?",
            (now, entry_id),
        )
        self.conn.commit()
        entry = self.get(entry_id)
        if entry is None:
            raise KeyError(entry_id)
        return entry

    def mark_done(self, entry_id: str, *, as_of: date | None = None) -> MemoryEntry:
        entry = self.get(entry_id)
        if entry is None:
            raise KeyError(entry_id)
        today = as_of or date.today()
        nxt = advance_memory_interval(entry.interval_days)
        now = _utc_now()
        if nxt is None:
            status = "mastered"
            interval = entry.interval_days or MEMORY_INTERVAL_LADDER[-1]
            next_revision = None
        else:
            status = "review"
            interval = nxt
            next_revision = today + timedelta(days=nxt)
        self.conn.execute(
            """
            UPDATE memory_entry SET
                status = ?,
                interval_days = ?,
                last_completed = ?,
                next_revision = ?,
                times_completed = times_completed + 1,
                updated_at = ?
            WHERE id = ?
            """,
            (
                status,
                interval,
                today.isoformat(),
                next_revision.isoformat() if next_revision else None,
                now,
                entry_id,
            ),
        )
        self.conn.commit()
        updated = self.get(entry_id)
        assert updated is not None
        return updated


class MemoryEngine:
    """Thin facade over MemoryRepository using the progress DB connection."""

    def __init__(self, conn: sqlite3.Connection, media_dir: Path) -> None:
        self.repo = MemoryRepository(conn)
        self.media_dir = Path(media_dir)
        self.media_dir.mkdir(parents=True, exist_ok=True)

    @classmethod
    def from_db_path(cls, db_path: Path | str, media_dir: Path | str | None = None) -> MemoryEngine:
        from constitution_memorizer.progress.db import open_progress_db

        path = Path(db_path)
        media = Path(media_dir) if media_dir else path.parent / "memory_media"
        return cls(open_progress_db(path), media)
