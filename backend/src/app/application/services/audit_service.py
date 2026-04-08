"""AuditService — fire-and-forget audit logging (task 4.4 GREEN).

Design decisions (ADR-2, ADR-3):
- log() spawns asyncio.create_task() so the audit write never blocks or rolls
  back the caller's business transaction.
- _write() opens its own DB session and commits independently.
- AuditService is testable by passing an audit_repo directly — the session
  factory path is used only in production (via get_audit_service() DI factory).
- Failure in _write() is caught and logged — never re-raised.
"""
import asyncio
import logging
import uuid
from datetime import datetime
from uuid import UUID

from app.domain.entities import AuditLog
from app.domain.ports.audit_repository import AuditRepository

logger = logging.getLogger(__name__)


class AuditService:
    def __init__(
        self,
        session_factory=None,  # async_sessionmaker — used in production
        audit_repo: AuditRepository | None = None,  # injected directly in tests
    ) -> None:
        self._session_factory = session_factory
        self._audit_repo = audit_repo

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def log(
        self,
        actor_id: UUID | None,
        tenant_id: UUID,
        action: str,
        resource_type: str | None = None,
        resource_id: UUID | None = None,
        details: dict | None = None,
        ip_address: str | None = None,
    ) -> None:
        """Fire-and-forget: spawn an asyncio task to persist the audit entry.

        Returns immediately — the write happens asynchronously.
        Failure in _write() is swallowed; the caller's request is unaffected.
        """
        entry = AuditLog(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            actor_id=actor_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            ip_address=ip_address,
        )
        asyncio.create_task(self._write(entry))

    async def list_audit_logs(
        self,
        page: int = 1,
        size: int = 50,
        action: str | None = None,
        actor_id: UUID | None = None,
        resource_type: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> tuple[list[AuditLog], int]:
        """Paginated read of audit log entries.

        Uses the injected repo (test) or opens a fresh session (production).
        """
        if self._audit_repo is not None:
            return await self._audit_repo.list_paginated(
                page=page,
                size=size,
                action=action,
                actor_id=actor_id,
                resource_type=resource_type,
                date_from=date_from,
                date_to=date_to,
            )

        # Production path: open a fresh session for the read
        from app.infrastructure.persistence.repositories.audit_repository import (
            SQLAlchemyAuditRepository,
        )

        async with self._session_factory() as session:
            repo = SQLAlchemyAuditRepository(session)
            return await repo.list_paginated(
                page=page,
                size=size,
                action=action,
                actor_id=actor_id,
                resource_type=resource_type,
                date_from=date_from,
                date_to=date_to,
            )

    # ------------------------------------------------------------------
    # Internal write — overridable for testing
    # ------------------------------------------------------------------

    async def _write(self, entry: AuditLog) -> None:
        """Persist a single AuditLog entry.

        Wraps everything in try/except so failures are never propagated.
        Uses the injected repo in tests or creates a fresh session in production.
        """
        try:
            if self._audit_repo is not None:
                await self._audit_repo.create(entry)
                return

            # Production path: import here to avoid circular imports at module level
            from app.infrastructure.persistence.repositories.audit_repository import (
                SQLAlchemyAuditRepository,
            )

            async with self._session_factory() as session:
                repo = SQLAlchemyAuditRepository(session)
                await repo.create(entry)
                await session.commit()

        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "AuditService._write() failed — audit entry not persisted. "
                "action=%s actor_id=%s error=%s",
                entry.action,
                entry.actor_id,
                exc,
            )
