"""Add subscription_tiers table and tenants.tier_id FK

Revision ID: 005
Revises: 004
Create Date: 2026-04-08

"""

import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Deterministic UUIDs — uuid5(NAMESPACE_DNS, "sigdoc.tier.<slug>")
FREE_TIER_ID = uuid.uuid5(uuid.NAMESPACE_DNS, "sigdoc.tier.free")
PRO_TIER_ID = uuid.uuid5(uuid.NAMESPACE_DNS, "sigdoc.tier.pro")
ENTERPRISE_TIER_ID = uuid.uuid5(uuid.NAMESPACE_DNS, "sigdoc.tier.enterprise")


def upgrade() -> None:
    # --- subscription_tiers ---
    op.create_table(
        "subscription_tiers",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("slug", sa.String(50), nullable=False, unique=True),
        sa.Column("monthly_document_limit", sa.Integer(), nullable=True),
        sa.Column("max_templates", sa.Integer(), nullable=True),
        sa.Column("max_users", sa.Integer(), nullable=True),
        sa.Column(
            "bulk_generation_limit",
            sa.Integer(),
            nullable=False,
            server_default="10",
        ),
        sa.Column("max_template_shares", sa.Integer(), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            default=True,
            server_default="true",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_index("ix_subscription_tiers_slug", "subscription_tiers", ["slug"])
    op.create_index(
        "ix_subscription_tiers_is_active", "subscription_tiers", ["is_active"]
    )

    # --- seed Free / Pro / Enterprise tiers ---
    op.execute(
        sa.text(
            """
            INSERT INTO subscription_tiers
                (id, name, slug, monthly_document_limit, max_templates,
                 max_users, bulk_generation_limit, max_template_shares, is_active)
            VALUES
                (CAST(:free_id AS uuid),       'Free',       'free',       50,   5,    3,   5,   5,   true),
                (CAST(:pro_id AS uuid),        'Pro',        'pro',        500,  50,   20,  25,  50,  true),
                (CAST(:enterprise_id AS uuid), 'Enterprise', 'enterprise', 5000, NULL, NULL, 100, NULL, true)
            """
        ).bindparams(
            free_id=str(FREE_TIER_ID),
            pro_id=str(PRO_TIER_ID),
            enterprise_id=str(ENTERPRISE_TIER_ID),
        )
    )

    # --- tenants.tier_id ---
    op.add_column(
        "tenants",
        sa.Column(
            "tier_id",
            sa.Uuid(),
            sa.ForeignKey("subscription_tiers.id"),
            nullable=True,  # temporarily nullable for backfill
        ),
    )

    # backfill all existing tenants to Free tier
    op.execute(
        sa.text(
            "UPDATE tenants SET tier_id = CAST(:free_id AS uuid) WHERE tier_id IS NULL"
        ).bindparams(free_id=str(FREE_TIER_ID))
    )

    # now enforce NOT NULL
    op.alter_column("tenants", "tier_id", nullable=False)

    op.create_index("ix_tenants_tier_id", "tenants", ["tier_id"])


def downgrade() -> None:
    op.drop_index("ix_tenants_tier_id", table_name="tenants")
    op.drop_column("tenants", "tier_id")

    op.drop_index("ix_subscription_tiers_is_active", table_name="subscription_tiers")
    op.drop_index("ix_subscription_tiers_slug", table_name="subscription_tiers")
    op.drop_table("subscription_tiers")
