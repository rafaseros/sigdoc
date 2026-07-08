from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass
class TemplateFolder:
    """A personal, flat (non-nested) grouping of the owner's own templates.

    Folders are strictly owner-scoped — there is no tenant-wide or shared
    folder concept, matching the strict-owner-only pattern already used for
    template shares and variables-meta.
    """

    id: UUID
    tenant_id: UUID
    owner_id: UUID
    name: str
    created_at: datetime | None = None
    updated_at: datetime | None = None
