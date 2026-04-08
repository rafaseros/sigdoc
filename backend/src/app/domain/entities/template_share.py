from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass
class TemplateShare:
    id: UUID
    template_id: UUID
    user_id: UUID
    tenant_id: UUID
    shared_by: UUID
    shared_at: datetime | None = None
