"""Tiers API — public tier listing and per-tenant tier + usage summary."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.services import get_quota_service
from app.application.services.quota_service import QuotaService
from app.infrastructure.persistence.database import get_session
from app.infrastructure.persistence.models.subscription_tier import SubscriptionTierModel
from app.infrastructure.persistence.models.tenant import TenantModel
from app.infrastructure.persistence.repositories.subscription_tier_repository import (
    SQLAlchemySubscriptionTierRepository,
)
from app.presentation.middleware.tenant import CurrentUser, get_current_user, get_tenant_session
from app.presentation.schemas.tier import (
    ResourceUsage,
    TenantTierResponse,
    TierPublicSchema,
    TiersListResponse,
    UsageSummary,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# Public endpoint — no auth required
# ---------------------------------------------------------------------------


@router.get("", response_model=TiersListResponse)
async def list_tiers(session: AsyncSession = Depends(get_session)):
    """Return all active subscription tiers ordered by monthly_document_limit ASC.

    Public — no authentication required.
    """
    stmt = (
        select(SubscriptionTierModel)
        .where(SubscriptionTierModel.is_active == True)  # noqa: E712
        .order_by(SubscriptionTierModel.monthly_document_limit.asc().nulls_last())
    )
    result = await session.execute(stmt)
    models = list(result.scalars().all())

    items = [
        TierPublicSchema(
            id=m.id,
            name=m.name,
            slug=m.slug,
            monthly_document_limit=m.monthly_document_limit,
            max_templates=m.max_templates,
            max_users=m.max_users,
            bulk_generation_limit=m.bulk_generation_limit,
            max_template_shares=m.max_template_shares,
            rate_limit_login=getattr(m, "rate_limit_login", "5/minute"),
            rate_limit_refresh=getattr(m, "rate_limit_refresh", "10/minute"),
            rate_limit_generate=getattr(m, "rate_limit_generate", "20/minute"),
            rate_limit_bulk=getattr(m, "rate_limit_bulk", "5/minute"),
        )
        for m in models
    ]

    return TiersListResponse(items=items, total=len(items))


# ---------------------------------------------------------------------------
# Authenticated endpoint — tenant's tier + usage
# ---------------------------------------------------------------------------


@router.get("/tenant", response_model=TenantTierResponse)
async def get_tenant_tier(
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
    quota_service: QuotaService = Depends(get_quota_service),
):
    """Return the authenticated tenant's current tier and usage summary.

    Max 4 DB queries: tenant, tier, usage total, template count, user count.
    """
    # 1. Load tenant to get tier_id
    tenant_stmt = select(TenantModel).where(TenantModel.id == current_user.tenant_id)
    tenant_result = await session.execute(tenant_stmt)
    tenant = tenant_result.scalar_one_or_none()

    if tenant is None or tenant.tier_id is None:
        # Fallback: load the free tier from the tier repo
        tier_repo = SQLAlchemySubscriptionTierRepository(session)
        tier_entity = await tier_repo.get_by_slug("free")
    else:
        tier_entity = await quota_service.get_tier_for_tenant(tenant.tier_id)

    # 2. Get usage summary from QuotaService
    tier_id = tier_entity.id
    summary = await quota_service.get_usage_summary(
        tenant_id=current_user.tenant_id,
        tier_id=tier_id,
    )

    # 3. Build response
    tier_schema = TierPublicSchema(
        id=tier_entity.id,
        name=tier_entity.name,
        slug=tier_entity.slug,
        monthly_document_limit=tier_entity.monthly_document_limit,
        max_templates=tier_entity.max_templates,
        max_users=tier_entity.max_users,
        bulk_generation_limit=tier_entity.bulk_generation_limit,
        max_template_shares=tier_entity.max_template_shares,
        rate_limit_login=tier_entity.rate_limit_login,
        rate_limit_refresh=tier_entity.rate_limit_refresh,
        rate_limit_generate=tier_entity.rate_limit_generate,
        rate_limit_bulk=tier_entity.rate_limit_bulk,
    )

    def _resource(data: dict) -> ResourceUsage:
        return ResourceUsage(
            used=data["used"],
            limit=data["limit"],
            percentage_used=data["percentage_used"],
            near_limit=data["near_limit"],
        )

    usage = UsageSummary(
        documents=_resource(summary["documents"]),
        templates=_resource(summary["templates"]),
        users=_resource(summary["users"]),
    )

    return TenantTierResponse(tier=tier_schema, usage=usage)
