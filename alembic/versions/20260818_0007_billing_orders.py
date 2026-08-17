"""Razorpay billing: orders table + 'payment' access-grant source.

Revision ID: 20260818_0007
Revises: 20260818_0006
Create Date: 2026-08-18
"""

from __future__ import annotations

from alembic import op

revision = "20260818_0007"
down_revision = "20260818_0006"
branch_labels = None
depends_on = None

SCHEMA = """
CREATE TABLE IF NOT EXISTS billing_orders (
    order_id TEXT PRIMARY KEY,
    user_id UUID NOT NULL,
    plan_days INTEGER NOT NULL,
    amount_paise INTEGER NOT NULL,
    currency TEXT NOT NULL DEFAULT 'INR',
    status TEXT NOT NULL DEFAULT 'created'
        CONSTRAINT billing_orders_status_check CHECK (status IN ('created', 'paid')),
    razorpay_payment_id TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    paid_at TIMESTAMPTZ NULL
);

CREATE INDEX IF NOT EXISTS idx_billing_orders_user ON billing_orders(user_id);

-- Verified payments insert access_grants rows with source 'payment' so
-- has_active_recall_access() keeps answering from one place.
ALTER TABLE access_grants DROP CONSTRAINT IF EXISTS access_grants_source_check;
ALTER TABLE access_grants ADD CONSTRAINT access_grants_source_check
    CHECK (source IN ('admin_grant', 'promotion', 'payment'));
"""

DOWNGRADE = """
ALTER TABLE access_grants DROP CONSTRAINT IF EXISTS access_grants_source_check;
ALTER TABLE access_grants ADD CONSTRAINT access_grants_source_check
    CHECK (source IN ('admin_grant', 'promotion'));
DROP TABLE IF EXISTS billing_orders;
"""


def upgrade() -> None:
    op.execute(SCHEMA)


def downgrade() -> None:
    op.execute(DOWNGRADE)
