"""Add rate limit columns to subscription_tiers and seed per-tier values

Revision ID: 006
Revises: 005
Create Date: 2026-04-07

Spec: REQ-RL-01, REQ-RL-02
"""

import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Deterministic UUIDs — must match migration 005 seed data
FREE_TIER_ID = uuid.uuid5(uuid.NAMESPACE_DNS, "sigdoc.tier.free")
PRO_TIER_ID = uuid.uuid5(uuid.NAMESPACE_DNS, "sigdoc.tier.pro")
ENTERPRISE_TIER_ID = uuid.uuid5(uuid.NAMESPACE_DNS, "sigdoc.tier.enterprise")


def upgrade() -> None:
    # Add 4 rate limit columns with entity-level defaults
    op.add_column(
        "subscription_tiers",
        sa.Column(
            "rate_limit_login",
            sa.String(50),
            nullable=False,
            server_default="5/minute",
        ),
    )
    op.add_column(
        "subscription_tiers",
        sa.Column(
            "rate_limit_refresh",
            sa.String(50),
            nullable=False,
            server_default="10/minute",
        ),
    )
    op.add_column(
        "subscription_tiers",
        sa.Column(
            "rate_limit_generate",
            sa.String(50),
            nullable=False,
            server_default="20/minute",
        ),
    )
    op.add_column(
        "subscription_tiers",
        sa.Column(
            "rate_limit_bulk",
            sa.String(50),
            nullable=False,
            server_default="5/minute",
        ),
    )

    # Seed per-tier values — REQ-RL-02
    # Free: strict (5/min login, 10/min refresh, 10/min generate, 2/min bulk)
    op.execute(
        sa.text(
            """
            UPDATE subscription_tiers
            SET rate_limit_login    = '5/minute',
                rate_limit_refresh  = '10/minute',
                rate_limit_generate = '10/minute',
                rate_limit_bulk     = '2/minute'
            WHERE id = CAST(:tier_id AS uuid)
            """
        ).bindparams(tier_id=str(FREE_TIER_ID))
    )

    # Pro: moderate (10/min login, 20/min refresh, 30/min generate, 10/min bulk)
    op.execute(
        sa.text(
            """
            UPDATE subscription_tiers
            SET rate_limit_login    = '10/minute',
                rate_limit_refresh  = '20/minute',
                rate_limit_generate = '30/minute',
                rate_limit_bulk     = '10/minute'
            WHERE id = CAST(:tier_id AS uuid)
            """
        ).bindparams(tier_id=str(PRO_TIER_ID))
    )

    # Enterprise: generous (20/min login, 30/min refresh, 60/min generate, 20/min bulk)
    op.execute(
        sa.text(
            """
            UPDATE subscription_tiers
            SET rate_limit_login    = '20/minute',
                rate_limit_refresh  = '30/minute',
                rate_limit_generate = '60/minute',
                rate_limit_bulk     = '20/minute'
            WHERE id = CAST(:tier_id AS uuid)
            """
        ).bindparams(tier_id=str(ENTERPRISE_TIER_ID))
    )


def downgrade() -> None:
    op.drop_column("subscription_tiers", "rate_limit_bulk")
    op.drop_column("subscription_tiers", "rate_limit_generate")
    op.drop_column("subscription_tiers", "rate_limit_refresh")
    op.drop_column("subscription_tiers", "rate_limit_login")
