from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID


@dataclass
class Document:
    """Domain entity representing a generated document.

    Phase 1 (pdf-export): renamed file_name → docx_file_name,
    minio_path → docx_minio_path, added pdf_file_name and pdf_minio_path.

    Backward-compat aliases `file_name` and `minio_path` are provided as
    read-only properties so existing consumers (presentation layer, service
    layer, repository) continue to work without change.
    These aliases will be REMOVED in Phase 2 once all call sites
    (SQLAlchemy model, document_service, documents.py endpoint, schemas)
    are updated to use the canonical docx_* names.

    TODO(pdf-export Phase 2): Remove file_name and minio_path properties
    after updating:
      - backend/src/app/infrastructure/persistence/repositories/document_repository.py
      - backend/src/app/application/services/document_service.py
      - backend/src/app/presentation/api/v1/documents.py
      - backend/src/app/presentation/schemas/document.py
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

    # ------------------------------------------------------------------
    # Backward-compat read-only aliases (Phase 1 only — see docstring)
    # ------------------------------------------------------------------

    @property
    def file_name(self) -> str:
        """Alias for docx_file_name — temporary, removed in Phase 2."""
        return self.docx_file_name

    @property
    def minio_path(self) -> str:
        """Alias for docx_minio_path — temporary, removed in Phase 2."""
        return self.docx_minio_path
