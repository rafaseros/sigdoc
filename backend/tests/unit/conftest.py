"""Unit test conftest — provides fresh fake instances for every test function."""
import pytest

from tests.fakes import (
    FakeDocumentRepository,
    FakeStorageService,
    FakeTemplateEngine,
    FakeTemplateRepository,
    FakeUserRepository,
    FakeUsageRepository,
    FakeAuditRepository,
    FakeSubscriptionTierRepository,
    FakeQuotaService,
    FakeTenantRepository,
)


@pytest.fixture
def fake_storage() -> FakeStorageService:
    """Fresh FakeStorageService with an empty files dict."""
    return FakeStorageService()


@pytest.fixture
def fake_template_engine() -> FakeTemplateEngine:
    """Fresh FakeTemplateEngine with default (no-fail) configuration."""
    return FakeTemplateEngine()


@pytest.fixture
def fake_template_repo() -> FakeTemplateRepository:
    """Fresh FakeTemplateRepository with an empty store."""
    return FakeTemplateRepository()


@pytest.fixture
def fake_document_repo() -> FakeDocumentRepository:
    """Fresh FakeDocumentRepository with an empty store."""
    return FakeDocumentRepository()


@pytest.fixture
def fake_user_repo() -> FakeUserRepository:
    """Fresh FakeUserRepository with an empty store."""
    return FakeUserRepository()


@pytest.fixture
def fake_usage_repo() -> FakeUsageRepository:
    """Fresh FakeUsageRepository with an empty event list."""
    return FakeUsageRepository()


@pytest.fixture
def fake_audit_repo() -> FakeAuditRepository:
    """Fresh FakeAuditRepository with an empty entry list."""
    return FakeAuditRepository()


@pytest.fixture
def fake_tier_repo() -> FakeSubscriptionTierRepository:
    """Fresh FakeSubscriptionTierRepository seeded with Free/Pro/Enterprise tiers."""
    return FakeSubscriptionTierRepository()


@pytest.fixture
def fake_quota_service() -> FakeQuotaService:
    """FakeQuotaService with no quotas exceeded (all checks pass by default)."""
    return FakeQuotaService()


@pytest.fixture
def fake_tenant_repo() -> FakeTenantRepository:
    """Fresh FakeTenantRepository with an empty store."""
    return FakeTenantRepository()
