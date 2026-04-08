from dataclasses import dataclass, field
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
    bulk_generation_limit: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    # Email verification (added in migration 009)
    email_verified: bool = False
    email_verification_token: str | None = None
    email_verification_sent_at: datetime | None = None
    # Password reset (added in migration 009)
    password_reset_token: str | None = None
    password_reset_sent_at: datetime | None = None
