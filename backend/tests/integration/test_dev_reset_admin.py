"""Integration tests — POST /api/v1/dev/reset-admin (env-gated dev recovery endpoint).

SCEN-DEVRESET-01: endpoint enabled + canonical admin exists → 200, DB updated
SCEN-DEVRESET-02: endpoint disabled (default) → 404 (route not registered)
SCEN-DEVRESET-03: endpoint enabled + canonical admin missing → 404
SCEN-DEVRESET-04: audit log gets DEV_ADMIN_RESET event with correct details
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.domain.entities import User
from app.domain.entities.audit_log import AuditAction
from app.infrastructure.auth.jwt_handler import hash_password, verify_password
from tests.fakes import (
    FakeAuditRepository,
    FakeDocumentRepository,
    FakeQuotaService,
    FakeStorageService,
    FakeTemplateEngine,
    FakeTemplateRepository,
    FakeUserRepository,
)

CANONICAL_EMAIL = "devrafaseros@gmail.com"
CANONICAL_ADMIN_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
TEST_TENANT_ID = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")


def _make_canonical_admin() -> User:
    return User(
        id=CANONICAL_ADMIN_ID,
        tenant_id=TEST_TENANT_ID,
        email=CANONICAL_EMAIL,
        hashed_password=hash_password("old-password"),
        full_name="Jose Rafael Gallegos Rojas",
        role="document_generator",  # simulate degraded state (forgot pw or role changed)
        is_active=True,
        email_verified=False,
        email_verification_token="old-verification-token",
        email_verification_sent_at=datetime.now(timezone.utc),
        password_reset_token="old-reset-token",
        password_reset_sent_at=datetime.now(timezone.utc),
        created_at=datetime.now(timezone.utc),
    )


def _make_fake_repo_class_for_dev(fake_repo: FakeUserRepository):
    """Return a drop-in for SQLAlchemyUserRepository used in dev.py."""

    class _Repo:
        def __init__(self, session):  # noqa: ARG002
            self._fake = fake_repo

        async def get_by_email(self, email: str):
            # Return user regardless of active status (dev recovery path)
            user_id = self._fake._by_email.get(email)
            if user_id is None:
                return None
            return self._fake._users.get(user_id)

        async def get_by_id(self, user_id):
            return await self._fake.get_by_id(user_id)

        async def update(self, user_id, **kwargs):
            return await self._fake.update(user_id, **kwargs)

    return _Repo


def _make_dev_enabled_app(fake_user_repo: FakeUserRepository, fake_audit_repo: FakeAuditRepository):
    """Build a fresh FastAPI app with enable_dev_reset=True and all fakes wired.

    Also patches dev.SQLAlchemyUserRepository to the fake so the session mock
    doesn't interfere.
    """
    import os
    os.environ["ENABLE_DEV_RESET"] = "true"

    from app.config import get_settings
    get_settings.cache_clear()

    from app.main import create_app
    from app.application.services import (
        get_audit_service,
        get_document_service,
        get_quota_service,
        get_template_service,
        get_usage_service,
        get_user_repository,
    )
    from app.application.services.audit_service import AuditService
    from app.application.services.document_service import DocumentService
    from app.application.services.template_service import TemplateService
    from app.application.services.usage_service import UsageService
    from app.infrastructure.persistence.database import get_session
    from app.presentation.middleware.tenant import get_tenant_session
    from tests.fakes import FakePdfConverter, FakeUsageRepository

    _app = create_app()

    fake_usage_repo = FakeUsageRepository()
    _usage_service = UsageService(usage_repo=fake_usage_repo)
    _audit_service = AuditService(audit_repo=fake_audit_repo)
    fake_storage = FakeStorageService()
    fake_template_engine = FakeTemplateEngine()
    fake_template_repo = FakeTemplateRepository()
    fake_document_repo = FakeDocumentRepository()
    fake_quota_service = FakeQuotaService()

    def _make_null_result_session() -> AsyncMock:
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        result_mock.scalars.return_value = MagicMock(all=MagicMock(return_value=[]))
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=result_mock)
        return mock_session

    async def override_get_tenant_session():
        yield _make_null_result_session()

    async def override_get_session():
        yield _make_null_result_session()

    async def override_get_usage_service():
        return _usage_service

    def override_get_audit_service():
        return _audit_service

    async def override_get_template_service():
        return TemplateService(
            repository=fake_template_repo,
            storage=fake_storage,
            engine=fake_template_engine,
            audit_service=_audit_service,
        )

    async def override_get_document_service():
        return DocumentService(
            document_repository=fake_document_repo,
            template_repository=fake_template_repo,
            storage=fake_storage,
            engine=fake_template_engine,
            pdf_converter=FakePdfConverter(),
            bulk_generation_limit=10,
            usage_service=_usage_service,
            audit_service=_audit_service,
        )

    async def override_get_quota_service():
        return fake_quota_service

    async def override_get_user_repository():
        return fake_user_repo

    _app.dependency_overrides[get_tenant_session] = override_get_tenant_session
    _app.dependency_overrides[get_session] = override_get_session
    _app.dependency_overrides[get_usage_service] = override_get_usage_service
    _app.dependency_overrides[get_audit_service] = override_get_audit_service
    _app.dependency_overrides[get_template_service] = override_get_template_service
    _app.dependency_overrides[get_document_service] = override_get_document_service
    _app.dependency_overrides[get_quota_service] = override_get_quota_service
    _app.dependency_overrides[get_user_repository] = override_get_user_repository

    return _app


def _make_dev_disabled_app():
    """Build a fresh FastAPI app with enable_dev_reset=False (default)."""
    import os
    os.environ.pop("ENABLE_DEV_RESET", None)

    from app.config import get_settings
    get_settings.cache_clear()

    from app.main import create_app
    return create_app()


def _cleanup_dev_env():
    import os
    os.environ.pop("ENABLE_DEV_RESET", None)
    from app.config import get_settings
    get_settings.cache_clear()


# ── SCEN-DEVRESET-01: enabled + canonical admin exists → 200 ─────────────────


@pytest.mark.asyncio
async def test_dev_reset_admin_success_when_enabled():
    """SCEN-DEVRESET-01: endpoint enabled + canonical admin in DB → 200, DB updated."""
    import app.presentation.api.v1.dev as dev_mod

    fake_user_repo = FakeUserRepository()
    fake_audit_repo = FakeAuditRepository()

    canonical_admin = _make_canonical_admin()
    fake_user_repo._users[canonical_admin.id] = canonical_admin
    fake_user_repo._by_email[canonical_admin.email] = canonical_admin.id

    dev_repo_class = _make_fake_repo_class_for_dev(fake_user_repo)
    original_repo_class = getattr(dev_mod, "SQLAlchemyUserRepository", None)
    dev_mod.SQLAlchemyUserRepository = dev_repo_class

    # Also patch get_audit_service in dev module to use our fake
    from app.application.services.audit_service import AuditService
    local_audit_service = AuditService(audit_repo=fake_audit_repo)
    original_get_audit = getattr(dev_mod, "get_audit_service", None)
    dev_mod.get_audit_service = lambda: local_audit_service

    _app = _make_dev_enabled_app(fake_user_repo, fake_audit_repo)

    try:
        async with AsyncClient(
            transport=ASGITransport(app=_app),
            base_url="http://test",
        ) as client:
            response = await client.post("/api/v1/dev/reset-admin")

        assert response.status_code == 200, response.text
        data = response.json()
        assert data["message"] == "Canonical admin reset"
        assert data["email"] == CANONICAL_EMAIL

        # Verify DB changes via fake_user_repo
        updated = fake_user_repo._users[canonical_admin.id]
        assert verify_password("admin123!", updated.hashed_password)
        assert updated.role == "admin"
        assert updated.is_active is True
        assert updated.email_verified is True
        assert updated.password_reset_token is None
        assert updated.password_reset_sent_at is None
        assert updated.email_verification_token is None
        assert updated.email_verification_sent_at is None
    finally:
        if original_repo_class is not None:
            dev_mod.SQLAlchemyUserRepository = original_repo_class
        if original_get_audit is not None:
            dev_mod.get_audit_service = original_get_audit
        _cleanup_dev_env()


# ── SCEN-DEVRESET-02: disabled (default) → 404 ───────────────────────────────


@pytest.mark.asyncio
async def test_dev_reset_admin_returns_404_when_disabled():
    """SCEN-DEVRESET-02: endpoint disabled (default) → route not registered → 404."""
    _app = _make_dev_disabled_app()

    async with AsyncClient(
        transport=ASGITransport(app=_app),
        base_url="http://test",
    ) as client:
        response = await client.post("/api/v1/dev/reset-admin")

    assert response.status_code == 404, response.text


# ── SCEN-DEVRESET-03: enabled but canonical admin missing → 404 ───────────────


@pytest.mark.asyncio
async def test_dev_reset_admin_returns_404_when_canonical_admin_missing():
    """SCEN-DEVRESET-03: endpoint enabled + canonical admin not in DB → 404."""
    import app.presentation.api.v1.dev as dev_mod

    fake_user_repo = FakeUserRepository()  # empty — no canonical admin
    fake_audit_repo = FakeAuditRepository()

    dev_repo_class = _make_fake_repo_class_for_dev(fake_user_repo)
    original_repo_class = getattr(dev_mod, "SQLAlchemyUserRepository", None)
    dev_mod.SQLAlchemyUserRepository = dev_repo_class

    _app = _make_dev_enabled_app(fake_user_repo, fake_audit_repo)

    try:
        async with AsyncClient(
            transport=ASGITransport(app=_app),
            base_url="http://test",
        ) as client:
            response = await client.post("/api/v1/dev/reset-admin")

        assert response.status_code == 404, response.text
    finally:
        if original_repo_class is not None:
            dev_mod.SQLAlchemyUserRepository = original_repo_class
        _cleanup_dev_env()


# ── SCEN-DEVRESET-04: audit log gets DEV_ADMIN_RESET event ───────────────────


@pytest.mark.asyncio
async def test_dev_reset_admin_logs_audit_event():
    """SCEN-DEVRESET-04: successful reset emits DEV_ADMIN_RESET audit entry with correct details."""
    import asyncio
    import app.presentation.api.v1.dev as dev_mod
    from app.application.services.audit_service import AuditService

    fake_user_repo = FakeUserRepository()
    local_audit_repo = FakeAuditRepository()
    local_audit_service = AuditService(audit_repo=local_audit_repo)

    canonical_admin = _make_canonical_admin()
    fake_user_repo._users[canonical_admin.id] = canonical_admin
    fake_user_repo._by_email[canonical_admin.email] = canonical_admin.id

    dev_repo_class = _make_fake_repo_class_for_dev(fake_user_repo)
    original_repo_class = getattr(dev_mod, "SQLAlchemyUserRepository", None)
    original_get_audit = getattr(dev_mod, "get_audit_service", None)

    dev_mod.SQLAlchemyUserRepository = dev_repo_class
    dev_mod.get_audit_service = lambda: local_audit_service

    _app = _make_dev_enabled_app(fake_user_repo, local_audit_repo)

    try:
        async with AsyncClient(
            transport=ASGITransport(app=_app),
            base_url="http://test",
        ) as client:
            response = await client.post("/api/v1/dev/reset-admin")

        assert response.status_code == 200, response.text

        # Give fire-and-forget audit task a chance to run
        await asyncio.sleep(0.05)

        audit_entries = [
            e for e in local_audit_repo._entries
            if e.action == AuditAction.DEV_ADMIN_RESET
        ]
        assert len(audit_entries) >= 1, (
            f"No DEV_ADMIN_RESET audit entry found. "
            f"Entries: {[e.action for e in local_audit_repo._entries]}"
        )

        entry = audit_entries[0]
        assert entry.details is not None
        assert entry.details.get("target_email") == CANONICAL_EMAIL
        assert entry.details.get("via") == "dev_endpoint"
        # actor_id should be the canonical admin's own id (self-reset semantics)
        assert entry.actor_id == canonical_admin.id
    finally:
        if original_repo_class is not None:
            dev_mod.SQLAlchemyUserRepository = original_repo_class
        if original_get_audit is not None:
            dev_mod.get_audit_service = original_get_audit
        _cleanup_dev_env()
