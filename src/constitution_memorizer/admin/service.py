"""Admin console service: inbox status transitions + audit composition.

Stored status values stay exactly what the DB CHECK constraints allow
(reports: new/reviewing/fixed/rejected · contact: new/reviewing/resolved);
the UI renames them New / Reviewing / Resolved / Dismissed. Transitions are
forward moves plus Reopen (any terminal → new); anything else is a
ValueError, which the routes surface as a 400.
"""

from __future__ import annotations

from typing import Any

from constitution_memorizer.admin.audit import AuditEntry

REPORT_TRANSITIONS: dict[str, set[str]] = {
    "new": {"reviewing", "fixed", "rejected"},
    "reviewing": {"fixed", "rejected"},
    "fixed": {"new"},
    "rejected": {"new"},
}

CONTACT_TRANSITIONS: dict[str, set[str]] = {
    "new": {"reviewing", "resolved"},
    "reviewing": {"resolved"},
    "resolved": {"new"},
}

STATUS_LABELS = {
    "new": "New",
    "reviewing": "Reviewing",
    "fixed": "Resolved",
    "resolved": "Resolved",
    "rejected": "Dismissed",
}

STATUS_COLORS = {
    "new": "amber",
    "reviewing": "ink",
    "fixed": "teal",
    "resolved": "teal",
    "rejected": "muted",
}


def moves_for(status: str, *, is_reports: bool) -> list[dict[str, str]]:
    """Forward buttons for one row: at most two moves plus Reopen."""
    moves: list[dict[str, str]] = []
    if status == "new":
        moves.append({"label": "Reviewing", "target": "reviewing", "color": "ink"})
    if status in {"new", "reviewing"}:
        moves.append(
            {
                "label": "Resolve",
                "target": "fixed" if is_reports else "resolved",
                "color": "teal",
            }
        )
        if is_reports:
            moves.append({"label": "Dismiss", "target": "rejected", "color": "red"})
    if status in {"fixed", "resolved", "rejected"}:
        moves.append({"label": "Reopen", "target": "new", "color": "muted"})
    return moves


class AdminService:
    """Validated inbox transitions; mutation + audit in one transaction."""

    def __init__(self, issue_report_repo: Any, contact_message_repo: Any) -> None:
        self._reports = issue_report_repo
        self._contacts = contact_message_repo

    def update_report_status(
        self, *, admin_user_id: str, report_id: str, status: str
    ) -> tuple[str, str]:
        if self._reports is None:
            raise LookupError("issue report repository unavailable")
        current = self._reports.get_report(report_id)
        if current is None:
            raise KeyError(report_id)
        allowed = REPORT_TRANSITIONS.get(current.status, set())
        if status not in allowed:
            raise ValueError(
                f"Invalid transition {current.status} → {status} for report"
            )
        entry = AuditEntry(
            admin_user_id=admin_user_id,
            action="report_status_change",
            target_type="issue_report",
            target_id=report_id,
            before_state={"status": current.status},
            after_state={"status": status},
        )
        result = self._reports.update_status(report_id, status, audit=entry)
        if result is None:
            raise KeyError(report_id)
        return result

    def update_contact_status(
        self, *, admin_user_id: str, message_id: str, status: str
    ) -> tuple[str, str]:
        if self._contacts is None:
            raise LookupError("contact message repository unavailable")
        current = self._contacts.get_message(message_id)
        if current is None:
            raise KeyError(message_id)
        allowed = CONTACT_TRANSITIONS.get(current.status, set())
        if status not in allowed:
            raise ValueError(
                f"Invalid transition {current.status} → {status} for contact"
            )
        entry = AuditEntry(
            admin_user_id=admin_user_id,
            action="contact_status_change",
            target_type="contact_message",
            target_id=message_id,
            before_state={"status": current.status},
            after_state={"status": status},
        )
        result = self._contacts.update_status(message_id, status, audit=entry)
        if result is None:
            raise KeyError(message_id)
        return result
