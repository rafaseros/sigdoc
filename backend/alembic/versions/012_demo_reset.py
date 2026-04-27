"""ONE-SHOT DEMO RESET — DESTRUCTIVE, IRREVERSIBLE — DO NOT RUN ON REAL DATA

Revision ID: 012
Revises: 011
Create Date: 2026-04-27

!!! WARNING — READ BEFORE APPLYING !!!

This migration is intended EXCLUSIVELY for the demo VPS at
sigdoc.devrafaseros.com. It:

  1. Wipes ALL data from every user-data table (FK-safe order).
  2. Re-seeds a single demo tenant + admin user with hardcoded credentials.

It is IRREVERSIBLE — downgrade() is a no-op. Once applied, the previous
data cannot be recovered (unless you have a DB snapshot).

SAFETY GUARD: The migration refuses to run if there are more than 10 users
in the database. This prevents accidental execution against a populated
production database. To override, raise the threshold in this file first.

After running once on the demo VPS, future `alembic upgrade head` calls
see this revision in alembic_version and skip it — it will NOT re-wipe.

Tables NOT touched (config/system data):
  - subscription_tiers  (seeded by migration 005, must survive)
  - rate_limits / subscription_tiers rate limit columns (seeded by 006)
  - alembic_version     (Alembic internal — never touch)
"""

import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "012"
down_revision: Union[str, None] = "011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# ---------------------------------------------------------------------------
# Demo seed values — hardcoded intentionally for the CAINCO demo VPS
# ---------------------------------------------------------------------------
ADMIN_EMAIL = "devrafaseros@gmail.com"
ADMIN_PASSWORD = "admin123!"
ADMIN_FULL_NAME = "Jose Rafael Gallegos Rojas"
TENANT_NAME = "SigDoc Demo"
TENANT_SLUG = "sigdoc-demo"

# Deterministic UUID for the Free tier — must match migration 005
FREE_TIER_ID = uuid.uuid5(uuid.NAMESPACE_DNS, "sigdoc.tier.free")

# Safety threshold — migration aborts if more than this many users exist
SAFETY_THRESHOLD = 10


def upgrade() -> None:
    try:
        from passlib.context import CryptContext
    except ImportError as exc:
        raise RuntimeError(
            "passlib is required for migration 012 but could not be imported. "
            "Install it with: pip install passlib[bcrypt]"
        ) from exc

    conn = op.get_bind()

    # ------------------------------------------------------------------
    # Safety guard — refuse to run on a populated database
    # ------------------------------------------------------------------
    user_count = conn.execute(sa.text("SELECT COUNT(*) FROM users")).scalar()
    if user_count > SAFETY_THRESHOLD:
        raise RuntimeError(
            f"Migration 012 (demo reset) aborted: {user_count} users found, "
            f"exceeding the safety threshold of {SAFETY_THRESHOLD}. This migration "
            f"is intended only for the demo VPS. If you need to wipe a populated DB "
            f"intentionally, raise the threshold in this migration first."
        )

    # ------------------------------------------------------------------
    # Wipe all user-data tables — children first (FK-safe order)
    # ------------------------------------------------------------------
    conn.execute(sa.text("DELETE FROM audit_logs"))
    conn.execute(sa.text("DELETE FROM usage_events"))
    conn.execute(sa.text("DELETE FROM template_shares"))
    conn.execute(sa.text("DELETE FROM documents"))
    conn.execute(sa.text("DELETE FROM template_versions"))
    conn.execute(sa.text("DELETE FROM templates"))
    conn.execute(sa.text("DELETE FROM users"))
    conn.execute(sa.text("DELETE FROM tenants"))

    # ------------------------------------------------------------------
    # Re-seed: one tenant + one admin user
    # ------------------------------------------------------------------
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    hashed_password = pwd_context.hash(ADMIN_PASSWORD)

    tenant_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())

    # tenants has a NOT NULL tier_id (migration 005) — use Free tier
    conn.execute(
        sa.text(
            "INSERT INTO tenants (id, name, slug, tier_id, is_active, created_at, updated_at) "
            "VALUES (:id, :name, :slug, CAST(:tier_id AS uuid), :is_active, NOW(), NOW())"
        ),
        {
            "id": tenant_id,
            "name": TENANT_NAME,
            "slug": TENANT_SLUG,
            "tier_id": str(FREE_TIER_ID),
            "is_active": True,
        },
    )

    # users schema as of migration 009 (email_verified + token columns added)
    # role column default is 'document_generator' (migration 011) but we seed admin explicitly
    conn.execute(
        sa.text(
            "INSERT INTO users "
            "(id, tenant_id, email, hashed_password, full_name, role, "
            " is_active, email_verified, created_at, updated_at) "
            "VALUES "
            "(:id, :tenant_id, :email, :hashed_password, :full_name, :role, "
            " :is_active, :email_verified, NOW(), NOW())"
        ),
        {
            "id": user_id,
            "tenant_id": tenant_id,
            "email": ADMIN_EMAIL,
            "hashed_password": hashed_password,
            "full_name": ADMIN_FULL_NAME,
            "role": "admin",
            "is_active": True,
            "email_verified": True,
        },
    )


def downgrade() -> None:
    # Downgrade is intentionally a no-op.
    # A data wipe cannot be reversed — there is no "un-delete" for the wiped
    # rows and no way to restore the hashed passwords of the previous users.
    # If you need to recover, restore from a DB snapshot taken before running
    # this migration.
    pass
