import uuid
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

# Deterministic UUIDs — must match migration 005 seed data
FREE_TIER_ID: UUID = uuid.uuid5(uuid.NAMESPACE_DNS, "sigdoc.tier.free")
PRO_TIER_ID: UUID = uuid.uuid5(uuid.NAMESPACE_DNS, "sigdoc.tier.pro")
ENTERPRISE_TIER_ID: UUID = uuid.uuid5(uuid.NAMESPACE_DNS, "sigdoc.tier.enterprise")


@dataclass(frozen=True)
class SubscriptionTier:
    """Value object representing a subscription tier.

    None values mean unlimited (e.g. Enterprise has no user cap).
    """

    id: UUID
    name: str
    slug: str
    monthly_document_limit: int | None  # None = unlimited
    max_templates: int | None           # None = unlimited
    max_users: int | None               # None = unlimited
    bulk_generation_limit: int          # always set; fallback = 10
    max_template_shares: int | None     # None = unlimited
    is_active: bool = True
    # Rate limit strings in slowapi format, e.g. "10/minute"
    rate_limit_login: str = "5/minute"
    rate_limit_refresh: str = "10/minute"
    rate_limit_generate: str = "20/minute"
    rate_limit_bulk: str = "5/minute"
    created_at: datetime | None = None
    updated_at: datetime | None = None
