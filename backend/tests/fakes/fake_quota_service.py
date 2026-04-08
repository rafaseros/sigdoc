"""FakeQuotaService — test double for QuotaService.

Configure `exceeded_resource` to the limit_type string that should raise,
or leave it None for no-op (all quotas pass).
"""
from uuid import UUID

from app.domain.exceptions import QuotaExceededError


class FakeQuotaService:
    """Configurable test double for QuotaService.

    Usage:
        # All checks pass (default)
        svc = FakeQuotaService()

        # Simulate document quota exceeded
        svc = FakeQuotaService(exceeded_resource="monthly_document_limit")

    When exceeded_resource matches the resource being checked, raises
    QuotaExceededError with sentinel values for easy assertion in tests.
    """

    def __init__(self, exceeded_resource: str | None = None) -> None:
        self.exceeded_resource = exceeded_resource

    def _maybe_raise(self, resource: str, limit_value: int, current: int, tier_name: str = "Free") -> None:
        if self.exceeded_resource == resource:
            raise QuotaExceededError(
                limit_type=resource,
                limit_value=limit_value,
                current_usage=current,
                tier_name=tier_name,
            )

    async def check_document_quota(
        self,
        tenant_id: UUID,
        tier_id: UUID,
        additional: int = 1,
    ) -> None:
        self._maybe_raise("monthly_document_limit", 50, 50)

    async def check_template_limit(
        self,
        tenant_id: UUID,
        tier_id: UUID,
    ) -> None:
        self._maybe_raise("max_templates", 5, 5)

    async def check_user_limit(
        self,
        tenant_id: UUID,
        tier_id: UUID,
    ) -> None:
        self._maybe_raise("max_users", 3, 3)

    async def check_bulk_limit(
        self,
        tenant_id: UUID,
        tier_id: UUID,
        requested_count: int,
        user_bulk_override: int | None = None,
    ) -> None:
        self._maybe_raise("bulk_generation_limit", 5, requested_count)

    async def check_share_limit(
        self,
        tenant_id: UUID,
        tier_id: UUID,
        template_id: UUID,
    ) -> None:
        self._maybe_raise("max_template_shares", 5, 5)

    async def get_usage_summary(
        self,
        tenant_id: UUID,
        tier_id: UUID,
    ) -> dict:
        return {
            "tier": {"id": str(tier_id), "name": "Free", "slug": "free"},
            "documents": {"used": 0, "limit": 50, "percentage_used": 0.0, "near_limit": False},
            "templates": {"used": 0, "limit": 5, "percentage_used": 0.0, "near_limit": False},
            "users": {"used": 0, "limit": 3, "percentage_used": 0.0, "near_limit": False},
        }

    async def get_tier_for_tenant(self, tier_id: UUID):
        from tests.fakes.fake_subscription_tier_repository import FREE_TIER
        return FREE_TIER
