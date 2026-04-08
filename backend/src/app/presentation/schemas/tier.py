from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict


class TierPublicSchema(BaseModel):
    """Public representation of a subscription tier."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    slug: str
    monthly_document_limit: int | None
    max_templates: int | None
    max_users: int | None
    bulk_generation_limit: int
    max_template_shares: int | None
    # Rate limit strings (slowapi format) — REQ-RL-06
    rate_limit_login: str
    rate_limit_refresh: str
    rate_limit_generate: str
    rate_limit_bulk: str


class TiersListResponse(BaseModel):
    """Response for GET /tiers — ordered list of active tiers."""

    items: list[TierPublicSchema]
    total: int


class ResourceUsage(BaseModel):
    """Usage stats for a single resource type."""

    used: int
    limit: int | None
    percentage_used: float | None
    near_limit: bool


class UsageSummary(BaseModel):
    """Usage summary across all quota-tracked resources."""

    documents: ResourceUsage
    templates: ResourceUsage
    users: ResourceUsage


class TenantTierResponse(BaseModel):
    """Response for GET /tenant/tier — tenant's current tier + usage."""

    tier: TierPublicSchema
    usage: UsageSummary
