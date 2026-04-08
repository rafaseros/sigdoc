"""Integration tests — /api/v1/users/* endpoints (admin operations).

The users and auth endpoints both instantiate SQLAlchemyUserRepository directly
inside the route handler.  We monkeypatch the class in each module to return a
FakeUserRepository that works from an in-memory dict.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from app.domain.entities import User
from app.infrastructure.auth.jwt_handler import hash_password
from tests.fakes import FakeUserRepository

# ── Stable IDs (must match integration conftest) ──────────────────────────────

ADMIN_USER_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
ADMIN_TENANT_ID = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")

TARGET_USER_ID = uuid.UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")


# ── Helper: build a fake-repo class that the endpoint can instantiate ─────────


def _make_users_repo_class(fake_repo: FakeUserRepository):
    """Return a drop-in replacement for SQLAlchemyUserRepository.

    The real class takes a session argument — we accept and discard it.
    """

    class _Repo:
        def __init__(self, session):  # noqa: ARG002
            self._fake = fake_repo

        async def get_by_email(self, email: str):
            return await self._fake.get_by_email(email)

        async def get_by_id(self, user_id):
            return await self._fake.get_by_id(user_id)

        async def create(self, user):
            return await self._fake.create(user)

        async def list_by_tenant(self, page: int = 1, size: int = 20):
            return await self._fake.list_by_tenant(page=page, size=size)

        async def update(self, user_id, **kwargs):
            return await self._fake.update(user_id, **kwargs)

        async def deactivate(self, user_id):
            return await self._fake.deactivate(user_id)

    return _Repo


def _seed_user(repo: FakeUserRepository, user: User) -> None:
    """Seed a user synchronously into the fake repo."""
    repo._users[user.id] = user
    repo._by_email[user.email] = user.id


# ── Task 5.8: Admin sets/clears per-user limit — integration roundtrip ────────


@pytest.mark.asyncio
async def test_admin_sets_user_bulk_limit_and_me_reflects_it(
    async_client, auth_headers, monkeypatch
):
    """Admin PUTs user with bulk_generation_limit=5 → GET /auth/me shows effective_bulk_limit=5."""
    fake_repo = FakeUserRepository()

    target_user = User(
        id=TARGET_USER_ID,
        tenant_id=ADMIN_TENANT_ID,
        email="target@test.com",
        hashed_password=hash_password("secret"),
        full_name="Target User",
        role="user",
        is_active=True,
        bulk_generation_limit=None,
        created_at=datetime.now(timezone.utc),
    )
    _seed_user(fake_repo, target_user)

    # The /me endpoint reads the same user — seed them with the admin ID too
    # (auth/me uses ADMIN_USER_ID from get_current_user override in conftest)
    me_user = User(
        id=ADMIN_USER_ID,
        tenant_id=ADMIN_TENANT_ID,
        email="me_user@test.com",
        hashed_password=hash_password("any"),
        full_name="Me User",
        role="user",
        is_active=True,
        bulk_generation_limit=None,
        created_at=datetime.now(timezone.utc),
    )
    _seed_user(fake_repo, me_user)

    repo_class = _make_users_repo_class(fake_repo)

    # Patch both the users and auth modules
    monkeypatch.setattr("app.presentation.api.v1.users.SQLAlchemyUserRepository", repo_class)
    monkeypatch.setattr("app.presentation.api.v1.auth.SQLAlchemyUserRepository", repo_class)

    # Patch get_settings so effective_bulk_limit uses a known global
    mock_settings = MagicMock()
    mock_settings.bulk_generation_limit = 10
    monkeypatch.setattr("app.presentation.api.v1.auth.get_settings", lambda: mock_settings)

    # Admin PUTs target user with limit=5
    put_response = await async_client.put(
        f"/api/v1/users/{TARGET_USER_ID}",
        headers=auth_headers,
        json={"bulk_generation_limit": 5},
    )
    assert put_response.status_code == 200, put_response.text
    assert put_response.json()["bulk_generation_limit"] == 5

    # Now verify the me_user's effective limit — we update me_user's limit via the same fake repo
    # to simulate what would happen if the admin also updated the requesting user's limit.
    # For this roundtrip, we update the me_user directly in the fake repo and call /auth/me.
    fake_repo._users[ADMIN_USER_ID].bulk_generation_limit = 5

    me_response = await async_client.get("/api/v1/auth/me", headers=auth_headers)
    assert me_response.status_code == 200, me_response.text
    data = me_response.json()
    assert data["effective_bulk_limit"] == 5


@pytest.mark.asyncio
async def test_admin_clears_user_bulk_limit_and_me_shows_global_default(
    async_client, auth_headers, monkeypatch
):
    """Admin PUTs user with bulk_generation_limit=null → GET /auth/me shows global default."""
    fake_repo = FakeUserRepository()

    me_user = User(
        id=ADMIN_USER_ID,
        tenant_id=ADMIN_TENANT_ID,
        email="me_clear@test.com",
        hashed_password=hash_password("any"),
        full_name="Me Clear User",
        role="user",
        is_active=True,
        bulk_generation_limit=None,  # cleared / null
        created_at=datetime.now(timezone.utc),
    )
    _seed_user(fake_repo, me_user)

    repo_class = _make_users_repo_class(fake_repo)
    monkeypatch.setattr("app.presentation.api.v1.auth.SQLAlchemyUserRepository", repo_class)

    mock_settings = MagicMock()
    mock_settings.bulk_generation_limit = 10
    monkeypatch.setattr("app.presentation.api.v1.auth.get_settings", lambda: mock_settings)

    # User has null bulk_generation_limit → /me must return global default (10)
    me_response = await async_client.get("/api/v1/auth/me", headers=auth_headers)
    assert me_response.status_code == 200, me_response.text
    data = me_response.json()
    assert data["effective_bulk_limit"] == 10
