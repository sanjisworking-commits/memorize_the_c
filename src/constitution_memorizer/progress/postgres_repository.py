"""PostgreSQL implementations of user-scoped progress/memory repositories."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import date, datetime, timezone
from typing import Any, Iterator
from uuid import UUID

from constitution_memorizer.progress.repository import (
    DEFAULT_NEWS_ARTICLES,
    DEFAULT_NOTIFICATION_FREQUENCY,
    DEFAULT_THEME,
    LEARN_MODES_SET,
    NEWS_ARTICLES_KEY,
    NOTIFICATION_FREQUENCY_KEY,
    NOTIFICATION_LAST_SLOT_KEY,
    THEME_KEY,
    VALID_NOTIFICATION_FREQUENCIES,
    VALID_THEMES,
    NotificationFrequency,
    ProgressRecord,
    ProgressStatus,
    SplitMode,
    ThemePreference,
)
from constitution_memorizer.progress.user_ids import as_user_id


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _row_progress(row: Any) -> ProgressRecord:
    return ProgressRecord(
        learning_unit_id=row["learning_unit_id"],
        status=row["status"],
        times_completed=int(row["times_completed"]),
        last_completed=row["last_completed"],
        next_revision=row["next_revision"],
        interval_days=int(row["interval_days"]),
        ease_factor=float(row["ease_factor"]),
        created_at=row["created_at"].isoformat()
        if hasattr(row["created_at"], "isoformat")
        else str(row["created_at"]),
        updated_at=row["updated_at"].isoformat()
        if hasattr(row["updated_at"], "isoformat")
        else str(row["updated_at"]),
    )


class PostgresProgressRepository:
    """psycopg-backed progress repository. Every query includes user_id."""

    def __init__(self, pool: Any) -> None:
        from psycopg.rows import dict_row

        self._pool = pool
        self._dict_row = dict_row

    @contextmanager
    def _cursor(self) -> Iterator[tuple[Any, Any]]:
        """Borrow a pooled connection; dict rows only on this cursor."""
        with self._pool.connection() as conn:
            with conn.cursor(row_factory=self._dict_row) as cur:
                yield conn, cur

    def get_progress(self, user_id: UUID | str, unit_id: str) -> ProgressRecord | None:
        with self._cursor() as (_conn, cur):
            cur.execute(
                """
                SELECT * FROM learning_unit_progress
                WHERE user_id = %s AND learning_unit_id = %s
                """,
                (as_user_id(user_id), unit_id),
            )
            row = cur.fetchone()
        return _row_progress(row) if row else None

    def ensure_progress(self, user_id: UUID | str, unit_id: str) -> ProgressRecord:
        existing = self.get_progress(user_id, unit_id)
        if existing is not None:
            return existing
        now = _utc_now()
        with self._cursor() as (conn, cur):
            cur.execute(
                """
                INSERT INTO learning_unit_progress (
                    user_id, learning_unit_id, status, times_completed,
                    last_completed, next_revision, interval_days, ease_factor,
                    created_at, updated_at
                ) VALUES (%s, %s, 'new', 0, NULL, NULL, 0, 2.5, %s, %s)
                ON CONFLICT DO NOTHING
                """,
                (as_user_id(user_id), unit_id, now, now),
            )
            conn.commit()
        record = self.get_progress(user_id, unit_id)
        assert record is not None
        return record

    def upsert_progress(
        self,
        user_id: UUID | str,
        *,
        unit_id: str,
        status: ProgressStatus,
        times_completed: int,
        last_completed: date | None,
        next_revision: date | None,
        interval_days: int,
        ease_factor: float = 2.5,
    ) -> ProgressRecord:
        now = _utc_now()
        with self._cursor() as (conn, cur):
            cur.execute(
                """
                INSERT INTO learning_unit_progress (
                    user_id, learning_unit_id, status, times_completed,
                    last_completed, next_revision, interval_days, ease_factor,
                    created_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (user_id, learning_unit_id) DO UPDATE SET
                    status = EXCLUDED.status,
                    times_completed = EXCLUDED.times_completed,
                    last_completed = EXCLUDED.last_completed,
                    next_revision = EXCLUDED.next_revision,
                    interval_days = EXCLUDED.interval_days,
                    ease_factor = EXCLUDED.ease_factor,
                    updated_at = EXCLUDED.updated_at
                """,
                (
                    as_user_id(user_id),
                    unit_id,
                    status,
                    times_completed,
                    last_completed,
                    next_revision,
                    interval_days,
                    ease_factor,
                    now,
                    now,
                ),
            )
            conn.commit()
        record = self.get_progress(user_id, unit_id)
        assert record is not None
        return record

    def list_due(
        self,
        user_id: UUID | str,
        as_of: date,
        *,
        include_new: bool = False,
    ) -> list[ProgressRecord]:
        with self._cursor() as (_conn, cur):
            cur.execute(
                """
                SELECT * FROM learning_unit_progress
                WHERE user_id = %s
                  AND status = 'review'
                  AND next_revision IS NOT NULL
                  AND next_revision <= %s
                ORDER BY next_revision ASC, learning_unit_id ASC
                """,
                (as_user_id(user_id), as_of),
            )
            due = [_row_progress(r) for r in cur.fetchall()]
            if include_new:
                cur.execute(
                    """
                    SELECT * FROM learning_unit_progress
                    WHERE user_id = %s AND status = 'new'
                    ORDER BY learning_unit_id ASC
                    """,
                    (as_user_id(user_id),),
                )
                due.extend(_row_progress(r) for r in cur.fetchall())
        return due

    def list_all_progress(self, user_id: UUID | str) -> list[ProgressRecord]:
        with self._cursor() as (_conn, cur):
            cur.execute(
                """
                SELECT * FROM learning_unit_progress
                WHERE user_id = %s
                ORDER BY learning_unit_id ASC
                """,
                (as_user_id(user_id),),
            )
            rows = cur.fetchall()
        return [_row_progress(r) for r in rows]

    def count_by_status(self, user_id: UUID | str) -> dict[str, int]:
        with self._cursor() as (_conn, cur):
            cur.execute(
                """
                SELECT status, COUNT(*) AS n
                FROM learning_unit_progress
                WHERE user_id = %s
                GROUP BY status
                """,
                (as_user_id(user_id),),
            )
            rows = cur.fetchall()
        return {str(r["status"]): int(r["n"]) for r in rows}

    def get_split_preference(
        self, user_id: UUID | str, parent_clause_id: str
    ) -> SplitMode | None:
        with self._cursor() as (_conn, cur):
            cur.execute(
                """
                SELECT mode FROM split_preference
                WHERE user_id = %s AND parent_clause_id = %s
                """,
                (as_user_id(user_id), parent_clause_id),
            )
            row = cur.fetchone()
        return None if row is None else row["mode"]

    def set_split_preference(
        self, user_id: UUID | str, parent_clause_id: str, mode: SplitMode
    ) -> None:
        with self._cursor() as (conn, cur):
            cur.execute(
                """
                INSERT INTO split_preference (user_id, parent_clause_id, mode, updated_at)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (user_id, parent_clause_id) DO UPDATE SET
                    mode = EXCLUDED.mode,
                    updated_at = EXCLUDED.updated_at
                """,
                (as_user_id(user_id), parent_clause_id, mode, _utc_now()),
            )
            conn.commit()

    def list_split_preferences(self, user_id: UUID | str) -> dict[str, SplitMode]:
        with self._cursor() as (_conn, cur):
            cur.execute(
                "SELECT parent_clause_id, mode FROM split_preference WHERE user_id = %s",
                (as_user_id(user_id),),
            )
            rows = cur.fetchall()
        return {str(r["parent_clause_id"]): r["mode"] for r in rows}

    def delete_progress(self, user_id: UUID | str, unit_id: str) -> None:
        with self._cursor() as (conn, cur):
            cur.execute(
                """
                DELETE FROM learning_unit_progress
                WHERE user_id = %s AND learning_unit_id = %s
                """,
                (as_user_id(user_id), unit_id),
            )
            conn.commit()

    def delete_all_progress(self, user_id: UUID | str) -> None:
        uid = as_user_id(user_id)
        with self._cursor() as (conn, cur):
            cur.execute(
                "DELETE FROM learning_unit_progress WHERE user_id = %s", (uid,)
            )
            cur.execute("DELETE FROM split_preference WHERE user_id = %s", (uid,))
            conn.commit()

    def delete_split_preference(
        self, user_id: UUID | str, parent_clause_id: str
    ) -> None:
        with self._cursor() as (conn, cur):
            cur.execute(
                """
                DELETE FROM split_preference
                WHERE user_id = %s AND parent_clause_id = %s
                """,
                (as_user_id(user_id), parent_clause_id),
            )
            conn.commit()

    def get_gloss(self, user_id: UUID | str, article_number: str) -> str | None:
        with self._cursor() as (_conn, cur):
            cur.execute(
                """
                SELECT text FROM article_gloss
                WHERE user_id = %s AND article_number = %s
                """,
                (as_user_id(user_id), article_number),
            )
            row = cur.fetchone()
        return None if row is None else str(row["text"])

    def upsert_gloss(
        self, user_id: UUID | str, article_number: str, text: str
    ) -> None:
        with self._cursor() as (conn, cur):
            cur.execute(
                """
                INSERT INTO article_gloss (user_id, article_number, text, updated_at)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (user_id, article_number) DO UPDATE SET
                    text = EXCLUDED.text,
                    updated_at = EXCLUDED.updated_at
                """,
                (as_user_id(user_id), article_number, text, _utc_now()),
            )
            conn.commit()

    def delete_gloss(self, user_id: UUID | str, article_number: str) -> None:
        with self._cursor() as (conn, cur):
            cur.execute(
                """
                DELETE FROM article_gloss
                WHERE user_id = %s AND article_number = %s
                """,
                (as_user_id(user_id), article_number),
            )
            conn.commit()

    def get_setting(self, user_id: UUID | str, key: str) -> str | None:
        with self._cursor() as (_conn, cur):
            cur.execute(
                "SELECT value FROM app_settings WHERE user_id = %s AND key = %s",
                (as_user_id(user_id), key),
            )
            row = cur.fetchone()
        return None if row is None else str(row["value"])

    def set_setting(self, user_id: UUID | str, key: str, value: str) -> None:
        with self._cursor() as (conn, cur):
            cur.execute(
                """
                INSERT INTO app_settings (user_id, key, value, updated_at)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (user_id, key) DO UPDATE SET
                    value = EXCLUDED.value,
                    updated_at = EXCLUDED.updated_at
                """,
                (as_user_id(user_id), key, value, _utc_now()),
            )
            conn.commit()

    def get_theme(self, user_id: UUID | str) -> ThemePreference:
        raw = self.get_setting(user_id, THEME_KEY)
        return raw if raw in VALID_THEMES else DEFAULT_THEME  # type: ignore[return-value]

    def set_theme(self, user_id: UUID | str, theme: ThemePreference) -> None:
        self.set_setting(user_id, THEME_KEY, theme)

    def get_notification_frequency(self, user_id: UUID | str) -> NotificationFrequency:
        raw = self.get_setting(user_id, NOTIFICATION_FREQUENCY_KEY)
        return (
            raw
            if raw in VALID_NOTIFICATION_FREQUENCIES
            else DEFAULT_NOTIFICATION_FREQUENCY
        )  # type: ignore[return-value]

    def set_notification_frequency(
        self, user_id: UUID | str, frequency: NotificationFrequency
    ) -> None:
        self.set_setting(user_id, NOTIFICATION_FREQUENCY_KEY, frequency)

    def get_notification_last_slot(self, user_id: UUID | str) -> datetime | None:
        raw = self.get_setting(user_id, NOTIFICATION_LAST_SLOT_KEY)
        if not raw:
            return None
        try:
            return datetime.fromisoformat(raw)
        except ValueError:
            return None

    def set_notification_last_slot(self, user_id: UUID | str, when: datetime) -> None:
        self.set_setting(
            user_id,
            NOTIFICATION_LAST_SLOT_KEY,
            when.replace(microsecond=0).isoformat(),
        )

    def get_news_articles_raw(self, user_id: UUID | str) -> str:
        raw = self.get_setting(user_id, NEWS_ARTICLES_KEY)
        return DEFAULT_NEWS_ARTICLES if raw is None else raw

    def set_news_articles_raw(self, user_id: UUID | str, value: str) -> None:
        self.set_setting(user_id, NEWS_ARTICLES_KEY, value.strip())

    def mark_mode_seen(self, user_id: UUID | str, unit_id: str, mode: str) -> set[str]:
        with self._cursor() as (conn, cur):
            cur.execute(
                """
                INSERT INTO unit_modes_seen (user_id, learning_unit_id, mode, seen_at)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (user_id, learning_unit_id, mode) DO UPDATE SET
                    seen_at = EXCLUDED.seen_at
                """,
                (as_user_id(user_id), unit_id, mode, _utc_now()),
            )
            conn.commit()
        return self.modes_seen(user_id, unit_id)

    def modes_seen(self, user_id: UUID | str, unit_id: str) -> set[str]:
        with self._cursor() as (_conn, cur):
            cur.execute(
                """
                SELECT mode FROM unit_modes_seen
                WHERE user_id = %s AND learning_unit_id = %s
                """,
                (as_user_id(user_id), unit_id),
            )
            rows = cur.fetchall()
        return {str(r["mode"]) for r in rows}

    def clear_modes_seen(self, user_id: UUID | str, unit_id: str) -> None:
        with self._cursor() as (conn, cur):
            cur.execute(
                "DELETE FROM unit_modes_seen WHERE user_id = %s AND learning_unit_id = %s",
                (as_user_id(user_id), unit_id),
            )
            conn.commit()

    def clear_all_modes_seen(self, user_id: UUID | str) -> None:
        with self._cursor() as (conn, cur):
            cur.execute(
                "DELETE FROM unit_modes_seen WHERE user_id = %s",
                (as_user_id(user_id),),
            )
            conn.commit()

    def modes_complete(self, user_id: UUID | str, unit_id: str) -> bool:
        return self.modes_seen(user_id, unit_id) >= LEARN_MODES_SET

    def upsert_profile(
        self,
        user_id: UUID | str,
        *,
        display_name: str | None,
        avatar_url: str | None,
    ) -> None:
        now = _utc_now()
        with self._cursor() as (conn, cur):
            cur.execute(
                """
                INSERT INTO user_profile (user_id, display_name, avatar_url, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (user_id) DO UPDATE SET
                    display_name = EXCLUDED.display_name,
                    avatar_url = EXCLUDED.avatar_url,
                    updated_at = EXCLUDED.updated_at
                """,
                (as_user_id(user_id), display_name, avatar_url, now, now),
            )
            conn.commit()

    def get_profile(self, user_id: UUID | str) -> dict[str, str | None] | None:
        with self._cursor() as (_conn, cur):
            cur.execute(
                """
                SELECT user_id, display_name, avatar_url, created_at, updated_at
                FROM user_profile WHERE user_id = %s
                """,
                (as_user_id(user_id),),
            )
            row = cur.fetchone()
        if row is None:
            return None
        created = row["created_at"]
        updated = row["updated_at"]
        return {
            "user_id": str(row["user_id"]),
            "display_name": row["display_name"],
            "avatar_url": row["avatar_url"],
            "created_at": created.isoformat()
            if hasattr(created, "isoformat")
            else str(created) if created is not None else None,
            "updated_at": updated.isoformat()
            if hasattr(updated, "isoformat")
            else str(updated) if updated is not None else None,
        }

    def needs_welcome(self, user_id: UUID | str) -> bool:
        profile = self.get_profile(user_id)
        if profile is None:
            return True
        name = (profile.get("display_name") or "").strip()
        return not name
