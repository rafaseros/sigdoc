from uuid import UUID

from sqlalchemy import asc, nulls_last, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.subscription_tier import SubscriptionTier
from app.domain.ports.subscription_tier_repository import SubscriptionTierRepository
from app.infrastructure.persistence.models.subscription_tier import SubscriptionTierModel


def _to_entity(model: SubscriptionTierModel) -> SubscriptionTier:
    return SubscriptionTier(
        id=model.id,
        name=model.name,
        slug=model.slug,
        monthly_document_limit=model.monthly_document_limit,
        max_templates=model.max_templates,
        max_users=model.max_users,
        bulk_generation_limit=model.bulk_generation_limit,
        max_template_shares=model.max_template_shares,
        is_active=model.is_active,
        rate_limit_login=model.rate_limit_login,
        rate_limit_refresh=model.rate_limit_refresh,
        rate_limit_generate=model.rate_limit_generate,
        rate_limit_bulk=model.rate_limit_bulk,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


class SQLAlchemySubscriptionTierRepository(SubscriptionTierRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, tier_id: UUID) -> SubscriptionTier | None:
        stmt = select(SubscriptionTierModel).where(SubscriptionTierModel.id == tier_id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return _to_entity(model) if model else None

    async def get_by_slug(self, slug: str) -> SubscriptionTier | None:
        stmt = select(SubscriptionTierModel).where(SubscriptionTierModel.slug == slug)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return _to_entity(model) if model else None

    async def list_active(self) -> list[SubscriptionTier]:
        """Return all active tiers ordered by monthly_document_limit ASC NULLS LAST."""
        stmt = (
            select(SubscriptionTierModel)
            .where(SubscriptionTierModel.is_active == True)  # noqa: E712
            .order_by(nulls_last(asc(SubscriptionTierModel.monthly_document_limit)))
        )
        result = await self._session.execute(stmt)
        models = list(result.scalars().all())
        return [_to_entity(m) for m in models]
