"""Integration test conftest.

Strategy
--------
- No real PostgreSQL needed: all repositories and storage are replaced with
  in-memory fakes via FastAPI dependency_overrides.
- Rate limiting is disabled per-test by resetting the limiter's in-memory
  storage before each request.
- Auth endpoints instantiate SQLAlchemyUserRepository directly (not via DI),
  so individual auth tests monkeypatch that class.
- Template/document service factories ARE injectable, so we override them here.
- UsageService and AuditService are also overridden via DI to use in-memory fakes.

Fixtures
--------
app               - FastAPI app with dependency overrides applied
async_client      - httpx.AsyncClient over ASGITransport
auth_headers      - {"Authorization": "Bearer <valid-access-token>"}
test_user_id      - UUID of the seeded test user
test_tenant_id    - UUID of the seeded test tenant
fake_usage_repo   - session-scoped FakeUsageRepository (shared across tests)
fake_audit_repo   - session-scoped FakeAuditRepository (shared across tests)
"""

from __future__ import annotations

import uuid
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

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
from app.infrastructure.auth.jwt_handler import create_access_token
from app.main import create_app
from app.presentation.middleware.tenant import CurrentUser, get_current_user
from tests.fakes import (
    FakeAuditRepository,
    FakeDocumentRepository,
    FakePdfConverter,
    FakeQuotaService,
    FakeStorageService,
    FakeSubscriptionTierRepository,
    FakeTemplateEngine,
    FakeTemplateRepository,
    FakeUsageRepository,
    FakeUserRepository,
)


# ── Stable test identifiers ────────────────────────────────────────────────────

TEST_USER_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
TEST_TENANT_ID = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
TEST_USER_ROLE = "admin"


# ── Session-scoped fakes shared across all integration tests ──────────────────

@pytest.fixture(scope="session")
def fake_storage() -> FakeStorageService:
    return FakeStorageService()


@pytest.fixture(scope="session")
def fake_template_engine() -> FakeTemplateEngine:
    return FakeTemplateEngine()


@pytest.fixture(scope="session")
def fake_template_repo() -> FakeTemplateRepository:
    return FakeTemplateRepository()


@pytest.fixture(scope="session")
def fake_document_repo() -> FakeDocumentRepository:
    return FakeDocumentRepository()


@pytest.fixture(scope="session")
def fake_user_repo() -> FakeUserRepository:
    """Shared FakeUserRepository for the entire integration test session."""
    return FakeUserRepository()


@pytest.fixture(scope="session")
def fake_usage_repo() -> FakeUsageRepository:
    """Shared FakeUsageRepository for the entire integration test session."""
    return FakeUsageRepository()


@pytest.fixture(scope="session")
def fake_audit_repo() -> FakeAuditRepository:
    """Shared FakeAuditRepository for the entire integration test session."""
    return FakeAuditRepository()


# ── test_user CurrentUser fixture ─────────────────────────────────────────────

@pytest.fixture(scope="session")
def test_user() -> CurrentUser:
    return CurrentUser(
        user_id=TEST_USER_ID,
        tenant_id=TEST_TENANT_ID,
        role=TEST_USER_ROLE,
    )


# ── FastAPI app with all overrides ────────────────────────────────────────────

@pytest.fixture(scope="session")
def app(
    fake_storage: FakeStorageService,
    fake_template_engine: FakeTemplateEngine,
    fake_template_repo: FakeTemplateRepository,
    fake_document_repo: FakeDocumentRepository,
    fake_usage_repo: FakeUsageRepository,
    fake_audit_repo: FakeAuditRepository,
    fake_user_repo: FakeUserRepository,
    test_user: CurrentUser,
):
    """Return the FastAPI app with dependency overrides for all integration tests."""
    _app = create_app()

    # Override get_current_user → always return test_user (for authenticated endpoints)
    async def override_get_current_user() -> CurrentUser:
        return test_user

    # Build shared service instances (session-scoped, reused by all overrides)
    _usage_service = UsageService(usage_repo=fake_usage_repo)
    _audit_service = AuditService(audit_repo=fake_audit_repo)

    # Override get_usage_service → UsageService backed by FakeUsageRepository
    async def override_get_usage_service() -> UsageService:
        return _usage_service

    # Override get_audit_service → AuditService backed by FakeAuditRepository
    def override_get_audit_service() -> AuditService:
        return _audit_service

    # Override get_template_service → TemplateService with all fakes
    async def override_get_template_service() -> TemplateService:
        return TemplateService(
            repository=fake_template_repo,
            storage=fake_storage,
            engine=fake_template_engine,
            audit_service=_audit_service,
        )

    # Override get_document_service → DocumentService with all fakes
    _fake_pdf_converter = FakePdfConverter()

    async def override_get_document_service() -> DocumentService:
        return DocumentService(
            document_repository=fake_document_repo,
            template_repository=fake_template_repo,
            storage=fake_storage,
            engine=fake_template_engine,
            pdf_converter=_fake_pdf_converter,
            bulk_generation_limit=10,
            usage_service=_usage_service,
            audit_service=_audit_service,
        )

    # Override get_quota_service → FakeQuotaService (no-op, all quotas pass)
    # This prevents quota-related DB queries from hitting the mock session.
    _fake_quota_service = FakeQuotaService()

    async def override_get_quota_service() -> FakeQuotaService:
        return _fake_quota_service

    # Override get_session → return a no-op AsyncMock (auth tests monkeypatch
    # SQLAlchemyUserRepository themselves; other endpoints use service overrides)
    # scalar_one_or_none() returns None so endpoints that read tenant.tier_id
    # degrade gracefully instead of crashing on a coroutine object.
    def _make_null_result_session() -> AsyncMock:
        """AsyncMock session whose execute().scalar_one_or_none() returns None."""
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        result_mock.scalars.return_value = MagicMock(all=MagicMock(return_value=[]))
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=result_mock)
        return mock_session

    async def override_get_session():
        yield _make_null_result_session()

    from app.infrastructure.persistence.database import get_session
    from app.presentation.middleware.tenant import get_tenant_session

    # Override get_tenant_session → no-op with proper None scalar result
    async def override_get_tenant_session() -> AsyncGenerator:
        yield _make_null_result_session()

    # Override get_user_repository → FakeUserRepository (used by share endpoints)
    async def override_get_user_repository() -> FakeUserRepository:
        return fake_user_repo

    _app.dependency_overrides[get_current_user] = override_get_current_user
    _app.dependency_overrides[get_usage_service] = override_get_usage_service
    _app.dependency_overrides[get_audit_service] = override_get_audit_service
    _app.dependency_overrides[get_template_service] = override_get_template_service
    _app.dependency_overrides[get_document_service] = override_get_document_service
    _app.dependency_overrides[get_quota_service] = override_get_quota_service
    _app.dependency_overrides[get_user_repository] = override_get_user_repository
    _app.dependency_overrides[get_session] = override_get_session
    _app.dependency_overrides[get_tenant_session] = override_get_tenant_session

    yield _app

    _app.dependency_overrides.clear()


# ── HTTP client ───────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
async def async_client(app) -> AsyncGenerator[AsyncClient, None]:
    """httpx AsyncClient backed by ASGITransport (no real network)."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client


# ── Auth helpers ──────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def valid_access_token() -> str:
    """Create a real JWT signed with the test SECRET_KEY."""
    return create_access_token(
        user_id=str(TEST_USER_ID),
        tenant_id=str(TEST_TENANT_ID),
        role=TEST_USER_ROLE,
    )


@pytest.fixture(scope="session")
def auth_headers(valid_access_token: str) -> dict[str, str]:
    """Authorization headers for authenticated requests."""
    return {"Authorization": f"Bearer {valid_access_token}"}


# ── Rate limiter reset ────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def reset_rate_limiter():
    """Reset slowapi's in-memory storage before each test to avoid 429s."""
    from app.presentation.middleware.rate_limit import limiter

    # The limiter uses a limits.storage.MemoryStorage backend.
    # Resetting it clears all hit counters.
    if hasattr(limiter, "_limiter") and hasattr(limiter._limiter, "storage"):
        try:
            limiter._limiter.storage.reset()
        except Exception:
            pass  # Not all storage backends support reset(); safe to ignore
    yield
