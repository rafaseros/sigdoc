"""Tenant-isolation tests for SQLAlchemyAuditRepository.list_paginated.

These tests exercise the REAL repository against an in-memory SQLite async
database (no PostgreSQL required). They prove that list_paginated returns only
rows belonging to the caller's tenant — the core fix for the cross-tenant
audit-log disclosure bug.

The audit_logs table declares a PostgreSQL JSONB column; SQLite cannot compile
JSONB natively, so a test-local compiler directive renders it as JSON. This
affects only the test engine and never touches production code.
"""
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.ext.compiler import compiles

from app.domain.entities import AuditAction
from app.infrastructure.persistence.models.audit_log import AuditLogModel
from app.infrastructure.persistence.repositories.audit_repository import (
    SQLAlchemyAuditRepository,
)


@compiles(JSONB, "sqlite")
def _render_jsonb_as_json_on_sqlite(element, compiler, **kw):  # pragma: no cover
    """Render PostgreSQL JSONB as JSON when compiling for the SQLite test engine."""
    return "JSON"


TENANT_A = uuid.UUID("aaaaaaaa-1111-1111-1111-aaaaaaaaaaaa")
TENANT_B = uuid.UUID("bbbbbbbb-2222-2222-2222-bbbbbbbbbbbb")


@pytest.fixture
async def session_factory():
    """In-memory SQLite async session factory with the audit_logs table created."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(AuditLogModel.__table__.create)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield factory
    finally:
        await engine.dispose()


async def _seed(factory, tenant_id, action, actor_id=None):
    async with factory() as session:
        session.add(
            AuditLogModel(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                actor_id=actor_id,
                action=action,
                created_at=datetime.now(timezone.utc),
            )
        )
        await session.commit()


class TestListPaginatedTenantScope:
    async def test_returns_only_callers_tenant_rows(self, session_factory):
        """list_paginated(tenant_id=A) must never leak tenant B rows."""
        await _seed(session_factory, TENANT_A, AuditAction.USER_CREATE)
        await _seed(session_factory, TENANT_A, AuditAction.DOCUMENT_GENERATE)
        await _seed(session_factory, TENANT_B, AuditAction.USER_CREATE)
        await _seed(session_factory, TENANT_B, AuditAction.TEMPLATE_DELETE)

        async with session_factory() as session:
            repo = SQLAlchemyAuditRepository(session)
            entries, total = await repo.list_paginated(tenant_id=TENANT_A)

        assert total == 2
        assert {e.tenant_id for e in entries} == {TENANT_A}

    async def test_tenant_filter_combines_with_action_filter(self, session_factory):
        """The tenant predicate is AND-combined with other filters."""
        await _seed(session_factory, TENANT_A, AuditAction.USER_CREATE)
        await _seed(session_factory, TENANT_A, AuditAction.DOCUMENT_GENERATE)
        await _seed(session_factory, TENANT_B, AuditAction.USER_CREATE)

        async with session_factory() as session:
            repo = SQLAlchemyAuditRepository(session)
            entries, total = await repo.list_paginated(
                tenant_id=TENANT_A, action=AuditAction.USER_CREATE
            )

        assert total == 1
        assert entries[0].tenant_id == TENANT_A
        assert entries[0].action == AuditAction.USER_CREATE

    async def test_empty_when_caller_tenant_has_no_rows(self, session_factory):
        """A tenant with no entries gets an empty page even when others have rows."""
        await _seed(session_factory, TENANT_B, AuditAction.USER_CREATE)

        async with session_factory() as session:
            repo = SQLAlchemyAuditRepository(session)
            entries, total = await repo.list_paginated(tenant_id=TENANT_A)

        assert total == 0
        assert entries == []
