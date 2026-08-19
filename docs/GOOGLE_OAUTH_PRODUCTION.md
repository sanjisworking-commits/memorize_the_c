# Google OAuth production branding

Recall the C’s production OAuth clients (Google Sign-In and the dedicated
Google Calendar client) must use a verified domain you control. Do not add
broader Calendar scopes than the product uses.

## Public URLs

```text
Homepage:
https://recall-the-c.in/

Privacy Policy:
https://recall-the-c.in/privacy

Terms:
https://recall-the-c.in/terms

Grievance:
https://recall-the-c.in/grievance
```

In Google Cloud → Google Auth Platform → **Branding**, set the homepage,
Privacy Policy, and Terms URLs above. Authorised domains must be domains you
own and have verified.

## Calendar scope

The only Calendar scope Recall the C requests is:

```text
https://www.googleapis.com/auth/calendar.app.created
```

This permits creating a secondary calendar and managing events on calendars
created by the app. It does not grant access to the user’s unrelated personal
calendars.

Do **not** add `calendar`, `calendar.events`, or other Workspace Calendar
scopes unless product functionality genuinely requires them.

Settings shows a disclosure immediately before **Connect Google Calendar**,
with a link to `/privacy#google-calendar`.

## Operator identity (`LEGAL_*`)

Public legal pages read:

```text
LEGAL_ENTITY_NAME
LEGAL_BUSINESS_ADDRESS
LEGAL_JURISDICTION
LEGAL_SUPPORT_EMAIL
LEGAL_PRIVACY_EMAIL
LEGAL_GRIEVANCE_EMAIL
LEGAL_GRIEVANCE_OFFICER
```

Empty values render as **Not yet configured**. Production logs a warning when
any required field is missing. Local development still runs.

## Pre-submission check

Do not submit Recall the C for Google production verification until all
required LEGAL_* values are configured and none of the public legal pages
display "Not yet configured".
