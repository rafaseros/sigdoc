"""Unit tests for QuotaService (task 7.1).

All deps are replaced with in-memory fakes; no DB or network required.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from uuid import UUID

import pytest

from app.application.services.quota_service import QuotaService
from app.domain.entities.subscription_tier import (
    ENTERPRISE_TIER_ID,
    FREE_TIER_ID,
    PRO_TIER_ID,
    SubscriptionTier,
)
from app.domain.exceptions import QuotaExceededError
from tests.fakes import (
    FakeSubscriptionTierRepository,
    FakeTemplateRepository,
    FakeUsageRepository,
    FakeUserRepository,
)
from tests.fakes.fake_subscription_tier_repository import (
    ENTERPRISE_TIER,
    FREE_TIER,
    PRO_TIER,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_service(
    tier_repo: FakeSubscriptionTierRepository | None = None,
    usage_repo: FakeUsageRepository | None = None,
    template_repo: FakeTemplateRepository | None = None,
    user_repo: FakeUserRepository | None = None,
) -> QuotaService:
    return QuotaService(
        tier_repo=tier_repo or FakeSubscriptionTierRepository(),
        usage_repo=usage_repo or FakeUsageRepository(),
        template_repo=template_repo or FakeTemplateRepository(),
        user_repo=user_repo or FakeUserRepository(),
    )


def seed_usage(repo: FakeUsageRepository, tenant_id: UUID, doc_count: int) -> None:
    """Seed a usage event in the current month for the given tenant."""
    from app.domain.entities import UsageEvent

    now = datetime.now(timezone.utc)
    event = UsageEvent(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        tenant_id=tenant_id,
        template_id=uuid.uuid4(),
        generation_type="single",
        document_count=doc_count,
        created_at=now,
    )
    repo._events.append(event)


def seed_templates(repo: FakeTemplateRepository, tenant_id: UUID, count: int) -> None:
    """Seed `count` templates in the fake repo for the given tenant."""
    from datetime import datetime, timezone
    from app.domain.entities import Template

    for _ in range(count):
        tid = uuid.uuid4()
        tpl = Template(
            id=tid,
            tenant_id=tenant_id,
            name=f"Template {tid}",
            description=None,
            current_version=1,
            created_by=uuid.uuid4(),
            versions=[],
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        repo._templates[tid] = tpl


def seed_users(repo: FakeUserRepository, tenant_id: UUID, count: int) -> None:
    """Seed `count` active users in the fake repo for the given tenant."""
    from app.domain.entities import User

    for _ in range(count):
        uid = uuid.uuid4()
        user = User(
            id=uid,
            tenant_id=tenant_id,
            email=f"user-{uid}@example.com",
            hashed_password="hash",
            full_name=f"User {uid}",
            role="user",
            is_active=True,
        )
        repo._users[uid] = user
        repo._by_email[user.email] = uid


# ---------------------------------------------------------------------------
# check_document_quota
# ---------------------------------------------------------------------------


class TestCheckDocumentQuota:
    async def test_under_limit_does_not_raise(self):
        """3 docs used, limit = 50 → passes."""
        tenant_id = uuid.uuid4()
        usage_repo = FakeUsageRepository()
        seed_usage(usage_repo, tenant_id, 3)

        svc = make_service(usage_repo=usage_repo)
        # Should not raise
        await svc.check_document_quota(tenant_id=tenant_id, tier_id=FREE_TIER_ID)

    async def test_at_limit_raises(self):
        """50 docs used, limit = 50, additional = 1 → QuotaExceededError."""
        tenant_id = uuid.uuid4()
        usage_repo = FakeUsageRepository()
        seed_usage(usage_repo, tenant_id, 50)

        svc = make_service(usage_repo=usage_repo)
        with pytest.raises(QuotaExceededError) as exc_info:
            await svc.check_document_quota(tenant_id=tenant_id, tier_id=FREE_TIER_ID)

        err = exc_info.value
        assert err.limit_type == "monthly_document_limit"
        assert err.limit_value == 50
        assert err.current_usage == 50
        assert err.tier_name == "Free"

    async def test_additional_pushes_over_limit_raises(self):
        """49 docs used, additional = 2, limit = 50 → QuotaExceededError."""
        tenant_id = uuid.uuid4()
        usage_repo = FakeUsageRepository()
        seed_usage(usage_repo, tenant_id, 49)

        svc = make_service(usage_repo=usage_repo)
        with pytest.raises(QuotaExceededError):
            await svc.check_document_quota(
                tenant_id=tenant_id,
                tier_id=FREE_TIER_ID,
                additional=2,
            )

    async def test_enterprise_unlimited_never_raises(self):
        """Enterprise has monthly_document_limit=5000, not None per our data.

        But we can test a custom tier with None limit to verify unlimited path.
        """
        unlimited_tier = SubscriptionTier(
            id=uuid.uuid5(uuid.NAMESPACE_DNS, "sigdoc.tier.unlimited-test"),
            name="Unlimited",
            slug="unlimited",
            monthly_document_limit=None,  # NULL = unlimited
            max_templates=None,
            max_users=None,
            bulk_generation_limit=1000,
            max_template_shares=None,
            is_active=True,
        )
        tier_repo = FakeSubscriptionTierRepository(extra_tiers=[unlimited_tier])
        usage_repo = FakeUsageRepository()
        seed_usage(usage_repo, uuid.uuid4(), 99999)

        svc = make_service(tier_repo=tier_repo, usage_repo=usage_repo)
        # Must not raise, regardless of usage
        await svc.check_document_quota(
            tenant_id=uuid.uuid4(),
            tier_id=unlimited_tier.id,
            additional=1,
        )


# ---------------------------------------------------------------------------
# check_template_limit
# ---------------------------------------------------------------------------


class TestCheckTemplateLimit:
    async def test_under_limit_does_not_raise(self):
        """3 templates, limit = 5 → passes."""
        tenant_id = uuid.uuid4()
        template_repo = FakeTemplateRepository()
        seed_templates(template_repo, tenant_id, 3)

        svc = make_service(template_repo=template_repo)
        await svc.check_template_limit(tenant_id=tenant_id, tier_id=FREE_TIER_ID)

    async def test_at_limit_raises(self):
        """5 templates, limit = 5 → QuotaExceededError."""
        tenant_id = uuid.uuid4()
        template_repo = FakeTemplateRepository()
        seed_templates(template_repo, tenant_id, 5)

        svc = make_service(template_repo=template_repo)
        with pytest.raises(QuotaExceededError) as exc_info:
            await svc.check_template_limit(tenant_id=tenant_id, tier_id=FREE_TIER_ID)

        err = exc_info.value
        assert err.limit_type == "max_templates"
        assert err.limit_value == 5
        assert err.current_usage == 5

    async def test_unlimited_tier_never_raises(self):
        """Enterprise max_templates = None → always passes."""
        unlimited_tier = SubscriptionTier(
            id=uuid.uuid5(uuid.NAMESPACE_DNS, "sigdoc.tier.unlimited-tpl"),
            name="Unlimited Templates",
            slug="unlimited-tpl",
            monthly_document_limit=None,
            max_templates=None,
            max_users=None,
            bulk_generation_limit=100,
            max_template_shares=None,
            is_active=True,
        )
        tier_repo = FakeSubscriptionTierRepository(extra_tiers=[unlimited_tier])
        template_repo = FakeTemplateRepository()
        tenant_id = uuid.uuid4()
        seed_templates(template_repo, tenant_id, 9999)

        svc = make_service(tier_repo=tier_repo, template_repo=template_repo)
        # Must not raise
        await svc.check_template_limit(tenant_id=tenant_id, tier_id=unlimited_tier.id)


# ---------------------------------------------------------------------------
# check_user_limit
# ---------------------------------------------------------------------------


class TestCheckUserLimit:
    async def test_under_limit_does_not_raise(self):
        """2 users, limit = 3 → passes."""
        tenant_id = uuid.uuid4()
        user_repo = FakeUserRepository()
        seed_users(user_repo, tenant_id, 2)

        svc = make_service(user_repo=user_repo)
        await svc.check_user_limit(tenant_id=tenant_id, tier_id=FREE_TIER_ID)

    async def test_at_limit_raises(self):
        """3 users, limit = 3 → QuotaExceededError."""
        tenant_id = uuid.uuid4()
        user_repo = FakeUserRepository()
        seed_users(user_repo, tenant_id, 3)

        svc = make_service(user_repo=user_repo)
        with pytest.raises(QuotaExceededError) as exc_info:
            await svc.check_user_limit(tenant_id=tenant_id, tier_id=FREE_TIER_ID)

        err = exc_info.value
        assert err.limit_type == "max_users"
        assert err.limit_value == 3
        assert err.current_usage == 3

    async def test_unlimited_tier_never_raises(self):
        """Null max_users → always passes regardless of user count."""
        unlimited_tier = SubscriptionTier(
            id=uuid.uuid5(uuid.NAMESPACE_DNS, "sigdoc.tier.unlimited-users"),
            name="Unlimited Users",
            slug="unlimited-users",
            monthly_document_limit=None,
            max_templates=None,
            max_users=None,
            bulk_generation_limit=100,
            max_template_shares=None,
            is_active=True,
        )
        tier_repo = FakeSubscriptionTierRepository(extra_tiers=[unlimited_tier])
        user_repo = FakeUserRepository()
        tenant_id = uuid.uuid4()
        seed_users(user_repo, tenant_id, 500)

        svc = make_service(tier_repo=tier_repo, user_repo=user_repo)
        await svc.check_user_limit(tenant_id=tenant_id, tier_id=unlimited_tier.id)


# ---------------------------------------------------------------------------
# check_share_limit
# ---------------------------------------------------------------------------


class TestCheckShareLimit:
    async def test_under_limit_does_not_raise(self):
        """3 shares, limit = 5 → passes."""
        tenant_id = uuid.uuid4()
        template_repo = FakeTemplateRepository()
        template_id = uuid.uuid4()
        # Add 3 shares for the template
        for _ in range(3):
            template_repo._shares[(template_id, uuid.uuid4())] = None  # type: ignore[assignment]

        svc = make_service(template_repo=template_repo)
        await svc.check_share_limit(
            tenant_id=tenant_id,
            tier_id=FREE_TIER_ID,
            template_id=template_id,
        )

    async def test_at_limit_raises(self):
        """5 shares, limit = 5 → QuotaExceededError."""
        tenant_id = uuid.uuid4()
        template_repo = FakeTemplateRepository()
        template_id = uuid.uuid4()
        for _ in range(5):
            template_repo._shares[(template_id, uuid.uuid4())] = None  # type: ignore[assignment]

        svc = make_service(template_repo=template_repo)
        with pytest.raises(QuotaExceededError) as exc_info:
            await svc.check_share_limit(
                tenant_id=tenant_id,
                tier_id=FREE_TIER_ID,
                template_id=template_id,
            )

        err = exc_info.value
        assert err.limit_type == "max_template_shares"
        assert err.limit_value == 5
        assert err.current_usage == 5

    async def test_unlimited_tier_never_raises(self):
        """Null max_template_shares → always passes."""
        unlimited_tier = SubscriptionTier(
            id=uuid.uuid5(uuid.NAMESPACE_DNS, "sigdoc.tier.unlimited-shares"),
            name="Unlimited Shares",
            slug="unlimited-shares",
            monthly_document_limit=None,
            max_templates=None,
            max_users=None,
            bulk_generation_limit=100,
            max_template_shares=None,
            is_active=True,
        )
        tier_repo = FakeSubscriptionTierRepository(extra_tiers=[unlimited_tier])
        template_repo = FakeTemplateRepository()
        template_id = uuid.uuid4()
        for _ in range(999):
            template_repo._shares[(template_id, uuid.uuid4())] = None  # type: ignore[assignment]

        svc = make_service(tier_repo=tier_repo, template_repo=template_repo)
        await svc.check_share_limit(
            tenant_id=uuid.uuid4(),
            tier_id=unlimited_tier.id,
            template_id=template_id,
        )


# ---------------------------------------------------------------------------
# check_bulk_limit
# ---------------------------------------------------------------------------


class TestCheckBulkLimit:
    async def test_under_tier_limit_does_not_raise(self):
        """4 rows requested, tier limit = 5 → passes."""
        svc = make_service()
        await svc.check_bulk_limit(
            tenant_id=uuid.uuid4(),
            tier_id=FREE_TIER_ID,
            requested_count=4,
        )

    async def test_at_tier_limit_does_not_raise(self):
        """Exactly 5 rows = tier limit → passes (strictly greater raises)."""
        svc = make_service()
        await svc.check_bulk_limit(
            tenant_id=uuid.uuid4(),
            tier_id=FREE_TIER_ID,
            requested_count=5,
        )

    async def test_over_tier_limit_raises(self):
        """6 rows, tier limit = 5 → QuotaExceededError."""
        svc = make_service()
        with pytest.raises(QuotaExceededError) as exc_info:
            await svc.check_bulk_limit(
                tenant_id=uuid.uuid4(),
                tier_id=FREE_TIER_ID,
                requested_count=6,
            )

        err = exc_info.value
        assert err.limit_type == "bulk_generation_limit"
        assert err.limit_value == 5
        assert err.current_usage == 6

    async def test_user_override_wins_when_lower_than_tier(self):
        """user_bulk_override = 2 < tier limit 5 → effectively 2, 3 rows raises."""
        svc = make_service()
        with pytest.raises(QuotaExceededError) as exc_info:
            await svc.check_bulk_limit(
                tenant_id=uuid.uuid4(),
                tier_id=FREE_TIER_ID,
                requested_count=3,
                user_bulk_override=2,
            )

        err = exc_info.value
        assert err.limit_value == 2

    async def test_user_override_not_used_when_none(self):
        """No override → tier limit applies; 5 rows on Free (limit=5) passes."""
        svc = make_service()
        # Should not raise — exactly at tier limit
        await svc.check_bulk_limit(
            tenant_id=uuid.uuid4(),
            tier_id=FREE_TIER_ID,
            requested_count=5,
            user_bulk_override=None,
        )

    async def test_user_override_used_even_when_larger_than_tier(self):
        """user_bulk_override = 100 on Free tier (limit=5) → 100 is used as effective limit.

        This matches ADR-5: override wins unconditionally when set.
        So 50 rows requested with override=100 passes.
        """
        svc = make_service()
        await svc.check_bulk_limit(
            tenant_id=uuid.uuid4(),
            tier_id=FREE_TIER_ID,
            requested_count=50,
            user_bulk_override=100,
        )


# ---------------------------------------------------------------------------
# get_usage_summary
# ---------------------------------------------------------------------------


class TestGetUsageSummary:
    async def test_returns_correct_structure(self):
        """get_usage_summary returns a dict with tier, documents, templates, users keys."""
        tenant_id = uuid.uuid4()
        usage_repo = FakeUsageRepository()
        template_repo = FakeTemplateRepository()
        user_repo = FakeUserRepository()

        # Seed some data
        seed_usage(usage_repo, tenant_id, 10)
        seed_templates(template_repo, tenant_id, 2)
        seed_users(user_repo, tenant_id, 1)

        svc = make_service(
            usage_repo=usage_repo,
            template_repo=template_repo,
            user_repo=user_repo,
        )
        summary = await svc.get_usage_summary(tenant_id=tenant_id, tier_id=FREE_TIER_ID)

        assert "tier" in summary
        assert "documents" in summary
        assert "templates" in summary
        assert "users" in summary

    async def test_documents_usage_matches_seeded_count(self):
        tenant_id = uuid.uuid4()
        usage_repo = FakeUsageRepository()
        seed_usage(usage_repo, tenant_id, 10)

        svc = make_service(usage_repo=usage_repo)
        summary = await svc.get_usage_summary(tenant_id=tenant_id, tier_id=FREE_TIER_ID)

        docs = summary["documents"]
        assert docs["used"] == 10
        assert docs["limit"] == 50
        assert docs["percentage_used"] == 20.0
        assert docs["near_limit"] is False

    async def test_near_limit_when_80_percent(self):
        """40/50 docs → 80% → near_limit True."""
        tenant_id = uuid.uuid4()
        usage_repo = FakeUsageRepository()
        seed_usage(usage_repo, tenant_id, 40)

        svc = make_service(usage_repo=usage_repo)
        summary = await svc.get_usage_summary(tenant_id=tenant_id, tier_id=FREE_TIER_ID)

        docs = summary["documents"]
        assert docs["percentage_used"] == 80.0
        assert docs["near_limit"] is True

    async def test_unlimited_resource_has_null_percentage(self):
        """Tier with None limit → percentage_used is None, near_limit is False."""
        unlimited_tier = SubscriptionTier(
            id=uuid.uuid5(uuid.NAMESPACE_DNS, "sigdoc.tier.unlimited-sum"),
            name="Unlimited",
            slug="unlimited-sum",
            monthly_document_limit=None,
            max_templates=None,
            max_users=None,
            bulk_generation_limit=100,
            max_template_shares=None,
            is_active=True,
        )
        tier_repo = FakeSubscriptionTierRepository(extra_tiers=[unlimited_tier])
        usage_repo = FakeUsageRepository()
        tenant_id = uuid.uuid4()
        seed_usage(usage_repo, tenant_id, 999)

        svc = make_service(tier_repo=tier_repo, usage_repo=usage_repo)
        summary = await svc.get_usage_summary(
            tenant_id=tenant_id, tier_id=unlimited_tier.id
        )

        docs = summary["documents"]
        assert docs["limit"] is None
        assert docs["percentage_used"] is None
        assert docs["near_limit"] is False

    async def test_tier_info_in_summary(self):
        svc = make_service()
        summary = await svc.get_usage_summary(
            tenant_id=uuid.uuid4(), tier_id=FREE_TIER_ID
        )

        tier_info = summary["tier"]
        assert tier_info["name"] == "Free"
        assert tier_info["slug"] == "free"
        assert str(FREE_TIER_ID) == tier_info["id"]
