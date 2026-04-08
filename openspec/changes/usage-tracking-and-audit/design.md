# Technical Design: usage-tracking-and-audit

**Status**: Draft
**Change**: usage-tracking-and-audit
**Date**: 2026-04-08

---

## 1. Overview

This design adds two subsystems to SigDoc: **usage tracking** (document generation metrics per user/tenant/month) and **audit logging** (immutable record of all significant actions). Both follow the existing clean architecture pattern: domain entity, port (ABC), SQLAlchemy adapter, application service, presentation schema, and API router.

---

## 2. Data Model

### 2.1 `usage_events` Table

```sql
CREATE TABLE usage_events (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   UUID        NOT NULL REFERENCES tenants(id),
    user_id     UUID        NOT NULL REFERENCES users(id),
    template_id UUID        NOT NULL REFERENCES templates(id),
    generation_type VARCHAR(10) NOT NULL,  -- 'single' | 'bulk'
    document_count  INTEGER     NOT NULL DEFAULT 1,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Monthly aggregation index (the critical query)
CREATE INDEX ix_usage_events_tenant_month
    ON usage_events (tenant_id, created_at);

-- Per-user monthly aggregation
CREATE INDEX ix_usage_events_user_month
    ON usage_events (user_id, created_at);

-- Per-template breakdown
CREATE INDEX ix_usage_events_template
    ON usage_events (template_id);
```

**Design decisions**:
- `template_id` references `templates.id` (not `template_versions.id`) because usage quota cares about the template, not the version.
- `document_count` is 1 for single generation, N for bulk. This avoids joining to count documents — `SUM(document_count) WHERE user_id = ? AND created_at >= month_start` is the subscription-tier query.
- No `updated_at` column. Usage events are append-only.
- Uses `TenantMixin` for automatic tenant_id FK and index, same as all other models.

### 2.2 `audit_logs` Table

```sql
CREATE TABLE audit_logs (
    id            UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id     UUID          NOT NULL REFERENCES tenants(id),
    actor_id      UUID          REFERENCES users(id),  -- NULL for system actions
    action        VARCHAR(50)   NOT NULL,               -- e.g. 'template.upload'
    resource_type VARCHAR(30)   NOT NULL,               -- e.g. 'template', 'document'
    resource_id   UUID,                                 -- NULL when N/A
    details       JSONB,                                -- arbitrary metadata
    ip_address    VARCHAR(45),                          -- supports IPv6
    created_at    TIMESTAMPTZ   NOT NULL DEFAULT now()
);

-- Primary query: tenant audit log, newest first
CREATE INDEX ix_audit_logs_tenant_created
    ON audit_logs (tenant_id, created_at DESC);

-- Filter by action type
CREATE INDEX ix_audit_logs_action
    ON audit_logs (action);

-- Filter by actor
CREATE INDEX ix_audit_logs_actor
    ON audit_logs (actor_id);
```

**Design decisions**:
- **NO `updated_at` column**. This table is append-only. The repository will only expose `create()` and `list_paginated()` — no update or delete methods.
- `actor_id` is nullable for future system-triggered events (scheduled cleanup, webhook events).
- `details` is JSONB for flexibility — each action type can store different metadata (e.g., template name for `template.delete`, row count for `document.generate_bulk`).
- `ip_address` is VARCHAR(45) to support IPv6 addresses (max 45 chars for full notation).

### 2.3 Action Enum

Actions are string constants, not a DB enum, for extensibility:

```python
class AuditAction:
    TEMPLATE_UPLOAD     = "template.upload"
    TEMPLATE_DELETE     = "template.delete"
    TEMPLATE_VERSION    = "template.version"
    TEMPLATE_SHARE      = "template.share"
    TEMPLATE_UNSHARE    = "template.unshare"
    DOCUMENT_GENERATE   = "document.generate"
    DOCUMENT_GENERATE_BULK = "document.generate_bulk"
    DOCUMENT_DELETE      = "document.delete"
    USER_CREATE          = "user.create"
    USER_UPDATE          = "user.update"
    USER_DEACTIVATE      = "user.deactivate"
    AUTH_LOGIN            = "auth.login"
    AUTH_LOGIN_FAILED     = "auth.login_failed"
    AUTH_CHANGE_PASSWORD  = "auth.change_password"
```

Stored in `app/domain/entities/audit_log.py` as class-level constants on the `AuditLog` dataclass.

---

## 3. Domain Layer

### 3.1 New Entities

**`app/domain/entities/usage_event.py`**:
```python
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass
class UsageEvent:
    id: UUID
    tenant_id: UUID
    user_id: UUID
    template_id: UUID
    generation_type: str  # "single" | "bulk"
    document_count: int
    created_at: datetime | None = None
```

**`app/domain/entities/audit_log.py`**:
```python
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


class AuditAction:
    """String constants for audit actions. Not a DB enum — extensible."""
    TEMPLATE_UPLOAD = "template.upload"
    TEMPLATE_DELETE = "template.delete"
    TEMPLATE_VERSION = "template.version"
    TEMPLATE_SHARE = "template.share"
    TEMPLATE_UNSHARE = "template.unshare"
    DOCUMENT_GENERATE = "document.generate"
    DOCUMENT_GENERATE_BULK = "document.generate_bulk"
    DOCUMENT_DELETE = "document.delete"
    USER_CREATE = "user.create"
    USER_UPDATE = "user.update"
    USER_DEACTIVATE = "user.deactivate"
    AUTH_LOGIN = "auth.login"
    AUTH_LOGIN_FAILED = "auth.login_failed"
    AUTH_CHANGE_PASSWORD = "auth.change_password"


@dataclass
class AuditLog:
    id: UUID
    tenant_id: UUID
    action: str
    resource_type: str
    actor_id: UUID | None = None
    resource_id: UUID | None = None
    details: dict | None = None
    ip_address: str | None = None
    created_at: datetime | None = None
```

### 3.2 Entities `__init__.py` Update

Add `UsageEvent` and `AuditLog` to `app/domain/entities/__init__.py`.

---

## 4. Ports (Repository Interfaces)

### 4.1 `UsageRepository` — `app/domain/ports/usage_repository.py`

```python
from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from app.domain.entities.usage_event import UsageEvent


class UsageRepository(ABC):
    @abstractmethod
    async def create(self, event: UsageEvent) -> UsageEvent:
        """Record a single usage event."""
        ...

    @abstractmethod
    async def get_user_month_total(
        self, user_id: UUID, month_start: datetime
    ) -> int:
        """Return SUM(document_count) for user since month_start."""
        ...

    @abstractmethod
    async def get_tenant_month_total(
        self, month_start: datetime
    ) -> int:
        """Return SUM(document_count) for entire tenant since month_start.
        Tenant filtering is handled by TenantMixin/do_orm_execute."""
        ...

    @abstractmethod
    async def get_tenant_user_breakdown(
        self, month_start: datetime
    ) -> list[dict]:
        """Return per-user document_count for the tenant since month_start.
        Returns: [{"user_id": UUID, "total": int}, ...]"""
        ...

    @abstractmethod
    async def get_template_month_total(
        self, template_id: UUID, month_start: datetime
    ) -> int:
        """Return SUM(document_count) for a specific template since month_start."""
        ...
```

**ADR-1: Separate repositories, not combined.**
Usage and audit have fundamentally different write patterns (sync vs async), query patterns (aggregation vs paginated list), and lifecycle expectations (usage feeds quotas, audit is for compliance). Combining them would create a god-repository that violates SRP.

### 4.2 `AuditRepository` — `app/domain/ports/audit_repository.py`

```python
from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from app.domain.entities.audit_log import AuditLog


class AuditRepository(ABC):
    @abstractmethod
    async def create(self, entry: AuditLog) -> AuditLog:
        """Insert a single audit log entry. Append-only."""
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
        """Paginated query with filters. Tenant scoping via do_orm_execute."""
        ...
```

**Note**: No `update()`, no `delete()`. The port interface enforces immutability at the architectural level — there is no way for any layer above to mutate or remove audit entries.

### 4.3 Ports `__init__.py` Update

Add `UsageRepository` and `AuditRepository` to `app/domain/ports/__init__.py`.

---

## 5. Infrastructure Layer (Persistence)

### 5.1 ORM Models

**`app/infrastructure/persistence/models/usage_event.py`**:
```python
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from ..database import TenantMixin
from .base import Base, UUIDMixin


class UsageEventModel(UUIDMixin, TenantMixin, Base):
    __tablename__ = "usage_events"
    __table_args__ = (
        Index("ix_usage_events_tenant_month", "tenant_id", "created_at"),
        Index("ix_usage_events_user_month", "user_id", "created_at"),
        Index("ix_usage_events_template", "template_id"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )
    template_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("templates.id"), nullable=False
    )
    generation_type: Mapped[str] = mapped_column(String(10), nullable=False)
    document_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )
```

**`app/infrastructure/persistence/models/audit_log.py`**:
```python
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ..database import TenantMixin
from .base import Base, UUIDMixin


class AuditLogModel(UUIDMixin, TenantMixin, Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_tenant_created", "tenant_id", "created_at"),
        Index("ix_audit_logs_action", "action"),
        Index("ix_audit_logs_actor", "actor_id"),
    )

    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(30), nullable=False)
    resource_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )
```

**Note**: Neither model uses `TimestampMixin` (which adds `updated_at`). Both define only `created_at`. This is deliberate — append-only tables have no use for `updated_at`.

### 5.2 Models `__init__.py` Update

Add `UsageEventModel` and `AuditLogModel` to `app/infrastructure/persistence/models/__init__.py`.

### 5.3 Repository Implementations

**`app/infrastructure/persistence/repositories/usage_repository.py`**:

SQLAlchemy adapter implementing `UsageRepository`. Key query for subscription-tier readiness:

```python
from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.usage_event import UsageEvent
from app.domain.ports.usage_repository import UsageRepository as UsageRepositoryPort
from app.infrastructure.persistence.models.usage_event import UsageEventModel


class SQLAlchemyUsageRepository(UsageRepositoryPort):
    def __init__(self, session: AsyncSession):
        self._session = session

    def _to_orm(self, event: UsageEvent) -> UsageEventModel:
        return UsageEventModel(
            id=event.id,
            tenant_id=event.tenant_id,
            user_id=event.user_id,
            template_id=event.template_id,
            generation_type=event.generation_type,
            document_count=event.document_count,
        )

    def _to_domain(self, model: UsageEventModel) -> UsageEvent:
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
        orm = self._to_orm(event)
        self._session.add(orm)
        await self._session.flush()
        return self._to_domain(orm)

    async def get_user_month_total(self, user_id: UUID, month_start: datetime) -> int:
        stmt = (
            select(func.coalesce(func.sum(UsageEventModel.document_count), 0))
            .where(UsageEventModel.user_id == user_id)
            .where(UsageEventModel.created_at >= month_start)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def get_tenant_month_total(self, month_start: datetime) -> int:
        # Tenant filtering by do_orm_execute (TenantMixin)
        stmt = (
            select(func.coalesce(func.sum(UsageEventModel.document_count), 0))
            .where(UsageEventModel.created_at >= month_start)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def get_tenant_user_breakdown(self, month_start: datetime) -> list[dict]:
        stmt = (
            select(
                UsageEventModel.user_id,
                func.sum(UsageEventModel.document_count).label("total"),
            )
            .where(UsageEventModel.created_at >= month_start)
            .group_by(UsageEventModel.user_id)
        )
        result = await self._session.execute(stmt)
        return [{"user_id": row.user_id, "total": row.total} for row in result.all()]

    async def get_template_month_total(self, template_id: UUID, month_start: datetime) -> int:
        stmt = (
            select(func.coalesce(func.sum(UsageEventModel.document_count), 0))
            .where(UsageEventModel.template_id == template_id)
            .where(UsageEventModel.created_at >= month_start)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one()
```

**`app/infrastructure/persistence/repositories/audit_repository.py`**:

```python
from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.audit_log import AuditLog
from app.domain.ports.audit_repository import AuditRepository as AuditRepositoryPort
from app.infrastructure.persistence.models.audit_log import AuditLogModel


class SQLAlchemyAuditRepository(AuditRepositoryPort):
    def __init__(self, session: AsyncSession):
        self._session = session

    def _to_orm(self, entry: AuditLog) -> AuditLogModel:
        return AuditLogModel(
            id=entry.id,
            tenant_id=entry.tenant_id,
            actor_id=entry.actor_id,
            action=entry.action,
            resource_type=entry.resource_type,
            resource_id=entry.resource_id,
            details=entry.details,
            ip_address=entry.ip_address,
        )

    def _to_domain(self, model: AuditLogModel) -> AuditLog:
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
        orm = self._to_orm(entry)
        self._session.add(orm)
        await self._session.flush()
        return self._to_domain(orm)

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

        if action:
            stmt = stmt.where(AuditLogModel.action == action)
            count_stmt = count_stmt.where(AuditLogModel.action == action)
        if actor_id:
            stmt = stmt.where(AuditLogModel.actor_id == actor_id)
            count_stmt = count_stmt.where(AuditLogModel.actor_id == actor_id)
        if resource_type:
            stmt = stmt.where(AuditLogModel.resource_type == resource_type)
            count_stmt = count_stmt.where(AuditLogModel.resource_type == resource_type)
        if date_from:
            stmt = stmt.where(AuditLogModel.created_at >= date_from)
            count_stmt = count_stmt.where(AuditLogModel.created_at >= date_from)
        if date_to:
            stmt = stmt.where(AuditLogModel.created_at <= date_to)
            count_stmt = count_stmt.where(AuditLogModel.created_at <= date_to)

        total_result = await self._session.execute(count_stmt)
        total = total_result.scalar_one()

        offset = (page - 1) * size
        stmt = stmt.order_by(AuditLogModel.created_at.desc()).offset(offset).limit(size)
        result = await self._session.execute(stmt)
        entries = [self._to_domain(row) for row in result.scalars().all()]

        return entries, total
```

---

## 6. Application Layer (Services)

### 6.1 `UsageService` — `app/application/services/usage_service.py`

**Synchronous write (within the same DB transaction)**. Usage data feeds quota enforcement, so it MUST be committed with the operation that created it.

```python
import uuid
from datetime import datetime, timezone
from uuid import UUID

from app.domain.entities.usage_event import UsageEvent
from app.domain.ports.usage_repository import UsageRepository


class UsageService:
    def __init__(self, repository: UsageRepository):
        self._repository = repository

    async def record(
        self,
        user_id: UUID,
        tenant_id: UUID,
        template_id: UUID,
        generation_type: str,
        document_count: int,
    ) -> UsageEvent:
        """Record a usage event. Called synchronously within the request transaction."""
        event = UsageEvent(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            user_id=user_id,
            template_id=template_id,
            generation_type=generation_type,
            document_count=document_count,
        )
        return await self._repository.create(event)

    async def get_current_month_usage(self, user_id: UUID) -> int:
        """Get document count for user in current calendar month."""
        month_start = datetime.now(timezone.utc).replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )
        return await self._repository.get_user_month_total(user_id, month_start)

    async def get_tenant_usage(self) -> dict:
        """Get tenant-level usage for current month."""
        month_start = datetime.now(timezone.utc).replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )
        total = await self._repository.get_tenant_month_total(month_start)
        breakdown = await self._repository.get_tenant_user_breakdown(month_start)
        return {
            "total": total,
            "month_start": month_start.isoformat(),
            "users": breakdown,
        }
```

### 6.2 `AuditService` — `app/application/services/audit_service.py`

**ADR-2: Fire-and-forget via dedicated session, not `asyncio.create_task()` with shared session.**

The critical design decision: audit writes MUST NOT share the request's DB session because:
1. The request session is committed/rolled back by `get_session()`. If audit write fails, it would roll back the business operation.
2. `asyncio.create_task()` can outlive the request scope — the shared session may already be closed.

**Solution**: `AuditService` receives a **session factory** (`async_session_factory`), not a session instance. Each `log()` call creates a fresh session, writes, commits, and closes it — fully independent of the request lifecycle.

```python
import asyncio
import logging
import uuid
from uuid import UUID

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.domain.entities.audit_log import AuditLog
from app.infrastructure.persistence.repositories.audit_repository import (
    SQLAlchemyAuditRepository,
)

logger = logging.getLogger(__name__)


class AuditService:
    def __init__(self, session_factory: async_sessionmaker):
        self._session_factory = session_factory

    def log(
        self,
        tenant_id: UUID,
        action: str,
        resource_type: str,
        actor_id: UUID | None = None,
        resource_id: UUID | None = None,
        details: dict | None = None,
        ip_address: str | None = None,
    ) -> None:
        """Fire-and-forget audit log entry. Non-blocking."""
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

    async def _write(self, entry: AuditLog) -> None:
        """Write audit entry in an independent session. Errors are logged, not raised."""
        try:
            async with self._session_factory() as session:
                if entry.tenant_id:
                    session.info["tenant_id"] = entry.tenant_id
                repo = SQLAlchemyAuditRepository(session)
                await repo.create(entry)
                await session.commit()
        except Exception:
            logger.exception("Failed to write audit log: %s", entry.action)

    async def list_audit_logs(
        self,
        tenant_id: UUID,
        page: int = 1,
        size: int = 20,
        action: str | None = None,
        actor_id: UUID | None = None,
        resource_type: str | None = None,
        date_from=None,
        date_to=None,
    ) -> tuple[list[AuditLog], int]:
        """Read audit logs — uses a fresh session (read path)."""
        async with self._session_factory() as session:
            session.info["tenant_id"] = tenant_id
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
```

**Key characteristics**:
- `log()` is a synchronous method that returns immediately (non-blocking). It spawns an `asyncio.create_task()`.
- `_write()` creates its own session, commits, closes. If it fails, the error is logged but the parent request is NOT affected.
- `list_audit_logs()` is a normal async method for the read API (paginated, with filters).

**ADR-3: Why `AuditService` imports the SQLAlchemy repository directly (violation of pure ports?)**

The `AuditService` needs to instantiate a repository per-call with a fresh session. The port ABC defines the interface, but the service needs to create concrete instances. Two options:

1. **Pass a repository factory function** — cleaner but adds a lambda/callable parameter to every DI chain.
2. **Import the concrete repository** — simpler, and the `AuditService` already lives in the application layer, which is allowed to know about infrastructure when justified.

We choose option 2 for simplicity. The read path (`list_audit_logs`) also creates its own session. If we need to test `AuditService` in isolation, we inject a fake `session_factory` that yields a mock session.

---

## 7. Service Integration Points

### 7.1 `DocumentService` Changes

Add `usage_service: UsageService | None = None` and `audit_service: AuditService | None = None` to `__init__()`. Both are optional with `None` default for backward compatibility (existing tests pass without change).

**`generate_single()` — after line 106** (after `document = await self._doc_repo.create(document)`):
```python
# Usage tracking (sync — within same transaction)
if self._usage_service:
    await self._usage_service.record(
        user_id=uuid.UUID(created_by),
        tenant_id=uuid.UUID(tenant_id),
        template_id=version.template_id,
        generation_type="single",
        document_count=1,
    )

# Audit logging (fire-and-forget)
if self._audit_service:
    self._audit_service.log(
        tenant_id=uuid.UUID(tenant_id),
        actor_id=uuid.UUID(created_by),
        action=AuditAction.DOCUMENT_GENERATE,
        resource_type="document",
        resource_id=doc_id,
        details={"template_id": str(version.template_id), "file_name": file_name},
        ip_address=ip_address,
    )
```

**`generate_bulk()` — after line 401** (after `await self._doc_repo.create_batch(documents)`):
```python
# Usage tracking (sync — count only successful docs)
if self._usage_service:
    await self._usage_service.record(
        user_id=uuid.UUID(created_by),
        tenant_id=uuid.UUID(tenant_id),
        template_id=version.template_id,
        generation_type="bulk",
        document_count=len(results["success"]),
    )

# Audit logging (fire-and-forget)
if self._audit_service:
    self._audit_service.log(
        tenant_id=uuid.UUID(tenant_id),
        actor_id=uuid.UUID(created_by),
        action=AuditAction.DOCUMENT_GENERATE_BULK,
        resource_type="document",
        resource_id=batch_id,
        details={
            "template_id": str(version.template_id),
            "document_count": len(results["success"]),
            "error_count": len(results["errors"]),
        },
        ip_address=ip_address,
    )
```

**`delete_document()` — after line 153** (after `await self._doc_repo.delete(document_id)`):
```python
if self._audit_service:
    self._audit_service.log(
        tenant_id=document.tenant_id,
        actor_id=None,  # caller must pass actor context
        action=AuditAction.DOCUMENT_DELETE,
        resource_type="document",
        resource_id=document_id,
        details={"file_name": document.file_name},
        ip_address=ip_address,
    )
```

**Note on `ip_address` propagation**: `DocumentService` methods gain an optional `ip_address: str | None = None` parameter. The presentation layer (router) extracts it from `request.client.host` and passes it down.

### 7.2 `TemplateService` Changes

Add `audit_service: AuditService | None = None` to `__init__()`.

| Method | After which line | Action |
|--------|-----------------|--------|
| `upload_template()` | After `template = await self._repository.create_template_with_version(...)` | `AuditAction.TEMPLATE_UPLOAD` |
| `upload_new_version()` | After `await self._repository.create_version(version_entity)` | `AuditAction.TEMPLATE_VERSION` |
| `delete_template()` | After `await self._repository.delete(template_id)` | `AuditAction.TEMPLATE_DELETE` |
| `share_template()` | After `await self._repository.add_share(...)` | `AuditAction.TEMPLATE_SHARE` |
| `unshare_template()` | After `await self._repository.remove_share(...)` | `AuditAction.TEMPLATE_UNSHARE` |

All follow the same pattern: `if self._audit_service: self._audit_service.log(...)`.

### 7.3 Auth Router Changes

The `auth.py` router calls repositories directly (not through a service). Audit logging for `auth.login` and `auth.login_failed` is added directly in the router:

```python
# In login endpoint, after successful auth:
if audit_service:
    audit_service.log(
        tenant_id=user.tenant_id,
        actor_id=user.id,
        action=AuditAction.AUTH_LOGIN,
        resource_type="auth",
        ip_address=request.client.host if request.client else None,
    )

# After failed auth:
if audit_service:
    audit_service.log(
        tenant_id=user.tenant_id if user else None,  # may be None if email not found
        actor_id=user.id if user else None,
        action=AuditAction.AUTH_LOGIN_FAILED,
        resource_type="auth",
        details={"email": body.email},
        ip_address=request.client.host if request.client else None,
    )
```

**ADR-4: For failed login where user is not found, we skip audit (tenant_id is required).**
The `audit_logs` table requires `tenant_id` (NOT NULL). If the email doesn't match any user, we have no tenant_id. Options:
1. Make `tenant_id` nullable — pollutes the table with non-tenant-scoped entries.
2. Skip audit for unknown emails — simpler, and brute-force detection is better handled by rate limiting.
3. Log to a separate table — overengineered.

We choose option 2. Auth failures for existing users ARE logged (we know the tenant).

### 7.4 Users Router Changes

The `users.py` router creates/updates/deactivates users directly via repository. Audit logging is added in the router (same pattern as auth):

| Endpoint | Action |
|----------|--------|
| `create_user()` | `AuditAction.USER_CREATE` with `resource_id=created.id` |
| `update_user()` | `AuditAction.USER_UPDATE` with `resource_id=user_id`, `details=update_data` |
| `deactivate_user()` | `AuditAction.USER_DEACTIVATE` with `resource_id=user_id` |

### 7.5 Change Password Audit

In `auth.py` `change_password()` endpoint, after successful password change:
```python
if audit_service:
    audit_service.log(
        tenant_id=current_user.tenant_id,
        actor_id=current_user.user_id,
        action=AuditAction.AUTH_CHANGE_PASSWORD,
        resource_type="auth",
        ip_address=request.client.host if request.client else None,
    )
```

---

## 8. Dependency Injection

### 8.1 New Factory Functions — `app/application/services/__init__.py`

```python
from app.application.services.usage_service import UsageService
from app.application.services.audit_service import AuditService
from app.infrastructure.persistence.database import async_session_factory
from app.infrastructure.persistence.repositories.usage_repository import SQLAlchemyUsageRepository


def get_audit_service() -> AuditService:
    """Singleton-like — AuditService only needs the session factory."""
    return AuditService(session_factory=async_session_factory)


async def get_usage_service(
    session: AsyncSession = Depends(get_tenant_session),
) -> UsageService:
    return UsageService(repository=SQLAlchemyUsageRepository(session))
```

### 8.2 Updated Service Factories

```python
async def get_template_service(
    session: AsyncSession = Depends(get_tenant_session),
) -> TemplateService:
    return TemplateService(
        repository=SQLAlchemyTemplateRepository(session),
        storage=get_storage_service(),
        engine=get_template_engine(),
        audit_service=get_audit_service(),
    )


async def get_document_service(
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
) -> DocumentService:
    # ... (existing user lookup for bulk_generation_limit)
    return DocumentService(
        document_repository=SQLAlchemyDocumentRepository(session),
        template_repository=SQLAlchemyTemplateRepository(session),
        storage=get_storage_service(),
        engine=get_template_engine(),
        bulk_generation_limit=effective_limit,
        usage_service=UsageService(repository=SQLAlchemyUsageRepository(session)),
        audit_service=get_audit_service(),
    )
```

**Note**: `UsageService` gets the SAME session as the document/template repos (synchronous write, same transaction). `AuditService` uses its OWN session factory (fire-and-forget, independent transaction).

### 8.3 `ip_address` Propagation

Routers that call service methods requiring audit need to pass `ip_address`:

```python
ip_address = request.client.host if request.client else None
result = await service.generate_single(
    ...,
    ip_address=ip_address,
)
```

The `Request` object is already available in most router handlers (for rate limiting). Methods that don't have it will add `request: Request` to their signature.

---

## 9. Presentation Layer (API)

### 9.1 Usage Endpoints — `app/presentation/api/v1/usage.py`

```python
router = APIRouter()

@router.get("")
async def get_my_usage(
    current_user: CurrentUser = Depends(get_current_user),
    usage_service: UsageService = Depends(get_usage_service),
) -> UsageResponse:
    """Get current user's document generation count for the current month."""
    total = await usage_service.get_current_month_usage(current_user.user_id)
    return UsageResponse(
        user_id=str(current_user.user_id),
        documents_this_month=total,
        month_start=...,  # first day of current month
        quota_limit=None,  # populated when subscription tiers are added
    )


@router.get("/tenant")
async def get_tenant_usage(
    current_user: CurrentUser = Depends(get_current_user),
    usage_service: UsageService = Depends(get_usage_service),
) -> TenantUsageResponse:
    """Get tenant-wide usage breakdown (admin only)."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    data = await usage_service.get_tenant_usage()
    return TenantUsageResponse(
        tenant_id=str(current_user.tenant_id),
        total_documents=data["total"],
        month_start=data["month_start"],
        users=[
            UserUsageItem(user_id=str(u["user_id"]), total=u["total"])
            for u in data["users"]
        ],
    )
```

### 9.2 Usage Schemas — `app/presentation/schemas/usage.py`

```python
from pydantic import BaseModel


class UsageResponse(BaseModel):
    user_id: str
    documents_this_month: int
    month_start: str
    quota_limit: int | None = None  # for subscription-tiers change


class UserUsageItem(BaseModel):
    user_id: str
    total: int


class TenantUsageResponse(BaseModel):
    tenant_id: str
    total_documents: int
    month_start: str
    users: list[UserUsageItem]
```

### 9.3 Audit Endpoints — `app/presentation/api/v1/audit.py`

```python
router = APIRouter()

@router.get("")
async def list_audit_logs(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    action: str | None = Query(None),
    actor_id: UUID | None = Query(None),
    resource_type: str | None = Query(None),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    current_user: CurrentUser = Depends(get_current_user),
) -> AuditLogListResponse:
    """List audit logs (admin only)."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin only")

    audit_service = get_audit_service()
    entries, total = await audit_service.list_audit_logs(
        tenant_id=current_user.tenant_id,
        page=page, size=size,
        action=action, actor_id=actor_id,
        resource_type=resource_type,
        date_from=date_from, date_to=date_to,
    )
    items = [
        AuditLogResponse(
            id=str(e.id),
            actor_id=str(e.actor_id) if e.actor_id else None,
            action=e.action,
            resource_type=e.resource_type,
            resource_id=str(e.resource_id) if e.resource_id else None,
            details=e.details,
            ip_address=e.ip_address,
            created_at=e.created_at,
        )
        for e in entries
    ]
    return AuditLogListResponse(items=items, total=total, page=page, size=size)
```

### 9.4 Audit Schemas — `app/presentation/schemas/audit.py`

```python
from datetime import datetime
from pydantic import BaseModel


class AuditLogResponse(BaseModel):
    id: str
    actor_id: str | None
    action: str
    resource_type: str
    resource_id: str | None
    details: dict | None
    ip_address: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class AuditLogListResponse(BaseModel):
    items: list[AuditLogResponse]
    total: int
    page: int
    size: int
```

### 9.5 Router Registration

In `app/main.py` (or wherever routers are included):
```python
from app.presentation.api.v1.usage import router as usage_router
from app.presentation.api.v1.audit import router as audit_router

app.include_router(usage_router, prefix="/api/v1/usage", tags=["usage"])
app.include_router(audit_router, prefix="/api/v1/audit-log", tags=["audit"])
```

---

## 10. Alembic Migration

**`backend/alembic/versions/004_usage_tracking_and_audit_logging.py`**

```python
"""Add usage_events and audit_logs tables

Revision ID: 004
Revises: 003
Create Date: 2026-04-08
"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- usage_events ---
    op.create_table(
        "usage_events",
        sa.Column("id", sa.Uuid(), primary_key=True, default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("template_id", sa.Uuid(), sa.ForeignKey("templates.id"), nullable=False),
        sa.Column("generation_type", sa.String(10), nullable=False),
        sa.Column("document_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_usage_events_tenant_id", "usage_events", ["tenant_id"])
    op.create_index("ix_usage_events_tenant_month", "usage_events", ["tenant_id", "created_at"])
    op.create_index("ix_usage_events_user_month", "usage_events", ["user_id", "created_at"])
    op.create_index("ix_usage_events_template", "usage_events", ["template_id"])

    # --- audit_logs ---
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Uuid(), primary_key=True, default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("actor_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("resource_type", sa.String(30), nullable=False),
        sa.Column("resource_id", sa.Uuid(), nullable=True),
        sa.Column("details", sa.dialects.postgresql.JSONB(), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_audit_logs_tenant_id", "audit_logs", ["tenant_id"])
    op.create_index("ix_audit_logs_tenant_created", "audit_logs", ["tenant_id", "created_at"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_actor", "audit_logs", ["actor_id"])


def downgrade() -> None:
    op.drop_index("ix_audit_logs_actor", table_name="audit_logs")
    op.drop_index("ix_audit_logs_action", table_name="audit_logs")
    op.drop_index("ix_audit_logs_tenant_created", table_name="audit_logs")
    op.drop_index("ix_audit_logs_tenant_id", table_name="audit_logs")
    op.drop_table("audit_logs")

    op.drop_index("ix_usage_events_template", table_name="usage_events")
    op.drop_index("ix_usage_events_user_month", table_name="usage_events")
    op.drop_index("ix_usage_events_tenant_month", table_name="usage_events")
    op.drop_index("ix_usage_events_tenant_id", table_name="usage_events")
    op.drop_table("usage_events")
```

---

## 11. Frontend Design

### 11.1 New Feature Modules

**`frontend/src/features/usage/`** — usage tracking feature
```
usage/
  api/
    index.ts
    keys.ts
    queries.ts
  components/
    UsageWidget.tsx       # Dashboard card: "Docs this month: X"
  index.ts
```

**`frontend/src/features/audit/`** — audit log feature
```
audit/
  api/
    index.ts
    keys.ts
    queries.ts
  components/
    AuditLogTable.tsx     # Paginated table with filters
    AuditLogFilters.tsx   # Filter form (action, user, date range)
  index.ts
```

### 11.2 Usage Widget

- Displayed on the dashboard (authenticated index route)
- Shows: "Documents generated this month: **42**"
- Optional quota bar (prepared for subscription-tiers, renders only when `quota_limit` is not null)
- Calls `GET /api/v1/usage`

### 11.3 Audit Log Page

- New route: `/_authenticated/audit-log/index.tsx`
- Admin-only (redirect or 403 component if not admin)
- Components:
  - **AuditLogFilters**: action dropdown (with `AuditAction` constants), user select, date range picker
  - **AuditLogTable**: paginated DataTable showing: timestamp, actor email (needs user name lookup or accept user_id), action, resource_type, resource_id, IP
- Calls `GET /api/v1/audit-log` with query params

### 11.4 Dashboard Route Update

The current `/_authenticated/index.tsx` just redirects to `/templates`. It needs to become a real dashboard page that shows the `UsageWidget` (and potentially other widgets in the future). Alternatively, the `UsageWidget` can be embedded in the templates list page sidebar.

**Decision**: Add `UsageWidget` to the templates list page initially (less routing changes). Move to a dedicated dashboard when more widgets exist.

### 11.5 Navigation Update

Add "Audit Log" link to the sidebar/nav (admin-only visibility).

---

## 12. Testing Strategy

### 12.1 Fake Repositories

**`tests/fakes/fake_usage_repository.py`**:
```python
class FakeUsageRepository(UsageRepository):
    def __init__(self):
        self._events: list[UsageEvent] = []

    async def create(self, event: UsageEvent) -> UsageEvent:
        if event.created_at is None:
            event.created_at = datetime.now(timezone.utc)
        self._events.append(event)
        return event

    async def get_user_month_total(self, user_id, month_start) -> int:
        return sum(
            e.document_count for e in self._events
            if e.user_id == user_id and e.created_at >= month_start
        )

    async def get_tenant_month_total(self, month_start) -> int:
        return sum(
            e.document_count for e in self._events
            if e.created_at >= month_start
        )

    async def get_tenant_user_breakdown(self, month_start) -> list[dict]:
        from collections import defaultdict
        totals = defaultdict(int)
        for e in self._events:
            if e.created_at >= month_start:
                totals[e.user_id] += e.document_count
        return [{"user_id": uid, "total": t} for uid, t in totals.items()]

    async def get_template_month_total(self, template_id, month_start) -> int:
        return sum(
            e.document_count for e in self._events
            if e.template_id == template_id and e.created_at >= month_start
        )
```

**`tests/fakes/fake_audit_repository.py`**:
```python
class FakeAuditRepository(AuditRepository):
    def __init__(self):
        self._entries: list[AuditLog] = []

    async def create(self, entry: AuditLog) -> AuditLog:
        if entry.created_at is None:
            entry.created_at = datetime.now(timezone.utc)
        self._entries.append(entry)
        return entry

    async def list_paginated(self, page=1, size=20, **filters) -> tuple[list, int]:
        items = self._entries
        if filters.get("action"):
            items = [e for e in items if e.action == filters["action"]]
        if filters.get("actor_id"):
            items = [e for e in items if e.actor_id == filters["actor_id"]]
        # ... other filters
        total = len(items)
        offset = (page - 1) * size
        return items[offset:offset + size], total
```

### 12.2 Testing `AuditService` Async Write

The key challenge: `AuditService.log()` uses `asyncio.create_task()`, which is fire-and-forget. Tests need to wait for the task to complete.

**Strategy**: In tests, use `await asyncio.sleep(0)` (or `await asyncio.gather(*asyncio.all_tasks() - {asyncio.current_task()})`) after calling `log()` to let the event loop process the background task.

**Alternative for unit tests**: Create a `SyncAuditService` subclass (or test helper) that awaits `_write()` directly instead of using `create_task()`.

Recommended approach for unit tests:
```python
class TestableAuditService(AuditService):
    """Subclass that makes log() awaitable for testing."""
    async def log_sync(self, **kwargs):
        """Like log(), but awaits the write for deterministic testing."""
        entry = AuditLog(id=uuid.uuid4(), **kwargs)
        await self._write(entry)
```

For integration tests: call the endpoint, then `await asyncio.sleep(0.1)` to let the background task complete, then query the audit log API to verify.

### 12.3 Unit Test Coverage

| Test file | Tests |
|-----------|-------|
| `test_usage_service.py` | `record()` creates event, `get_current_month_usage()` aggregates correctly, ignores events from prior months |
| `test_audit_service.py` | `log()` creates entry in background, `_write()` handles exceptions gracefully, `list_audit_logs()` filters correctly |
| `test_document_service.py` (extended) | `generate_single` creates usage event + audit entry, `generate_bulk` creates usage event with correct count, services work when usage/audit services are None |
| `test_template_service.py` (extended) | `upload_template` creates audit entry, `delete_template` creates audit entry, service works when audit_service is None |

### 12.4 Integration Test Coverage

| Test file | Tests |
|-----------|-------|
| `test_usage_api.py` | GET /usage returns monthly total, GET /usage/tenant returns breakdown (admin), GET /usage/tenant returns 403 for non-admin |
| `test_audit_api.py` | GET /audit-log returns paginated entries (admin), filters by action/actor/date_from/date_to, returns 403 for non-admin |

### 12.5 Integration Conftest Update

Add `FakeUsageRepository` and `FakeAuditRepository` to the integration conftest. Update service factory overrides to inject them:

```python
# In override_get_document_service:
return DocumentService(
    ...,
    usage_service=UsageService(repository=fake_usage_repo),
    audit_service=None,  # or a testable audit service
)
```

For audit API integration tests, create a pre-populated `FakeAuditRepository` and wire it through a test-specific `AuditService`.

---

## 13. Architecture Decision Records

### ADR-1: Separate `UsageRepository` and `AuditRepository`

**Context**: Both subsystems persist events. Should they share a repository?

**Decision**: Separate repositories.

**Rationale**:
- Different write patterns: usage is synchronous (same transaction), audit is fire-and-forget.
- Different query patterns: usage needs aggregation (SUM, GROUP BY), audit needs paginated list with filters.
- Different lifecycle: usage feeds quota enforcement, audit feeds compliance.
- SRP: a combined repo would have two reasons to change.

### ADR-2: Fire-and-forget audit with dedicated session factory

**Context**: Audit writes must not block or fail the parent request.

**Decision**: `AuditService` receives `async_session_factory` (not an `AsyncSession`). Each `log()` call creates a fresh session via `asyncio.create_task()`.

**Rationale**:
- Sharing the request session means audit failure rolls back the business operation.
- Background tasks can outlive the request scope — the shared session may be closed.
- A dedicated session is fully independent: commit or fail without affecting the caller.

**Tradeoffs**:
- Extra DB connections for each audit write. Acceptable at current scale (<100 req/s).
- Need to handle connection pool exhaustion at scale (future: batch audit writes with a queue).

### ADR-3: AuditService imports concrete repository

**Context**: `AuditService` needs to create repository instances per-call with fresh sessions.

**Decision**: Import `SQLAlchemyAuditRepository` directly in `AuditService`.

**Rationale**:
- A factory function adds complexity to every DI chain for minimal benefit.
- `AuditService` is application-layer, which may know about infrastructure when architecturally justified.
- Testability is maintained by injecting a fake `session_factory`.

### ADR-4: Skip audit for unknown email login failures

**Context**: `audit_logs.tenant_id` is NOT NULL. Failed login with unknown email has no tenant.

**Decision**: Only log `auth.login_failed` when the user exists (email found but password wrong).

**Rationale**:
- Making `tenant_id` nullable pollutes the table and breaks tenant-scoped queries.
- Brute-force detection for unknown emails is better handled by rate limiting (already in place: 5/minute).
- This is the simplest approach that covers the important case (credential stuffing against known accounts).

### ADR-5: Usage tracking is synchronous within the request transaction

**Context**: Should usage tracking be fire-and-forget like audit?

**Decision**: No. Usage writes share the request's DB session and transaction.

**Rationale**:
- Usage data feeds subscription quota enforcement (next change). If usage write fails silently, the user could exceed their quota.
- Consistency: the usage event and the document creation must succeed or fail together.
- Performance impact is minimal: one INSERT per request, no complex queries.

### ADR-6: Optional service injection for backward compatibility

**Context**: Existing `DocumentService` and `TemplateService` constructors will change.

**Decision**: New parameters (`usage_service`, `audit_service`) are optional with `None` default.

**Rationale**:
- All 144 existing tests pass without modification.
- Service methods check `if self._usage_service:` before calling — no NoneType errors.
- Gradual rollout: services work without tracking until DI is updated.

---

## 14. File Inventory

### New Files (17)

| Layer | File |
|-------|------|
| Domain | `backend/src/app/domain/entities/usage_event.py` |
| Domain | `backend/src/app/domain/entities/audit_log.py` |
| Ports | `backend/src/app/domain/ports/usage_repository.py` |
| Ports | `backend/src/app/domain/ports/audit_repository.py` |
| ORM | `backend/src/app/infrastructure/persistence/models/usage_event.py` |
| ORM | `backend/src/app/infrastructure/persistence/models/audit_log.py` |
| Repo | `backend/src/app/infrastructure/persistence/repositories/usage_repository.py` |
| Repo | `backend/src/app/infrastructure/persistence/repositories/audit_repository.py` |
| Service | `backend/src/app/application/services/usage_service.py` |
| Service | `backend/src/app/application/services/audit_service.py` |
| API | `backend/src/app/presentation/api/v1/usage.py` |
| API | `backend/src/app/presentation/api/v1/audit.py` |
| Schema | `backend/src/app/presentation/schemas/usage.py` |
| Schema | `backend/src/app/presentation/schemas/audit.py` |
| Migration | `backend/alembic/versions/004_usage_tracking_and_audit_logging.py` |
| Test | `backend/tests/fakes/fake_usage_repository.py` |
| Test | `backend/tests/fakes/fake_audit_repository.py` |

### Modified Files (12)

| File | Change |
|------|--------|
| `backend/src/app/domain/entities/__init__.py` | Export `UsageEvent`, `AuditLog` |
| `backend/src/app/domain/ports/__init__.py` | Export `UsageRepository`, `AuditRepository` |
| `backend/src/app/infrastructure/persistence/models/__init__.py` | Export `UsageEventModel`, `AuditLogModel` |
| `backend/src/app/application/services/__init__.py` | Add `get_usage_service`, `get_audit_service`, update factories |
| `backend/src/app/application/services/document_service.py` | Add usage/audit service params, emit events |
| `backend/src/app/application/services/template_service.py` | Add audit_service param, emit events |
| `backend/src/app/presentation/api/v1/auth.py` | Add audit logging for login/login_failed/change_password |
| `backend/src/app/presentation/api/v1/users.py` | Add audit logging for create/update/deactivate |
| `backend/src/app/presentation/api/v1/documents.py` | Pass ip_address to service methods |
| `backend/src/app/presentation/api/v1/templates.py` | Pass ip_address to service methods |
| `backend/src/app/main.py` | Register usage and audit routers |
| `backend/tests/fakes/__init__.py` | Export `FakeUsageRepository`, `FakeAuditRepository` |

### Frontend New Files (8+)

| File | Purpose |
|------|---------|
| `frontend/src/features/usage/api/keys.ts` | Query keys |
| `frontend/src/features/usage/api/queries.ts` | `useMyUsage()` hook |
| `frontend/src/features/usage/api/index.ts` | Re-exports |
| `frontend/src/features/usage/components/UsageWidget.tsx` | Dashboard card |
| `frontend/src/features/usage/index.ts` | Feature barrel |
| `frontend/src/features/audit/api/keys.ts` | Query keys |
| `frontend/src/features/audit/api/queries.ts` | `useAuditLogs()` hook |
| `frontend/src/features/audit/api/index.ts` | Re-exports |
| `frontend/src/features/audit/components/AuditLogTable.tsx` | Paginated table |
| `frontend/src/features/audit/components/AuditLogFilters.tsx` | Filter form |
| `frontend/src/features/audit/index.ts` | Feature barrel |
| `frontend/src/routes/_authenticated/audit-log/index.tsx` | Audit log page route |

### Frontend Modified Files (2)

| File | Change |
|------|--------|
| `frontend/src/routes/_authenticated/templates/index.tsx` (or layout) | Add `UsageWidget` |
| Navigation component | Add "Audit Log" link (admin-only) |

---

## 15. Sequence Diagrams

### 15.1 Document Generation with Usage + Audit

```
Client → Router.generate_document()
  → extract ip_address from request.client.host
  → service.generate_single(..., ip_address=ip_address)
    → template_repo.get_version_by_id()
    → template_repo.has_access()
    → storage.download_file()
    → engine.render()
    → storage.upload_file()
    → doc_repo.create()
    → usage_service.record()          ← SYNC (same session/transaction)
    → audit_service.log()             ← FIRE-AND-FORGET (background task)
  ← return DocumentResponse
                                      ← (background) audit_service._write()
                                        → new session from factory
                                        → audit_repo.create()
                                        → session.commit()
```

### 15.2 Audit Log Query

```
Admin → Router.list_audit_logs(page, filters)
  → verify admin role
  → audit_service.list_audit_logs(tenant_id, page, filters)
    → new session from factory
    → session.info["tenant_id"] = tenant_id
    → audit_repo.list_paginated(page, filters)
    ← (entries, total)
  ← return AuditLogListResponse
```

---

## 16. Open Questions / Future Considerations

1. **Usage aggregation rollup table**: At scale (>100K events/month), `SUM()` on raw events becomes slow. Add a `usage_monthly_totals` materialized view or cron-based aggregation table. Not needed now.

2. **Audit log retention**: Consider TTL or archival strategy after 12 months. Not in scope for this change.

3. **Actor email in audit response**: The API currently returns `actor_id` (UUID). The frontend needs to display the user's name/email. Options: (a) join in the query, (b) frontend looks up users separately. Start with (b) — the admin already has the user list.

4. **WebSocket/SSE for real-time audit**: Out of scope. The admin polls on page load and manual refresh.
