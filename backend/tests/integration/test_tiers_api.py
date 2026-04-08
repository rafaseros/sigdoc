"""Integration tests — /api/v1/tiers/* endpoints.

Task 7.4: GET /tiers and GET /tiers/tenant endpoint coverage.
Task 7.5: QuotaExceededError → 429 via document generate endpoint.

The tiers endpoints hit the DB session directly (not via a service DI).
We override both get_session and get_tenant_session with mocks that return
pre-seeded tier models and tenant models.
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.application.services import get_quota_service
from app.application.services.document_service import DocumentService
from app.application.services.template_service import TemplateService
from app.application.services.usage_service import UsageService
from app.application.services.audit_service import AuditService
from app.domain.entities.subscription_tier import FREE_TIER_ID
from app.domain.exceptions import QuotaExceededError
from app.infrastructure.persistence.database import get_session
from app.main import create_app
from app.presentation.middleware.tenant import CurrentUser, get_current_user, get_tenant_session
from tests.fakes import (
    FakeDocumentRepository,
    FakeQuotaService,
    FakeStorageService,
    FakeSubscriptionTierRepository,
    FakeTemplateEngine,
    FakeTemplateRepository,
    FakeUsageRepository,
    FakeAuditRepository,
)
from tests.fakes.fake_subscription_tier_repository import (
    ENTERPRISE_TIER,
    FREE_TIER,
    PRO_TIER,
)

# ---------------------------------------------------------------------------
# Stable identifiers
# ---------------------------------------------------------------------------

TEST_USER_ID = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
TEST_TENANT_ID = uuid.UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")


# ---------------------------------------------------------------------------
# Helpers — build a mock SQLAlchemy scalars result from tier dicts
# ---------------------------------------------------------------------------


def _make_tier_model(tier):
    """Build a simple attribute object (not ORM) from a SubscriptionTier entity.

    The tiers router maps model attributes directly → we simulate ORM models via
    a simple namespace object with all required fields.
    """
    m = MagicMock()
    m.id = tier.id
    m.name = tier.name
    m.slug = tier.slug
    m.monthly_document_limit = tier.monthly_document_limit
    m.max_templates = tier.max_templates
    m.max_users = tier.max_users
    m.bulk_generation_limit = tier.bulk_generation_limit
    m.max_template_shares = tier.max_template_shares
    m.is_active = tier.is_active
    # Rate limit fields — added in migration 006 (Task 4.2)
    m.rate_limit_login = tier.rate_limit_login
    m.rate_limit_refresh = tier.rate_limit_refresh
    m.rate_limit_generate = tier.rate_limit_generate
    m.rate_limit_bulk = tier.rate_limit_bulk
    return m


def _make_tenant_model(tenant_id: uuid.UUID, tier_id: uuid.UUID):
    """Build a mock TenantModel with tier_id set."""
    m = MagicMock()
    m.id = tenant_id
    m.tier_id = tier_id
    return m


def _make_session_returning_tiers(tiers):
    """Return an AsyncMock session that yields tier models when execute() is called."""
    tier_models = [_make_tier_model(t) for t in tiers]

    scalars_mock = MagicMock()
    scalars_mock.all.return_value = tier_models

    result_mock = MagicMock()
    result_mock.scalars.return_value = scalars_mock

    session = AsyncMock()
    session.execute = AsyncMock(return_value=result_mock)
    return session


def _make_session_returning_tenant(tenant_model):
    """Return an AsyncMock session whose execute() returns a tenant model.

    scalar_one_or_none() is called by the tenant endpoint to fetch the tenant.
    """
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = tenant_model

    session = AsyncMock()
    session.execute = AsyncMock(return_value=result_mock)
    return session


# ---------------------------------------------------------------------------
# Tiers list — GET /api/v1/tiers (no auth)
# ---------------------------------------------------------------------------


@pytest.fixture
def tiers_app_no_auth():
    """App with session overridden to return 3 tiers. No auth override needed."""
    _app = create_app()

    tiers = [FREE_TIER, PRO_TIER, ENTERPRISE_TIER]
    mock_session = _make_session_returning_tiers(tiers)

    async def override_get_session():
        yield mock_session

    async def override_get_tenant_session():
        yield mock_session

    _app.dependency_overrides[get_session] = override_get_session
    _app.dependency_overrides[get_tenant_session] = override_get_tenant_session

    yield _app
    _app.dependency_overrides.clear()


@pytest.fixture
async def tiers_client(tiers_app_no_auth):
    async with AsyncClient(
        transport=ASGITransport(app=tiers_app_no_auth),
        base_url="http://test",
    ) as client:
        yield client


@pytest.mark.asyncio
async def test_list_tiers_returns_200(tiers_client):
    """GET /api/v1/tiers returns 200 with a list of tiers."""
    response = await tiers_client.get("/api/v1/tiers")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_list_tiers_returns_all_tiers(tiers_client):
    """GET /api/v1/tiers body contains 3 tiers (Free, Pro, Enterprise)."""
    response = await tiers_client.get("/api/v1/tiers")
    data = response.json()

    assert "items" in data
    assert data["total"] == 3
    assert len(data["items"]) == 3


@pytest.mark.asyncio
async def test_list_tiers_item_fields(tiers_client):
    """Each tier item has expected fields."""
    response = await tiers_client.get("/api/v1/tiers")
    data = response.json()

    item = data["items"][0]
    assert "id" in item
    assert "name" in item
    assert "slug" in item
    assert "monthly_document_limit" in item
    assert "bulk_generation_limit" in item


# ---------------------------------------------------------------------------
# Tenant tier — GET /api/v1/tiers/tenant (requires auth)
# ---------------------------------------------------------------------------


@pytest.fixture
def tenant_tier_app():
    """App wired for GET /api/v1/tiers/tenant with a FakeQuotaService."""
    _app = create_app()

    tenant_model = _make_tenant_model(TEST_TENANT_ID, FREE_TIER_ID)
    mock_session = _make_session_returning_tenant(tenant_model)

    current_user = CurrentUser(
        user_id=TEST_USER_ID,
        tenant_id=TEST_TENANT_ID,
        role="user",
    )

    fake_quota = FakeQuotaService()  # all quotas pass, returns Free tier summary

    async def override_get_current_user() -> CurrentUser:
        return current_user

    async def override_get_session():
        yield mock_session

    async def override_get_tenant_session():
        yield mock_session

    async def override_get_quota_service() -> FakeQuotaService:
        return fake_quota

    _app.dependency_overrides[get_current_user] = override_get_current_user
    _app.dependency_overrides[get_session] = override_get_session
    _app.dependency_overrides[get_tenant_session] = override_get_tenant_session
    _app.dependency_overrides[get_quota_service] = override_get_quota_service

    yield _app
    _app.dependency_overrides.clear()


@pytest.fixture
async def tenant_tier_client(tenant_tier_app):
    async with AsyncClient(
        transport=ASGITransport(app=tenant_tier_app),
        base_url="http://test",
    ) as client:
        yield client


@pytest.mark.asyncio
async def test_tenant_tier_without_auth_returns_401(tiers_app_no_auth):
    """GET /api/v1/tiers/tenant without auth override returns 401."""
    async with AsyncClient(
        transport=ASGITransport(app=tiers_app_no_auth),
        base_url="http://test",
    ) as client:
        response = await client.get("/api/v1/tiers/tenant")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_tenant_tier_with_auth_returns_200(tenant_tier_client):
    """GET /api/v1/tiers/tenant with auth returns 200."""
    response = await tenant_tier_client.get("/api/v1/tiers/tenant")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_tenant_tier_response_has_tier_and_usage(tenant_tier_client):
    """GET /api/v1/tiers/tenant body has tier and usage keys."""
    response = await tenant_tier_client.get("/api/v1/tiers/tenant")
    data = response.json()

    assert "tier" in data
    assert "usage" in data


@pytest.mark.asyncio
async def test_tenant_tier_usage_has_resource_keys(tenant_tier_client):
    """The usage summary contains documents, templates, and users."""
    response = await tenant_tier_client.get("/api/v1/tiers/tenant")
    data = response.json()

    usage = data["usage"]
    assert "documents" in usage
    assert "templates" in usage
    assert "users" in usage


@pytest.mark.asyncio
async def test_tenant_tier_resource_usage_fields(tenant_tier_client):
    """Each resource usage entry has used, limit, percentage_used, near_limit."""
    response = await tenant_tier_client.get("/api/v1/tiers/tenant")
    data = response.json()

    docs = data["usage"]["documents"]
    assert "used" in docs
    assert "limit" in docs
    assert "percentage_used" in docs
    assert "near_limit" in docs


# ---------------------------------------------------------------------------
# Task 5.4 — SC-RL-07: GET /tiers includes rate limit fields
# Task 5.4 — SC-RL-08: GET /tiers/tenant includes rate limit fields
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_tiers_includes_rate_limit_fields(tiers_client):
    """SC-RL-07: GET /api/v1/tiers response includes rate limit fields for each tier."""
    response = await tiers_client.get("/api/v1/tiers")
    assert response.status_code == 200
    data = response.json()

    for item in data["items"]:
        assert "rate_limit_login" in item, f"rate_limit_login missing in {item['name']}"
        assert "rate_limit_refresh" in item, f"rate_limit_refresh missing in {item['name']}"
        assert "rate_limit_generate" in item, f"rate_limit_generate missing in {item['name']}"
        assert "rate_limit_bulk" in item, f"rate_limit_bulk missing in {item['name']}"


@pytest.mark.asyncio
async def test_list_tiers_rate_limit_values_are_strings(tiers_client):
    """SC-RL-07: Rate limit fields are non-empty strings (slowapi format)."""
    response = await tiers_client.get("/api/v1/tiers")
    data = response.json()

    free = next(i for i in data["items"] if i["slug"] == "free")
    assert isinstance(free["rate_limit_login"], str) and len(free["rate_limit_login"]) > 0
    assert isinstance(free["rate_limit_generate"], str) and len(free["rate_limit_generate"]) > 0

    # Free tier generate limit is "10/minute" (stricter than global 20/minute)
    assert free["rate_limit_generate"] == "10/minute"
    # Free tier bulk limit is "2/minute"
    assert free["rate_limit_bulk"] == "2/minute"


@pytest.mark.asyncio
async def test_tenant_tier_includes_rate_limit_fields(tenant_tier_client):
    """SC-RL-08: GET /api/v1/tiers/tenant response tier object includes rate limit fields."""
    response = await tenant_tier_client.get("/api/v1/tiers/tenant")
    assert response.status_code == 200
    data = response.json()

    tier = data["tier"]
    assert "rate_limit_login" in tier
    assert "rate_limit_refresh" in tier
    assert "rate_limit_generate" in tier
    assert "rate_limit_bulk" in tier


# ---------------------------------------------------------------------------
# Task 7.5 — QuotaExceededError → HTTP 429 via document endpoint
# ---------------------------------------------------------------------------


@pytest.fixture
def quota_app():
    """App where document generation is overridden to use a FakeQuotaService
    configured to raise QuotaExceededError on monthly_document_limit.
    """
    _app = create_app()

    fake_doc_repo = FakeDocumentRepository()
    fake_tpl_repo = FakeTemplateRepository()
    fake_storage = FakeStorageService()
    fake_engine = FakeTemplateEngine()
    fake_usage_repo = FakeUsageRepository()
    fake_audit_repo = FakeAuditRepository()

    # FakeQuotaService that raises on any document check
    exceeded_quota = FakeQuotaService(exceeded_resource="monthly_document_limit")

    current_user = CurrentUser(
        user_id=TEST_USER_ID,
        tenant_id=TEST_TENANT_ID,
        role="user",
    )

    _usage_service = UsageService(usage_repo=fake_usage_repo)
    _audit_service = AuditService(audit_repo=fake_audit_repo)

    async def override_get_current_user() -> CurrentUser:
        return current_user

    async def override_get_quota_service() -> FakeQuotaService:
        return exceeded_quota

    async def override_get_document_service() -> DocumentService:
        return DocumentService(
            document_repository=fake_doc_repo,
            template_repository=fake_tpl_repo,
            storage=fake_storage,
            engine=fake_engine,
            bulk_generation_limit=10,
            usage_service=_usage_service,
            audit_service=_audit_service,
            quota_service=exceeded_quota,
            tier_id=FREE_TIER_ID,
        )

    async def override_get_template_service() -> TemplateService:
        return TemplateService(
            repository=fake_tpl_repo,
            storage=fake_storage,
            engine=fake_engine,
        )

    async def override_get_session():
        yield AsyncMock()

    async def override_get_tenant_session():
        yield AsyncMock()

    from app.application.services import get_document_service, get_template_service

    _app.dependency_overrides[get_current_user] = override_get_current_user
    _app.dependency_overrides[get_quota_service] = override_get_quota_service
    _app.dependency_overrides[get_document_service] = override_get_document_service
    _app.dependency_overrides[get_template_service] = override_get_template_service
    _app.dependency_overrides[get_session] = override_get_session
    _app.dependency_overrides[get_tenant_session] = override_get_tenant_session

    yield _app
    _app.dependency_overrides.clear()


@pytest.fixture
async def quota_client(quota_app):
    async with AsyncClient(
        transport=ASGITransport(app=quota_app),
        base_url="http://test",
    ) as client:
        yield client


@pytest.mark.asyncio
async def test_quota_exceeded_returns_429(quota_client):
    """When FakeQuotaService raises QuotaExceededError, the endpoint returns 429."""
    # Seed a template version in the fake repos so the endpoint can proceed to quota check
    import uuid as _uuid
    from datetime import datetime, timezone
    from app.domain.entities import Template, TemplateVersion

    # The document generate endpoint calls quota check FIRST (before template fetch),
    # so we don't need a real template seeded — the quota raises immediately.
    version_id = str(_uuid.uuid4())

    response = await quota_client.post(
        "/api/v1/documents/generate",
        json={
            "template_version_id": version_id,
            "variables": {"name": "Alice"},
        },
    )
    assert response.status_code == 429


@pytest.mark.asyncio
async def test_quota_exceeded_response_body(quota_client):
    """The 429 response has a structured JSON body with error and quota details."""
    version_id = str(uuid.uuid4())

    response = await quota_client.post(
        "/api/v1/documents/generate",
        json={
            "template_version_id": version_id,
            "variables": {"name": "Alice"},
        },
    )

    assert response.status_code == 429
    data = response.json()

    # The global exception handler maps QuotaExceededError → structured body
    assert "error" in data or "detail" in data  # handler may use either key
    # At minimum, quota-specific fields must be present
    assert "limit_type" in data or "detail" in str(data)
