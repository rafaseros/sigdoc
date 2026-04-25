from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID


@dataclass
class Document:
    """Domain entity representing a generated document.

    Phase 2 (pdf-export): Removed backward-compat aliases file_name and
    minio_path. All call sites now use canonical docx_file_name /
    docx_minio_path. SQLAlchemy model and Alembic migration 010 have been
    updated to match.

    Fields:
      - docx_file_name / docx_minio_path: the generated Word document
      - pdf_file_name / pdf_minio_path: the generated PDF (nullable; NULL
        means the row predates Phase 2 and needs lazy backfill via ensure_pdf)
    """

    id: UUID
    tenant_id: UUID
    template_version_id: UUID
    docx_file_name: str
    docx_minio_path: str
    generation_type: str  # "single" or "bulk"
    variables_snapshot: dict
    created_by: UUID
    pdf_file_name: str | None = None
    pdf_minio_path: str | None = None
    batch_id: UUID | None = None
    status: str = "completed"  # "completed" or "failed"
    error_message: str | None = None
    created_at: datetime | None = None
