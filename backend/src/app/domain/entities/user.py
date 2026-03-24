from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass
class User:
    id: UUID
    tenant_id: UUID
    email: str
    hashed_password: str
    full_name: str
    role: str = "user"
    is_active: bool = True
    created_at: datetime | None = None
    updated_at: datetime | None = None
