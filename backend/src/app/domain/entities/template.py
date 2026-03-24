from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID


@dataclass
class TemplateVersion:
    id: UUID
    tenant_id: UUID
    template_id: UUID
    version: int
    minio_path: str
    variables: list[str] = field(default_factory=list)
    file_size: int = 0
    created_at: datetime | None = None


@dataclass
class Template:
    id: UUID
    tenant_id: UUID
    name: str
    created_by: UUID
    description: str | None = None
    current_version: int = 1
    versions: list[TemplateVersion] = field(default_factory=list)
    created_at: datetime | None = None
    updated_at: datetime | None = None
