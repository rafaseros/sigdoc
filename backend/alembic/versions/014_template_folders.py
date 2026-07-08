"""Personal flat template folders

Revision ID: 014
Revises: 013
Create Date: 2026-07-07

Folders are PERSONAL (owner-scoped) and FLAT (no nesting, v1) — they
organize only the owner's OWN templates, matching the strict-owner-only
visibility model already used for template shares and variables-meta.
Tenant-wide or shared folders are intentionally out of scope.

What this migration does:
  1. Creates `template_folders`: id, tenant_id, owner_id, name,
     created_at/updated_at. Unique per (tenant_id, owner_id, name) — the
     same folder name is allowed across different owners in the same
     tenant, but not twice for the same owner.
  2. Adds `templates.folder_id` — nullable FK to template_folders.id with
     `ondelete="SET NULL"`. Deleting a folder unfiles its templates at the
     DB level; templates are never deleted as a side effect of deleting a
     folder.

downgrade() drops the column and the table. This is SAFE and LOSSLESS for
the `templates` table (dropping a nullable FK column loses no template
data — templates themselves are untouched). It IS lossy for the folder
rows themselves (their names/groupings are permanently lost), which is
expected and acceptable for a downgrade.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "014"
down_revision: Union[str, None] = "013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- template_folders ---
    op.create_table(
        "template_folders",
        sa.Column("id", sa.Uuid(), primary_key=True, default=sa.text("gen_random_uuid()")),
        sa.Column(
            "tenant_id",
            sa.Uuid(),
            sa.ForeignKey("tenants.id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "owner_id",
            sa.Uuid(),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint(
            "tenant_id", "owner_id", "name", name="uq_template_folders_tenant_owner_name"
        ),
    )

    # --- templates.folder_id ---
    op.add_column(
        "templates",
        sa.Column(
            "folder_id",
            sa.Uuid(),
            sa.ForeignKey("template_folders.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_templates_folder_id", "templates", ["folder_id"])


def downgrade() -> None:
    op.drop_index("ix_templates_folder_id", table_name="templates")
    op.drop_column("templates", "folder_id")
    op.drop_table("template_folders")
