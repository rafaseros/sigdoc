from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import AuditLog
from app.domain.ports.audit_repository import AuditRepository as AuditRepositoryPort
from app.infrastructure.persistence.models.audit_log import AuditLogModel


class SQLAlchemyAuditRepository(AuditRepositoryPort):
    def __init__(self, session: AsyncSession):
        self._session = session

    @staticmethod
    def _to_entity(model: AuditLogModel) -> AuditLog:
        return AuditLog(
            id=model.id,
            tenant_id=model.tenant_id,
            actor_id=model.actor_id,
            action=model.action,
            resource_type=model.resource_type,
            resource_id=model.resource_id,
            details=model.details,
            ip_address=model.ip_address,
            created_at=model.created_at,
        )

    async def create(self, entry: AuditLog) -> AuditLog:
        model = AuditLogModel(
            id=entry.id,
            tenant_id=entry.tenant_id,
            actor_id=entry.actor_id,
            action=entry.action,
            resource_type=entry.resource_type,
            resource_id=entry.resource_id,
            details=entry.details,
            ip_address=entry.ip_address,
        )
        self._session.add(model)
        await self._session.flush()
        return self._to_entity(model)

    async def list_paginated(
        self,
        page: int = 1,
        size: int = 20,
        action: str | None = None,
        actor_id: UUID | None = None,
        resource_type: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> tuple[list[AuditLog], int]:
        stmt = select(AuditLogModel)
        count_stmt = select(func.count()).select_from(AuditLogModel)

        filters = []
        if action is not None:
            filters.append(AuditLogModel.action == action)
        if actor_id is not None:
            filters.append(AuditLogModel.actor_id == actor_id)
        if resource_type is not None:
            filters.append(AuditLogModel.resource_type == resource_type)
        if date_from is not None:
            filters.append(AuditLogModel.created_at >= date_from)
        if date_to is not None:
            filters.append(AuditLogModel.created_at <= date_to)

        if filters:
            stmt = stmt.where(*filters)
            count_stmt = count_stmt.where(*filters)

        total_result = await self._session.execute(count_stmt)
        total = total_result.scalar_one()

        offset = (page - 1) * size
        stmt = stmt.order_by(AuditLogModel.created_at.desc()).offset(offset).limit(size)

        result = await self._session.execute(stmt)
        entries = [self._to_entity(m) for m in result.scalars().all()]

        return entries, total
