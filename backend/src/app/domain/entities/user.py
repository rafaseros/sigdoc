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
    role: str = "document_generator"
    is_active: bool = True
    bulk_generation_limit: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    # Email verification (added in migration 009).
    # Per single-org-cutover (REQ-SOS-15): default is True — email verification
    # is no longer enforced; all newly constructed users are treated as verified.
    email_verified: bool = True
    email_verification_token: str | None = None
    email_verification_sent_at: datetime | None = None
    # Password reset (added in migration 009)
    password_reset_token: str | None = None
    password_reset_sent_at: datetime | None = None
