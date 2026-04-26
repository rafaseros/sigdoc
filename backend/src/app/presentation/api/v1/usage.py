from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.services import get_quota_service, get_usage_service
from app.application.services.quota_service import QuotaService
from app.application.services.usage_service import UsageService
from app.infrastructure.persistence.models.tenant import TenantModel
from app.presentation.api.dependencies import require_tenant_usage_viewer
from app.presentation.middleware.tenant import CurrentUser, get_current_user, get_tenant_session
from app.presentation.schemas.usage import TenantUsageResponse, UserUsageResponse, UserUsageStat

router = APIRouter()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _current_year_month() -> tuple[int, int]:
    today = date.today()
    return today.year, today.month


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("", response_model=UserUsageResponse)
async def get_user_usage(
    year: int | None = Query(None, ge=2000, le=9999),
    month: int | None = Query(None, ge=1, le=12),
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
    usage_service: UsageService = Depends(get_usage_service),
    quota_service: QuotaService = Depends(get_quota_service),
):
    """Return the current user's document-generation stats for a given month.

    Defaults to the current calendar month when year/month are omitted.
    Enriches the response with monthly_limit and percentage_used from QuotaService.
    """
    if year is None or month is None:
        year, month = _current_year_month()

    total = await usage_service.get_current_month_usage(
        user_id=current_user.user_id,
        year=year,
        month=month,
    )

    # Enrich with quota limit data when available
    monthly_limit: int | None = None
    percentage_used: float | None = None
    tenant_stmt = select(TenantModel).where(TenantModel.id == current_user.tenant_id)
    tenant_result = await session.execute(tenant_stmt)
    tenant = tenant_result.scalar_one_or_none()
    if tenant is not None and tenant.tier_id is not None:
        try:
            tier = await quota_service.get_tier_for_tenant(tenant.tier_id)
            monthly_limit = tier.monthly_document_limit
            if monthly_limit is not None and monthly_limit > 0:
                percentage_used = round((total / monthly_limit) * 100, 1)
        except Exception:
            pass  # Non-critical enrichment — degrade gracefully

    return UserUsageResponse(
        user_id=str(current_user.user_id),
        year=year,
        month=month,
        total_documents=total,
        by_template=[],  # per-template breakdown is a Phase-9+ enhancement
        monthly_limit=monthly_limit,
        percentage_used=percentage_used,
    )


@router.get("/tenant", response_model=TenantUsageResponse)
async def get_tenant_usage(
    year: int | None = Query(None, ge=2000, le=9999),
    month: int | None = Query(None, ge=1, le=12),
    current_user: CurrentUser = Depends(require_tenant_usage_viewer),
    usage_service: UsageService = Depends(get_usage_service),
):
    """Return all users' usage within the tenant for a given month.

    Admin-only — returns 403 for non-admin callers.
    """
    if year is None or month is None:
        year, month = _current_year_month()

    data = await usage_service.get_tenant_usage(year=year, month=month)

    by_user = [
        UserUsageStat(
            user_id=str(row["user_id"]),
            user_email=row.get("user_email", ""),
            full_name=row.get("full_name"),
            document_count=row["total"],
        )
        for row in data.get("by_user", [])
    ]

    return TenantUsageResponse(
        tenant_id=str(current_user.tenant_id),
        year=year,
        month=month,
        total_documents=data.get("total", 0),
        by_user=by_user,
    )
