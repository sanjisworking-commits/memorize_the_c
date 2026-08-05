"""Memory log — personal list/acronym scheduler (user-scoped)."""

from __future__ import annotations

import secrets
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID, uuid4

from constitution_memorizer.progress.user_ids import LOCAL_USER_ID, as_user_id

MEMORY_INTERVAL_LADDER: tuple[int, ...] = (1, 3, 7, 14, 30)


def advance_memory_interval(current_interval_days: int) -> int | None:
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
    user_id: str
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
        user_id=str(row["user_id"]),
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
    """CRUD for memory_entry / memory_media scoped by user_id."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def get(self, user_id: UUID | str, entry_id: str) -> MemoryEntry | None:
        row = self.conn.execute(
            "SELECT * FROM memory_entry WHERE id = ? AND user_id = ?",
            (entry_id, as_user_id(user_id)),
        ).fetchone()
        if row is None:
            return None
        media = self.conn.execute(
            """
            SELECT storage_key FROM memory_media
            WHERE entry_id = ? AND user_id = ?
            """,
            (entry_id, as_user_id(user_id)),
        ).fetchone()
        return _row_to_entry(row, media["storage_key"] if media else None)

    def list_all(self, user_id: UUID | str) -> list[MemoryEntry]:
        uid = as_user_id(user_id)
        rows = self.conn.execute(
            """
            SELECT * FROM memory_entry
            WHERE user_id = ?
            ORDER BY logged_date DESC, created_at DESC
            """,
            (uid,),
        ).fetchall()
        photos = {
            r["entry_id"]: r["storage_key"]
            for r in self.conn.execute(
                "SELECT entry_id, storage_key FROM memory_media WHERE user_id = ?",
                (uid,),
            )
        }
        return [_row_to_entry(row, photos.get(row["id"])) for row in rows]

    def create(
        self,
        user_id: UUID | str,
        *,
        title: str,
        acronym: str = "",
        logged_date: date | None = None,
    ) -> MemoryEntry:
        entry_id = f"mem-{secrets.token_hex(6)}"
        today = logged_date or date.today()
        now = _utc_now()
        next_rev = today + timedelta(days=1)
        uid = as_user_id(user_id)
        self.conn.execute(
            """
            INSERT INTO memory_entry (
                id, user_id, title, acronym, notes, logged_date, status, interval_days,
                last_completed, next_revision, times_completed, created_at, updated_at
            ) VALUES (?, ?, ?, ?, '', ?, 'review', 1, NULL, ?, 0, ?, ?)
            """,
            (
                entry_id,
                uid,
                title.strip(),
                (acronym or "").strip(),
                today.isoformat(),
                next_rev.isoformat(),
                now,
                now,
            ),
        )
        self.conn.commit()
        entry = self.get(user_id, entry_id)
        assert entry is not None
        return entry

    def update_notes(self, user_id: UUID | str, entry_id: str, notes: str) -> MemoryEntry:
        now = _utc_now()
        cur = self.conn.execute(
            """
            UPDATE memory_entry SET notes = ?, updated_at = ?
            WHERE id = ? AND user_id = ?
            """,
            (notes, now, entry_id, as_user_id(user_id)),
        )
        self.conn.commit()
        if cur.rowcount == 0:
            raise KeyError(entry_id)
        entry = self.get(user_id, entry_id)
        if entry is None:
            raise KeyError(entry_id)
        return entry

    def set_photo(
        self, user_id: UUID | str, entry_id: str, storage_key: str
    ) -> MemoryEntry:
        if self.get(user_id, entry_id) is None:
            raise KeyError(entry_id)
        now = _utc_now()
        media_id = str(uuid4())
        uid = as_user_id(user_id)
        self.conn.execute(
            """
            INSERT INTO memory_media (id, user_id, entry_id, storage_key, uploaded_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(entry_id) DO UPDATE SET
                storage_key = excluded.storage_key,
                uploaded_at = excluded.uploaded_at,
                user_id = excluded.user_id
            """,
            (media_id, uid, entry_id, storage_key, now),
        )
        self.conn.execute(
            "UPDATE memory_entry SET updated_at = ? WHERE id = ? AND user_id = ?",
            (now, entry_id, uid),
        )
        self.conn.commit()
        entry = self.get(user_id, entry_id)
        if entry is None:
            raise KeyError(entry_id)
        return entry

    def mark_done(
        self, user_id: UUID | str, entry_id: str, *, as_of: date | None = None
    ) -> MemoryEntry:
        entry = self.get(user_id, entry_id)
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
            WHERE id = ? AND user_id = ?
            """,
            (
                status,
                interval,
                today.isoformat(),
                next_revision.isoformat() if next_revision else None,
                now,
                entry_id,
                as_user_id(user_id),
            ),
        )
        self.conn.commit()
        updated = self.get(user_id, entry_id)
        assert updated is not None
        return updated


class MemoryEngine:
    """Thin facade over MemoryRepository using the progress DB connection."""

    def __init__(
        self,
        conn: sqlite3.Connection,
        media_dir: Path,
        *,
        user_id: UUID = LOCAL_USER_ID,
    ) -> None:
        self.repo = MemoryRepository(conn)
        self.media_dir = Path(media_dir).expanduser().resolve()
        self.media_dir.mkdir(parents=True, exist_ok=True)
        self.user_id = user_id

    def for_user(self, user_id: UUID) -> MemoryEngine:
        return MemoryEngine(self.repo.conn, self.media_dir, user_id=user_id)

    def user_media_dir(self) -> Path:
        path = self.media_dir / as_user_id(self.user_id)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def photo_file(self, entry_id: str) -> Path | None:
        entry = self.repo.get(self.user_id, entry_id)
        if entry is None or not entry.photo_path:
            return None
        # storage_key is relative to media_dir, e.g. "{user_id}/{entry_id}.png"
        key = entry.photo_path.replace("\\", "/")
        if ".." in key.split("/"):
            return None
        path = (self.media_dir / key).resolve()
        try:
            path.relative_to(self.media_dir)
        except ValueError:
            return None
        return path if path.is_file() else None

    def create(self, *, title: str, acronym: str = "", logged_date: date | None = None):
        return self.repo.create(
            self.user_id, title=title, acronym=acronym, logged_date=logged_date
        )

    def list_all(self):
        return self.repo.list_all(self.user_id)

    def get(self, entry_id: str):
        return self.repo.get(self.user_id, entry_id)

    def update_notes(self, entry_id: str, notes: str):
        return self.repo.update_notes(self.user_id, entry_id, notes)

    def set_photo(self, entry_id: str, storage_key: str):
        return self.repo.set_photo(self.user_id, entry_id, storage_key)

    def mark_done(self, entry_id: str, *, as_of: date | None = None):
        return self.repo.mark_done(self.user_id, entry_id, as_of=as_of)

    @classmethod
    def from_db_path(
        cls,
        db_path: Path | str,
        media_dir: Path | str | None = None,
        *,
        user_id: UUID = LOCAL_USER_ID,
    ) -> MemoryEngine:
        from constitution_memorizer.progress.db import open_progress_db

        path = Path(db_path).expanduser().resolve()
        media = (
            Path(media_dir).expanduser().resolve()
            if media_dir
            else (path.parent / "memory_media")
        )
        return cls(open_progress_db(path), media, user_id=user_id)
