from datetime import datetime, timezone
from uuid import UUID

from app.domain.entities import AuditLog
from app.domain.ports.audit_repository import AuditRepository


class FakeAuditRepository(AuditRepository):
    """In-memory append-only implementation of AuditRepository for testing."""

    def __init__(self) -> None:
        self._entries: list[AuditLog] = []

    async def create(self, entry: AuditLog) -> AuditLog:
        if entry.created_at is None:
            entry.created_at = datetime.now(timezone.utc)
        self._entries.append(entry)
        return entry

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
        items = list(self._entries)

        if action is not None:
            items = [e for e in items if e.action == action]
        if actor_id is not None:
            items = [e for e in items if e.actor_id == actor_id]
        if resource_type is not None:
            items = [e for e in items if e.resource_type == resource_type]
        if date_from is not None:
            items = [e for e in items if e.created_at is not None and e.created_at >= date_from]
        if date_to is not None:
            items = [e for e in items if e.created_at is not None and e.created_at <= date_to]

        # Order by created_at DESC (mirrors SQL repo behaviour)
        items.sort(key=lambda e: e.created_at or datetime.min.replace(tzinfo=timezone.utc), reverse=True)

        total = len(items)
        offset = (page - 1) * size
        page_items = items[offset : offset + size]

        return page_items, total
