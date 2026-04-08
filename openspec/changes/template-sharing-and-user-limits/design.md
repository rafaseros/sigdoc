# Technical Design: template-sharing-and-user-limits

## Overview

This document defines the technical architecture for introducing private-by-default templates with explicit sharing, and per-user bulk generation limits. Every decision is grounded in the current codebase: SQLAlchemy async + PostgreSQL + TenantMixin + Clean Architecture (domain ports, infra adapters, presentation).

---

## ADR-1: Composite Unique vs Surrogate PK for template_shares

### Context

The `template_shares` table needs a primary key strategy. Two options: (A) surrogate UUID PK + unique constraint on `(template_id, user_id)`, or (B) composite PK `(template_id, user_id)` with no surrogate.

### Decision

**Surrogate UUID PK + unique constraint on `(template_id, user_id)`.**

### Rationale

1. **Consistency with every other table in the codebase** -- all 5 existing tables (`tenants`, `users`, `templates`, `template_versions`, `documents`) use UUID PKs via `UUIDMixin`. Breaking this pattern for one table creates cognitive overhead for zero benefit.

2. **The `shared_by` and `shared_at` metadata fields** make this more than a pure join table. It has entity semantics (who shared, when) which justifies an identity column.

3. **API referencing** -- the `DELETE /templates/{id}/shares/{user_id}` endpoint uses `user_id` in the path, not the share's PK. But having a UUID PK means we can reference individual share records in logs, audit trails, and future webhook events without exposing composite keys.

4. **SQLAlchemy relationship loading** -- surrogate PKs work more naturally with `relationship()` lazy loading and identity map behavior.

### Consequences

- Table has `id` UUID PK (via `UUIDMixin`) + `UNIQUE(template_id, user_id)` constraint
- The unique constraint doubles as the primary lookup index (composite index on the unique constraint columns)
- Extra 16 bytes per row for the UUID -- negligible

---

## ADR-2: New TemplateShareRepository Port vs Extending TemplateRepository

### Context

Sharing operations need repository methods: `add_share`, `remove_share`, `list_shares_for_template`, `has_access`. Should these go on `TemplateRepository` (extend) or a new `TemplateShareRepository` (separate)?

### Decision

**Extend `TemplateRepository` with sharing-related methods. No new port.**

### Rationale

1. **Single Responsibility is about cohesion, not method count.** Template sharing IS template management. The share table exists to control template visibility. Splitting it into a separate repo would force the service to coordinate two repositories for a single domain concept.

2. **The critical query is `list_accessible()`** -- templates where `created_by = user_id OR EXISTS share OR user is admin`. This query joins `templates` with `template_shares`. If shares lived in a separate repo, the service would need to fetch share IDs first, then pass them to the template repo -- two round trips instead of one SQL query.

3. **The existing codebase has 3 repos mapping 1:1 to domain aggregates** (template, document, user). `template_shares` is not an aggregate -- it's a subordinate entity of the Template aggregate. It belongs in the template repo.

4. **Counterargument**: "But the port interface gets big." It goes from 8 methods to 12. That's fine. The `DocumentRepository` port could also grow if we added batch-level queries. Method count is not a quality metric.

### Consequences

- `TemplateRepository` port gains 4 new abstract methods
- `SQLAlchemyTemplateRepository` implements them using the same session
- No new port file, no new fake file -- extend `FakeTemplateRepository` with the same 4 methods
- `TemplateService` gets sharing logic without needing a second repository

---

## ADR-3: Authorization Pattern -- Service-Level Enforcement, Not Middleware

### Context

Ownership and sharing checks need to happen for version upload, delete, get, share/unshare. Options: (A) a reusable FastAPI dependency (middleware-ish), (B) service-layer enforcement, (C) decorator pattern.

### Decision

**Service-layer enforcement via an internal `_check_template_access()` method on `TemplateService`.**

### Rationale

1. **Clean Architecture boundary** -- authorization rules are business logic: "only the owner can version a template" is a domain rule, not an HTTP concern. Putting it in a FastAPI dependency couples the authorization logic to the presentation layer.

2. **The check requires DB access** -- we need to query the template's `created_by` field and optionally check `template_shares`. The service already has the repository. A middleware dependency would need its own repository instance or duplicate the DI wiring.

3. **Testability** -- service-level checks are tested with unit tests using fakes. Middleware-level checks require integration tests with HTTP clients. Unit tests are faster, more focused, and already the established pattern (see hardening design ADR-2).

4. **The admin bypass is already a service concern** -- the current `list_templates` endpoint passes `created_by=None` for admins. This pattern continues: the service receives the `user_id` and `role`, and decides access internally.

5. **Reusable helper method** -- `_check_template_access(template_id, user_id, role, required_level)` where `required_level` is `"view"` (owner/shared/admin) or `"manage"` (owner/admin only). One method, two permission levels, called from every service method that needs it.

### Consequences

- New domain exception: `TemplateAccessDeniedError(DomainError)` -- raised when access check fails
- API layer catches `TemplateAccessDeniedError` and returns 403
- Service methods receive `user_id` and `role` parameters (already available from `CurrentUser`)
- No new middleware, no new dependency

---

## ADR-4: Per-User Limit Resolution -- Service Layer with User Repository

### Context

`DocumentService.parse_excel_data` currently uses `self._bulk_limit` (injected from `Settings.bulk_generation_limit`). Now the limit must be resolved per-user: `user.bulk_generation_limit ?? settings.bulk_generation_limit`. Where does this resolution happen?

### Decision

**Resolve at the API layer (dependency injection) and pass the effective limit to `DocumentService.__init__`.**

### Rationale

1. **DocumentService already receives `bulk_generation_limit` as a constructor parameter.** The resolution logic is: "read user's limit from DB, fall back to settings." This is DI wiring, not business logic.

2. **Alternative: inject `UserRepository` into `DocumentService`** -- this would mean DocumentService depends on UserRepository just to read one integer. That violates Interface Segregation -- DocumentService has no business knowing about users beyond their ID.

3. **The `get_document_service` factory function** already accesses `get_settings()` and the session. Adding a user lookup there is natural:

```python
async def get_document_service(
    session: AsyncSession = Depends(get_tenant_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> DocumentService:
    settings = get_settings()
    user_repo = SQLAlchemyUserRepository(session)
    user = await user_repo.get_by_id(current_user.user_id)
    effective_limit = (
        user.bulk_generation_limit
        if user and user.bulk_generation_limit is not None
        else settings.bulk_generation_limit
    )
    return DocumentService(
        ...,
        bulk_generation_limit=effective_limit,
    )
```

4. **This keeps DocumentService pure** -- it receives an integer, not a user object. Unit tests don't change (they already inject the limit as an int).

### Consequences

- `get_document_service` gains a `current_user` dependency and does a user lookup
- `DocumentService` interface unchanged -- still receives `bulk_generation_limit: int`
- One extra DB query per document-service call (user lookup) -- acceptable since it's cached in the session identity map
- The effective limit is also exposed via `GET /auth/me` for frontend use

---

## ADR-5: template_shares and TenantMixin -- Include Tenant Column

### Context

The `template_shares` table has `tenant_id`. Should it use `TenantMixin` (which adds the `tenant_id` FK and enables automatic tenant filtering via `do_orm_execute`)?

### Decision

**YES -- use `TenantMixin` on `TemplateShareModel`.**

### Rationale

1. **Every table with tenant-scoped data uses `TenantMixin`** -- templates, users, documents, template_versions. Breaking this for shares would mean share queries bypass automatic tenant filtering, creating a cross-tenant data leak risk.

2. **The `do_orm_execute` event** automatically filters `SELECT` queries on `TenantMixin` models by `session.info["tenant_id"]`. Without it, a `list_shares` query could return shares from other tenants if the query doesn't explicitly filter.

3. **The tenant_id on shares is redundant** (derivable from template.tenant_id), but it serves as a belt-and-suspenders safety net for tenant isolation.

### Consequences

- `TemplateShareModel` extends `TenantMixin` + `UUIDMixin` + `Base`
- Automatic tenant filtering applies to all share queries
- Share creation must set `tenant_id` explicitly (same as all other models)

---

## Data Model

### New Table: template_shares

```sql
CREATE TABLE template_shares (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    template_id UUID NOT NULL REFERENCES templates(id) ON DELETE CASCADE,
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    tenant_id   UUID NOT NULL REFERENCES tenants(id),
    shared_by   UUID NOT NULL REFERENCES users(id),
    shared_at   TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),

    CONSTRAINT uq_template_shares_template_user UNIQUE (template_id, user_id)
);

CREATE INDEX ix_template_shares_user ON template_shares(user_id);
CREATE INDEX ix_template_shares_tenant ON template_shares(tenant_id);
-- The unique constraint on (template_id, user_id) implicitly creates an index
```

**Index rationale:**
- `UNIQUE(template_id, user_id)` -- primary lookup for "does user X have access to template Y?" and prevents duplicates
- `ix_template_shares_user` -- for "list all templates shared with user X" (the `list_accessible` query)
- `ix_template_shares_tenant` -- for TenantMixin automatic filtering

### Modified Table: users

```sql
ALTER TABLE users ADD COLUMN bulk_generation_limit INTEGER NULL;
-- No default. NULL means "use global setting."
```

### New Domain Entity: TemplateShare

```python
# backend/src/app/domain/entities/template_share.py
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass
class TemplateShare:
    id: UUID
    template_id: UUID
    user_id: UUID
    tenant_id: UUID
    shared_by: UUID
    shared_at: datetime | None = None
```

### Modified Domain Entity: User

```python
# backend/src/app/domain/entities/user.py
@dataclass
class User:
    id: UUID
    tenant_id: UUID
    email: str
    hashed_password: str
    full_name: str
    role: str = "user"
    is_active: bool = True
    bulk_generation_limit: int | None = None  # NEW: None = use global default
    created_at: datetime | None = None
    updated_at: datetime | None = None
```

### New ORM Model: TemplateShareModel

```python
# backend/src/app/infrastructure/persistence/models/template_share.py
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint, Index, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import TenantMixin
from .base import Base, UUIDMixin


class TemplateShareModel(UUIDMixin, TenantMixin, Base):
    __tablename__ = "template_shares"
    __table_args__ = (
        UniqueConstraint("template_id", "user_id", name="uq_template_shares_template_user"),
        Index("ix_template_shares_user", "user_id"),
    )

    template_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("templates.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    shared_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
    )
    shared_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )

    template = relationship("TemplateModel", lazy="selectin")
    user = relationship("UserModel", foreign_keys=[user_id], lazy="selectin")
    sharer = relationship("UserModel", foreign_keys=[shared_by], lazy="selectin")
```

### Modified ORM Model: UserModel

```python
# Add to backend/src/app/infrastructure/persistence/models/user.py
from sqlalchemy import Integer
# ... existing imports ...

class UserModel(UUIDMixin, TimestampMixin, TenantMixin, Base):
    # ... existing columns ...
    bulk_generation_limit: Mapped[int | None] = mapped_column(
        Integer, nullable=True, default=None
    )
```

---

## Repository Changes

### Extended Port: TemplateRepository

```python
# New abstract methods added to backend/src/app/domain/ports/template_repository.py

class TemplateRepository(ABC):
    # ... existing 8 methods unchanged ...

    @abstractmethod
    async def list_accessible(
        self,
        user_id: UUID,
        page: int = 1,
        size: int = 20,
        search: str | None = None,
    ) -> tuple[list[Template], int]:
        """List templates user owns OR has been shared.
        Returns (templates, total_count)."""
        ...

    @abstractmethod
    async def add_share(
        self,
        template_id: UUID,
        user_id: UUID,
        tenant_id: UUID,
        shared_by: UUID,
    ) -> None:
        """Create a share record. Idempotent -- no error if already exists."""
        ...

    @abstractmethod
    async def remove_share(self, template_id: UUID, user_id: UUID) -> None:
        """Remove a share record. No error if not found."""
        ...

    @abstractmethod
    async def has_access(self, template_id: UUID, user_id: UUID) -> bool:
        """Check if user has access via ownership or share."""
        ...

    @abstractmethod
    async def list_shares(self, template_id: UUID) -> list:
        """List all shares for a template. Returns share records with user info."""
        ...
```

### Implementation: SQLAlchemyTemplateRepository

The key query is `list_accessible`. This uses a UNION approach:

```python
async def list_accessible(
    self,
    user_id: UUID,
    page: int = 1,
    size: int = 20,
    search: str | None = None,
) -> tuple[list, int]:
    from sqlalchemy import union_all, literal_column

    # Owned templates
    owned = (
        select(
            TemplateModel.id,
            literal_column("'owned'").label("access_type"),
        )
        .where(TemplateModel.created_by == user_id)
    )

    # Shared templates
    shared = (
        select(
            TemplateShareModel.template_id.label("id"),
            literal_column("'shared'").label("access_type"),
        )
        .where(TemplateShareModel.user_id == user_id)
    )

    accessible = union_all(owned, shared).subquery("accessible")

    # Main query joining back to TemplateModel for full data
    stmt = (
        select(TemplateModel, accessible.c.access_type)
        .join(accessible, TemplateModel.id == accessible.c.id)
        .options(selectinload(TemplateModel.versions))
    )
    count_stmt = (
        select(func.count())
        .select_from(accessible)
    )

    if search:
        # Need to join for search filter in count too
        stmt = stmt.where(TemplateModel.name.ilike(f"%{search}%"))
        count_stmt = (
            select(func.count())
            .select_from(TemplateModel)
            .join(accessible, TemplateModel.id == accessible.c.id)
            .where(TemplateModel.name.ilike(f"%{search}%"))
        )

    total_result = await self._session.execute(count_stmt)
    total = total_result.scalar_one()

    offset = (page - 1) * size
    stmt = stmt.order_by(TemplateModel.created_at.desc()).offset(offset).limit(size)

    result = await self._session.execute(stmt)
    rows = result.unique().all()
    # Each row is (TemplateModel, access_type)
    # Attach access_type as a transient attribute
    templates = []
    for template, access_type in rows:
        template._access_type = access_type
        templates.append(template)

    return templates, total
```

**`add_share` -- idempotent via INSERT ... ON CONFLICT DO NOTHING:**

```python
async def add_share(
    self, template_id: UUID, user_id: UUID, tenant_id: UUID, shared_by: UUID
) -> None:
    from sqlalchemy.dialects.postgresql import insert

    stmt = insert(TemplateShareModel).values(
        id=uuid.uuid4(),
        template_id=template_id,
        user_id=user_id,
        tenant_id=tenant_id,
        shared_by=shared_by,
    ).on_conflict_do_nothing(
        constraint="uq_template_shares_template_user"
    )
    await self._session.execute(stmt)
    await self._session.flush()
```

**`has_access` -- single query:**

```python
async def has_access(self, template_id: UUID, user_id: UUID) -> bool:
    # Check ownership
    template = await self.get_by_id(template_id)
    if template is None:
        return False
    if template.created_by == user_id:
        return True
    # Check share
    stmt = select(TemplateShareModel.id).where(
        TemplateShareModel.template_id == template_id,
        TemplateShareModel.user_id == user_id,
    ).limit(1)
    result = await self._session.execute(stmt)
    return result.scalar_one_or_none() is not None
```

---

## Service Layer Changes

### TemplateService -- Authorization Helper

```python
class TemplateService:
    # ... existing __init__ unchanged ...

    async def _check_access(
        self,
        template_id: uuid.UUID,
        user_id: uuid.UUID,
        role: str,
        require_owner: bool = False,
    ) -> None:
        """Check user's access to a template.

        Args:
            template_id: The template to check.
            user_id: The requesting user.
            role: User's role ("admin" or "user").
            require_owner: If True, shared access is insufficient (for version/delete).

        Raises:
            TemplateNotFoundError: Template doesn't exist.
            TemplateAccessDeniedError: User lacks required access.
        """
        template = await self._repository.get_by_id(template_id)
        if not template:
            raise TemplateNotFoundError(f"Template {template_id} not found")

        # Admins always pass
        if role == "admin":
            return

        is_owner = template.created_by == user_id
        if require_owner and not is_owner:
            raise TemplateAccessDeniedError(
                "Solo el propietario de la plantilla puede realizar esta accion"
            )
        if not is_owner:
            has_share = await self._repository.has_access(template_id, user_id)
            if not has_share:
                raise TemplateAccessDeniedError(
                    "No tiene acceso a esta plantilla"
                )
```

### Modified Service Methods

**`get_template`** -- add access check:

```python
async def get_template(self, template_id: uuid.UUID, user_id: uuid.UUID, role: str):
    await self._check_access(template_id, user_id, role)
    return await self._repository.get_by_id(template_id)
```

**`upload_new_version`** -- owner-only check:

```python
async def upload_new_version(
    self, template_id: str, file_bytes: bytes, file_size: int,
    tenant_id: str, user_id: str, role: str,
) -> dict:
    tid = uuid.UUID(template_id)
    await self._check_access(tid, uuid.UUID(user_id), role, require_owner=True)
    # ... rest unchanged ...
```

**`delete_template`** -- owner or admin:

```python
async def delete_template(
    self, template_id: uuid.UUID, user_id: uuid.UUID, role: str
) -> None:
    await self._check_access(template_id, user_id, role, require_owner=True)
    # ... rest unchanged ...
```

**`list_templates`** -- bifurcate admin vs regular:

```python
async def list_templates(
    self, page: int, size: int, search: str | None,
    user_id: str | None, role: str,
) -> tuple[list, int]:
    if role == "admin":
        # Admins see all tenant templates (existing behavior)
        return await self._repository.list_paginated(page=page, size=size, search=search)
    else:
        # Regular users see owned + shared
        return await self._repository.list_accessible(
            user_id=uuid.UUID(user_id),
            page=page, size=size, search=search,
        )
```

**New: `share_template` and `unshare_template`:**

```python
async def share_template(
    self, template_id: uuid.UUID, target_user_id: uuid.UUID,
    owner_id: uuid.UUID, owner_role: str, tenant_id: uuid.UUID,
) -> None:
    """Share a template with a target user. Only owner can share."""
    await self._check_access(template_id, owner_id, owner_role, require_owner=True)

    # Validate target user exists and is in same tenant
    # (user_repo is NOT injected -- see design note below)
    # This validation happens at the API layer before calling the service.

    await self._repository.add_share(
        template_id=template_id,
        user_id=target_user_id,
        tenant_id=tenant_id,
        shared_by=owner_id,
    )

async def unshare_template(
    self, template_id: uuid.UUID, target_user_id: uuid.UUID,
    owner_id: uuid.UUID, owner_role: str,
) -> None:
    """Remove a share. Only owner can unshare."""
    await self._check_access(template_id, owner_id, owner_role, require_owner=True)
    await self._repository.remove_share(template_id, target_user_id)

async def list_template_shares(
    self, template_id: uuid.UUID, user_id: uuid.UUID, role: str,
) -> list:
    """List shares for a template. Only owner or admin can view shares."""
    await self._check_access(template_id, user_id, role, require_owner=True)
    return await self._repository.list_shares(template_id)
```

**Design note on target user validation:**
The "target user exists and is in same tenant" check happens at the API layer, not in `TemplateService`. Why? Because `TemplateService` should not depend on `UserRepository` -- it would violate the principle that each service manages its own aggregate. The API layer already has access to a `UserRepository` (via session) and can validate the target user before calling the service.

### DocumentService -- Template Access Check

```python
async def generate_single(
    self, template_version_id: str, variables: dict,
    tenant_id: str, created_by: str, role: str,  # NEW: role param
) -> dict:
    version = await self._tpl_repo.get_version_by_id(uuid.UUID(template_version_id))
    if not version:
        raise TemplateVersionNotFoundError(...)

    # NEW: Check access to the parent template
    if role != "admin":
        has_access = await self._tpl_repo.has_access(
            version.template_id, uuid.UUID(created_by)
        )
        if not has_access:
            raise TemplateAccessDeniedError("No tiene acceso a esta plantilla")

    # ... rest unchanged ...
```

Same check added to `generate_bulk`, `parse_excel_data`, and `generate_excel_template`.

---

## API Layer Changes

### New Endpoints: Template Sharing

```python
# Added to backend/src/app/presentation/api/v1/templates.py

@router.post("/{template_id}/shares", status_code=status.HTTP_201_CREATED)
async def share_template(
    template_id: UUID,
    body: ShareTemplateRequest,  # { "user_id": UUID }
    current_user: CurrentUser = Depends(get_current_user),
    service: TemplateService = Depends(get_template_service),
    session: AsyncSession = Depends(get_tenant_session),
):
    """Share a template with another user in the same tenant."""
    # Validate target user exists in same tenant
    user_repo = SQLAlchemyUserRepository(session)
    target = await user_repo.get_by_id(body.user_id)
    if not target or target.tenant_id != current_user.tenant_id:
        raise HTTPException(422, "Usuario no encontrado en este tenant")
    if not target.is_active:
        raise HTTPException(422, "No se puede compartir con un usuario inactivo")

    try:
        await service.share_template(
            template_id=template_id,
            target_user_id=body.user_id,
            owner_id=current_user.user_id,
            owner_role=current_user.role,
            tenant_id=current_user.tenant_id,
        )
    except TemplateAccessDeniedError as e:
        raise HTTPException(403, str(e))
    except TemplateNotFoundError:
        raise HTTPException(404, "Plantilla no encontrada")

    return {"status": "shared"}


@router.delete("/{template_id}/shares/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unshare_template(
    template_id: UUID,
    user_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    service: TemplateService = Depends(get_template_service),
):
    """Remove a share from a template."""
    try:
        await service.unshare_template(
            template_id=template_id,
            target_user_id=user_id,
            owner_id=current_user.user_id,
            owner_role=current_user.role,
        )
    except TemplateAccessDeniedError as e:
        raise HTTPException(403, str(e))
    except TemplateNotFoundError:
        raise HTTPException(404, "Plantilla no encontrada")


@router.get("/{template_id}/shares")
async def list_template_shares(
    template_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    service: TemplateService = Depends(get_template_service),
):
    """List users a template is shared with. Owner or admin only."""
    try:
        shares = await service.list_template_shares(
            template_id=template_id,
            user_id=current_user.user_id,
            role=current_user.role,
        )
    except TemplateAccessDeniedError as e:
        raise HTTPException(403, str(e))
    except TemplateNotFoundError:
        raise HTTPException(404, "Plantilla no encontrada")

    return [
        {
            "user_id": str(s.user_id),
            "user_email": s.user.email if hasattr(s, "user") else None,
            "user_name": s.user.full_name if hasattr(s, "user") else None,
            "shared_by": str(s.shared_by),
            "shared_at": s.shared_at,
        }
        for s in shares
    ]
```

### Modified Existing Endpoints

**`list_templates`** -- pass role and user_id:

```python
@router.get("", response_model=TemplateListResponse)
async def list_templates(...):
    templates, total = await service.list_templates(
        page=page, size=size, search=search,
        user_id=str(current_user.user_id),
        role=current_user.role,
    )
    # Build response -- add access_type field to TemplateResponse
    items = []
    for t in templates:
        access_type = getattr(t, "_access_type", "owned")
        items.append(TemplateResponse(
            ...,
            access_type=access_type,
            is_owner=(t.created_by == current_user.user_id),
        ))
```

**`get_template`** -- add access check:

```python
@router.get("/{template_id}")
async def get_template(...):
    try:
        t = await service.get_template(
            template_id, user_id=current_user.user_id, role=current_user.role
        )
    except TemplateAccessDeniedError as e:
        raise HTTPException(403, str(e))
```

**`upload_new_version`** -- pass user_id and role:

```python
result = await service.upload_new_version(
    ...,
    user_id=str(current_user.user_id),
    role=current_user.role,
)
```

**`delete_template`** -- pass user_id and role:

```python
await service.delete_template(
    template_id, user_id=current_user.user_id, role=current_user.role
)
```

**`generate_document` / `generate_bulk`** -- pass role:

```python
result = await service.generate_single(
    ...,
    role=current_user.role,  # NEW
)
```

### New/Modified Pydantic Schemas

```python
# backend/src/app/presentation/schemas/template.py

class ShareTemplateRequest(BaseModel):
    user_id: UUID  # Target user to share with

class ShareResponse(BaseModel):
    user_id: str
    user_email: str | None = None
    user_name: str | None = None
    shared_by: str
    shared_at: datetime

class TemplateResponse(BaseModel):
    # ... existing fields ...
    access_type: str = "owned"  # NEW: "owned" | "shared" | "admin"
    is_owner: bool = True       # NEW: convenience flag for frontend
```

```python
# backend/src/app/presentation/schemas/user.py

class UpdateUserRequest(BaseModel):
    email: str | None = None
    full_name: str | None = None
    is_active: bool | None = None
    bulk_generation_limit: int | None = None  # NEW -- admin can set/clear

# backend/src/app/presentation/schemas/auth.py

class UserResponse(BaseModel):
    id: str
    email: str
    full_name: str
    role: str
    tenant_id: str
    effective_bulk_limit: int | None = None  # NEW -- resolved limit for frontend
```

### Modified GET /auth/me

```python
@router.get("/me")
async def get_me(
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    repo = SQLAlchemyUserRepository(session)
    user = await repo.get_by_id(current_user.user_id)
    if not user:
        raise HTTPException(404, "User not found")

    settings = get_settings()
    effective_limit = (
        user.bulk_generation_limit
        if user.bulk_generation_limit is not None
        else settings.bulk_generation_limit
    )

    return UserResponse(
        id=str(user.id),
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        tenant_id=str(user.tenant_id),
        effective_bulk_limit=effective_limit,
    )
```

---

## New Domain Exception

```python
# Add to backend/src/app/domain/exceptions.py

class TemplateAccessDeniedError(DomainError):
    """User does not have required access to the template."""
```

---

## Alembic Migration

**Revision `003_template_shares_and_user_limits`**, depends on `002`.

```python
"""Add template_shares table and users.bulk_generation_limit column

Revision ID: 003
Revises: 002
"""

def upgrade() -> None:
    # 1. template_shares table
    op.create_table(
        "template_shares",
        sa.Column("id", sa.Uuid(), primary_key=True, default=sa.text("gen_random_uuid()")),
        sa.Column("template_id", sa.Uuid(),
                  sa.ForeignKey("templates.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Uuid(),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", sa.Uuid(),
                  sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("shared_by", sa.Uuid(),
                  sa.ForeignKey("users.id"), nullable=False),
        sa.Column("shared_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("template_id", "user_id",
                            name="uq_template_shares_template_user"),
    )
    op.create_index("ix_template_shares_user", "template_shares", ["user_id"])

    # 2. Per-user bulk generation limit
    op.add_column(
        "users",
        sa.Column("bulk_generation_limit", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "bulk_generation_limit")
    op.drop_table("template_shares")
```

**Backfill strategy: NONE required.** The `list_accessible` query includes `created_by = user_id` as a condition, so existing templates are visible to their creators without any share records. Admins already see all templates. No data migration needed.

---

## Frontend Changes

### Template List -- Sharing Indicators

The `TemplateList.tsx` table adds a column for sharing status:

- **Owned templates**: show normally (no indicator)
- **Shared templates**: show a "Compartida" badge with a share icon
- The `access_type` field from the API response drives this

### Template Detail -- Share Dialog

`TemplateDetail.tsx` gets a new "Compartir" button (visible only to owners, i.e., `is_owner === true`):

- Opens a `ShareTemplateDialog` component
- Dialog shows a user picker (fetches tenant users from `GET /users`)
- Displays currently shared users with "remove" buttons
- Calls `POST /templates/{id}/shares` and `DELETE /templates/{id}/shares/{userId}`

New components:
- `frontend/src/features/templates/components/ShareTemplateDialog.tsx`

### Template Detail -- Conditional Action Buttons

Owner-only actions (version upload, delete) are conditionally rendered based on `is_owner`:

```tsx
{template.is_owner && (
  <>
    <Button onClick={uploadVersion}>Subir Nueva Version</Button>
    <Button variant="destructive" onClick={deleteTemplate}>Eliminar</Button>
  </>
)}
<Button onClick={shareTemplate}>Compartir</Button> {/* owner only */}
```

### Bulk Generation -- User Limit Display

In the bulk generation page, the `effective_bulk_limit` from `GET /auth/me` is displayed:

```tsx
<p>Limite maximo: {user.effective_bulk_limit} filas por archivo</p>
```

### New API Hooks

```typescript
// frontend/src/features/templates/api/mutations.ts

export function useShareTemplate() { ... }
export function useUnshareTemplate() { ... }
export function useTemplateShares(templateId: string) { ... }
```

---

## Test Strategy

### New Unit Tests (using fakes)

| Test | What it verifies |
|------|------------------|
| `test_list_templates_returns_owned_and_shared` | Regular user sees owned + shared templates with correct `access_type` |
| `test_list_templates_admin_sees_all` | Admin bypass returns all tenant templates |
| `test_get_template_access_denied` | Unrelated user gets `TemplateAccessDeniedError` |
| `test_get_template_shared_user_succeeds` | Shared user can view template |
| `test_upload_version_owner_only` | Shared user gets `TemplateAccessDeniedError` |
| `test_delete_template_owner_only` | Shared user gets `TemplateAccessDeniedError` |
| `test_delete_template_admin_bypass` | Admin can delete any template |
| `test_share_template_by_owner` | Owner shares successfully |
| `test_share_template_non_owner_denied` | Non-owner gets error |
| `test_unshare_template` | Share removed, user no longer has access |
| `test_share_idempotent` | Duplicate share does not error |
| `test_bulk_limit_user_override` | User's limit used when set |
| `test_bulk_limit_fallback_to_global` | Global default used when user limit is NULL |
| `test_generate_checks_template_access` | `generate_single` rejects unrelated user |
| `test_generate_allows_shared_user` | `generate_single` succeeds for shared user |

### New Integration Tests

| Test | What it verifies |
|------|------------------|
| `test_share_endpoint_201` | POST /templates/{id}/shares returns 201 |
| `test_share_endpoint_403_non_owner` | Non-owner share attempt returns 403 |
| `test_share_endpoint_422_invalid_user` | Share with non-tenant user returns 422 |
| `test_unshare_endpoint_204` | DELETE /templates/{id}/shares/{uid} returns 204 |
| `test_list_templates_mixed_access` | List shows owned + shared with correct access_type |
| `test_get_template_403_unrelated` | GET /templates/{id} returns 403 for unrelated user |
| `test_version_upload_403_shared_user` | POST /templates/{id}/versions returns 403 |
| `test_delete_403_shared_user` | DELETE /templates/{id} returns 403 |
| `test_generate_403_unrelated` | POST /documents/generate returns 403 |
| `test_bulk_limit_per_user` | Bulk generation respects user-specific limit |
| `test_me_effective_bulk_limit` | GET /auth/me returns correct effective_bulk_limit |
| `test_admin_set_user_limit` | PUT /users/{id} with bulk_generation_limit updates |

### Extended Fakes

`FakeTemplateRepository` gains 5 new methods (`list_accessible`, `add_share`, `remove_share`, `has_access`, `list_shares`) backed by a `self._shares: dict[tuple[UUID, UUID], TemplateShare]` dict.

---

## Files Modified/Created

### New Files (5)
- `backend/src/app/domain/entities/template_share.py` -- TemplateShare domain entity
- `backend/src/app/infrastructure/persistence/models/template_share.py` -- ORM model
- `backend/alembic/versions/003_template_shares_and_user_limits.py` -- Migration
- `frontend/src/features/templates/components/ShareTemplateDialog.tsx` -- Share UI
- `openspec/changes/template-sharing-and-user-limits/design.md` -- This document

### Modified Files (16)
- `backend/src/app/domain/entities/__init__.py` -- Export TemplateShare
- `backend/src/app/domain/entities/user.py` -- Add bulk_generation_limit field
- `backend/src/app/domain/exceptions.py` -- Add TemplateAccessDeniedError
- `backend/src/app/domain/ports/template_repository.py` -- 5 new abstract methods
- `backend/src/app/infrastructure/persistence/models/__init__.py` -- Export TemplateShareModel
- `backend/src/app/infrastructure/persistence/models/user.py` -- Add bulk_generation_limit column
- `backend/src/app/infrastructure/persistence/repositories/template_repository.py` -- Implement 5 new methods
- `backend/src/app/application/services/template_service.py` -- Access checks, share/unshare methods
- `backend/src/app/application/services/document_service.py` -- Template access check before generation
- `backend/src/app/application/services/__init__.py` -- get_document_service resolves user limit
- `backend/src/app/presentation/api/v1/templates.py` -- 3 new endpoints, modify existing 4
- `backend/src/app/presentation/api/v1/documents.py` -- Pass role to service
- `backend/src/app/presentation/api/v1/auth.py` -- GET /me returns effective_bulk_limit
- `backend/src/app/presentation/schemas/template.py` -- ShareTemplateRequest, TemplateResponse fields
- `backend/src/app/presentation/schemas/user.py` -- bulk_generation_limit in UpdateUserRequest
- `backend/src/app/presentation/schemas/auth.py` -- effective_bulk_limit in UserResponse

### Modified Test Files (4)
- `backend/tests/fakes/fake_template_repository.py` -- 5 new fake methods + shares dict
- `backend/tests/unit/test_template_service.py` -- Sharing + access tests
- `backend/tests/unit/test_document_service.py` -- Access check tests + per-user limit tests
- `backend/tests/integration/test_templates_api.py` -- Share endpoint tests + access tests

### Modified Frontend Files (3)
- `frontend/src/features/templates/api/queries.ts` -- Add access_type, is_owner to Template interface
- `frontend/src/features/templates/api/mutations.ts` -- Share/unshare mutations
- `frontend/src/features/templates/components/TemplateDetail.tsx` -- Conditional actions, share button
- `frontend/src/features/templates/components/TemplateList.tsx` -- Sharing indicators

---

## Key Risks and Mitigations

| Risk | Severity | Mitigation |
|------|----------|------------|
| N+1 on `has_access` calls inside `generate_single`/`generate_bulk` | Medium | `has_access` is a single indexed query. Bulk generation calls it once before the loop, not per-row. |
| `list_accessible` UNION query performance with many templates | Low | The UNION is on indexed columns (`created_by`, `user_id`). Pagination limits result set. Index on `template_shares(user_id)` covers the shared subquery. |
| Breaking existing template list for current users | Medium | No backfill needed -- `list_accessible` includes `created_by = user_id` clause. Existing templates remain visible to creators. Admins see all. |
| `_access_type` transient attribute on ORM model | Low | This is a read-only annotation used for one request cycle. Alternative: return tuples from service (more complex API). The transient attribute is simpler and localized. |
| `get_document_service` now does a user DB lookup | Low | User is likely already in the session identity map from JWT validation. Even if not, it's one indexed query per request. |
