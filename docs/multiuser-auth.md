# Multi-user authentication (hosted)

This branch adds Supabase Auth (Google + phone OTP), server-side sessions, and
PostgreSQL-backed per-user progress. The Constitution corpus remains shared.

Single-user local mode (`scripts/mac/start-ui.command`, SQLite without
`MULTIUSER_ENABLED`) remains available on `main` and still works on this branch
when `MULTIUSER_ENABLED` is unset/false.

## Local setup

1. Create a PostgreSQL database and set `DATABASE_URL`.
2. Copy `.env.example` → `.env` and fill secrets.
3. Apply migrations:

```bash
export DATABASE_URL=postgresql://user:password@localhost:5432/recall_the_c_multiuser
alembic upgrade head
# or:
python -m constitution_memorizer.multiuser.migrate
```

4. Launch:

```bash
# macOS
open scripts/mac/start-multiuser.command

# or:
export MULTIUSER_ENABLED=true PORT=8010
python -m constitution_memorizer.cli serve --host 127.0.0.1 --port 8010
```

Hosted:

```bash
python -m constitution_memorizer.cli serve --host 0.0.0.0 --port "$PORT"
```

## Supabase dashboard

1. Create a Supabase project.
2. Authentication → Providers → enable **Google**.
3. Authentication → Providers → enable **Phone**.
4. Authentication → URL configuration:
   - Site URL: `APP_BASE_URL`
   - Redirect URLs: `{APP_BASE_URL}/auth/callback`
5. Copy Project URL → `SUPABASE_URL`
6. Copy `anon` public key → `SUPABASE_ANON_KEY`
7. Never put the **service role** key in the web app or browser.

## Google provider

1. Google Cloud Console → OAuth client (Web).
2. Authorized redirect URI must be the Supabase callback
   (`https://<project>.supabase.co/auth/v1/callback`).
3. Paste Client ID/secret into Supabase Google provider settings.

## Phone / SMS provider

1. In Supabase Phone provider, configure an SMS gateway (Twilio, MessageBird, etc.).
2. Use E.164 numbers only (`+919876543210`). The app does not guess country codes.
3. Application-level OTP rate limits apply in addition to provider limits.

## Feature flags

| Variable | Effect |
|----------|--------|
| `AUTH_GOOGLE_ENABLED=false` | Hide Google button / reject Google start |
| `AUTH_PHONE_ENABLED=false` | Hide phone forms / reject OTP routes |
| Both false in staging/production | Startup fails |

## Account identity

Google and phone logins may create **different** Supabase user UUIDs.
This phase does **not** auto-link accounts. Account linking is a future feature.

## Tests

```bash
pytest -m "not integration" -q
pytest tests/test_multiuser_auth.py tests/test_multiuser_isolation.py -q
```

Tests use `FakeAuthProvider` and never contact Google or send SMS.

## Known limitations

- No email/password auth.
- No automatic Google↔phone account linking.
- Hosted multi-user reminder fan-out is not implemented (CLI reminders remain single-tenant).
- Local SQLite progress DBs are not auto-imported into Postgres.
