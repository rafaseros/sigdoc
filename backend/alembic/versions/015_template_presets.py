"""Template presets — recurring-client stored values

Revision ID: 015
Revises: 014
Create Date: 2026-07-08

Presets let a template's users save a named set of variable values (e.g. a
recurring client's data) and reload them next time they generate a document
from that template. Unlike folders (strictly owner-scoped), presets are
shared by EVERYONE who has access to the template — owner, shared users, and
admins alike — since they are a convenience for whoever generates documents
from that template, not a personal organization tool (explicit product
decision).

What this migration does:
  1. Creates `template_presets`: id, tenant_id, template_id, name, values
     (JSONB dict[str, str]), created_by, created_at/updated_at.
  2. Unique per (template_id, name) — presets are named per-template, and a
     duplicate name for the SAME template is rejected; the same name is
     allowed across different templates.
  3. `template_id` has ON DELETE CASCADE — deleting a template deletes its
     presets (unlike folders, which never cascade-delete templates: here
     presets are subordinate to the template, not the reverse).
  4. Explicit index on `template_id` for the list-by-template query, in
     addition to the unique constraint (which already covers it, but an
     explicit index keeps the query plan independent of constraint
     internals and matches the ix_templates_folder_id precedent in 014).

downgrade() drops the index and the table. This is lossy for the preset rows
themselves (their stored values are permanently lost), which is expected and
acceptable for a downgrade — it does NOT touch the `templates` table.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "015"
down_revision: Union[str, None] = "014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "template_presets",
        sa.Column("id", sa.Uuid(), primary_key=True, default=sa.text("gen_random_uuid()")),
        sa.Column(
            "tenant_id",
            sa.Uuid(),
            sa.ForeignKey("tenants.id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "template_id",
            sa.Uuid(),
            sa.ForeignKey("templates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column(
            "values",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint(
            "template_id", "name", name="uq_template_presets_template_name"
        ),
    )
    op.create_index("ix_template_presets_template_id", "template_presets", ["template_id"])


def downgrade() -> None:
    op.drop_index("ix_template_presets_template_id", table_name="template_presets")
    op.drop_table("template_presets")
