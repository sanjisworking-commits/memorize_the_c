"""Dev-only server for hands-on testing of the Admin console (5A/5B).

Runs the app in MULTIUSER mode with the FakeAuthProvider (no Supabase
needed) and ADMIN_ENABLED + entitlement/pricing flags ON, against a
throwaway SQLite DB. The dev Google account is seeded as an administrator
on startup, so /login → Google lands you in an admin session.

    .venv/bin/python scripts/dev_admin_server.py            # port 8899
    .venv/bin/python scripts/dev_admin_server.py --port 9001

    # Seed demo members + grants so Users/Access/Audit have content
    .venv/bin/python scripts/dev_admin_server.py --seed-demo

    # Reset the throwaway DB
    .venv/bin/python scripts/dev_admin_server.py --reset

The rule this harness deliberately preserves: multiuser off ≠ admin. Plain
`constitution-memorizer serve` keeps full local access and /admin 404s.
"""

from __future__ import annotations

import argparse
import sys
import uuid as uuid_mod
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

DEV_DB = ROOT / "data" / "progress" / "dev_admin.db"
DEV_ADMIN = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
DEV_EMAIL = "admin@recall.dev"


def _settings(port: int = 8899):
    from constitution_memorizer.multiuser.settings import MultiUserSettings

    return MultiUserSettings(
        _env_file=None,
        # Must match the origin the browser uses, or the OAuth state cookie
        # is lost across the fake provider's redirect.
        APP_BASE_URL=f"http://localhost:{port}",
        APP_ENV="test",
        MULTIUSER_ENABLED="true",
        AUTH_GOOGLE_ENABLED="true",
        AUTH_PHONE_ENABLED="true",
        SESSION_SECRET="dev-only-secret",
        SUPABASE_URL="http://example.invalid",
        SUPABASE_ANON_KEY="dev-anon",
        DATABASE_URL="",
        COOKIE_SECURE="false",
        ARTICLE_ENTITLEMENTS_ENABLED="true",
        PRICING_ENABLED="true",
        ADMIN_ENABLED="true",
    )


def _iso(dt: datetime) -> str:
    return dt.replace(microsecond=0).isoformat()


def _seed_admin_role(conn) -> None:
    conn.execute(
        """
        INSERT INTO user_roles (user_id, role, created_at)
        VALUES (?, 'admin', ?) ON CONFLICT DO NOTHING
        """,
        (str(DEV_ADMIN), _iso(datetime.now(timezone.utc))),
    )
    conn.commit()


def _seed_demo(conn) -> None:
    now = datetime.now(timezone.utc)
    members = [
        ("Ananya Rao", "ananya.rao@gmail.com", "+91 98200 41772"),
        ("Vikram Iyer", "vikram.iyer@outlook.com", "+91 90040 88231"),
        ("Priya Nambiar", "priya.n@zoho.in", "+91 87600 51199"),
    ]
    ids = []
    for name, email, phone in members:
        uid = str(uuid_mod.uuid4())
        ids.append(uid)
        conn.execute(
            """
            INSERT INTO user_profile (
                user_id, display_name, avatar_url, created_at, updated_at,
                email, phone, last_sign_in_at
            ) VALUES (?, ?, NULL, ?, ?, ?, ?, ?)
            ON CONFLICT DO NOTHING
            """,
            (uid, name, _iso(now), _iso(now), email, phone, _iso(now)),
        )
    grants = [
        (ids[1], "admin_grant", now - timedelta(days=1), now + timedelta(days=44), None,
         "Support #218 — UPI mandate lapsed mid-plan"),
        (ids[2], "promotion", now + timedelta(days=14), now + timedelta(days=104), None,
         "NLU Delhi pilot cohort"),
        (ids[0], "admin_grant", now - timedelta(days=60), now - timedelta(days=30), None,
         "Beta tester, 30 days"),
    ]
    for uid, source, starts, ends, revoked, reason in grants:
        conn.execute(
            """
            INSERT INTO access_grants (
                id, user_id, source, starts_at, ends_at, reason,
                granted_by, created_at, revoked_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(uuid_mod.uuid4()),
                uid,
                source,
                _iso(starts),
                _iso(ends) if ends else None,
                reason,
                str(DEV_ADMIN),
                _iso(now),
                _iso(revoked) if revoked else None,
            ),
        )
    # A few claimed Free Articles for the first member.
    for article in ("14", "19"):
        conn.execute(
            """
            INSERT INTO user_free_articles (user_id, article_number, claimed_at)
            VALUES (?, ?, ?) ON CONFLICT DO NOTHING
            """,
            (ids[0], article, _iso(now)),
        )
    conn.commit()
    print(f"Seeded {len(members)} demo members, {len(grants)} grants.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8899)
    parser.add_argument("--seed-demo", action="store_true")
    parser.add_argument("--reset", action="store_true")
    args = parser.parse_args()

    if args.reset:
        if DEV_DB.exists():
            DEV_DB.unlink()
            print(f"Removed {DEV_DB}")
        else:
            print("Nothing to reset.")
        return 0

    from constitution_memorizer.progress.db import open_progress_db

    conn = open_progress_db(DEV_DB)
    _seed_admin_role(conn)
    if args.seed_demo:
        _seed_demo(conn)
        conn.close()
        return 0
    conn.close()

    import uvicorn

    from constitution_memorizer.auth.fake_provider import FakeAuthProvider
    from constitution_memorizer.auth.sessions import InMemorySessionStore
    from constitution_memorizer.web.app import create_app

    provider = FakeAuthProvider()
    provider.seed_google_user(
        user_id=DEV_ADMIN, email=DEV_EMAIL, display_name="Sanjana (Admin)"
    )
    app = create_app(
        db_path=DEV_DB,
        multiuser=True,
        multiuser_settings=_settings(args.port),
        auth_provider=provider,
        session_store=InMemorySessionStore(),
    )
    print("Admin console dev server (fake auth, ADMIN_ENABLED=true)")
    print(f"  http://127.0.0.1:{args.port}/login     sign in via Google → admin session")
    print(f"  http://127.0.0.1:{args.port}/admin     console")
    print(f"  db={DEV_DB}  (throwaway)")
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
