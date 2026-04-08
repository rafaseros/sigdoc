from datetime import date, datetime, timezone
from uuid import UUID

from app.domain.entities import UsageEvent
from app.domain.ports.usage_repository import UsageRepository


def _month_start_dt(month_start: date) -> datetime:
    """Convert a date to a timezone-aware datetime at midnight UTC."""
    return datetime(month_start.year, month_start.month, month_start.day, tzinfo=timezone.utc)


def _month_end_dt(month_start: date) -> datetime:
    """Compute the first moment of the next month."""
    if month_start.month == 12:
        return datetime(month_start.year + 1, 1, 1, tzinfo=timezone.utc)
    return datetime(month_start.year, month_start.month + 1, 1, tzinfo=timezone.utc)


class FakeUsageRepository(UsageRepository):
    """In-memory implementation of UsageRepository for testing."""

    def __init__(self) -> None:
        self._events: list[UsageEvent] = []

    async def create(self, event: UsageEvent) -> UsageEvent:
        if event.created_at is None:
            event.created_at = datetime.now(timezone.utc)
        self._events.append(event)
        return event

    async def get_user_month_total(self, user_id: UUID, month_start: date) -> int:
        start = _month_start_dt(month_start)
        end = _month_end_dt(month_start)
        return sum(
            e.document_count
            for e in self._events
            if e.user_id == user_id
            and e.created_at is not None
            and start <= e.created_at < end
        )

    async def get_tenant_month_total(self, month_start: date) -> int:
        start = _month_start_dt(month_start)
        end = _month_end_dt(month_start)
        return sum(
            e.document_count
            for e in self._events
            if e.created_at is not None and start <= e.created_at < end
        )

    async def get_tenant_user_breakdown(self, month_start: date) -> list[dict]:
        start = _month_start_dt(month_start)
        end = _month_end_dt(month_start)
        totals: dict[UUID, int] = {}
        for e in self._events:
            if e.created_at is not None and start <= e.created_at < end:
                totals[e.user_id] = totals.get(e.user_id, 0) + e.document_count
        return [{"user_id": uid, "total": total} for uid, total in totals.items()]

    async def get_template_month_total(self, template_id: UUID, month_start: date) -> int:
        start = _month_start_dt(month_start)
        end = _month_end_dt(month_start)
        return sum(
            e.document_count
            for e in self._events
            if e.template_id == template_id
            and e.created_at is not None
            and start <= e.created_at < end
        )
