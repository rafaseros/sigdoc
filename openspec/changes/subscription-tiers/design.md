# Design: subscription-tiers

## Overview

This document provides the technical design for introducing subscription tiers to SigDoc. It covers the data model, new domain entities and ports, the QuotaService, enforcement integration points, new API endpoints, the database migration, frontend components, and error handling.

---

## ADR-1: SubscriptionTier as an Immutable Value Object on Read Path

**Context**: QuotaService needs to load the tenant's tier limits on every quota check. Loading the full ORM model and mapping to a domain entity on every request adds overhead.

**Decision**: `SubscriptionTier` is a frozen dataclass (value object). It is loaded ONCE per QuotaService call (not per-check), cached on the QuotaService instance for the duration of a single request. No cross-request caching -- each HTTP request gets a fresh QuotaService via DI.

**Consequence**: Simple, no stale cache issues. The tier query is a single indexed PK lookup -- negligible latency.

---

## ADR-2: New Port Methods for Counting (count_active_by_tenant)

**Context**: QuotaService needs to count templates, users, and shares for a tenant. The existing repository ports do not expose count methods -- only paginated list methods.

**Decision**: Add `count_active_by_tenant(tenant_id)` to `UserRepository` and `TemplateRepository` ports. Add `count_shares(template_id)` to `TemplateRepository`. These are simple `SELECT COUNT(*)` queries with the tenant filter applied automatically by the `do_orm_execute` event.

**Why not reuse `list_paginated`**: Count queries are O(1) in indexed tables vs. O(n) for fetching full rows. QuotaService needs counts, not entities.

**Consequence**: Three new abstract methods + three SQLAlchemy implementations. Minimal surface area.

---

## ADR-3: QuotaService Receives Repositories, Not Other Services

**Context**: QuotaService needs usage data (from UsageRepository), tier data (from SubscriptionTierRepository), template count (from TemplateRepository), user count (from UserRepository), and share count (from TemplateRepository).

**Decision**: QuotaService receives **repository ports** directly, NOT service wrappers (not UsageService, not TemplateService). This avoids circular dependencies (DocumentService -> QuotaService -> UsageService -> UsageRepository vs. DocumentService -> QuotaService -> UsageRepository).

**Consequence**: QuotaService has 4 repository dependencies: `SubscriptionTierRepository`, `UsageRepository`, `TemplateRepository`, `UserRepository`. All are injected via the DI factory in `services/__init__.py`.

---

## ADR-4: QuotaService is Optional in Existing Services (Backward Compat)

**Context**: 188 existing tests construct DocumentService and TemplateService without a QuotaService.

**Decision**: `QuotaService` is an optional dependency (`quota_service: QuotaService | None = None`) in `DocumentService` and `TemplateService` constructors. When `None`, quota checks are silently skipped. This means ALL existing tests pass unchanged.

**Consequence**: New tests for quota enforcement must explicitly pass a `QuotaService` (or fake). The DI factory in production always provides one.

---

## ADR-5: Bulk Limit Resolution Order

**Context**: Three sources can define a bulk limit: (1) per-user `bulk_generation_limit` on User, (2) tier's `bulk_generation_limit`, (3) global `settings.bulk_generation_limit`. Which wins?

**Decision**: Resolution order (highest priority first):
1. Per-user `bulk_generation_limit` (if set on User entity, i.e., not None)
2. Tier's `bulk_generation_limit` (from subscription_tiers table)
3. Fall through -- if tier is also somehow None, use 10 as absolute default (defensive)

**Consequence**: `QuotaService.check_bulk_limit()` receives the user entity (or at least the per-user override value) so it can check the override first. The existing `DocumentService._bulk_limit` field becomes a fallback for when QuotaService is None (backward compat).

---

## ADR-6: QuotaExceededError Carries Structured Context

**Context**: The frontend needs to display which limit was hit, the current usage, and the limit value.

**Decision**: `QuotaExceededError` includes `limit_type`, `limit_value`, `current_usage`, and `tier_name`. The presentation layer maps it to HTTP 429 with a structured JSON body.

**Consequence**: The error handler is a single catch in a shared exception handler (added to `main.py`), not duplicated in every router.

---

## ADR-7: Deterministic UUIDs via uuid5 for Seed Tiers

**Context**: Migration 005 seeds three tiers and references the Free tier UUID as the DEFAULT for `tenants.tier_id`.

**Decision**: Use `uuid.uuid5(uuid.NAMESPACE_DNS, "sigdoc.tier.free")` etc. to produce deterministic, reproducible UUIDs.

**Values** (pre-computed):
```python
import uuid
FREE_TIER_ID  = uuid.uuid5(uuid.NAMESPACE_DNS, "sigdoc.tier.free")
# => UUID('d4b4c4e0-...') -- actual value computed at migration write time
PRO_TIER_ID   = uuid.uuid5(uuid.NAMESPACE_DNS, "sigdoc.tier.pro")
ENT_TIER_ID   = uuid.uuid5(uuid.NAMESPACE_DNS, "sigdoc.tier.enterprise")
```

These UUIDs are also exported as constants from `domain/entities/subscription_tier.py` for use in tests and service code.

---

## 1. Data Model

### 1.1 SQL Schema: `subscription_tiers`

```sql
CREATE TABLE subscription_tiers (
    id                      UUID PRIMARY KEY,
    name                    VARCHAR(100) NOT NULL,
    slug                    VARCHAR(50) NOT NULL UNIQUE,
    monthly_document_limit  INTEGER,          -- NULL = unlimited
    max_templates           INTEGER,          -- NULL = unlimited
    max_users               INTEGER,          -- NULL = unlimited
    bulk_generation_limit   INTEGER NOT NULL DEFAULT 10,
    max_template_shares     INTEGER,          -- NULL = unlimited
    is_active               BOOLEAN NOT NULL DEFAULT TRUE,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### 1.2 SQL Change: `tenants`

```sql
ALTER TABLE tenants
    ADD COLUMN tier_id UUID NOT NULL
        REFERENCES subscription_tiers(id)
        DEFAULT '{FREE_TIER_ID}';
```

### 1.3 Seed Data

| slug | name | monthly_document_limit | max_templates | max_users | bulk_generation_limit | max_template_shares |
|------|------|----------------------|---------------|-----------|---------------------|-------------------|
| free | Free | 50 | 5 | 3 | 5 | 5 |
| pro | Pro | 500 | 50 | 20 | 25 | 50 |
| enterprise | Enterprise | 5000 | NULL | NULL | 100 | NULL |

---

## 2. Domain Layer

### 2.1 Entity: `SubscriptionTier`

**File**: `backend/src/app/domain/entities/subscription_tier.py`

```python
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID
import uuid as _uuid

# Deterministic UUIDs for seed tiers
FREE_TIER_ID = _uuid.uuid5(_uuid.NAMESPACE_DNS, "sigdoc.tier.free")
PRO_TIER_ID = _uuid.uuid5(_uuid.NAMESPACE_DNS, "sigdoc.tier.pro")
ENTERPRISE_TIER_ID = _uuid.uuid5(_uuid.NAMESPACE_DNS, "sigdoc.tier.enterprise")


@dataclass(frozen=True)
class SubscriptionTier:
    id: UUID
    name: str
    slug: str
    monthly_document_limit: int | None  # None = unlimited
    max_templates: int | None           # None = unlimited
    max_users: int | None               # None = unlimited
    bulk_generation_limit: int
    max_template_shares: int | None     # None = unlimited
    is_active: bool = True
    created_at: datetime | None = None
    updated_at: datetime | None = None
```

### 2.2 Update: `Tenant` Entity

**File**: `backend/src/app/domain/entities/tenant.py`

Add `tier_id` field:

```python
@dataclass
class Tenant:
    id: UUID
    name: str
    slug: str
    tier_id: UUID | None = None      # FK to subscription_tiers
    is_active: bool = True
    created_at: datetime | None = None
    updated_at: datetime | None = None
```

`tier_id` defaults to `None` in the dataclass for backward compat in tests (existing Tenant constructions won't break). The DB column is NOT NULL with a DEFAULT.

### 2.3 Update: `entities/__init__.py`

Add `SubscriptionTier`, `FREE_TIER_ID`, `PRO_TIER_ID`, `ENTERPRISE_TIER_ID` to exports.

### 2.4 Exception: `QuotaExceededError`

**File**: `backend/src/app/domain/exceptions.py`

```python
class QuotaExceededError(DomainError):
    """Tenant has exceeded a subscription tier limit."""

    def __init__(
        self,
        limit_type: str,       # "documents", "templates", "users", "bulk", "shares"
        limit_value: int,
        current_usage: int,
        tier_name: str = "",
    ):
        self.limit_type = limit_type
        self.limit_value = limit_value
        self.current_usage = current_usage
        self.tier_name = tier_name
        super().__init__(
            f"Quota exceeded: {limit_type} limit is {limit_value}, "
            f"current usage is {current_usage} (tier: {tier_name})"
        )
```

### 2.5 Port: `SubscriptionTierRepository`

**File**: `backend/src/app/domain/ports/subscription_tier_repository.py`

```python
from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.entities.subscription_tier import SubscriptionTier


class SubscriptionTierRepository(ABC):
    @abstractmethod
    async def get_by_id(self, tier_id: UUID) -> SubscriptionTier | None:
        ...

    @abstractmethod
    async def get_by_slug(self, slug: str) -> SubscriptionTier | None:
        ...

    @abstractmethod
    async def list_active(self) -> list[SubscriptionTier]:
        ...
```

### 2.6 Port Updates: `UserRepository`

Add one new abstract method:

```python
@abstractmethod
async def count_active_by_tenant(self) -> int:
    """Count active users in the current tenant (filtered by do_orm_execute)."""
    ...
```

### 2.7 Port Updates: `TemplateRepository`

Add two new abstract methods:

```python
@abstractmethod
async def count_by_tenant(self) -> int:
    """Count all templates in the current tenant."""
    ...

@abstractmethod
async def count_shares(self, template_id: UUID) -> int:
    """Count the number of share records for a given template."""
    ...
```

### 2.8 Update: `ports/__init__.py`

Add `SubscriptionTierRepository` to exports.

---

## 3. Infrastructure Layer

### 3.1 ORM Model: `SubscriptionTierModel`

**File**: `backend/src/app/infrastructure/persistence/models/subscription_tier.py`

```python
from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin, UUIDMixin


class SubscriptionTierModel(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "subscription_tiers"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    monthly_document_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_templates: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_users: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bulk_generation_limit: Mapped[int] = mapped_column(
        Integer, nullable=False, default=10, server_default="10"
    )
    max_template_shares: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true"
    )
```

Note: `SubscriptionTierModel` does NOT use `TenantMixin`. Subscription tiers are global (not tenant-scoped). The `do_orm_execute` filter does not apply.

### 3.2 Update: `TenantModel`

**File**: `backend/src/app/infrastructure/persistence/models/tenant.py`

```python
import uuid

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, UUIDMixin


class TenantModel(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "tenants"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    tier_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("subscription_tiers.id"),
        nullable=False,
    )

    tier = relationship("SubscriptionTierModel", lazy="selectin")
```

### 3.3 Update: `models/__init__.py`

Add `SubscriptionTierModel` to imports and `__all__`.

### 3.4 Repository: `SQLAlchemySubscriptionTierRepository`

**File**: `backend/src/app/infrastructure/persistence/repositories/subscription_tier_repository.py`

```python
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.subscription_tier import SubscriptionTier
from app.domain.ports.subscription_tier_repository import (
    SubscriptionTierRepository as SubscriptionTierRepositoryPort,
)
from app.infrastructure.persistence.models.subscription_tier import SubscriptionTierModel


class SQLAlchemySubscriptionTierRepository(SubscriptionTierRepositoryPort):
    def __init__(self, session: AsyncSession):
        self._session = session

    @staticmethod
    def _to_entity(model: SubscriptionTierModel) -> SubscriptionTier:
        return SubscriptionTier(
            id=model.id,
            name=model.name,
            slug=model.slug,
            monthly_document_limit=model.monthly_document_limit,
            max_templates=model.max_templates,
            max_users=model.max_users,
            bulk_generation_limit=model.bulk_generation_limit,
            max_template_shares=model.max_template_shares,
            is_active=model.is_active,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def get_by_id(self, tier_id: UUID) -> SubscriptionTier | None:
        stmt = select(SubscriptionTierModel).where(SubscriptionTierModel.id == tier_id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def get_by_slug(self, slug: str) -> SubscriptionTier | None:
        stmt = select(SubscriptionTierModel).where(SubscriptionTierModel.slug == slug)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def list_active(self) -> list[SubscriptionTier]:
        stmt = (
            select(SubscriptionTierModel)
            .where(SubscriptionTierModel.is_active == True)  # noqa: E712
            .order_by(SubscriptionTierModel.bulk_generation_limit.asc())
        )
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().all()]
```

### 3.5 Repository Updates: `SQLAlchemyUserRepository`

Add `count_active_by_tenant`:

```python
async def count_active_by_tenant(self) -> int:
    """Count active users in the current tenant (filtered by do_orm_execute)."""
    stmt = select(func.count()).select_from(UserModel).where(
        UserModel.is_active == True  # noqa: E712
    )
    result = await self._session.execute(stmt)
    return result.scalar_one()
```

### 3.6 Repository Updates: `SQLAlchemyTemplateRepository`

Add `count_by_tenant` and `count_shares`:

```python
async def count_by_tenant(self) -> int:
    """Count all templates in the current tenant (auto-filtered by do_orm_execute)."""
    stmt = select(func.count()).select_from(TemplateModel)
    result = await self._session.execute(stmt)
    return result.scalar_one()

async def count_shares(self, template_id: UUID) -> int:
    """Count the number of share records for a given template."""
    stmt = select(func.count()).select_from(TemplateShareModel).where(
        TemplateShareModel.template_id == template_id
    )
    result = await self._session.execute(stmt)
    return result.scalar_one()
```

### 3.7 Update: `repositories/__init__.py`

Add `SQLAlchemySubscriptionTierRepository` to imports and `__all__`.

---

## 4. Application Layer: QuotaService

**File**: `backend/src/app/application/services/quota_service.py`

### 4.1 Class Design

```python
"""QuotaService -- centralized subscription tier limit enforcement."""
import logging
from datetime import date
from uuid import UUID

from app.domain.entities.subscription_tier import SubscriptionTier
from app.domain.exceptions import QuotaExceededError
from app.domain.ports.subscription_tier_repository import SubscriptionTierRepository
from app.domain.ports.template_repository import TemplateRepository
from app.domain.ports.usage_repository import UsageRepository
from app.domain.ports.user_repository import UserRepository

logger = logging.getLogger(__name__)


class QuotaService:
    def __init__(
        self,
        tier_repo: SubscriptionTierRepository,
        usage_repo: UsageRepository,
        template_repo: TemplateRepository,
        user_repo: UserRepository,
    ) -> None:
        self._tier_repo = tier_repo
        self._usage_repo = usage_repo
        self._template_repo = template_repo
        self._user_repo = user_repo

    async def _load_tier(self, tenant_id: UUID) -> SubscriptionTier:
        """Load the subscription tier for a tenant.

        Queries the tenant's tier_id, then loads the tier.
        Raises ValueError if tier not found (data integrity issue).
        """
        # The tenant's tier_id is needed. We get it from the TenantModel
        # via a lightweight query. This could be optimized with a JOIN
        # but for clarity and separation we do two lookups.
        from app.infrastructure.persistence.models.tenant import TenantModel
        from sqlalchemy import select

        # NOTE: We access the session indirectly through the tier_repo's session.
        # This is a pragmatic choice -- QuotaService shares the request's session.
        session = self._tier_repo._session  # type: ignore[attr-defined]
        stmt = select(TenantModel.tier_id).where(TenantModel.id == tenant_id)
        result = await session.execute(stmt)
        tier_id = result.scalar_one_or_none()

        if tier_id is None:
            raise ValueError(f"Tenant {tenant_id} not found or has no tier")

        tier = await self._tier_repo.get_by_id(tier_id)
        if tier is None:
            raise ValueError(f"Tier {tier_id} not found (data integrity issue)")

        return tier

    async def get_tier_for_tenant(self, tenant_id: UUID) -> SubscriptionTier:
        """Public method to load the tier for a tenant. Used by API endpoints."""
        return await self._load_tier(tenant_id)

    async def check_document_quota(
        self,
        tenant_id: UUID,
        additional: int = 1,
    ) -> None:
        """Check if the tenant can generate `additional` more documents this month.

        Raises QuotaExceededError if the monthly document limit would be exceeded.
        No-op if the tier has unlimited documents (limit is None).
        """
        tier = await self._load_tier(tenant_id)
        if tier.monthly_document_limit is None:
            return  # unlimited

        today = date.today()
        month_start = date(today.year, today.month, 1)
        current_usage = await self._usage_repo.get_tenant_month_total(
            month_start=month_start
        )

        if current_usage + additional > tier.monthly_document_limit:
            raise QuotaExceededError(
                limit_type="documents",
                limit_value=tier.monthly_document_limit,
                current_usage=current_usage,
                tier_name=tier.name,
            )

    async def check_template_limit(self, tenant_id: UUID) -> None:
        """Check if the tenant can create one more template.

        Raises QuotaExceededError if the max_templates limit would be exceeded.
        No-op if the tier has unlimited templates (limit is None).
        """
        tier = await self._load_tier(tenant_id)
        if tier.max_templates is None:
            return  # unlimited

        current_count = await self._template_repo.count_by_tenant()
        if current_count >= tier.max_templates:
            raise QuotaExceededError(
                limit_type="templates",
                limit_value=tier.max_templates,
                current_usage=current_count,
                tier_name=tier.name,
            )

    async def check_user_limit(self, tenant_id: UUID) -> None:
        """Check if the tenant can create one more user.

        Raises QuotaExceededError if the max_users limit would be exceeded.
        No-op if the tier has unlimited users (limit is None).
        """
        tier = await self._load_tier(tenant_id)
        if tier.max_users is None:
            return  # unlimited

        current_count = await self._user_repo.count_active_by_tenant()
        if current_count >= tier.max_users:
            raise QuotaExceededError(
                limit_type="users",
                limit_value=tier.max_users,
                current_usage=current_count,
                tier_name=tier.name,
            )

    async def check_bulk_limit(
        self,
        tenant_id: UUID,
        requested_count: int,
        user_bulk_override: int | None = None,
    ) -> None:
        """Check if a bulk generation of `requested_count` rows is allowed.

        Resolution order:
        1. Per-user override (if not None) -- wins over tier
        2. Tier's bulk_generation_limit

        Raises QuotaExceededError if requested_count exceeds the effective limit.
        """
        if user_bulk_override is not None:
            effective_limit = user_bulk_override
        else:
            tier = await self._load_tier(tenant_id)
            effective_limit = tier.bulk_generation_limit

        if requested_count > effective_limit:
            raise QuotaExceededError(
                limit_type="bulk",
                limit_value=effective_limit,
                current_usage=requested_count,
                tier_name="",  # may not be loaded if override was used
            )

    async def check_share_limit(
        self,
        tenant_id: UUID,
        template_id: UUID,
    ) -> None:
        """Check if one more share can be added to a template.

        Raises QuotaExceededError if the max_template_shares limit would be exceeded.
        No-op if the tier has unlimited shares (limit is None).
        """
        tier = await self._load_tier(tenant_id)
        if tier.max_template_shares is None:
            return  # unlimited

        current_count = await self._template_repo.count_shares(template_id)
        if current_count >= tier.max_template_shares:
            raise QuotaExceededError(
                limit_type="shares",
                limit_value=tier.max_template_shares,
                current_usage=current_count,
                tier_name=tier.name,
            )

    async def get_usage_summary(self, tenant_id: UUID) -> dict:
        """Return a summary of the tenant's current usage vs tier limits.

        Used by the GET /api/v1/tenant/tier endpoint.
        """
        tier = await self._load_tier(tenant_id)
        today = date.today()
        month_start = date(today.year, today.month, 1)

        docs_used = await self._usage_repo.get_tenant_month_total(month_start=month_start)
        templates_used = await self._template_repo.count_by_tenant()
        users_used = await self._user_repo.count_active_by_tenant()

        def _pct(used: int, limit: int | None) -> float | None:
            if limit is None or limit == 0:
                return None
            return round((used / limit) * 100, 1)

        return {
            "tier": tier,
            "usage": {
                "documents": {
                    "used": docs_used,
                    "limit": tier.monthly_document_limit,
                    "percentage": _pct(docs_used, tier.monthly_document_limit),
                },
                "templates": {
                    "used": templates_used,
                    "limit": tier.max_templates,
                    "percentage": _pct(templates_used, tier.max_templates),
                },
                "users": {
                    "used": users_used,
                    "limit": tier.max_users,
                    "percentage": _pct(users_used, tier.max_users),
                },
                "bulk_generation_limit": tier.bulk_generation_limit,
                "max_template_shares": tier.max_template_shares,
            },
        }
```

### 4.2 Design Note: `_load_tier` and Session Access

`_load_tier` needs the tenant's `tier_id` which is on the `tenants` table. Rather than adding a `TenantRepository` port (overengineering for a single field lookup), we do a direct SQLAlchemy query via the shared session. This is a pragmatic compromise -- the QuotaService already operates within the infrastructure boundary (it receives concrete repository instances).

**Alternative considered**: Pass `tier_id` as a parameter from the caller. Rejected because callers (DocumentService, TemplateService, user router) don't have easy access to the tier_id -- they have `tenant_id` from the JWT. Adding tier_id to CurrentUser would couple auth to subscription tiers.

---

## 5. DI Factory Updates

**File**: `backend/src/app/application/services/__init__.py`

### 5.1 New Factory: `get_quota_service`

```python
async def get_quota_service(
    session: AsyncSession = Depends(get_tenant_session),
) -> QuotaService:
    from app.infrastructure.persistence.repositories.subscription_tier_repository import (
        SQLAlchemySubscriptionTierRepository,
    )
    from app.infrastructure.persistence.repositories.usage_repository import (
        SQLAlchemyUsageRepository,
    )

    return QuotaService(
        tier_repo=SQLAlchemySubscriptionTierRepository(session),
        usage_repo=SQLAlchemyUsageRepository(session),
        template_repo=SQLAlchemyTemplateRepository(session),
        user_repo=SQLAlchemyUserRepository(session),
    )
```

### 5.2 Update: `get_template_service`

Add optional `quota_service` injection:

```python
async def get_template_service(
    session: AsyncSession = Depends(get_tenant_session),
    quota_service: QuotaService = Depends(get_quota_service),
) -> TemplateService:
    return TemplateService(
        repository=SQLAlchemyTemplateRepository(session),
        storage=get_storage_service(),
        engine=get_template_engine(),
        audit_service=get_audit_service(),
        quota_service=quota_service,  # NEW
    )
```

### 5.3 Update: `get_document_service`

Add optional `quota_service` injection:

```python
async def get_document_service(
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
    quota_service: QuotaService = Depends(get_quota_service),
) -> DocumentService:
    # ... existing code ...
    return DocumentService(
        document_repository=SQLAlchemyDocumentRepository(session),
        template_repository=SQLAlchemyTemplateRepository(session),
        storage=get_storage_service(),
        engine=get_template_engine(),
        bulk_generation_limit=effective_limit,
        usage_service=UsageService(usage_repo=SQLAlchemyUsageRepository(session)),
        audit_service=get_audit_service(),
        quota_service=quota_service,  # NEW
    )
```

---

## 6. Enforcement Points

### 6.1 DocumentService Changes

**File**: `backend/src/app/application/services/document_service.py`

**Constructor**: Add `quota_service: QuotaService | None = None` parameter. Store as `self._quota_service`.

**`generate_single()`**: Insert at the TOP (before any work):

```python
if self._quota_service is not None:
    await self._quota_service.check_document_quota(
        tenant_id=uuid.UUID(tenant_id),
        additional=1,
    )
```

**`generate_bulk()`**: Insert at the TOP (before any work):

```python
if self._quota_service is not None:
    await self._quota_service.check_document_quota(
        tenant_id=uuid.UUID(tenant_id),
        additional=len(rows),
    )
```

**`parse_excel_data()`**: Replace the existing bulk limit check:

```python
# OLD:
# if len(rows) > self._bulk_limit:
#     raise BulkLimitExceededError(limit=self._bulk_limit)

# NEW:
if self._quota_service is not None:
    await self._quota_service.check_bulk_limit(
        tenant_id=uuid.UUID(tenant_id),
        requested_count=len(rows),
        user_bulk_override=user_bulk_override,  # passed from caller
    )
elif len(rows) > self._bulk_limit:
    raise BulkLimitExceededError(limit=self._bulk_limit)
```

Note: `parse_excel_data()` currently does not receive `tenant_id` or user override info. The method signature must be updated to accept these:

```python
async def parse_excel_data(
    self,
    template_version_id: str,
    excel_bytes: bytes,
    user_id: str | None = None,
    role: str = "user",
    tenant_id: str | None = None,         # NEW
    user_bulk_override: int | None = None, # NEW
) -> list[dict[str, str]]:
```

### 6.2 TemplateService Changes

**File**: `backend/src/app/application/services/template_service.py`

**Constructor**: Add `quota_service: QuotaService | None = None` parameter. Store as `self._quota_service`.

**`upload_template()`**: Insert BEFORE the file upload (after variable extraction, before MinIO upload):

```python
if self._quota_service is not None:
    await self._quota_service.check_template_limit(
        tenant_id=uuid.UUID(tenant_id) if isinstance(tenant_id, str) else tenant_id,
    )
```

**`share_template()`**: Insert at the TOP (before access check):

```python
if self._quota_service is not None:
    await self._quota_service.check_share_limit(
        tenant_id=tenant_id,
        template_id=template_id,
    )
```

### 6.3 User Creation (Router-Level)

**File**: `backend/src/app/presentation/api/v1/users.py`

In `create_user()`, inject `QuotaService` via `Depends` and call before creating:

```python
@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    request: CreateUserRequest,
    admin: CurrentUser = Depends(require_admin),
    session: AsyncSession = Depends(get_tenant_session),
    quota_service: QuotaService = Depends(get_quota_service),  # NEW
):
    # Quota check BEFORE creating
    await quota_service.check_user_limit(admin.tenant_id)

    # ... existing code ...
```

---

## 7. API Endpoints

### 7.1 New Router: `tiers.py`

**File**: `backend/src/app/presentation/api/v1/tiers.py`

```
GET /api/v1/tiers         -- List all active tiers (authenticated)
GET /api/v1/tenant/tier   -- Current tenant's tier + usage summary (authenticated)
```

#### `GET /api/v1/tiers`

Response: `list[TierResponse]`

```json
[
  {
    "id": "uuid",
    "name": "Free",
    "slug": "free",
    "monthly_document_limit": 50,
    "max_templates": 5,
    "max_users": 3,
    "bulk_generation_limit": 5,
    "max_template_shares": 5
  },
  ...
]
```

#### `GET /api/v1/tenant/tier`

Response: `TenantTierResponse`

```json
{
  "tier": {
    "id": "uuid",
    "name": "Free",
    "slug": "free",
    "monthly_document_limit": 50,
    "max_templates": 5,
    "max_users": 3,
    "bulk_generation_limit": 5,
    "max_template_shares": 5
  },
  "usage": {
    "documents": {
      "used": 23,
      "limit": 50,
      "percentage": 46.0
    },
    "templates": {
      "used": 3,
      "limit": 5,
      "percentage": 60.0
    },
    "users": {
      "used": 2,
      "limit": 3,
      "percentage": 66.7
    },
    "bulk_generation_limit": 5,
    "max_template_shares": 5
  }
}
```

### 7.2 Pydantic Schemas

**File**: `backend/src/app/presentation/schemas/tier.py`

```python
from pydantic import BaseModel


class TierResponse(BaseModel):
    id: str
    name: str
    slug: str
    monthly_document_limit: int | None
    max_templates: int | None
    max_users: int | None
    bulk_generation_limit: int
    max_template_shares: int | None


class UsageDetail(BaseModel):
    used: int
    limit: int | None
    percentage: float | None


class UsageSummary(BaseModel):
    documents: UsageDetail
    templates: UsageDetail
    users: UsageDetail
    bulk_generation_limit: int
    max_template_shares: int | None


class TenantTierResponse(BaseModel):
    tier: TierResponse
    usage: UsageSummary
```

### 7.3 Router Registration

**File**: `backend/src/app/main.py`

Add:
```python
from app.presentation.api.v1 import tiers

app.include_router(tiers.router, prefix=f"{settings.api_v1_prefix}/tiers", tags=["tiers"])
app.include_router(tiers.tenant_router, prefix=f"{settings.api_v1_prefix}/tenant", tags=["tenant"])
```

The `tiers.py` file exports two routers:
- `router` for `/api/v1/tiers` (tier listing)
- `tenant_router` for `/api/v1/tenant/tier` (tenant tier info)

---

## 8. Error Handling

### 8.1 Global Exception Handler for QuotaExceededError

**File**: `backend/src/app/main.py`

Add a global exception handler so that `QuotaExceededError` is caught regardless of which router raises it:

```python
from app.domain.exceptions import QuotaExceededError

@app.exception_handler(QuotaExceededError)
async def quota_exceeded_handler(request: Request, exc: QuotaExceededError):
    return JSONResponse(
        status_code=429,
        content={
            "detail": str(exc),
            "limit_type": exc.limit_type,
            "limit_value": exc.limit_value,
            "current_usage": exc.current_usage,
            "tier_name": exc.tier_name,
        },
    )
```

This avoids adding `try/except QuotaExceededError` in every router endpoint.

---

## 9. Migration: `005_subscription_tiers`

**File**: `backend/alembic/versions/005_subscription_tiers.py`

### 9.1 Steps (in order)

1. **Create `subscription_tiers` table** with all columns + indexes
2. **Insert seed tiers** (Free, Pro, Enterprise) using deterministic UUIDs
3. **Add `tier_id` column** to `tenants` with FK and DEFAULT = Free tier UUID
4. **Backfill** existing tenants to Free tier (UPDATE tenants SET tier_id = FREE_TIER_ID WHERE tier_id IS NULL) -- handled automatically by the column DEFAULT, but explicit backfill is safer

### 9.2 Migration Skeleton

```python
"""Add subscription_tiers table and tenant.tier_id FK

Revision ID: 005
Revises: 004
Create Date: 2026-04-08
"""

import uuid as _uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Deterministic UUIDs for seed tiers
FREE_TIER_ID = str(_uuid.uuid5(_uuid.NAMESPACE_DNS, "sigdoc.tier.free"))
PRO_TIER_ID = str(_uuid.uuid5(_uuid.NAMESPACE_DNS, "sigdoc.tier.pro"))
ENT_TIER_ID = str(_uuid.uuid5(_uuid.NAMESPACE_DNS, "sigdoc.tier.enterprise"))


def upgrade() -> None:
    # 1. Create subscription_tiers table
    op.create_table(
        "subscription_tiers",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("slug", sa.String(50), unique=True, nullable=False),
        sa.Column("monthly_document_limit", sa.Integer(), nullable=True),
        sa.Column("max_templates", sa.Integer(), nullable=True),
        sa.Column("max_users", sa.Integer(), nullable=True),
        sa.Column("bulk_generation_limit", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("max_template_shares", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # 2. Seed default tiers
    op.execute(
        sa.text(
            """
            INSERT INTO subscription_tiers (id, name, slug, monthly_document_limit, max_templates, max_users, bulk_generation_limit, max_template_shares)
            VALUES
                (:free_id, 'Free', 'free', 50, 5, 3, 5, 5),
                (:pro_id, 'Pro', 'pro', 500, 50, 20, 25, 50),
                (:ent_id, 'Enterprise', 'enterprise', 5000, NULL, NULL, 100, NULL)
            """
        ).bindparams(
            free_id=FREE_TIER_ID,
            pro_id=PRO_TIER_ID,
            ent_id=ENT_TIER_ID,
        )
    )

    # 3. Add tier_id to tenants with FK + DEFAULT
    op.add_column(
        "tenants",
        sa.Column(
            "tier_id",
            sa.Uuid(),
            sa.ForeignKey("subscription_tiers.id"),
            nullable=False,
            server_default=sa.text(f"'{FREE_TIER_ID}'"),
        ),
    )

    # 4. Backfill existing tenants (handled by server_default, but explicit for safety)
    op.execute(
        sa.text(
            "UPDATE tenants SET tier_id = :free_id WHERE tier_id IS NULL"
        ).bindparams(free_id=FREE_TIER_ID)
    )


def downgrade() -> None:
    op.drop_column("tenants", "tier_id")
    op.drop_table("subscription_tiers")
```

---

## 10. Frontend Design

### 10.1 New Feature Module: `features/subscription`

```
frontend/src/features/subscription/
  api/
    keys.ts          -- React Query keys
    queries.ts       -- useActiveTiers(), useTenantTier()
    index.ts
  components/
    TierCard.tsx     -- Dashboard tier card with usage bars
    QuotaExceededDialog.tsx  -- Modal on 429 responses
  index.ts
```

### 10.2 API Client

```typescript
// queries.ts
export interface TierInfo {
  id: string;
  name: string;
  slug: string;
  monthly_document_limit: number | null;
  max_templates: number | null;
  max_users: number | null;
  bulk_generation_limit: number;
  max_template_shares: number | null;
}

export interface UsageDetail {
  used: number;
  limit: number | null;
  percentage: number | null;
}

export interface TenantTierResponse {
  tier: TierInfo;
  usage: {
    documents: UsageDetail;
    templates: UsageDetail;
    users: UsageDetail;
    bulk_generation_limit: number;
    max_template_shares: number | null;
  };
}

export function useTenantTier() {
  return useQuery({
    queryKey: subscriptionKeys.tenantTier(),
    queryFn: async () => {
      const { data } = await apiClient.get<TenantTierResponse>("/tenant/tier");
      return data;
    },
  });
}
```

### 10.3 TierCard Component

Placed on the usage/dashboard page. Shows:
- Plan name badge (Free / Pro / Enterprise)
- Three progress bars: Documents, Templates, Users
- Each bar shows "X / Y" (or "X / unlimited")
- Color coding: green (<60%), yellow (60-80%), red (>80%)
- "Upgrade" text link when on Free tier

### 10.4 QuotaExceededDialog Component

A reusable dialog that:
- Listens for 429 responses via an Axios response interceptor added to `api-client.ts`
- When a 429 with `limit_type` in the body is detected, opens a modal
- Shows: "Quota exceeded: [limit_type] limit reached" with current usage and limit
- CTA: "Contact your administrator to upgrade your plan"

**Axios interceptor addition** (`api-client.ts`):

```typescript
// Store for the quota exceeded callback (set by QuotaExceededProvider)
let onQuotaExceeded: ((data: QuotaExceededData) => void) | null = null;

export function setQuotaExceededHandler(handler: typeof onQuotaExceeded) {
  onQuotaExceeded = handler;
}

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 429 && error.response?.data?.limit_type) {
      onQuotaExceeded?.(error.response.data);
    }
    // ... existing 401 handling ...
    return Promise.reject(error);
  }
);
```

### 10.5 Layout Integration

In `_authenticated.tsx`, add the TierCard or a compact tier indicator in the header. The QuotaExceededDialog provider wraps the `<Outlet />`.

### 10.6 Existing Component Updates

- **UsageWidget**: Enhance to show "23/50 documents" with a progress bar (currently shows just the count)
- **UserList**: Add "2/3 users" badge in the header (admin only)
- **TemplateList**: Add "3/5 templates" badge near the upload button

---

## 11. File Change Summary

### New Files

| File | Layer | Description |
|------|-------|-------------|
| `domain/entities/subscription_tier.py` | Domain | SubscriptionTier entity + tier UUID constants |
| `domain/ports/subscription_tier_repository.py` | Domain | SubscriptionTierRepository ABC |
| `infrastructure/persistence/models/subscription_tier.py` | Infrastructure | SubscriptionTierModel ORM |
| `infrastructure/persistence/repositories/subscription_tier_repository.py` | Infrastructure | SQLAlchemy implementation |
| `application/services/quota_service.py` | Application | QuotaService |
| `presentation/api/v1/tiers.py` | Presentation | Tier + tenant-tier endpoints |
| `presentation/schemas/tier.py` | Presentation | Pydantic schemas |
| `alembic/versions/005_subscription_tiers.py` | Migration | DB migration |
| `frontend/src/features/subscription/` | Frontend | New feature module (api + components) |

### Modified Files

| File | Change |
|------|--------|
| `domain/entities/tenant.py` | Add `tier_id` field |
| `domain/entities/__init__.py` | Export SubscriptionTier + constants |
| `domain/exceptions.py` | Add QuotaExceededError |
| `domain/ports/user_repository.py` | Add `count_active_by_tenant()` |
| `domain/ports/template_repository.py` | Add `count_by_tenant()`, `count_shares()` |
| `domain/ports/__init__.py` | Export SubscriptionTierRepository |
| `infrastructure/persistence/models/tenant.py` | Add `tier_id` column + relationship |
| `infrastructure/persistence/models/__init__.py` | Export SubscriptionTierModel |
| `infrastructure/persistence/repositories/user_repository.py` | Implement `count_active_by_tenant()` |
| `infrastructure/persistence/repositories/template_repository.py` | Implement `count_by_tenant()`, `count_shares()` |
| `infrastructure/persistence/repositories/__init__.py` | Export SQLAlchemySubscriptionTierRepository |
| `application/services/__init__.py` | Add `get_quota_service()`, update `get_template_service()`, update `get_document_service()` |
| `application/services/document_service.py` | Add `quota_service` param + quota checks in generate_single, generate_bulk, parse_excel_data |
| `application/services/template_service.py` | Add `quota_service` param + quota checks in upload_template, share_template |
| `presentation/api/v1/users.py` | Inject QuotaService, call check_user_limit |
| `presentation/api/v1/documents.py` | Pass tenant_id + user_bulk_override to parse_excel_data |
| `main.py` | Register tier routers + QuotaExceededError handler |
| `frontend/src/shared/lib/api-client.ts` | Add 429 quota interceptor |
| `frontend/src/routes/_authenticated.tsx` | Add QuotaExceededDialog provider |
| `frontend/src/features/usage/components/UsageWidget.tsx` | Enhance with limit + progress bar |

---

## 12. Dependency Diagram

```
                    SubscriptionTierRepository
                           |
                    SubscriptionTierModel
                           |
QuotaService ------+------ UsageRepository
    |              |
    |              +------ TemplateRepository (count_by_tenant, count_shares)
    |              |
    |              +------ UserRepository (count_active_by_tenant)
    |
    +--- injected into --> DocumentService
    +--- injected into --> TemplateService
    +--- injected into --> users router (via Depends)
    +--- injected into --> tiers router (via Depends)
```

---

## 13. Test Strategy

### 13.1 Fakes Needed

- `FakeSubscriptionTierRepository` -- returns configurable tier(s)
- `FakeQuotaService` -- pass-through (no checks) or raises on demand

### 13.2 Unit Tests

- `test_quota_service.py`:
  - `check_document_quota` -- under limit, at limit, over limit, unlimited (None)
  - `check_template_limit` -- under, at, over, unlimited
  - `check_user_limit` -- under, at, over, unlimited
  - `check_bulk_limit` -- with/without user override, over limit
  - `check_share_limit` -- under, at, over, unlimited
  - `get_usage_summary` -- verify all fields populated

- Extend `test_document_service.py`:
  - Verify quota check called before generate_single
  - Verify quota check called before generate_bulk
  - Verify QuotaExceededError propagates when over quota

- Extend `test_template_service.py`:
  - Verify template limit check before upload_template
  - Verify share limit check before share_template

### 13.3 Integration Tests

- `test_tier_api.py`:
  - GET /tiers returns 3 tiers
  - GET /tenant/tier returns usage summary
  - Generate document when at quota limit returns 429
  - Upload template when at template limit returns 429
  - Create user when at user limit returns 429

---

## 14. Sequencing / Task Dependencies

```
1. Migration 005 (DB foundation)
   |
2. Domain entities + ports (SubscriptionTier, QuotaExceededError, new port methods)
   |
3. Infrastructure (ORM models, repositories, count methods)
   |
4. QuotaService (application layer)
   |
5. DI factory updates (services/__init__.py)
   |
6. Service integration (DocumentService, TemplateService quota checks)
   |
7. API endpoints (tiers.py, users.py quota check)
   |
8. Error handler (main.py)
   |
9. Frontend (subscription feature module, widget updates, quota dialog)
   |
10. Tests (unit + integration)
```

Steps 1-3 can be implemented in one batch. Steps 4-5 form a batch. Steps 6-8 form a batch. Step 9 (frontend) can proceed in parallel with steps 6-8 once the API contract is defined. Step 10 follows TDD -- tests are written alongside each batch.
