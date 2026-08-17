"""Append-only admin audit log: entry shape + shared insert SQL.

Every sensitive admin mutation writes one of these rows in the same
transaction as the mutation itself — if the audit insert fails, the mutation
rolls back. Any repository holding a connection to the app database can emit
a row with the SQL below; the shapes stay identical across backends.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class AuditEntry:
    """One admin action, before/after as plain dicts (JSON-serialized on write)."""

    admin_user_id: str
    action: str
    target_user_id: str | None = None
    target_type: str | None = None
    target_id: str | None = None
    before_state: dict | None = None
    after_state: dict | None = None
    reason: str | None = None


PG_AUDIT_INSERT = """
INSERT INTO admin_audit_log (
    admin_user_id, action, target_user_id, target_type, target_id,
    before_state, after_state, reason, created_at
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
"""

SQLITE_AUDIT_INSERT = """
INSERT INTO admin_audit_log (
    id, admin_user_id, action, target_user_id, target_type, target_id,
    before_state, after_state, reason, created_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""


def _dump(state: dict | None) -> str | None:
    return None if state is None else json.dumps(state, sort_keys=True)


def pg_audit_params(entry: AuditEntry, now: datetime) -> tuple:
    return (
        entry.admin_user_id,
        entry.action,
        entry.target_user_id,
        entry.target_type,
        entry.target_id,
        _dump(entry.before_state),
        _dump(entry.after_state),
        entry.reason,
        now,
    )


def sqlite_audit_params(entry: AuditEntry, row_id: str, now_iso: str) -> tuple:
    return (
        row_id,
        entry.admin_user_id,
        entry.action,
        entry.target_user_id,
        entry.target_type,
        entry.target_id,
        _dump(entry.before_state),
        _dump(entry.after_state),
        entry.reason,
        now_iso,
    )
