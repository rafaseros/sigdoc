from abc import ABC, abstractmethod
from datetime import date
from uuid import UUID

from app.domain.entities import UsageEvent


class UsageRepository(ABC):
    @abstractmethod
    async def create(self, event: UsageEvent) -> UsageEvent:
        ...

    @abstractmethod
    async def get_user_month_total(self, user_id: UUID, month_start: date) -> int:
        """Return the total document_count for a user in the given month."""
        ...

    @abstractmethod
    async def get_tenant_month_total(self, month_start: date) -> int:
        """Return the total document_count for the whole tenant in the given month."""
        ...

    @abstractmethod
    async def get_tenant_user_breakdown(self, month_start: date) -> list[dict]:
        """Return per-user breakdown: [{"user_id": UUID, "total": int}, ...]"""
        ...

    @abstractmethod
    async def get_template_month_total(self, template_id: UUID, month_start: date) -> int:
        """Return the total document_count for a specific template in the given month."""
        ...
