"""Tenant onboarding: global email uniqueness + tenant name constraint

Revision ID: 007
Revises: 006
Create Date: 2026-04-08

Spec: REQ-SIGNUP-03, REQ-SIGNUP-04
- REQ-SIGNUP-03: Global email uniqueness — unique index on users.email (global,
  not per-tenant). The existing composite constraint uq_users_tenant_email is
  kept for backward compatibility; this new index makes email globally unique.
- REQ-SIGNUP-04: Organization name uniqueness — unique constraint on tenants.name.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # REQ-SIGNUP-03: global email uniqueness
    # Create a unique index on users.email (not per-tenant)
    op.create_index(
        "uq_users_email_global",
        "users",
        ["email"],
        unique=True,
    )

    # REQ-SIGNUP-04: tenant name uniqueness
    op.create_unique_constraint(
        "uq_tenants_name",
        "tenants",
        ["name"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_tenants_name", "tenants", type_="unique")
    op.drop_index("uq_users_email_global", table_name="users")
