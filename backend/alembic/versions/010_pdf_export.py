"""PDF export — rename document columns and add PDF file fields

Revision ID: 010
Revises: 009
Create Date: 2026-04-25

Spec: REQ-DDF-01, REQ-DDF-02
Design: ADR-PDF-06

Renames the existing single-format storage columns:
  file_name   → docx_file_name
  minio_path  → docx_minio_path

Adds two nullable columns for the new PDF format:
  pdf_file_name  VARCHAR(255) NULL
  pdf_minio_path VARCHAR(500) NULL

Legacy rows keep pdf_file_name=NULL / pdf_minio_path=NULL as the sentinel
that triggers lazy PDF backfill in ensure_pdf() (Phase 3).
No data backfill at migration time.
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision: str = "010"
down_revision: str = "009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Rename DOCX columns (preserves all existing data)
    op.alter_column("documents", "file_name", new_column_name="docx_file_name")
    op.alter_column("documents", "minio_path", new_column_name="docx_minio_path")

    # Add nullable PDF columns (legacy rows get NULL — handled by ensure_pdf lazy backfill)
    op.add_column("documents", sa.Column("pdf_file_name", sa.String(255), nullable=True))
    op.add_column("documents", sa.Column("pdf_minio_path", sa.String(500), nullable=True))


def downgrade() -> None:
    # Remove the PDF columns added in upgrade
    op.drop_column("documents", "pdf_minio_path")
    op.drop_column("documents", "pdf_file_name")

    # Rename DOCX columns back to original names
    op.alter_column("documents", "docx_minio_path", new_column_name="minio_path")
    op.alter_column("documents", "docx_file_name", new_column_name="file_name")
