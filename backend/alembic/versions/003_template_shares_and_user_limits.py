"""Add template_shares table and users.bulk_generation_limit

Revision ID: 003
Revises: 002
Create Date: 2026-04-07

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- template_shares ---
    op.create_table(
        "template_shares",
        sa.Column("id", sa.Uuid(), primary_key=True, default=sa.text("gen_random_uuid()")),
        sa.Column(
            "template_id",
            sa.Uuid(),
            sa.ForeignKey("templates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "tenant_id",
            sa.Uuid(),
            sa.ForeignKey("tenants.id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "shared_by",
            sa.Uuid(),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column(
            "shared_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("template_id", "user_id", name="uq_template_shares_template_user"),
    )

    op.create_index("ix_template_shares_template", "template_shares", ["template_id"])
    op.create_index("ix_template_shares_user", "template_shares", ["user_id"])

    # --- users.bulk_generation_limit ---
    op.add_column(
        "users",
        sa.Column("bulk_generation_limit", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "bulk_generation_limit")
    op.drop_index("ix_template_shares_user", table_name="template_shares")
    op.drop_index("ix_template_shares_template", table_name="template_shares")
    op.drop_table("template_shares")
