"""Integration tests — /api/v1/auth/* endpoints.

Auth endpoints (login, me) create SQLAlchemyUserRepository(session) directly
inside the route handler — they do NOT use FastAPI DI for the repo.  We
monkeypatch the class in the auth module to return a FakeUserRepository that
ignores the session argument and works from an in-memory dict.
"""

from __future__ import annotations

import uuid

import pytest

from app.domain.entities import User
from app.infrastructure.auth.jwt_handler import (
    create_refresh_token,
    hash_password,
)
from tests.fakes import FakeUserRepository

# ── Helpers ───────────────────────────────────────────────────────────────────

TEST_EMAIL = "integration_test@example.com"
TEST_PASSWORD = "supersecret123"
TEST_TENANT_ID = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
TEST_USER_ID = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")


def _make_fake_repo_class(user: User | None):
    """
    Return a class whose constructor signature matches SQLAlchemyUserRepository(session)
    but delegates all calls to a FakeUserRepository pre-seeded with the given user.
    """
    repo = FakeUserRepository()
    if user is not None:
        # Seed synchronously via the internal dict (bypass async create)
        repo._users[user.id] = user
        repo._by_email[user.email] = user.id

    class _Repo:
        def __init__(self, session):  # session is ignored
            self._fake = repo

        async def get_by_email(self, email: str):
            return await self._fake.get_by_email(email)

        async def get_by_id(self, user_id):
            return await self._fake.get_by_id(user_id)

    return _Repo


# ── Login tests ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_login_valid_credentials_returns_200(async_client, monkeypatch):
    user = User(
        id=TEST_USER_ID,
        tenant_id=TEST_TENANT_ID,
        email=TEST_EMAIL,
        hashed_password=hash_password(TEST_PASSWORD),
        full_name="Test User",
        role="user",
    )

    monkeypatch.setattr(
        "app.presentation.api.v1.auth.SQLAlchemyUserRepository",
        _make_fake_repo_class(user),
    )

    response = await async_client.post(
        "/api/v1/auth/login",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
    )

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_invalid_password_returns_401(async_client, monkeypatch):
    user = User(
        id=TEST_USER_ID,
        tenant_id=TEST_TENANT_ID,
        email=TEST_EMAIL,
        hashed_password=hash_password(TEST_PASSWORD),
        full_name="Test User",
        role="user",
    )

    monkeypatch.setattr(
        "app.presentation.api.v1.auth.SQLAlchemyUserRepository",
        _make_fake_repo_class(user),
    )

    response = await async_client.post(
        "/api/v1/auth/login",
        json={"email": TEST_EMAIL, "password": "wrong-password"},
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_unknown_email_returns_401(async_client, monkeypatch):
    monkeypatch.setattr(
        "app.presentation.api.v1.auth.SQLAlchemyUserRepository",
        _make_fake_repo_class(None),  # empty repo
    )

    response = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@example.com", "password": "whatever"},
    )

    assert response.status_code == 401


# ── Refresh token tests ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_refresh_with_valid_token_returns_200(async_client, monkeypatch):
    """POST /auth/refresh with a valid token → 200 with new access + refresh tokens.

    Updated for ADR-ROLE-01: the handler now does a DB lookup via
    SQLAlchemyUserRepository.get_by_id, so we monkeypatch the class to return
    a valid user (same pattern as login/me tests in this file).
    """
    user = User(
        id=TEST_USER_ID,
        tenant_id=TEST_TENANT_ID,
        email=TEST_EMAIL,
        hashed_password=hash_password(TEST_PASSWORD),
        full_name="Test User",
        role="user",
        is_active=True,
    )

    monkeypatch.setattr(
        "app.presentation.api.v1.auth.SQLAlchemyUserRepository",
        _make_fake_repo_class(user),
    )

    refresh_token = create_refresh_token(
        user_id=str(TEST_USER_ID),
        tenant_id=str(TEST_TENANT_ID),
    )

    response = await async_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data


@pytest.mark.asyncio
async def test_refresh_with_invalid_token_returns_401(async_client):
    response = await async_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": "this.is.not.a.jwt"},
    )

    assert response.status_code == 401


# ── /me tests ─────────────────────────────────────────────────────────────────

# NOTE: The conftest overrides get_current_user globally, so /me will always
# receive the test_user from conftest (TEST_USER_ID = aaaaaaaa...).
# We must seed a user with THAT id in the repo.
CONFTEST_USER_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
CONFTEST_TENANT_ID = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")


@pytest.mark.asyncio
async def test_get_me_with_valid_token_returns_200(async_client, auth_headers, monkeypatch):
    user = User(
        id=CONFTEST_USER_ID,
        tenant_id=CONFTEST_TENANT_ID,
        email="me@test.com",
        hashed_password=hash_password("any"),
        full_name="Me User",
        role="admin",
    )

    monkeypatch.setattr(
        "app.presentation.api.v1.auth.SQLAlchemyUserRepository",
        _make_fake_repo_class(user),
    )

    response = await async_client.get("/api/v1/auth/me", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "me@test.com"
    assert data["role"] == "admin"


@pytest.mark.asyncio
async def test_get_me_without_token_returns_401(async_client, app):
    """Unauthenticated request to /me must return 401.

    We temporarily remove the get_current_user override for this test so the
    real dependency (which enforces the Bearer token) kicks in.
    """
    from app.presentation.middleware.tenant import get_current_user

    # Remove the override so the real auth dependency runs
    original = app.dependency_overrides.pop(get_current_user, None)
    try:
        response = await async_client.get("/api/v1/auth/me")
        assert response.status_code == 401
    finally:
        if original is not None:
            app.dependency_overrides[get_current_user] = original


# ── Task 5.8: effective_bulk_limit in /me response ────────────────────────────


@pytest.mark.asyncio
async def test_get_me_with_null_limit_shows_global_default(async_client, auth_headers, monkeypatch):
    """User with null bulk_generation_limit sees the global default in /me response."""
    from unittest.mock import MagicMock

    # Create a user with bulk_generation_limit=None
    user = User(
        id=CONFTEST_USER_ID,
        tenant_id=CONFTEST_TENANT_ID,
        email="nolimit@test.com",
        hashed_password=hash_password("any"),
        full_name="No Limit User",
        role="user",
        bulk_generation_limit=None,  # no per-user limit
    )

    monkeypatch.setattr(
        "app.presentation.api.v1.auth.SQLAlchemyUserRepository",
        _make_fake_repo_class(user),
    )

    # Patch get_settings to return mock with known global limit
    mock_settings = MagicMock()
    mock_settings.bulk_generation_limit = 10
    monkeypatch.setattr("app.presentation.api.v1.auth.get_settings", lambda: mock_settings)

    response = await async_client.get("/api/v1/auth/me", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["effective_bulk_limit"] == 10


@pytest.mark.asyncio
async def test_get_me_with_custom_limit_shows_that_limit(async_client, auth_headers, monkeypatch):
    """User with custom bulk_generation_limit=50 sees 50 in /me response (overrides global 10)."""
    from unittest.mock import MagicMock

    user = User(
        id=CONFTEST_USER_ID,
        tenant_id=CONFTEST_TENANT_ID,
        email="customlimit@test.com",
        hashed_password=hash_password("any"),
        full_name="Custom Limit User",
        role="user",
        bulk_generation_limit=50,
    )

    monkeypatch.setattr(
        "app.presentation.api.v1.auth.SQLAlchemyUserRepository",
        _make_fake_repo_class(user),
    )

    # Global limit is 10, but user has 50 — user's limit wins
    mock_settings = MagicMock()
    mock_settings.bulk_generation_limit = 10
    monkeypatch.setattr("app.presentation.api.v1.auth.get_settings", lambda: mock_settings)

    response = await async_client.get("/api/v1/auth/me", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["effective_bulk_limit"] == 50


# ── /me includes email_verified ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_me_includes_email_verified_field(async_client, auth_headers, monkeypatch):
    """GET /auth/me should return email_verified field."""
    from unittest.mock import MagicMock

    user = User(
        id=CONFTEST_USER_ID,
        tenant_id=CONFTEST_TENANT_ID,
        email="verified@test.com",
        hashed_password=hash_password("any"),
        full_name="Verified User",
        role="user",
        email_verified=True,
    )

    monkeypatch.setattr(
        "app.presentation.api.v1.auth.SQLAlchemyUserRepository",
        _make_fake_repo_class(user),
    )

    mock_settings = MagicMock()
    mock_settings.bulk_generation_limit = 10
    monkeypatch.setattr("app.presentation.api.v1.auth.get_settings", lambda: mock_settings)

    response = await async_client.get("/api/v1/auth/me", headers=auth_headers)
    assert response.status_code == 200
    assert "email_verified" in response.json()


@pytest.mark.asyncio
async def test_auth_me_returns_email_verified_true_even_if_db_false(
    async_client, auth_headers, monkeypatch
):
    """REQ-SOS-14 / SCEN-SOS-09: GET /auth/me MUST return email_verified=True even when DB has False.

    RED: currently passes if auth.py uses getattr(user, 'email_verified', True) AND the
    user has email_verified=False — because getattr returns False from DB.
    GREEN: passes after email_verified is hardcoded to True unconditionally.
    """
    from unittest.mock import MagicMock

    user = User(
        id=CONFTEST_USER_ID,
        tenant_id=CONFTEST_TENANT_ID,
        email="unverified-me@test.com",
        hashed_password=hash_password("any"),
        full_name="Unverified Me User",
        role="user",
        email_verified=False,  # DB value is False — response MUST still be True
    )

    monkeypatch.setattr(
        "app.presentation.api.v1.auth.SQLAlchemyUserRepository",
        _make_fake_repo_class(user),
    )

    mock_settings = MagicMock()
    mock_settings.bulk_generation_limit = 10
    monkeypatch.setattr("app.presentation.api.v1.auth.get_settings", lambda: mock_settings)

    response = await async_client.get("/api/v1/auth/me", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["email_verified"] is True, (
        f"Expected email_verified=True regardless of DB value, got: {data['email_verified']}"
    )
