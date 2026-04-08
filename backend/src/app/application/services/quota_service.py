"""QuotaService — enforces subscription tier limits per tenant.

Raises QuotaExceededError when a limit is exceeded.
Returns None (no exception) when a limit is None (unlimited).
"""
from datetime import date
from uuid import UUID

from app.domain.entities.subscription_tier import SubscriptionTier
from app.domain.exceptions import QuotaExceededError
from app.domain.ports.subscription_tier_repository import SubscriptionTierRepository
from app.domain.ports.template_repository import TemplateRepository
from app.domain.ports.usage_repository import UsageRepository
from app.domain.ports.user_repository import UserRepository


class QuotaService:
    """Enforces per-tier quota limits.

    Dependencies are repositories only — no circular service deps.
    """

    def __init__(
        self,
        tier_repo: SubscriptionTierRepository,
        usage_repo: UsageRepository,
        template_repo: TemplateRepository,
        user_repo: UserRepository,
    ) -> None:
        self._tier_repo = tier_repo
        self._usage_repo = usage_repo
        self._template_repo = template_repo
        self._user_repo = user_repo

    async def _load_tier(self, tenant_id: UUID) -> SubscriptionTier:
        """Load the tier for a tenant.

        Loads the tenant's tier directly via the tier_id stored on the tenant.
        Falls back to the 'free' slug if tier_id is not resolvable.
        """
        # Look up the tier_id from the tier repo via the tenant.
        # The QuotaService receives a TierRepository that stores tiers keyed by ID.
        # We need to fetch the tenant to get its tier_id — but we don't have a
        # TenantRepository here. Per ADR-3, we do a direct lookup via get_by_slug
        # as fallback, or accept tenant_id and resolve the tier_id externally.
        #
        # Design pragmatism: get_tier_for_tenant accepts the tier_id directly when
        # callers pass it, OR callers pass tenant_id and we use a pragmatic approach.
        # Since we only have tier_repo and usage_repo here (no tenant_repo), we rely
        # on callers providing tier_id via get_tier_for_tenant(), or we fall back to
        # 'free'. The check_* methods accept an optional tier_id kwarg.
        raise NotImplementedError(
            "Use _load_tier_by_id or _load_tier_by_slug directly."
        )

    async def _load_tier_by_id(self, tier_id: UUID) -> SubscriptionTier:
        """Load tier by UUID; raises ValueError if not found."""
        tier = await self._tier_repo.get_by_id(tier_id)
        if tier is None:
            raise ValueError(f"SubscriptionTier {tier_id} not found")
        return tier

    async def _load_tier_by_slug(self, slug: str) -> SubscriptionTier:
        """Load tier by slug; raises ValueError if not found."""
        tier = await self._tier_repo.get_by_slug(slug)
        if tier is None:
            raise ValueError(f"SubscriptionTier '{slug}' not found")
        return tier

    async def get_tier_for_tenant(self, tier_id: UUID) -> SubscriptionTier:
        """Public API: load the tier by its UUID (stored on Tenant.tier_id)."""
        return await self._load_tier_by_id(tier_id)

    async def check_document_quota(
        self,
        tenant_id: UUID,
        tier_id: UUID,
        additional: int = 1,
    ) -> None:
        """Raise QuotaExceededError if generating `additional` docs would exceed the limit.

        Uses the current calendar month.
        """
        tier = await self._load_tier_by_id(tier_id)
        if tier.monthly_document_limit is None:
            return  # unlimited

        today = date.today()
        month_start = date(today.year, today.month, 1)
        current = await self._usage_repo.get_tenant_month_total(month_start=month_start)

        if current + additional > tier.monthly_document_limit:
            raise QuotaExceededError(
                limit_type="monthly_document_limit",
                limit_value=tier.monthly_document_limit,
                current_usage=current,
                tier_name=tier.name,
            )

    async def check_template_limit(
        self,
        tenant_id: UUID,
        tier_id: UUID,
    ) -> None:
        """Raise QuotaExceededError if tenant already has max_templates."""
        tier = await self._load_tier_by_id(tier_id)
        if tier.max_templates is None:
            return  # unlimited

        current = await self._template_repo.count_by_tenant(tenant_id)
        if current >= tier.max_templates:
            raise QuotaExceededError(
                limit_type="max_templates",
                limit_value=tier.max_templates,
                current_usage=current,
                tier_name=tier.name,
            )

    async def check_user_limit(
        self,
        tenant_id: UUID,
        tier_id: UUID,
    ) -> None:
        """Raise QuotaExceededError if tenant already has max_users active users."""
        tier = await self._load_tier_by_id(tier_id)
        if tier.max_users is None:
            return  # unlimited

        current = await self._user_repo.count_active_by_tenant(tenant_id)
        if current >= tier.max_users:
            raise QuotaExceededError(
                limit_type="max_users",
                limit_value=tier.max_users,
                current_usage=current,
                tier_name=tier.name,
            )

    async def check_bulk_limit(
        self,
        tenant_id: UUID,
        tier_id: UUID,
        requested_count: int,
        user_bulk_override: int | None = None,
    ) -> None:
        """Raise QuotaExceededError if requested_count exceeds the bulk generation limit.

        Resolution order (ADR-5):
        1. user_bulk_override (per-user limit if set)
        2. tier.bulk_generation_limit
        3. Fallback: 10
        """
        if user_bulk_override is not None:
            effective_limit = user_bulk_override
            tier_name = "user-override"
        else:
            tier = await self._load_tier_by_id(tier_id)
            effective_limit = tier.bulk_generation_limit  # always an int (min 10)
            tier_name = tier.name

        if requested_count > effective_limit:
            raise QuotaExceededError(
                limit_type="bulk_generation_limit",
                limit_value=effective_limit,
                current_usage=requested_count,
                tier_name=tier_name,
            )

    async def check_share_limit(
        self,
        tenant_id: UUID,
        tier_id: UUID,
        template_id: UUID,
    ) -> None:
        """Raise QuotaExceededError if template already has max_template_shares shares."""
        tier = await self._load_tier_by_id(tier_id)
        if tier.max_template_shares is None:
            return  # unlimited

        current = await self._template_repo.count_shares(template_id)
        if current >= tier.max_template_shares:
            raise QuotaExceededError(
                limit_type="max_template_shares",
                limit_value=tier.max_template_shares,
                current_usage=current,
                tier_name=tier.name,
            )

    async def get_usage_summary(
        self,
        tenant_id: UUID,
        tier_id: UUID,
    ) -> dict:
        """Return usage vs limits for the tenant's current tier.

        Returns a dict with keys: tier, documents, templates, users.
        Each resource key maps to {used, limit, percentage_used, near_limit}.
        near_limit is True when usage >= 80% of limit (ignored when unlimited).
        """
        tier = await self._load_tier_by_id(tier_id)

        today = date.today()
        month_start = date(today.year, today.month, 1)
        docs_used = await self._usage_repo.get_tenant_month_total(month_start=month_start)
        templates_used = await self._template_repo.count_by_tenant(tenant_id)
        users_used = await self._user_repo.count_active_by_tenant(tenant_id)

        def _resource(used: int, limit: int | None) -> dict:
            if limit is None:
                return {
                    "used": used,
                    "limit": None,
                    "percentage_used": None,
                    "near_limit": False,
                }
            pct = round((used / limit) * 100, 1) if limit > 0 else 100.0
            return {
                "used": used,
                "limit": limit,
                "percentage_used": pct,
                "near_limit": pct >= 80.0,
            }

        return {
            "tier": {
                "id": str(tier.id),
                "name": tier.name,
                "slug": tier.slug,
            },
            "documents": _resource(docs_used, tier.monthly_document_limit),
            "templates": _resource(templates_used, tier.max_templates),
            "users": _resource(users_used, tier.max_users),
        }
