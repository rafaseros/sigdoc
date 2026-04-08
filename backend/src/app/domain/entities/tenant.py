from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass
class Tenant:
    id: UUID
    name: str
    slug: str
    is_active: bool = True
    tier_id: UUID | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
