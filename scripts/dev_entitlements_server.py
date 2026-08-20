"""Dev-only server for hands-on testing of the entitlement + pricing flags.

Runs the app in MULTIUSER mode with the FakeAuthProvider (no Supabase needed)
and both feature flags ON, against a throwaway SQLite progress DB so your real
data/progress/progress.db is untouched.

    .venv/bin/python scripts/dev_entitlements_server.py            # port 8898
    .venv/bin/python scripts/dev_entitlements_server.py --port 9000

Sign in with the fake Google account: on /login choose Google — the fake
provider auto-approves and lands you on /welcome → /dashboard.

Scenario helpers (run while the server is up, same DB file):

    # Occupy all 3 Free slots so the next Article shows the cap gate + locks
    .venv/bin/python scripts/dev_entitlements_server.py --claim 14 19 21

    # Reset the throwaway DB to start fresh
    .venv/bin/python scripts/dev_entitlements_server.py --reset
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

DEV_DB = ROOT / "data" / "progress" / "dev_entitlements.db"
DEV_USER = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
DEV_EMAIL = "dev@example.com"


def _settings(port: int = 8898):
    import os

    from constitution_memorizer.multiuser.settings import MultiUserSettings

    # Razorpay + Google Calendar keys come from the developer's own .env
    # (never hardcoded here) so both flows can be exercised end-to-end.
    env_values: dict[str, str] = {}
    env_path = ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, _, value = line.partition("=")
                env_values[key.strip()] = value.strip()

    def _env(key: str) -> str:
        return os.environ.get(key, env_values.get(key, ""))

    razorpay_id = _env("RAZORPAY_KEY_ID")
    razorpay_secret = _env("RAZORPAY_KEY_SECRET")

    return MultiUserSettings(
        _env_file=None,
        APP_ENV="test",
        APP_BASE_URL=f"http://localhost:{port}",
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
        RAZORPAY_KEY_ID=razorpay_id,
        RAZORPAY_KEY_SECRET=razorpay_secret,
        GCAL_CLIENT_ID=_env("GCAL_CLIENT_ID"),
        GCAL_CLIENT_SECRET=_env("GCAL_CLIENT_SECRET"),
        GCAL_TOKEN_KEY=_env("GCAL_TOKEN_KEY"),
        DEEPGRAM_API_KEY=_env("DEEPGRAM_API_KEY"),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8898)
    parser.add_argument(
        "--claim",
        nargs="*",
        metavar="ARTICLE",
        help="Claim these Article numbers for the dev user, then exit.",
    )
    parser.add_argument(
        "--reset", action="store_true", help="Delete the throwaway dev DB and exit."
    )
    args = parser.parse_args()

    if args.reset:
        if DEV_DB.exists():
            DEV_DB.unlink()
            print(f"Removed {DEV_DB}")
        else:
            print("Nothing to reset.")
        return 0

    if args.claim is not None:
        from constitution_memorizer.progress.db import open_progress_db
        from constitution_memorizer.progress.repository import ProgressRepository

        repo = ProgressRepository(open_progress_db(DEV_DB))
        for article in args.claim:
            repo.claim_article(DEV_USER, article)
        print(f"Claimed for dev user: {sorted(repo.claimed_articles(DEV_USER))}")
        return 0

    import uvicorn

    from constitution_memorizer.auth.fake_provider import FakeAuthProvider
    from constitution_memorizer.auth.sessions import InMemorySessionStore
    from constitution_memorizer.web.app import create_app

    provider = FakeAuthProvider()
    provider.seed_google_user(
        user_id=DEV_USER, email=DEV_EMAIL, display_name="Dev Learner"
    )
    app = create_app(
        db_path=DEV_DB,
        multiuser=True,
        multiuser_settings=_settings(args.port),
        auth_provider=provider,
        session_store=InMemorySessionStore(),
    )
    print("Entitlement/pricing dev server (fake auth, flags ON)")
    print(f"  http://127.0.0.1:{args.port}/          guest view")
    print(f"  http://127.0.0.1:{args.port}/login     sign in via Google (auto-approves)")
    print(f"  db={DEV_DB}  (throwaway — your real progress.db is untouched)")
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
