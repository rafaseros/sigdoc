from datetime import date, datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import UsageEvent
from app.domain.ports.usage_repository import UsageRepository as UsageRepositoryPort
from app.infrastructure.persistence.models.usage_event import UsageEventModel


def _month_start_dt(month_start: date) -> datetime:
    """Convert a date to a timezone-aware datetime at midnight UTC."""
    return datetime(month_start.year, month_start.month, month_start.day, tzinfo=timezone.utc)


def _month_end_dt(month_start: date) -> datetime:
    """Compute the first moment of the next month."""
    if month_start.month == 12:
        return datetime(month_start.year + 1, 1, 1, tzinfo=timezone.utc)
    return datetime(month_start.year, month_start.month + 1, 1, tzinfo=timezone.utc)


class SQLAlchemyUsageRepository(UsageRepositoryPort):
    def __init__(self, session: AsyncSession):
        self._session = session

    @staticmethod
    def _to_entity(model: UsageEventModel) -> UsageEvent:
        return UsageEvent(
            id=model.id,
            tenant_id=model.tenant_id,
            user_id=model.user_id,
            template_id=model.template_id,
            generation_type=model.generation_type,
            document_count=model.document_count,
            created_at=model.created_at,
        )

    async def create(self, event: UsageEvent) -> UsageEvent:
        model = UsageEventModel(
            id=event.id,
            tenant_id=event.tenant_id,
            user_id=event.user_id,
            template_id=event.template_id,
            generation_type=event.generation_type,
            document_count=event.document_count,
        )
        self._session.add(model)
        await self._session.flush()
        return self._to_entity(model)

    async def get_user_month_total(self, user_id: UUID, month_start: date) -> int:
        start_dt = _month_start_dt(month_start)
        end_dt = _month_end_dt(month_start)
        stmt = select(func.coalesce(func.sum(UsageEventModel.document_count), 0)).where(
            UsageEventModel.user_id == user_id,
            UsageEventModel.created_at >= start_dt,
            UsageEventModel.created_at < end_dt,
        )
        result = await self._session.execute(stmt)
        return int(result.scalar_one())

    async def get_tenant_month_total(self, month_start: date) -> int:
        start_dt = _month_start_dt(month_start)
        end_dt = _month_end_dt(month_start)
        stmt = select(func.coalesce(func.sum(UsageEventModel.document_count), 0)).where(
            UsageEventModel.created_at >= start_dt,
            UsageEventModel.created_at < end_dt,
        )
        result = await self._session.execute(stmt)
        return int(result.scalar_one())

    async def get_tenant_user_breakdown(self, month_start: date) -> list[dict]:
        start_dt = _month_start_dt(month_start)
        end_dt = _month_end_dt(month_start)
        stmt = (
            select(
                UsageEventModel.user_id,
                func.sum(UsageEventModel.document_count).label("total"),
            )
            .where(
                UsageEventModel.created_at >= start_dt,
                UsageEventModel.created_at < end_dt,
            )
            .group_by(UsageEventModel.user_id)
        )
        result = await self._session.execute(stmt)
        return [{"user_id": row.user_id, "total": int(row.total)} for row in result.all()]

    async def get_template_month_total(self, template_id: UUID, month_start: date) -> int:
        start_dt = _month_start_dt(month_start)
        end_dt = _month_end_dt(month_start)
        stmt = select(func.coalesce(func.sum(UsageEventModel.document_count), 0)).where(
            UsageEventModel.template_id == template_id,
            UsageEventModel.created_at >= start_dt,
            UsageEventModel.created_at < end_dt,
        )
        result = await self._session.execute(stmt)
        return int(result.scalar_one())
