"""Unit tests for UsageService (task 4.1 RED)."""
import uuid
from datetime import date, datetime, timezone

import pytest

from app.application.services.usage_service import UsageService
from app.domain.entities import UsageEvent
from tests.fakes import FakeUsageRepository


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_service(repo: FakeUsageRepository) -> UsageService:
    return UsageService(usage_repo=repo)


def make_event(
    user_id: uuid.UUID,
    tenant_id: uuid.UUID,
    template_id: uuid.UUID,
    generation_type: str = "single",
    document_count: int = 1,
    created_at: datetime | None = None,
) -> UsageEvent:
    return UsageEvent(
        id=uuid.uuid4(),
        user_id=user_id,
        tenant_id=tenant_id,
        template_id=template_id,
        generation_type=generation_type,
        document_count=document_count,
        created_at=created_at,
    )


# ---------------------------------------------------------------------------
# record()
# ---------------------------------------------------------------------------


class TestUsageServiceRecord:
    async def test_record_appends_event_to_repo(
        self,
        fake_usage_repo: FakeUsageRepository,
    ):
        """record() should create a UsageEvent in the repository."""
        service = make_service(fake_usage_repo)

        user_id = uuid.uuid4()
        tenant_id = uuid.uuid4()
        template_id = uuid.uuid4()

        await service.record(
            user_id=user_id,
            tenant_id=tenant_id,
            template_id=template_id,
            generation_type="single",
            document_count=1,
        )

        assert len(fake_usage_repo._events) == 1
        event = fake_usage_repo._events[0]
        assert event.user_id == user_id
        assert event.tenant_id == tenant_id
        assert event.template_id == template_id
        assert event.generation_type == "single"
        assert event.document_count == 1

    async def test_record_bulk_stores_correct_count(
        self,
        fake_usage_repo: FakeUsageRepository,
    ):
        """record() with bulk type stores the correct document_count."""
        service = make_service(fake_usage_repo)

        await service.record(
            user_id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            template_id=uuid.uuid4(),
            generation_type="bulk",
            document_count=5,
        )

        assert len(fake_usage_repo._events) == 1
        assert fake_usage_repo._events[0].document_count == 5
        assert fake_usage_repo._events[0].generation_type == "bulk"

    async def test_record_failure_is_swallowed_not_raised(
        self,
        fake_usage_repo: FakeUsageRepository,
    ):
        """If the repo raises, record() must NOT propagate the exception."""

        class FailingRepo(FakeUsageRepository):
            async def create(self, event):
                raise RuntimeError("DB is down")

        service = make_service(FailingRepo())

        # Should NOT raise — failure must be swallowed
        await service.record(
            user_id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            template_id=uuid.uuid4(),
            generation_type="single",
            document_count=1,
        )

    async def test_record_without_template_id_is_allowed(
        self,
        fake_usage_repo: FakeUsageRepository,
    ):
        """template_id is optional — record() should accept None."""
        service = make_service(fake_usage_repo)

        await service.record(
            user_id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            template_id=None,
            generation_type="single",
            document_count=1,
        )

        assert len(fake_usage_repo._events) == 1
        assert fake_usage_repo._events[0].template_id is None


# ---------------------------------------------------------------------------
# get_current_month_usage()
# ---------------------------------------------------------------------------


class TestGetCurrentMonthUsage:
    async def test_returns_sum_for_user_in_current_month(
        self,
        fake_usage_repo: FakeUsageRepository,
    ):
        """get_current_month_usage() sums document_count for the user in the given month."""
        service = make_service(fake_usage_repo)

        user_id = uuid.uuid4()
        tenant_id = uuid.uuid4()
        template_id = uuid.uuid4()
        year, month = 2026, 4
        ts = datetime(2026, 4, 15, 12, 0, 0, tzinfo=timezone.utc)

        # Seed two events for this user
        await fake_usage_repo.create(
            make_event(user_id, tenant_id, template_id, document_count=3, created_at=ts)
        )
        await fake_usage_repo.create(
            make_event(user_id, tenant_id, template_id, document_count=2, created_at=ts)
        )

        total = await service.get_current_month_usage(
            user_id=user_id, year=year, month=month
        )

        assert total == 5

    async def test_excludes_other_users(
        self,
        fake_usage_repo: FakeUsageRepository,
    ):
        """get_current_month_usage() only counts the specified user's events."""
        service = make_service(fake_usage_repo)

        user_a = uuid.uuid4()
        user_b = uuid.uuid4()
        tenant_id = uuid.uuid4()
        template_id = uuid.uuid4()
        ts = datetime(2026, 4, 10, tzinfo=timezone.utc)

        await fake_usage_repo.create(
            make_event(user_a, tenant_id, template_id, document_count=4, created_at=ts)
        )
        await fake_usage_repo.create(
            make_event(user_b, tenant_id, template_id, document_count=10, created_at=ts)
        )

        total = await service.get_current_month_usage(user_id=user_a, year=2026, month=4)
        assert total == 4

    async def test_returns_zero_when_no_events(
        self,
        fake_usage_repo: FakeUsageRepository,
    ):
        """Returns 0 when the user has no events in the given month."""
        service = make_service(fake_usage_repo)

        total = await service.get_current_month_usage(
            user_id=uuid.uuid4(), year=2026, month=4
        )
        assert total == 0


# ---------------------------------------------------------------------------
# get_tenant_usage()
# ---------------------------------------------------------------------------


class TestGetTenantUsage:
    async def test_returns_total_and_per_user_breakdown(
        self,
        fake_usage_repo: FakeUsageRepository,
    ):
        """get_tenant_usage() returns total + per-user breakdown dict."""
        service = make_service(fake_usage_repo)

        user_a = uuid.uuid4()
        user_b = uuid.uuid4()
        tenant_id = uuid.uuid4()
        template_id = uuid.uuid4()
        ts = datetime(2026, 4, 5, tzinfo=timezone.utc)

        await fake_usage_repo.create(
            make_event(user_a, tenant_id, template_id, document_count=3, created_at=ts)
        )
        await fake_usage_repo.create(
            make_event(user_b, tenant_id, template_id, document_count=7, created_at=ts)
        )

        result = await service.get_tenant_usage(year=2026, month=4)

        assert result["total"] == 10
        assert "by_user" in result
        # Check that both users appear in breakdown
        user_ids_in_breakdown = {row["user_id"] for row in result["by_user"]}
        assert user_a in user_ids_in_breakdown
        assert user_b in user_ids_in_breakdown

    async def test_returns_zero_total_when_empty(
        self,
        fake_usage_repo: FakeUsageRepository,
    ):
        """Returns total=0 and empty by_user when no events exist."""
        service = make_service(fake_usage_repo)

        result = await service.get_tenant_usage(year=2026, month=4)

        assert result["total"] == 0
        assert result["by_user"] == []
