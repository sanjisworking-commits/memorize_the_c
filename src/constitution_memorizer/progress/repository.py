"""CRUD for learning_unit_progress and split_preference."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Literal

SplitMode = Literal["whole", "letters"]
ProgressStatus = Literal["new", "review", "mastered"]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _date_iso(value: date | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


@dataclass(frozen=True)
class ProgressRecord:
    """One row from learning_unit_progress."""

    learning_unit_id: str
    status: ProgressStatus
    times_completed: int
    last_completed: date | None
    next_revision: date | None
    interval_days: int
    ease_factor: float
    created_at: str
    updated_at: str


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    return date.fromisoformat(value[:10])


def _row_to_progress(row: sqlite3.Row) -> ProgressRecord:
    return ProgressRecord(
        learning_unit_id=row["learning_unit_id"],
        status=row["status"],  # type: ignore[arg-type]
        times_completed=int(row["times_completed"]),
        last_completed=_parse_date(row["last_completed"]),
        next_revision=_parse_date(row["next_revision"]),
        interval_days=int(row["interval_days"]),
        ease_factor=float(row["ease_factor"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


class ProgressRepository:
    """SQLite-backed progress and split-preference store."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    @property
    def conn(self) -> sqlite3.Connection:
        return self._conn

    def get_progress(self, unit_id: str) -> ProgressRecord | None:
        row = self._conn.execute(
            "SELECT * FROM learning_unit_progress WHERE learning_unit_id = ?",
            (unit_id,),
        ).fetchone()
        return _row_to_progress(row) if row else None

    def ensure_progress(self, unit_id: str) -> ProgressRecord:
        existing = self.get_progress(unit_id)
        if existing is not None:
            return existing
        now = _utc_now_iso()
        self._conn.execute(
            """
            INSERT INTO learning_unit_progress (
                learning_unit_id, status, times_completed, last_completed,
                next_revision, interval_days, ease_factor, created_at, updated_at
            ) VALUES (?, 'new', 0, NULL, NULL, 0, 2.5, ?, ?)
            """,
            (unit_id, now, now),
        )
        self._conn.commit()
        record = self.get_progress(unit_id)
        assert record is not None
        return record

    def upsert_progress(
        self,
        *,
        unit_id: str,
        status: ProgressStatus,
        times_completed: int,
        last_completed: date | None,
        next_revision: date | None,
        interval_days: int,
        ease_factor: float = 2.5,
    ) -> ProgressRecord:
        now = _utc_now_iso()
        existing = self.get_progress(unit_id)
        if existing is None:
            self._conn.execute(
                """
                INSERT INTO learning_unit_progress (
                    learning_unit_id, status, times_completed, last_completed,
                    next_revision, interval_days, ease_factor, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    unit_id,
                    status,
                    times_completed,
                    _date_iso(last_completed),
                    _date_iso(next_revision),
                    interval_days,
                    ease_factor,
                    now,
                    now,
                ),
            )
        else:
            self._conn.execute(
                """
                UPDATE learning_unit_progress
                SET status = ?, times_completed = ?, last_completed = ?,
                    next_revision = ?, interval_days = ?, ease_factor = ?,
                    updated_at = ?
                WHERE learning_unit_id = ?
                """,
                (
                    status,
                    times_completed,
                    _date_iso(last_completed),
                    _date_iso(next_revision),
                    interval_days,
                    ease_factor,
                    now,
                    unit_id,
                ),
            )
        self._conn.commit()
        record = self.get_progress(unit_id)
        assert record is not None
        return record

    def list_due(
        self,
        as_of: date,
        *,
        include_new: bool = False,
    ) -> list[ProgressRecord]:
        """Return review rows due on/before as_of; optionally unscheded new rows."""
        rows = self._conn.execute(
            """
            SELECT * FROM learning_unit_progress
            WHERE status = 'review'
              AND next_revision IS NOT NULL
              AND next_revision <= ?
            ORDER BY next_revision ASC, learning_unit_id ASC
            """,
            (_date_iso(as_of),),
        ).fetchall()
        due = [_row_to_progress(r) for r in rows]
        if include_new:
            new_rows = self._conn.execute(
                """
                SELECT * FROM learning_unit_progress
                WHERE status = 'new'
                ORDER BY learning_unit_id ASC
                """
            ).fetchall()
            due.extend(_row_to_progress(r) for r in new_rows)
        return due

    def count_by_status(self) -> dict[str, int]:
        rows = self._conn.execute(
            """
            SELECT status, COUNT(*) AS n
            FROM learning_unit_progress
            GROUP BY status
            """
        ).fetchall()
        return {str(r["status"]): int(r["n"]) for r in rows}

    def get_split_preference(self, parent_clause_id: str) -> SplitMode | None:
        row = self._conn.execute(
            "SELECT mode FROM split_preference WHERE parent_clause_id = ?",
            (parent_clause_id,),
        ).fetchone()
        if row is None:
            return None
        return row["mode"]  # type: ignore[return-value]

    def set_split_preference(
        self,
        parent_clause_id: str,
        mode: SplitMode,
    ) -> None:
        if mode not in ("whole", "letters"):
            raise ValueError(f"Invalid split preference mode: {mode}")
        now = _utc_now_iso()
        self._conn.execute(
            """
            INSERT INTO split_preference (parent_clause_id, mode, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(parent_clause_id) DO UPDATE SET
                mode = excluded.mode,
                updated_at = excluded.updated_at
            """,
            (parent_clause_id, mode, now),
        )
        self._conn.commit()

    def delete_split_preference(self, parent_clause_id: str) -> None:
        self._conn.execute(
            "DELETE FROM split_preference WHERE parent_clause_id = ?",
            (parent_clause_id,),
        )
        self._conn.commit()

    def list_split_preferences(self) -> dict[str, SplitMode]:
        rows = self._conn.execute(
            "SELECT parent_clause_id, mode FROM split_preference"
        ).fetchall()
        return {str(r["parent_clause_id"]): r["mode"] for r in rows}  # type: ignore[misc]
