from uuid import UUID

from app.domain.entities.subscription_tier import (
    ENTERPRISE_TIER_ID,
    FREE_TIER_ID,
    PRO_TIER_ID,
    SubscriptionTier,
)
from app.domain.ports.subscription_tier_repository import SubscriptionTierRepository

# Canonical seed tiers — mirror migration 005 + 006 seed data
FREE_TIER = SubscriptionTier(
    id=FREE_TIER_ID,
    name="Free",
    slug="free",
    monthly_document_limit=50,
    max_templates=5,
    max_users=3,
    bulk_generation_limit=5,
    max_template_shares=5,
    is_active=True,
    # REQ-RL-02: strict limits
    rate_limit_login="5/minute",
    rate_limit_refresh="10/minute",
    rate_limit_generate="10/minute",
    rate_limit_bulk="2/minute",
)

PRO_TIER = SubscriptionTier(
    id=PRO_TIER_ID,
    name="Pro",
    slug="pro",
    monthly_document_limit=500,
    max_templates=50,
    max_users=20,
    bulk_generation_limit=25,
    max_template_shares=50,
    is_active=True,
    # REQ-RL-02: moderate limits
    rate_limit_login="10/minute",
    rate_limit_refresh="20/minute",
    rate_limit_generate="30/minute",
    rate_limit_bulk="10/minute",
)

ENTERPRISE_TIER = SubscriptionTier(
    id=ENTERPRISE_TIER_ID,
    name="Enterprise",
    slug="enterprise",
    monthly_document_limit=5000,
    max_templates=None,
    max_users=None,
    bulk_generation_limit=100,
    max_template_shares=None,
    is_active=True,
    # REQ-RL-02: generous limits
    rate_limit_login="20/minute",
    rate_limit_refresh="30/minute",
    rate_limit_generate="60/minute",
    rate_limit_bulk="20/minute",
)

_DEFAULT_TIERS: list[SubscriptionTier] = [FREE_TIER, PRO_TIER, ENTERPRISE_TIER]


class FakeSubscriptionTierRepository(SubscriptionTierRepository):
    """In-memory implementation of SubscriptionTierRepository for testing.

    Pre-seeded with Free / Pro / Enterprise tiers matching migration 005.
    Additional tiers can be injected via the constructor.
    """

    def __init__(self, extra_tiers: list[SubscriptionTier] | None = None) -> None:
        self._tiers: dict[UUID, SubscriptionTier] = {
            t.id: t for t in _DEFAULT_TIERS
        }
        if extra_tiers:
            for tier in extra_tiers:
                self._tiers[tier.id] = tier

    async def get_by_id(self, tier_id: UUID) -> SubscriptionTier | None:
        return self._tiers.get(tier_id)

    async def get_by_slug(self, slug: str) -> SubscriptionTier | None:
        for tier in self._tiers.values():
            if tier.slug == slug:
                return tier
        return None

    async def list_active(self) -> list[SubscriptionTier]:
        """Return active tiers ordered by monthly_document_limit ASC NULLS LAST."""
        active = [t for t in self._tiers.values() if t.is_active]
        # Sort: finite limits first (ascending), then None (unlimited) last
        return sorted(
            active,
            key=lambda t: (
                t.monthly_document_limit is None,
                t.monthly_document_limit or 0,
            ),
        )
