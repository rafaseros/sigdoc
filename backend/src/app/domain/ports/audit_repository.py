from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from app.domain.entities import AuditLog


class AuditRepository(ABC):
    @abstractmethod
    async def create(self, entry: AuditLog) -> AuditLog:
        ...

    @abstractmethod
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
        """Return paginated audit log entries ordered by created_at DESC."""
        ...
