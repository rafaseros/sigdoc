"""Unit tests for AuditService (task 4.3 RED).

AuditService uses asyncio.create_task() for fire-and-forget writes.
In unit tests we use SyncAuditService — a testable subclass that overrides
_write() to run synchronously so tests can assert on stored entries.
"""
import uuid
from datetime import datetime, timezone
import pytest

from app.application.services.audit_service import AuditService
from app.domain.entities import AuditAction, AuditLog
from tests.fakes import FakeAuditRepository


# ---------------------------------------------------------------------------
# Testable subclass — runs _write() synchronously (no create_task)
# ---------------------------------------------------------------------------


class SyncAuditService(AuditService):
    """AuditService subclass whose log() awaits _write() directly.

    This makes test assertions deterministic without requiring real event loops
    or asyncio.create_task() scheduling to settle.
    """

    async def log(
        self,
        actor_id: uuid.UUID | None,
        tenant_id: uuid.UUID,
        action: str,
        resource_type: str | None = None,
        resource_id: uuid.UUID | None = None,
        details: dict | None = None,
        ip_address: str | None = None,
    ) -> None:
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
        await self._write(entry)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_service(repo: FakeAuditRepository) -> SyncAuditService:
    """Build a SyncAuditService backed by a FakeAuditRepository."""
    # AuditService normally accepts a session_factory.
    # For unit tests we pass in the repo directly via the optional kwarg.
    return SyncAuditService(audit_repo=repo)


# ---------------------------------------------------------------------------
# AuditService.log() — creates entries
# ---------------------------------------------------------------------------


class TestAuditServiceLog:
    async def test_log_creates_entry_in_repo(
        self,
        fake_audit_repo: FakeAuditRepository,
    ):
        """log() should create an AuditLog entry in the repository."""
        service = make_service(fake_audit_repo)

        actor_id = uuid.uuid4()
        tenant_id = uuid.uuid4()

        await service.log(
            actor_id=actor_id,
            tenant_id=tenant_id,
            action=AuditAction.DOCUMENT_GENERATE,
            resource_type="document",
            resource_id=uuid.uuid4(),
        )

        assert len(fake_audit_repo._entries) == 1
        entry = fake_audit_repo._entries[0]
        assert entry.actor_id == actor_id
        assert entry.tenant_id == tenant_id
        assert entry.action == AuditAction.DOCUMENT_GENERATE
        assert entry.resource_type == "document"

    async def test_log_stores_ip_address(
        self,
        fake_audit_repo: FakeAuditRepository,
    ):
        """ip_address is persisted on the entry when provided."""
        service = make_service(fake_audit_repo)

        await service.log(
            actor_id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            action=AuditAction.AUTH_LOGIN,
            ip_address="192.168.1.1",
        )

        assert fake_audit_repo._entries[0].ip_address == "192.168.1.1"

    async def test_log_with_null_actor_id(
        self,
        fake_audit_repo: FakeAuditRepository,
    ):
        """actor_id is nullable — system-level entries have no actor."""
        service = make_service(fake_audit_repo)

        await service.log(
            actor_id=None,
            tenant_id=uuid.uuid4(),
            action=AuditAction.USER_CREATE,
        )

        assert len(fake_audit_repo._entries) == 1
        assert fake_audit_repo._entries[0].actor_id is None

    async def test_log_failure_is_swallowed(
        self,
        fake_audit_repo: FakeAuditRepository,
    ):
        """If _write() raises, log() must NOT propagate the exception."""

        class FailingRepo(FakeAuditRepository):
            async def create(self, entry):
                raise RuntimeError("DB is down")

        service = make_service(FailingRepo())

        # Must NOT raise
        await service.log(
            actor_id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            action=AuditAction.TEMPLATE_DELETE,
        )

    async def test_log_stores_details_dict(
        self,
        fake_audit_repo: FakeAuditRepository,
    ):
        """Arbitrary details dict is stored as-is."""
        service = make_service(fake_audit_repo)

        details = {"template_name": "Invoice", "version": 2}
        await service.log(
            actor_id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            action=AuditAction.TEMPLATE_VERSION,
            details=details,
        )

        assert fake_audit_repo._entries[0].details == details


# ---------------------------------------------------------------------------
# list_audit_logs() — delegates to repo
# ---------------------------------------------------------------------------


class TestAuditServiceListLogs:
    async def test_list_returns_entries_from_repo(
        self,
        fake_audit_repo: FakeAuditRepository,
    ):
        """list_audit_logs() should delegate to the repository."""
        service = make_service(fake_audit_repo)

        tenant_id = uuid.uuid4()
        actor_id = uuid.uuid4()

        # Seed two entries directly in the repo
        for action in [AuditAction.USER_CREATE, AuditAction.USER_UPDATE]:
            await fake_audit_repo.create(
                AuditLog(
                    id=uuid.uuid4(),
                    tenant_id=tenant_id,
                    actor_id=actor_id,
                    action=action,
                    created_at=datetime.now(timezone.utc),
                )
            )

        items, total = await service.list_audit_logs(page=1, size=10)

        assert total == 2
        assert len(items) == 2

    async def test_list_filters_by_action(
        self,
        fake_audit_repo: FakeAuditRepository,
    ):
        """list_audit_logs() passes action filter to the repository."""
        service = make_service(fake_audit_repo)

        tenant_id = uuid.uuid4()
        ts = datetime.now(timezone.utc)

        await fake_audit_repo.create(
            AuditLog(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                action=AuditAction.USER_CREATE,
                created_at=ts,
            )
        )
        await fake_audit_repo.create(
            AuditLog(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                action=AuditAction.TEMPLATE_DELETE,
                created_at=ts,
            )
        )

        items, total = await service.list_audit_logs(
            page=1, size=10, action=AuditAction.USER_CREATE
        )

        assert total == 1
        assert items[0].action == AuditAction.USER_CREATE

    async def test_list_respects_pagination(
        self,
        fake_audit_repo: FakeAuditRepository,
    ):
        """list_audit_logs() respects page + size params."""
        service = make_service(fake_audit_repo)

        tenant_id = uuid.uuid4()
        ts = datetime.now(timezone.utc)

        for _ in range(5):
            await fake_audit_repo.create(
                AuditLog(
                    id=uuid.uuid4(),
                    tenant_id=tenant_id,
                    action=AuditAction.DOCUMENT_GENERATE,
                    created_at=ts,
                )
            )

        items, total = await service.list_audit_logs(page=1, size=3)

        assert total == 5
        assert len(items) == 3
