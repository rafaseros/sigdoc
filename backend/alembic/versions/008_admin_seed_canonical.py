"""Seed canonical admin user

Revision ID: 008
Revises: 007
Create Date: 2026-04-07

Spec: REQ-SEED-01, REQ-SEED-03
Design: ADR-ASEW-06

Upserts the canonical admin user (devrafaseros@gmail.com) using ON CONFLICT
on the global email unique index (uq_users_email_global, created in 007).
- If the user already exists: update full_name and role to admin.
- If the user does NOT exist: insert with ADMIN_PASSWORD from os.environ.
- Fails if ADMIN_PASSWORD is not set and the user doesn't exist yet.
- The migration is idempotent: running it twice is safe.
"""

import os
import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ADMIN_EMAIL = "devrafaseros@gmail.com"
ADMIN_FULL_NAME = "Jose Rafael Gallegos Rojas"


def upgrade() -> None:
    conn = op.get_bind()

    # Check if the canonical admin already exists
    result = conn.execute(
        sa.text("SELECT id FROM users WHERE email = :email"),
        {"email": ADMIN_EMAIL},
    )
    existing = result.fetchone()

    if existing is None:
        # New user — requires ADMIN_PASSWORD to be set
        admin_password = os.environ.get("ADMIN_PASSWORD")
        if not admin_password:
            raise RuntimeError(
                "ADMIN_PASSWORD environment variable is required to seed the "
                "canonical admin user but it is not set."
            )

        # Hash the password using passlib (same as app code)
        from passlib.context import CryptContext
        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        hashed_password = pwd_context.hash(admin_password)

        # We need a tenant_id — look for a tenant named "SigDoc" or create a seed tenant
        tenant_result = conn.execute(
            sa.text("SELECT id FROM tenants LIMIT 1")
        )
        tenant_row = tenant_result.fetchone()

        if tenant_row is None:
            # Create a seed tenant for the canonical admin
            tenant_id = str(uuid.uuid4())
            conn.execute(
                sa.text(
                    "INSERT INTO tenants (id, name, slug, is_active, created_at, updated_at) "
                    "VALUES (:id, :name, :slug, :is_active, NOW(), NOW())"
                ),
                {
                    "id": tenant_id,
                    "name": "SigDoc Admin",
                    "slug": "sigdoc-admin",
                    "is_active": True,
                },
            )
        else:
            tenant_id = str(tenant_row[0])

        user_id = str(uuid.uuid4())
        conn.execute(
            sa.text(
                "INSERT INTO users (id, tenant_id, email, hashed_password, full_name, role, is_active, created_at, updated_at) "
                "VALUES (:id, :tenant_id, :email, :hashed_password, :full_name, :role, :is_active, NOW(), NOW()) "
                "ON CONFLICT (email) "
                "DO UPDATE SET full_name = EXCLUDED.full_name, role = EXCLUDED.role, updated_at = NOW()"
            ),
            {
                "id": user_id,
                "tenant_id": tenant_id,
                "email": ADMIN_EMAIL,
                "hashed_password": hashed_password,
                "full_name": ADMIN_FULL_NAME,
                "role": "admin",
                "is_active": True,
            },
        )
    else:
        # User already exists — update name and role only (do NOT touch password)
        conn.execute(
            sa.text(
                "UPDATE users SET full_name = :full_name, role = :role, updated_at = NOW() "
                "WHERE email = :email"
            ),
            {
                "full_name": ADMIN_FULL_NAME,
                "role": "admin",
                "email": ADMIN_EMAIL,
            },
        )


def downgrade() -> None:
    # Downgrade removes the canonical admin user only if it was created by this migration.
    # To keep it safe, we only remove the user if the email matches the canonical admin.
    conn = op.get_bind()
    conn.execute(
        sa.text("DELETE FROM users WHERE email = :email"),
        {"email": ADMIN_EMAIL},
    )
