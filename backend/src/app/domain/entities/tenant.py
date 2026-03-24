from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass
class Tenant:
    id: UUID
    name: str
    slug: str
    is_active: bool = True
    created_at: datetime | None = None
    updated_at: datetime | None = None
