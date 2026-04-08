"""Email verification and password reset fields on users table

Revision ID: 009
Revises: 008
Create Date: 2026-04-07

Spec: REQ-VERIFY-01
Design: Migration 009 SQL (ADR-ASEW-02)

Adds 5 columns to users:
  - email_verified BOOLEAN NOT NULL DEFAULT false
  - email_verification_token VARCHAR(255) NULL
  - email_verification_sent_at TIMESTAMP NULL
  - password_reset_token VARCHAR(255) NULL
  - password_reset_sent_at TIMESTAMP NULL

Sets email_verified=true for all existing users (they predate verification).
Creates partial indexes on token columns for fast lookup.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add email_verified column (existing users are already verified)
    op.add_column(
        "users",
        sa.Column(
            "email_verified",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )

    # Add email verification token columns
    op.add_column(
        "users",
        sa.Column("email_verification_token", sa.String(255), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("email_verification_sent_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Add password reset token columns
    op.add_column(
        "users",
        sa.Column("password_reset_token", sa.String(255), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("password_reset_sent_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Existing users are already verified (they predate this feature)
    op.execute("UPDATE users SET email_verified = true")

    # Partial indexes on token columns for fast token lookup
    op.create_index(
        "ix_users_email_verification_token",
        "users",
        ["email_verification_token"],
        unique=True,
        postgresql_where=sa.text("email_verification_token IS NOT NULL"),
    )
    op.create_index(
        "ix_users_password_reset_token",
        "users",
        ["password_reset_token"],
        unique=True,
        postgresql_where=sa.text("password_reset_token IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_users_password_reset_token", table_name="users")
    op.drop_index("ix_users_email_verification_token", table_name="users")
    op.drop_column("users", "password_reset_sent_at")
    op.drop_column("users", "password_reset_token")
    op.drop_column("users", "email_verification_sent_at")
    op.drop_column("users", "email_verification_token")
    op.drop_column("users", "email_verified")
