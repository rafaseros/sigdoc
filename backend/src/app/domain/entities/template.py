from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID


@dataclass
class TemplateVersionFile:
    """A related .docx attached to a template version (besides the primary).

    All files of a version share ONE variable set: the version's `variables`
    is the union of the primary's and every related file's extraction. The
    per-file `variables` list keeps this file's own extracted names so the
    union can be recomputed when a file is detached.
    """

    id: UUID
    tenant_id: UUID
    version_id: UUID
    label: str
    minio_path: str
    variables: list[str] = field(default_factory=list)
    file_size: int = 0
    position: int = 0
    created_at: datetime | None = None


@dataclass
class TemplateVersion:
    id: UUID
    tenant_id: UUID
    template_id: UUID
    version: int
    minio_path: str
    variables: list[str] = field(default_factory=list)
    variables_meta: list[dict] | None = None
    file_size: int = 0
    created_at: datetime | None = None
    files: list[TemplateVersionFile] = field(default_factory=list)


@dataclass
class Template:
    id: UUID
    tenant_id: UUID
    name: str
    created_by: UUID
    description: str | None = None
    current_version: int = 1
    versions: list[TemplateVersion] = field(default_factory=list)
    folder_id: UUID | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
