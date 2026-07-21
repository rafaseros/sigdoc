"""Related documents per template version + document generation groups

Revision ID: 016
Revises: 015
Create Date: 2026-07-21

A template version can now carry, besides its primary docx, N related docx
files (e.g. primary "Contrato" + related "Recibo de pago") that share ONE
variable set. Generating fills the variables once and renders every file of
the version, producing one document row per file.

What this migration does:
  1. Creates `template_version_files`: id, tenant_id, version_id (FK →
     template_versions ON DELETE CASCADE — files die with their version),
     label (unique per version), minio_path, variables (JSONB list of the
     file's own extracted names, used to recompute the union on detach),
     file_size, position (rendering order after the primary), created_at.
  2. Composite index (tenant_id, version_id) for the list-by-version query,
     mirroring ix_template_versions_tenant_template.
  3. Adds `documents.group_id` (nullable UUID): documents generated together
     from one multi-file generation share a group_id; NULL for documents of
     versions without related files (existing behavior unchanged).
  4. Partial index on (tenant_id, group_id) WHERE group_id IS NOT NULL,
     mirroring the ix_documents_batch style from 001.

downgrade() drops the index/column and the table. This is lossy for the
related-file rows and for group membership (group_id values are permanently
lost), which is expected and acceptable for a downgrade — the MinIO objects
under .../files/ are NOT touched.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "016"
down_revision: Union[str, None] = "015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "template_version_files",
        sa.Column("id", sa.Uuid(), primary_key=True, default=sa.text("gen_random_uuid()")),
        sa.Column(
            "tenant_id",
            sa.Uuid(),
            sa.ForeignKey("tenants.id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "version_id",
            sa.Uuid(),
            sa.ForeignKey("template_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("label", sa.String(120), nullable=False),
        sa.Column("minio_path", sa.String(500), nullable=False),
        sa.Column(
            "variables",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column("file_size", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "version_id", "label", name="uq_template_version_files_version_label"
        ),
    )
    op.create_index(
        "ix_template_version_files_tenant_version",
        "template_version_files",
        ["tenant_id", "version_id"],
    )

    op.add_column("documents", sa.Column("group_id", sa.Uuid(), nullable=True))
    op.create_index(
        "ix_documents_tenant_group",
        "documents",
        ["tenant_id", "group_id"],
        postgresql_where=sa.text("group_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_documents_tenant_group", table_name="documents")
    op.drop_column("documents", "group_id")
    op.drop_index(
        "ix_template_version_files_tenant_version",
        table_name="template_version_files",
    )
    op.drop_table("template_version_files")
