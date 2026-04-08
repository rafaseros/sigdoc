"""Integration tests — POST /api/v1/auth/signup.

Strategy: monkeypatch the repository classes + SignupService in the auth module,
just like the existing auth tests do for SQLAlchemyUserRepository.

Scenarios:
- Happy path → 201 with tokens + user info
- Duplicate email → 409
- Duplicate org name → 409
- Weak password (< 8 chars) → 422
- Missing fields → 422
- Rate limit (3/hour per IP) → 429
"""

from __future__ import annotations

import pytest

from app.application.services.signup_service import SignupError, SignupResult
from app.domain.entities.user import User
from tests.fakes import FakeTenantRepository, FakeUserRepository, FakeSubscriptionTierRepository

import uuid


# ── stub SignupService ────────────────────────────────────────────────────────


class _StubSignupService:
    """Controls what signup() raises or returns based on test setup."""

    def __init__(self, *, raise_error: SignupError | None = None, result=None):
        self._error = raise_error
        self._result = result

    async def signup(self, **kwargs):
        if self._error is not None:
            raise self._error
        return self._result


def _make_stub_class(stub: _StubSignupService):
    """Return a class whose constructor matches SignupService(tenant_repo, user_repo, tier_repo, audit_service)."""
    class _Cls:
        def __init__(self, tenant_repo, user_repo, tier_repo, audit_service=None):
            self._stub = stub

        async def signup(self, **kwargs):
            return await self._stub.signup(**kwargs)

    return _Cls


def _make_happy_result() -> SignupResult:
    user_id = uuid.UUID("11111111-1111-1111-1111-111111111111")
    tenant_id = uuid.UUID("22222222-2222-2222-2222-222222222222")
    user = User(
        id=user_id,
        tenant_id=tenant_id,
        email="alice@example.com",
        hashed_password="hashed",
        full_name="Alice Smith",
        role="admin",
    )
    return SignupResult(
        access_token="fake.access.token",
        refresh_token="fake.refresh.token",
        user=user,
    )


# ── happy path ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_signup_happy_path_returns_201(async_client, monkeypatch):
    result = _make_happy_result()
    stub = _StubSignupService(result=result)

    monkeypatch.setattr(
        "app.presentation.api.v1.auth.SignupService",
        _make_stub_class(stub),
    )

    response = await async_client.post(
        "/api/v1/auth/signup",
        json={
            "email": "alice@example.com",
            "password": "securepassword",
            "full_name": "Alice Smith",
            "organization_name": "Acme Corp",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"
    assert "user" in data
    assert data["user"]["email"] == "alice@example.com"
    assert data["user"]["role"] == "admin"
    assert "tenant_id" in data["user"]


# ── duplicate email ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_signup_duplicate_email_returns_409(async_client, monkeypatch):
    stub = _StubSignupService(
        raise_error=SignupError("Email already registered", field="email")
    )

    monkeypatch.setattr(
        "app.presentation.api.v1.auth.SignupService",
        _make_stub_class(stub),
    )

    response = await async_client.post(
        "/api/v1/auth/signup",
        json={
            "email": "taken@example.com",
            "password": "securepassword",
            "full_name": "User",
            "organization_name": "New Org",
        },
    )

    assert response.status_code == 409
    assert "Email already registered" in response.json()["detail"]


# ── duplicate org name ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_signup_duplicate_org_returns_409(async_client, monkeypatch):
    stub = _StubSignupService(
        raise_error=SignupError("Organization name already taken", field="organization_name")
    )

    monkeypatch.setattr(
        "app.presentation.api.v1.auth.SignupService",
        _make_stub_class(stub),
    )

    response = await async_client.post(
        "/api/v1/auth/signup",
        json={
            "email": "new@example.com",
            "password": "securepassword",
            "full_name": "User",
            "organization_name": "Taken Corp",
        },
    )

    assert response.status_code == 409
    assert "Organization name already taken" in response.json()["detail"]


# ── validation errors ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_signup_short_password_returns_422(async_client):
    response = await async_client.post(
        "/api/v1/auth/signup",
        json={
            "email": "user@example.com",
            "password": "short",  # < 8 chars
            "full_name": "User",
            "organization_name": "My Org",
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_signup_invalid_email_returns_422(async_client):
    response = await async_client.post(
        "/api/v1/auth/signup",
        json={
            "email": "not-an-email",
            "password": "securepassword",
            "full_name": "User",
            "organization_name": "My Org",
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_signup_missing_fields_returns_422(async_client):
    response = await async_client.post(
        "/api/v1/auth/signup",
        json={"email": "user@example.com"},
    )
    assert response.status_code == 422


# ── rate limit ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_signup_rate_limit_returns_429(async_client, monkeypatch):
    """Hitting signup 4 times from the same IP triggers rate limit on the 4th."""
    result = _make_happy_result()
    stub = _StubSignupService(result=result)

    monkeypatch.setattr(
        "app.presentation.api.v1.auth.SignupService",
        _make_stub_class(stub),
    )

    # Patch get_settings to return "3/minute" so we don't have to wait an hour
    from unittest.mock import MagicMock
    mock_settings = MagicMock()
    mock_settings.rate_limit_signup = "3/minute"
    monkeypatch.setattr("app.presentation.api.v1.auth.get_settings", lambda: mock_settings)

    payload = {
        "email": "rl@example.com",
        "password": "securepassword",
        "full_name": "RL User",
        "organization_name": "RL Org",
    }

    # 3 requests should succeed
    for _ in range(3):
        r = await async_client.post("/api/v1/auth/signup", json=payload)
        assert r.status_code in (201, 409)  # may conflict but not rate-limited

    # 4th should be rate limited
    r = await async_client.post("/api/v1/auth/signup", json=payload)
    assert r.status_code == 429
