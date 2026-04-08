from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass
class UsageEvent:
    id: UUID
    tenant_id: UUID
    user_id: UUID
    generation_type: str  # "single" or "bulk"
    document_count: int
    template_id: UUID | None = None
    created_at: datetime | None = None
