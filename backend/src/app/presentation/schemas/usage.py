from uuid import UUID

from pydantic import BaseModel


class TemplateUsageStat(BaseModel):
    """Per-template breakdown within a user's usage stats."""

    template_id: str
    template_name: str | None = None
    document_count: int


class UserUsageResponse(BaseModel):
    """Monthly usage stats for the current authenticated user."""

    user_id: str
    year: int
    month: int
    total_documents: int
    by_template: list[TemplateUsageStat] = []
    # Quota enrichment — None when QuotaService is not wired or tier is unlimited
    monthly_limit: int | None = None
    percentage_used: float | None = None


class UserUsageStat(BaseModel):
    """Per-user breakdown within a tenant's usage stats."""

    user_id: str
    user_email: str
    full_name: str | None = None
    document_count: int


class TenantUsageResponse(BaseModel):
    """Monthly usage stats for the entire tenant (admin only)."""

    tenant_id: str
    year: int
    month: int
    total_documents: int
    by_user: list[UserUsageStat] = []
