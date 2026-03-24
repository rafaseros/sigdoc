from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass
class Document:
    id: UUID
    tenant_id: UUID
    template_version_id: UUID
    minio_path: str
    file_name: str
    generation_type: str  # "single" or "bulk"
    variables_snapshot: dict
    created_by: UUID
    batch_id: UUID | None = None
    status: str = "completed"  # "completed" or "failed"
    error_message: str | None = None
    created_at: datetime | None = None
