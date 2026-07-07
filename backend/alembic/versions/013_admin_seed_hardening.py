"""Harden the demo admin seed against the public hardcoded credential

Revision ID: 013
Revises: 012
Create Date: 2026-07-07

This repository is PUBLIC. Migration 012 (demo reset) seeds a hardcoded
admin credential (devrafaseros@gmail.com / admin123!) so that anyone who
reads the git history knows it. Every fresh database that runs the full
migration chain (001..012) ends up with this publicly-known admin account
active — which is exactly what happened on the production DigitalOcean
deploy: migration 012 overwrote the env-configured admin from migration
001 with the hardcoded demo credential.

This migration is NON-DESTRUCTIVE and IDEMPOTENT:
  - It never deletes rows and only INSERTs when no admin/tenant exists yet.
  - Running it repeatedly converges to the same end state and is safe.

What it does, in order:
  1. If ADMIN_EMAIL/ADMIN_PASSWORD are configured via environment
     variables, ensure an admin user with that email/password exists:
       a. If a user with ADMIN_EMAIL already exists, update it in place.
       b. Else, if the legacy demo row (devrafaseros@gmail.com) exists,
          rename and re-hash it in place (preserves id and FK references).
       c. Else, create a tenant (if needed) and insert a fresh admin user.
  2. ALWAYS — regardless of whether ADMIN_EMAIL/ADMIN_PASSWORD were
     configured — neutralize the legacy hardcoded demo credential
     wherever it is still found under its original email AND its stored
     hash still verifies against the publicly-known demo password. The
     row's password hash is replaced with a random, unusable one. If the
     legacy row was re-passworded legitimately, it is left untouched.

Spec: production admin credential hardening, 2026-07
"""

from __future__ import annotations

import os
import secrets
import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "013"
down_revision: Union[str, None] = "012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Legacy hardcoded demo credential seeded by migration 012 — publicly known
# because this repository is public. Must be neutralized on every fresh DB.
LEGACY_DEMO_EMAIL = "devrafaseros@gmail.com"
LEGACY_DEMO_PASSWORD = "admin123!"

# Deterministic UUID for the Free tier — must match migrations 005 / 012
FREE_TIER_ID = uuid.uuid5(uuid.NAMESPACE_DNS, "sigdoc.tier.free")


def upgrade() -> None:
    try:
        from passlib.context import CryptContext
    except ImportError as exc:
        raise RuntimeError(
            "passlib is required for migration 013 but could not be imported. "
            "Install it with: pip install passlib[bcrypt]"
        ) from exc

    conn = op.get_bind()
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

    admin_email = os.environ.get("ADMIN_EMAIL")
    admin_password = os.environ.get("ADMIN_PASSWORD")
    admin_full_name = os.environ.get("ADMIN_FULL_NAME", "Administrator")

    if admin_email and admin_password:
        hashed_password = pwd_context.hash(admin_password)

        admin_count = conn.execute(
            sa.text("SELECT COUNT(*) FROM users WHERE email = :admin_email"),
            {"admin_email": admin_email},
        ).scalar()

        if admin_count and admin_count > 0:
            # (a) ADMIN_EMAIL row already exists — bring it in line with env.
            conn.execute(
                sa.text(
                    "UPDATE users SET hashed_password = :hashed_password, "
                    "role = :role, is_active = :is_active, "
                    "email_verified = :email_verified, updated_at = NOW() "
                    "WHERE email = :admin_email"
                ),
                {
                    "hashed_password": hashed_password,
                    "role": "admin",
                    "is_active": True,
                    "email_verified": True,
                    "admin_email": admin_email,
                },
            )
        else:
            legacy_count = conn.execute(
                sa.text("SELECT COUNT(*) FROM users WHERE email = :legacy_email"),
                {"legacy_email": LEGACY_DEMO_EMAIL},
            ).scalar()

            if legacy_count and legacy_count > 0:
                # (b) Rename the legacy demo row in place — preserves id/FKs.
                conn.execute(
                    sa.text(
                        "UPDATE users SET email = :new_email, "
                        "hashed_password = :hashed_password, role = :role, "
                        "is_active = :is_active, email_verified = :email_verified, "
                        "updated_at = NOW() WHERE email = :legacy_email"
                    ),
                    {
                        "new_email": admin_email,
                        "hashed_password": hashed_password,
                        "role": "admin",
                        "is_active": True,
                        "email_verified": True,
                        "legacy_email": LEGACY_DEMO_EMAIL,
                    },
                )
            else:
                # (c) Neither exists — create tenant (if needed) + admin user.
                tenant_id = conn.execute(
                    sa.text("SELECT id FROM tenants LIMIT 1")
                ).scalar()

                if tenant_id is None:
                    tenant_id = str(uuid.uuid4())
                    conn.execute(
                        sa.text(
                            "INSERT INTO tenants "
                            "(id, name, slug, tier_id, is_active, created_at, updated_at) "
                            "VALUES (:id, :name, :slug, CAST(:tier_id AS uuid), "
                            ":is_active, NOW(), NOW())"
                        ),
                        {
                            "id": tenant_id,
                            "name": "SigDoc",
                            "slug": "sigdoc",
                            "tier_id": str(FREE_TIER_ID),
                            "is_active": True,
                        },
                    )
                else:
                    tenant_id = str(tenant_id)

                user_id = str(uuid.uuid4())
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
                        "email": admin_email,
                        "hashed_password": hashed_password,
                        "full_name": admin_full_name,
                        "role": "admin",
                        "is_active": True,
                        "email_verified": True,
                    },
                )
    else:
        print(
            "Migration 013: ADMIN_EMAIL/ADMIN_PASSWORD are not set in the "
            "environment — skipping admin seeding. This is expected for CI "
            "test databases; production deploys must set both."
        )

    # ------------------------------------------------------------------
    # ALWAYS — neutralize the legacy hardcoded demo credential wherever
    # it is still found, regardless of whether ADMIN_EMAIL/ADMIN_PASSWORD
    # were configured above.
    # ------------------------------------------------------------------
    legacy_hash = conn.execute(
        sa.text("SELECT hashed_password FROM users WHERE email = :legacy_email"),
        {"legacy_email": LEGACY_DEMO_EMAIL},
    ).scalar()

    if legacy_hash:
        compromised = False
        try:
            compromised = pwd_context.verify(LEGACY_DEMO_PASSWORD, legacy_hash)
        except Exception:
            # Malformed/unknown hash — treat as not a match, leave it alone.
            compromised = False

        if compromised:
            conn.execute(
                sa.text(
                    "UPDATE users SET hashed_password = :hashed_password, "
                    "updated_at = NOW() WHERE email = :legacy_email"
                ),
                {
                    "hashed_password": pwd_context.hash(secrets.token_hex(32)),
                    "legacy_email": LEGACY_DEMO_EMAIL,
                },
            )
            print(
                "Migration 013: neutralized the compromised legacy demo "
                "credential (devrafaseros@gmail.com) — its stored password "
                "hash no longer matches the publicly-known demo password."
            )


def downgrade() -> None:
    # No-op — this is a data-hardening migration. Reversing it would mean
    # restoring a known-compromised password hash, which defeats its
    # purpose. Nothing to reverse.
    pass
