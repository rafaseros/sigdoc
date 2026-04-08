from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.entities.subscription_tier import SubscriptionTier


class SubscriptionTierRepository(ABC):
    @abstractmethod
    async def get_by_id(self, tier_id: UUID) -> SubscriptionTier | None:
        """Return the tier with the given UUID, or None if not found."""
        ...

    @abstractmethod
    async def get_by_slug(self, slug: str) -> SubscriptionTier | None:
        """Return the tier with the given slug, or None if not found."""
        ...

    @abstractmethod
    async def list_active(self) -> list[SubscriptionTier]:
        """Return all active tiers ordered by monthly_document_limit ASC NULLS LAST."""
        ...
