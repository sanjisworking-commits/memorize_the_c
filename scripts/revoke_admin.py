"""Revoke the admin role from a user (CLI-only until admin accounts have MFA).

Deletes the user_roles row and writes the audit log in the same transaction.
Takes effect on the target's next request — the console re-checks the role
store every time. Does not touch grants, progress or billing state.

    .venv/bin/python scripts/revoke_admin.py --user-id <uuid>
    .venv/bin/python scripts/revoke_admin.py --email name@recall.app
    .venv/bin/python scripts/revoke_admin.py --sqlite data/progress/progress.db --user-id <uuid>
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _audit_states(user_id: str) -> tuple[str, str]:
    return (
        json.dumps({"role": "admin", "user_id": user_id}),
        json.dumps({"role": None}),
    )


def _revoke_postgres(database_url: str, user_id: str | None, email: str | None) -> int:
    import psycopg

    url = database_url.replace("postgresql+psycopg://", "postgresql://")
    with psycopg.connect(url) as conn:
        with conn.cursor() as cur:
            if user_id is None:
                assert email is not None
                cur.execute(
                    "SELECT user_id FROM user_profile WHERE LOWER(email) = LOWER(%s)",
                    (email,),
                )
                row = cur.fetchone()
                if row is None:
                    print(f"No user_profile row with email {email!r}.")
                    return 1
                user_id = str(row[0])
            cur.execute(
                "DELETE FROM user_roles WHERE user_id = %s AND role = 'admin'",
                (user_id,),
            )
            if cur.rowcount == 0:
                print(f"{user_id} is not an administrator; nothing to do.")
                conn.rollback()
                return 0
            before, after = _audit_states(user_id)
            cur.execute(
                """
                INSERT INTO admin_audit_log (
                    admin_user_id, action, target_user_id, target_type,
                    target_id, before_state, after_state, reason, created_at
                ) VALUES (%s, 'revoke_admin_role', %s, 'user_role', %s, %s, %s, %s, NOW())
                """,
                (
                    user_id,
                    user_id,
                    user_id,
                    before,
                    after,
                    "CLI revoke_admin.py",
                ),
            )
        conn.commit()
    print(f"Revoked admin from {user_id} (audit row written).")
    return 0


def _revoke_sqlite(db_path: Path, user_id: str | None, email: str | None) -> int:
    from constitution_memorizer.progress.db import open_progress_db

    conn = open_progress_db(db_path)
    try:
        if user_id is None:
            assert email is not None
            row = conn.execute(
                "SELECT user_id FROM user_profile WHERE LOWER(email) = LOWER(?)",
                (email,),
            ).fetchone()
            if row is None:
                print(f"No user_profile row with email {email!r}.")
                return 1
            user_id = str(row["user_id"])
        cur = conn.execute(
            "DELETE FROM user_roles WHERE user_id = ? AND role = 'admin'",
            (user_id,),
        )
        if cur.rowcount == 0:
            print(f"{user_id} is not an administrator; nothing to do.")
            return 0
        before, after = _audit_states(user_id)
        conn.execute(
            """
            INSERT INTO admin_audit_log (
                id, admin_user_id, action, target_user_id, target_type,
                target_id, before_state, after_state, reason, created_at
            ) VALUES (?, ?, 'revoke_admin_role', ?, 'user_role', ?, ?, ?, ?, ?)
            """,
            (
                str(uuid.uuid4()),
                user_id,
                user_id,
                user_id,
                before,
                after,
                "CLI revoke_admin.py",
                _now_iso(),
            ),
        )
        conn.commit()
    finally:
        conn.close()
    print(f"Revoked admin from {user_id} (audit row written).")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    who = parser.add_mutually_exclusive_group(required=True)
    who.add_argument("--user-id", help="Supabase user UUID")
    who.add_argument("--email", help="Email from the identity directory")
    parser.add_argument(
        "--sqlite",
        metavar="DB_PATH",
        help="Use a local SQLite progress DB instead of DATABASE_URL",
    )
    args = parser.parse_args()

    if args.user_id is not None:
        try:
            uuid.UUID(args.user_id)
        except ValueError:
            print(f"Not a UUID: {args.user_id!r}")
            return 1

    if args.sqlite:
        return _revoke_sqlite(Path(args.sqlite), args.user_id, args.email)

    from constitution_memorizer.multiuser.settings import (
        get_multiuser_settings,
        load_env_file,
    )

    load_env_file()
    database_url = (get_multiuser_settings().database_url or "").strip()
    if not database_url.startswith("postgresql"):
        print(
            "DATABASE_URL is not a PostgreSQL URL. For local SQLite use "
            "--sqlite data/progress/progress.db"
        )
        return 1
    return _revoke_postgres(database_url, args.user_id, args.email)


if __name__ == "__main__":
    raise SystemExit(main())
