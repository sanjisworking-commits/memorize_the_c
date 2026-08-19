# Google Calendar integration — setup & deployment

Recall the C mirrors each connected user's revision schedule into a dedicated
**"Recall the C — Revision Schedule"** Google calendar: one event per day with
that day's revisions, updated automatically on every learn/complete/defer/
reset. Recall's database is authoritative — Google is only a projection. If
Google is down, revoked, or the calendar is deleted, Recall keeps working and
no progress is ever affected.

## How it works (implementation map)

- `calendar_sync/projection.py` — projects each unit's FULL remaining
  revision ladder (pending rung plus every later rung assuming on-time
  completion, via the same `remaining_review_schedule` helper as the in-app
  month calendar) into per-day workload. 120-day horizon (the entire ladder, Day 60 included, from the first sync); the pending rung
  rolls into today when due/overdue; past hypothetical rungs are never
  re-materialized; split preferences and Part Overviews filtered exactly
  like the dashboard.
- `calendar_sync/sync.py` — idempotent reconciliation: create missing events,
  patch changed days (full payload hash: items + time + duration + timezone +
  link), delete zero-work days. Runs async after state changes; a durable
  `sync_pending` flag survives crashes and keeps failed syncs retryable.
- `calendar_sync/google_client.py` — five Calendar-v3 REST calls over httpx
  under the **`calendar.app.created`** scope (the narrowest Calendar scope:
  the app can only manage calendars it created — it can never see or touch
  personal calendars).
- Refresh tokens are sealed with Fernet (`GCAL_TOKEN_KEY`) before storage.
- Disconnect tombstones the connection: credentials deleted, the calendar id
  kept so reconnecting reuses the same calendar (`Calendars.get`, create only
  on 404) — never a duplicate. The Google calendar itself is never deleted.

## 1 · Google Cloud setup

1. Go to https://console.cloud.google.com → create (or pick) a project,
   e.g. `recall-the-c`.
2. **APIs & Services → Library** → search "Google Calendar API" → **Enable**.
3. **APIs & Services → OAuth consent screen**:
   - User type: **External** → Create.
   - Fill app name ("Recall the C"), support email, developer email. Save.
   - **Scopes** → Add or remove scopes → paste
     `https://www.googleapis.com/auth/calendar.app.created` → Update. Save.
     Do not add `calendar` or `calendar.events`.
   - **Test users** → add your own Google account(s). Save.
   Production homepage, Privacy, and Terms URLs are listed in
   `docs/GOOGLE_OAUTH_PRODUCTION.md`.
4. **APIs & Services → Credentials → Create credentials → OAuth client ID**:
   - Application type: **Web application**.
   - Name: `Recall the C — Calendar` (a **dedicated client — do NOT reuse the
     Supabase sign-in client**; the Calendar grant must be independently
     revocable without touching Google sign-in).
   - Authorized redirect URIs — add exactly:
     - `https://<your-production-domain>/calendar/google/callback`
     - `http://localhost:8899/calendar/google/callback` (dev harness)
   - Create → copy the **Client ID** and **Client secret**.

## 2 · Testing mode vs Production — read this

While the consent screen is in **Testing** mode:

- only the listed test users can connect, and
- **refresh tokens expire after 7 days** — every connection silently needs
  re-consent weekly (the app shows the reconnect prompt when this happens).

That's fine for staging. **Before public launch you must publish the app**
(OAuth consent screen → *Publish app*). Google may require verification for
sensitive scopes; `calendar.app.created` is designed to be low-friction
precisely because it only reaches app-created calendars. After publishing,
refresh tokens are long-lived.

## 3 · Environment variables

Generate the token-sealing key once:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Set (Railway → your service → **Variables**; locally in `.env`):

```text
GCAL_CLIENT_ID=<OAuth client id>
GCAL_CLIENT_SECRET=<OAuth client secret>
GCAL_TOKEN_KEY=<Fernet key from above>
```

`APP_BASE_URL` must already be your real https origin — it builds the OAuth
redirect URI and the event deep links. All three GCAL vars present = the
"Revision calendar" section appears in Settings; any missing = the feature is
completely hidden and no route does anything.

Rotating `GCAL_TOKEN_KEY` invalidates stored tokens: users see the reconnect
prompt (progress unaffected).

## 4 · Migrate & deploy (Railway)

```bash
# one-time, against the production DATABASE_URL:
alembic upgrade head       # adds google_calendar_connections + google_calendar_events
```

Then redeploy the service (the web process itself is unchanged — sync runs
in-request-triggered async tasks; there is no worker service and no cron).

## 5 · Production verification checklist

1. Settings shows **Revision calendar → Connect Google Calendar**.
2. Connect → Google consent screen shows ONLY the "calendars created by this
   app" permission → back to Settings with "Connected — syncing…".
3. "Recall the C — Revision Schedule" appears in Google Calendar within a
   minute, with one event per upcoming revision day at your chosen time.
4. Complete revisions → today's event updates to the remaining count; when
   zero remain, today's event disappears; future dates shift, no duplicates.
5. Change revision time/duration/timezone in Settings → future events move.
   Open any synced event → its notification list shows a 10-minute popup (or
   your chosen cadence — see below).
6. Disconnect → syncing stops AND the app's Google grant is revoked; Google
   then removes the app-created calendar from your calendar list. Reconnect →
   a FRESH "Recall the C — Revision Schedule" calendar appears, fully
   repopulated (the old, delisted one cannot be re-listed under the
   calendar.app.created scope — calendarList.insert needs broader scopes).
7. Break connectivity (e.g. temporarily wrong client secret) → completing a
   revision still works; Settings shows "⚠ Sync issue · Try again".

## Notifications (reminder cadence)

A fresh app-created secondary calendar has **no default notifications**, so
every synced event carries explicit per-event popup overrides
(`reminders.useDefault=false`) — allowed under the `calendar.app.created`
scope because reminders are part of the event resource.

After the first successful connect, Settings shows a one-time popup asking
how many reminders per revision day:

| Cadence | Popups (minutes before the event) |
| --- | --- |
| Once (default) | 10 min |
| Twice | morning 08:00 + 10 min |
| Thrice | 8 h, 4 h and 10 min — evenly spaced |

Dismissing the popup keeps the **Once** default, so nobody ends up
notification-free. Offsets that would cross into the previous day are
dropped automatically for early revision times (a 07:00 revision degrades
Twice to a single 10-minute popup). The choice is stored as the
`gcal_reminder_cadence` app-setting and is changeable any time from the
"Reminders" select in Settings → Event preferences; because the offsets are
part of each event's content hash, a cadence change repatches every future
event on the next sync.

## Local development

The fake-auth dev harness passes GCAL vars through from `.env`:

```bash
.venv/bin/python scripts/dev_entitlements_server.py --port 8899
```

Use the `http://localhost:8899/calendar/google/callback` redirect URI (added
above) and a test-mode consent screen. Without the GCAL vars, local dev is
completely unaffected — the section simply doesn't render.

## Deployment assumption — one web replica

Per-user sync serialization is in-process only. Two replicas syncing the same
user could each insert the same day's event before either records the
mapping. **v1 assumes a single calendar-syncing web replica** (the current
Railway deployment). Add a DB-level claim (e.g. an outbox-style
`ON CONFLICT` insert) before scaling the web service out.

## Scope note

The Memory log is a single-user/local feature and is **out of scope for
multiuser** (production runs `MEMORY_LOG_ENABLED=false`). The calendar
projection therefore covers Constitution units only, by design — not as a
deferral.

## Future considerations (deliberately NOT implemented)

"✅ Complete" for finished days (needs authoritative
`last_completed == today` evidence, not an empty projection);
keep-vs-remove calendar choice on disconnect; a notifications-side consumer
of the same projection; ICS/Apple Calendar; per-day duration estimates.
