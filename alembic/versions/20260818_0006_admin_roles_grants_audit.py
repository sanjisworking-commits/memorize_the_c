"""Admin foundation: roles, manual access grants, audit log, identity columns.

Revision ID: 20260818_0006
Revises: 20260817_0005
Create Date: 2026-08-18
"""

from __future__ import annotations

from alembic import op

revision = "20260818_0006"
down_revision = "20260817_0005"
branch_labels = None
depends_on = None

SCHEMA = """
CREATE TABLE IF NOT EXISTS user_roles (
    user_id UUID NOT NULL,
    role TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by UUID NULL,
    PRIMARY KEY (user_id, role),
    CONSTRAINT user_roles_role_check CHECK (role IN ('admin'))
);

-- Manual access grants only (admin/promotional). Paid access gets its own
-- billing tables later; both feed one has_active_recall_access() check.
CREATE TABLE IF NOT EXISTS access_grants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    source TEXT NOT NULL DEFAULT 'admin_grant',
    starts_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ends_at TIMESTAMPTZ NULL,
    reason TEXT NULL,
    granted_by UUID NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    revoked_at TIMESTAMPTZ NULL,
    CONSTRAINT access_grants_source_check CHECK (
        source IN ('admin_grant', 'promotion')
    )
);

CREATE INDEX IF NOT EXISTS idx_access_grants_user ON access_grants(user_id);
CREATE INDEX IF NOT EXISTS idx_access_grants_active
    ON access_grants(user_id, ends_at) WHERE revoked_at IS NULL;

CREATE TABLE IF NOT EXISTS admin_audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    admin_user_id UUID NOT NULL,
    action TEXT NOT NULL,
    target_user_id UUID NULL,
    target_type TEXT NULL,
    target_id TEXT NULL,
    before_state JSONB NULL,
    after_state JSONB NULL,
    reason TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_admin
    ON admin_audit_log(admin_user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_audit_target
    ON admin_audit_log(target_user_id, created_at);

ALTER TABLE user_roles ENABLE ROW LEVEL SECURITY;
ALTER TABLE access_grants ENABLE ROW LEVEL SECURITY;
ALTER TABLE admin_audit_log ENABLE ROW LEVEL SECURITY;

-- Durable identity directory: email/phone refresh on every sign-in so the
-- admin console can find users who have not signed in recently.
ALTER TABLE user_profile ADD COLUMN IF NOT EXISTS email TEXT NULL;
ALTER TABLE user_profile ADD COLUMN IF NOT EXISTS phone TEXT NULL;
ALTER TABLE user_profile ADD COLUMN IF NOT EXISTS last_sign_in_at TIMESTAMPTZ NULL;

CREATE INDEX IF NOT EXISTS idx_user_profile_email
    ON user_profile (LOWER(email));
"""

# One-time backfill from the newest session row per user; sessions are the
# only place email/phone lived before this migration.
BACKFILL = """
INSERT INTO user_profile (user_id, display_name, avatar_url, created_at, updated_at,
                          email, phone, last_sign_in_at)
SELECT s.user_id, s.display_name, s.avatar_url, s.created_at, s.created_at,
       s.email, s.phone, s.created_at
FROM (
    SELECT DISTINCT ON (user_id)
        user_id, display_name, avatar_url, email, phone, created_at
    FROM app_session
    ORDER BY user_id, created_at DESC
) s
ON CONFLICT (user_id) DO UPDATE SET
    email = COALESCE(user_profile.email, EXCLUDED.email),
    phone = COALESCE(user_profile.phone, EXCLUDED.phone),
    last_sign_in_at = COALESCE(user_profile.last_sign_in_at, EXCLUDED.last_sign_in_at);
"""


def upgrade() -> None:
    op.execute(SCHEMA)
    op.execute(BACKFILL)


def downgrade() -> None:
    op.execute(
        """
        DROP INDEX IF EXISTS idx_user_profile_email;
        ALTER TABLE user_profile DROP COLUMN IF EXISTS last_sign_in_at;
        ALTER TABLE user_profile DROP COLUMN IF EXISTS phone;
        ALTER TABLE user_profile DROP COLUMN IF EXISTS email;
        DROP INDEX IF EXISTS idx_audit_target;
        DROP INDEX IF EXISTS idx_audit_admin;
        DROP TABLE IF EXISTS admin_audit_log;
        DROP INDEX IF EXISTS idx_access_grants_active;
        DROP INDEX IF EXISTS idx_access_grants_user;
        DROP TABLE IF EXISTS access_grants;
        DROP TABLE IF EXISTS user_roles;
        """
    )
