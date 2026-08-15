"""CRUD for learning_unit_progress, split_preference, and app_settings (user-scoped)."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Literal
from uuid import UUID

from constitution_memorizer.progress.user_ids import as_user_id

SplitMode = Literal["whole", "letters"]
ProgressStatus = Literal["new", "review", "mastered"]
NotificationFrequency = Literal["twice", "thrice", "hourly"]

NOTIFICATION_FREQUENCY_KEY = "notification_frequency"
NOTIFICATION_LAST_SLOT_KEY = "notification_last_slot"
DEFAULT_NOTIFICATION_FREQUENCY: NotificationFrequency = "thrice"
VALID_NOTIFICATION_FREQUENCIES: frozenset[str] = frozenset(
    ("twice", "thrice", "hourly")
)

THEME_KEY = "theme"
ThemePreference = Literal["auto", "dark", "light"]
DEFAULT_THEME: ThemePreference = "auto"
VALID_THEMES: frozenset[str] = frozenset(("auto", "dark", "light"))

NEWS_ARTICLES_KEY = "news_articles"
DEFAULT_NEWS_ARTICLES = "19"

LEARN_MODES: tuple[str, ...] = ("read", "cloze", "letters", "type", "recite", "card")
LEARN_MODES_SET: frozenset[str] = frozenset(LEARN_MODES)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _date_iso(value: date | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


@dataclass(frozen=True)
class ProgressRecord:

    learning_unit_id: str
    status: ProgressStatus
    times_completed: int
    last_completed: date | None
    next_revision: date | None
    interval_days: int
    ease_factor: float
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class RequestBootstrap:
    """Bundled request-start reads (progress, prefs, theme, optional news/profile)."""

    progress: list[ProgressRecord]
    split_preferences: dict[str, SplitMode]
    theme: ThemePreference
    news_articles_raw: str | None = None
    profile: dict[str, str | None] | None = None


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
    """SQLite-backed user-scoped progress and preference store."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    @property
    def conn(self) -> sqlite3.Connection:
        return self._conn

    def get_progress(self, user_id: UUID | str, unit_id: str) -> ProgressRecord | None:
        uid = as_user_id(user_id)
        row = self._conn.execute(
            """
            SELECT * FROM learning_unit_progress
            WHERE user_id = ? AND learning_unit_id = ?
            """,
            (uid, unit_id),
        ).fetchone()
        return _row_to_progress(row) if row else None

    def ensure_progress(self, user_id: UUID | str, unit_id: str) -> ProgressRecord:
        existing = self.get_progress(user_id, unit_id)
        if existing is not None:
            return existing
        now = _utc_now_iso()
        uid = as_user_id(user_id)
        self._conn.execute(
            """
            INSERT INTO learning_unit_progress (
                user_id, learning_unit_id, status, times_completed, last_completed,
                next_revision, interval_days, ease_factor, created_at, updated_at
            ) VALUES (?, ?, 'new', 0, NULL, NULL, 0, 2.5, ?, ?)
            """,
            (uid, unit_id, now, now),
        )
        self._conn.commit()
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
        now = _utc_now_iso()
        uid = as_user_id(user_id)
        existing = self.get_progress(user_id, unit_id)
        if existing is None:
            self._conn.execute(
                """
                INSERT INTO learning_unit_progress (
                    user_id, learning_unit_id, status, times_completed, last_completed,
                    next_revision, interval_days, ease_factor, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    uid,
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
                WHERE user_id = ? AND learning_unit_id = ?
                """,
                (
                    status,
                    times_completed,
                    _date_iso(last_completed),
                    _date_iso(next_revision),
                    interval_days,
                    ease_factor,
                    now,
                    uid,
                    unit_id,
                ),
            )
        self._conn.commit()
        record = self.get_progress(user_id, unit_id)
        assert record is not None
        return record

    def delete_progress(self, user_id: UUID | str, unit_id: str) -> None:
        self._conn.execute(
            "DELETE FROM learning_unit_progress WHERE user_id = ? AND learning_unit_id = ?",
            (as_user_id(user_id), unit_id),
        )
        self._conn.commit()

    def delete_all_progress(self, user_id: UUID | str) -> None:
        uid = as_user_id(user_id)
        self._conn.execute("DELETE FROM learning_unit_progress WHERE user_id = ?", (uid,))
        self._conn.execute("DELETE FROM split_preference WHERE user_id = ?", (uid,))
        self._conn.commit()

    def list_due(
        self,
        user_id: UUID | str,
        as_of: date,
        *,
        include_new: bool = False,
    ) -> list[ProgressRecord]:
        uid = as_user_id(user_id)
        rows = self._conn.execute(
            """
            SELECT * FROM learning_unit_progress
            WHERE user_id = ?
              AND status = 'review'
              AND next_revision IS NOT NULL
              AND next_revision <= ?
            ORDER BY next_revision ASC, learning_unit_id ASC
            """,
            (uid, _date_iso(as_of)),
        ).fetchall()
        due = [_row_to_progress(r) for r in rows]
        if include_new:
            new_rows = self._conn.execute(
                """
                SELECT * FROM learning_unit_progress
                WHERE user_id = ? AND status = 'new'
                ORDER BY learning_unit_id ASC
                """,
                (uid,),
            ).fetchall()
            due.extend(_row_to_progress(r) for r in new_rows)
        return due

    def list_all_progress(self, user_id: UUID | str) -> list[ProgressRecord]:
        rows = self._conn.execute(
            """
            SELECT * FROM learning_unit_progress
            WHERE user_id = ?
            ORDER BY learning_unit_id ASC
            """,
            (as_user_id(user_id),),
        ).fetchall()
        return [_row_to_progress(r) for r in rows]

    def count_by_status(self, user_id: UUID | str) -> dict[str, int]:
        rows = self._conn.execute(
            """
            SELECT status, COUNT(*) AS n
            FROM learning_unit_progress
            WHERE user_id = ?
            GROUP BY status
            """,
            (as_user_id(user_id),),
        ).fetchall()
        return {str(r["status"]): int(r["n"]) for r in rows}

    def get_split_preference(
        self, user_id: UUID | str, parent_clause_id: str
    ) -> SplitMode | None:
        row = self._conn.execute(
            """
            SELECT mode FROM split_preference
            WHERE user_id = ? AND parent_clause_id = ?
            """,
            (as_user_id(user_id), parent_clause_id),
        ).fetchone()
        if row is None:
            return None
        return row["mode"]  # type: ignore[return-value]

    def set_split_preference(
        self,
        user_id: UUID | str,
        parent_clause_id: str,
        mode: SplitMode,
    ) -> None:
        if mode not in ("whole", "letters"):
            raise ValueError(f"Invalid split preference mode: {mode}")
        now = _utc_now_iso()
        self._conn.execute(
            """
            INSERT INTO split_preference (user_id, parent_clause_id, mode, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id, parent_clause_id) DO UPDATE SET
                mode = excluded.mode,
                updated_at = excluded.updated_at
            """,
            (as_user_id(user_id), parent_clause_id, mode, now),
        )
        self._conn.commit()

    def delete_split_preference(self, user_id: UUID | str, parent_clause_id: str) -> None:
        self._conn.execute(
            "DELETE FROM split_preference WHERE user_id = ? AND parent_clause_id = ?",
            (as_user_id(user_id), parent_clause_id),
        )
        self._conn.commit()

    def list_split_preferences(self, user_id: UUID | str) -> dict[str, SplitMode]:
        rows = self._conn.execute(
            "SELECT parent_clause_id, mode FROM split_preference WHERE user_id = ?",
            (as_user_id(user_id),),
        ).fetchall()
        return {str(r["parent_clause_id"]): r["mode"] for r in rows}  # type: ignore[misc]

    def get_gloss(self, user_id: UUID | str, article_number: str) -> str | None:
        row = self._conn.execute(
            """
            SELECT text FROM article_gloss
            WHERE user_id = ? AND article_number = ?
            """,
            (as_user_id(user_id), article_number),
        ).fetchone()
        if row is None:
            return None
        return str(row["text"])

    def upsert_gloss(self, user_id: UUID | str, article_number: str, text: str) -> None:
        now = _utc_now_iso()
        self._conn.execute(
            """
            INSERT INTO article_gloss (user_id, article_number, text, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id, article_number) DO UPDATE SET
                text = excluded.text,
                updated_at = excluded.updated_at
            """,
            (as_user_id(user_id), article_number, text, now),
        )
        self._conn.commit()

    def delete_gloss(self, user_id: UUID | str, article_number: str) -> None:
        self._conn.execute(
            "DELETE FROM article_gloss WHERE user_id = ? AND article_number = ?",
            (as_user_id(user_id), article_number),
        )
        self._conn.commit()

    def get_setting(self, user_id: UUID | str, key: str) -> str | None:
        row = self._conn.execute(
            "SELECT value FROM app_settings WHERE user_id = ? AND key = ?",
            (as_user_id(user_id), key),
        ).fetchone()
        if row is None:
            return None
        return str(row["value"])

    def set_setting(self, user_id: UUID | str, key: str, value: str) -> None:
        now = _utc_now_iso()
        self._conn.execute(
            """
            INSERT INTO app_settings (user_id, key, value, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id, key) DO UPDATE SET
                value = excluded.value,
                updated_at = excluded.updated_at
            """,
            (as_user_id(user_id), key, value, now),
        )
        self._conn.commit()

    def get_notification_frequency(self, user_id: UUID | str) -> NotificationFrequency:
        raw = self.get_setting(user_id, NOTIFICATION_FREQUENCY_KEY)
        if raw in VALID_NOTIFICATION_FREQUENCIES:
            return raw  # type: ignore[return-value]
        return DEFAULT_NOTIFICATION_FREQUENCY

    def set_notification_frequency(
        self, user_id: UUID | str, frequency: NotificationFrequency
    ) -> None:
        if frequency not in VALID_NOTIFICATION_FREQUENCIES:
            raise ValueError(f"Invalid notification frequency: {frequency}")
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

    def get_theme(self, user_id: UUID | str) -> ThemePreference:
        raw = self.get_setting(user_id, THEME_KEY)
        if raw in VALID_THEMES:
            return raw  # type: ignore[return-value]
        return DEFAULT_THEME

    def set_theme(self, user_id: UUID | str, theme: ThemePreference) -> None:
        if theme not in VALID_THEMES:
            raise ValueError(f"Invalid theme: {theme}")
        self.set_setting(user_id, THEME_KEY, theme)

    def get_news_articles_raw(self, user_id: UUID | str) -> str:
        raw = self.get_setting(user_id, NEWS_ARTICLES_KEY)
        if raw is None:
            return DEFAULT_NEWS_ARTICLES
        return raw

    def set_news_articles_raw(self, user_id: UUID | str, value: str) -> None:
        self.set_setting(user_id, NEWS_ARTICLES_KEY, value.strip())

    def mark_mode_seen(self, user_id: UUID | str, unit_id: str, mode: str) -> set[str]:
        if mode not in LEARN_MODES_SET:
            raise ValueError(f"Invalid learn mode: {mode}")
        now = _utc_now_iso()
        self._conn.execute(
            """
            INSERT INTO unit_modes_seen (user_id, learning_unit_id, mode, seen_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id, learning_unit_id, mode) DO UPDATE SET
                seen_at = excluded.seen_at
            """,
            (as_user_id(user_id), unit_id, mode, now),
        )
        self._conn.commit()
        return self.modes_seen(user_id, unit_id)

    def modes_seen(self, user_id: UUID | str, unit_id: str) -> set[str]:
        rows = self._conn.execute(
            """
            SELECT mode FROM unit_modes_seen
            WHERE user_id = ? AND learning_unit_id = ?
            """,
            (as_user_id(user_id), unit_id),
        ).fetchall()
        return {str(r["mode"]) for r in rows}

    def clear_modes_seen(self, user_id: UUID | str, unit_id: str) -> None:
        self._conn.execute(
            "DELETE FROM unit_modes_seen WHERE user_id = ? AND learning_unit_id = ?",
            (as_user_id(user_id), unit_id),
        )
        self._conn.commit()

    def clear_all_modes_seen(self, user_id: UUID | str) -> None:
        self._conn.execute(
            "DELETE FROM unit_modes_seen WHERE user_id = ?",
            (as_user_id(user_id),),
        )
        self._conn.commit()

    def modes_complete(self, user_id: UUID | str, unit_id: str) -> bool:
        return self.modes_seen(user_id, unit_id) >= LEARN_MODES_SET

    def upsert_profile(
        self,
        user_id: UUID | str,
        *,
        display_name: str | None,
        avatar_url: str | None,
    ) -> None:
        now = _utc_now_iso()
        uid = as_user_id(user_id)
        existing = self.get_profile(user_id)
        if existing is None:
            self._conn.execute(
                """
                INSERT INTO user_profile (user_id, display_name, avatar_url, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (uid, display_name, avatar_url, now, now),
            )
        else:
            self._conn.execute(
                """
                UPDATE user_profile
                SET display_name = ?, avatar_url = ?, updated_at = ?
                WHERE user_id = ?
                """,
                (display_name, avatar_url, now, uid),
            )
        self._conn.commit()

    def get_profile(self, user_id: UUID | str) -> dict[str, str | None] | None:
        row = self._conn.execute(
            """
            SELECT user_id, display_name, avatar_url, created_at, updated_at
            FROM user_profile WHERE user_id = ?
            """,
            (as_user_id(user_id),),
        ).fetchone()
        if row is None:
            return None
        return {
            "user_id": str(row["user_id"]),
            "display_name": row["display_name"],
            "avatar_url": row["avatar_url"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def needs_welcome(self, user_id: UUID | str) -> bool:
        profile = self.get_profile(user_id)
        if profile is None:
            return True
        name = (profile.get("display_name") or "").strip()
        return not name

    def load_request_bootstrap(
        self,
        user_id: UUID | str,
        *,
        include_profile: bool = False,
        include_news: bool = False,
    ) -> RequestBootstrap:
        return RequestBootstrap(
            progress=self.list_all_progress(user_id),
            split_preferences=self.list_split_preferences(user_id),
            theme=self.get_theme(user_id),
            news_articles_raw=self.get_news_articles_raw(user_id) if include_news else None,
            profile=self.get_profile(user_id) if include_profile else None,
        )


# Backward-compatible alias used by docs/plan wording.
SQLiteProgressRepository = ProgressRepository
