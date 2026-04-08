from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.services.audit_service import AuditService
from app.application.services.document_service import DocumentService
from app.application.services.quota_service import QuotaService
from app.application.services.template_service import TemplateService
from app.application.services.usage_service import UsageService
from app.config import get_settings
from app.infrastructure.persistence.database import async_session_factory
from app.infrastructure.persistence.repositories.template_repository import (
    SQLAlchemyTemplateRepository,
)
from app.infrastructure.storage import get_storage_service
from app.infrastructure.templating import get_template_engine
from app.presentation.middleware.tenant import CurrentUser, get_current_user, get_tenant_session


def get_audit_service() -> AuditService:
    """Return a singleton-like AuditService backed by the global session factory.

    Each log() call creates its own session internally — this factory is cheap.
    """
    return AuditService(session_factory=async_session_factory)


async def get_usage_service(
    session: AsyncSession = Depends(get_tenant_session),
) -> UsageService:
    """Return a UsageService that shares the request's DB session.

    Usage tracking is synchronous — it participates in the same transaction as
    the document creation so usage is never recorded for failed generations.
    """
    from app.infrastructure.persistence.repositories.usage_repository import (
        SQLAlchemyUsageRepository,
    )

    return UsageService(usage_repo=SQLAlchemyUsageRepository(session))


async def get_quota_service(
    session: AsyncSession = Depends(get_tenant_session),
) -> QuotaService:
    """Return a QuotaService that shares the request's DB session."""
    from app.infrastructure.persistence.repositories.subscription_tier_repository import (
        SQLAlchemySubscriptionTierRepository,
    )
    from app.infrastructure.persistence.repositories.usage_repository import (
        SQLAlchemyUsageRepository,
    )
    from app.infrastructure.persistence.repositories.user_repository import (
        SQLAlchemyUserRepository,
    )

    return QuotaService(
        tier_repo=SQLAlchemySubscriptionTierRepository(session),
        usage_repo=SQLAlchemyUsageRepository(session),
        template_repo=SQLAlchemyTemplateRepository(session),
        user_repo=SQLAlchemyUserRepository(session),
    )


async def get_template_service(
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
    quota_service: QuotaService = Depends(get_quota_service),
) -> TemplateService:
    from sqlalchemy import select

    from app.infrastructure.persistence.models.tenant import TenantModel

    # Resolve the tenant's tier_id for quota enforcement
    tenant_stmt = select(TenantModel).where(TenantModel.id == current_user.tenant_id)
    tenant_result = await session.execute(tenant_stmt)
    tenant = tenant_result.scalar_one_or_none()
    tier_id = tenant.tier_id if tenant is not None else None

    return TemplateService(
        repository=SQLAlchemyTemplateRepository(session),
        storage=get_storage_service(),
        engine=get_template_engine(),
        audit_service=get_audit_service(),
        quota_service=quota_service,
        tier_id=tier_id,
    )


async def get_document_service(
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
    quota_service: QuotaService = Depends(get_quota_service),
) -> DocumentService:
    from sqlalchemy import select

    from app.infrastructure.persistence.models.tenant import TenantModel
    from app.infrastructure.persistence.repositories.document_repository import (
        SQLAlchemyDocumentRepository,
    )
    from app.infrastructure.persistence.repositories.usage_repository import (
        SQLAlchemyUsageRepository,
    )
    from app.infrastructure.persistence.repositories.user_repository import (
        SQLAlchemyUserRepository,
    )

    settings = get_settings()
    global_limit = settings.bulk_generation_limit

    # Resolve per-user bulk_generation_limit
    user_repo = SQLAlchemyUserRepository(session)
    user = await user_repo.get_by_id(current_user.user_id)
    user_bulk_override = (
        user.bulk_generation_limit
        if user is not None and user.bulk_generation_limit is not None
        else None
    )
    effective_limit = user_bulk_override if user_bulk_override is not None else global_limit

    # Resolve the tenant's tier_id for quota enforcement
    tenant_stmt = select(TenantModel).where(TenantModel.id == current_user.tenant_id)
    tenant_result = await session.execute(tenant_stmt)
    tenant = tenant_result.scalar_one_or_none()
    tier_id = tenant.tier_id if tenant is not None else None

    return DocumentService(
        document_repository=SQLAlchemyDocumentRepository(session),
        template_repository=SQLAlchemyTemplateRepository(session),
        storage=get_storage_service(),
        engine=get_template_engine(),
        bulk_generation_limit=effective_limit,
        usage_service=UsageService(usage_repo=SQLAlchemyUsageRepository(session)),
        audit_service=get_audit_service(),
        quota_service=quota_service,
        tier_id=tier_id,
        user_bulk_override=user_bulk_override,
    )
