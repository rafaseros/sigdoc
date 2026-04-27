"""Integration tests — /auth/refresh re-fetches role from DB.

REQ-ROLE-09: refresh MUST read role from DB, not from token payload.
REQ-ROLE-10: refresh MUST return 401 for deleted/deactivated users.

SCEN-ROLE-06: Promoted user gets updated role in new access token.
SCEN-ROLE-07: Deleted user gets 401.

Strategy: monkeypatch SQLAlchemyUserRepository in the auth module, same
pattern used by test_auth_api.py for login/me tests. The conftest
get_session override provides a no-op session, but the handler constructs
the repo directly, so we patch the class.
"""

from __future__ import annotations

import uuid

import pytest
from jose import jwt

from app.config import get_settings
from app.domain.entities import User
from app.infrastructure.auth.jwt_handler import (
    create_refresh_token,
    hash_password,
)

TEST_USER_ID = uuid.UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")
TEST_TENANT_ID = uuid.UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee")


def _make_repo_class(user: User | None):
    """Return a fake SQLAlchemyUserRepository whose get_by_id returns the given user."""

    class _FakeRepo:
        def __init__(self, session):  # session is ignored
            pass

        async def get_by_id(self, user_id):
            return user

    return _FakeRepo


# ── SCEN-ROLE-06 ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_refresh_returns_db_role_after_promotion(async_client, monkeypatch):
    """SCEN-ROLE-06: User promoted to template_creator — refresh must return the new role.

    The refresh token was issued when the user was document_generator.
    After admin promotes the user, the DB row has role='template_creator'.
    The new access token MUST carry role='template_creator' (from DB), NOT
    'document_generator' (from the old token payload / fallback).
    """
    # DB state AFTER promotion: user is now template_creator
    user = User(
        id=TEST_USER_ID,
        tenant_id=TEST_TENANT_ID,
        email="promoted@example.com",
        hashed_password=hash_password("password123"),
        full_name="Promoted User",
        role="template_creator",  # DB-current role (after promotion)
        is_active=True,
    )

    # The refresh token was issued with no role claim (correct — refresh tokens
    # don't carry role in this codebase's create_refresh_token)
    refresh_token = create_refresh_token(
        user_id=str(TEST_USER_ID),
        tenant_id=str(TEST_TENANT_ID),
    )

    monkeypatch.setattr(
        "app.presentation.api.v1.auth.SQLAlchemyUserRepository",
        _make_repo_class(user),
    )

    response = await async_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data

    # Decode the new access token and assert role came from DB
    settings = get_settings()
    payload = jwt.decode(data["access_token"], settings.secret_key, algorithms=["HS256"])
    assert payload["role"] == "template_creator", (
        f"Expected role='template_creator' from DB, got role='{payload['role']}'"
    )


# ── SCEN-ROLE-07 ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_refresh_returns_401_for_deleted_user(async_client, monkeypatch):
    """SCEN-ROLE-07: User deleted from DB — refresh must return 401, no new token.

    The refresh token is valid (not expired, correct signature), but the user
    no longer exists in the database. The endpoint MUST return HTTP 401 and
    MUST NOT issue a new access token.
    """
    # DB state: user does not exist (get_by_id returns None)
    refresh_token = create_refresh_token(
        user_id=str(TEST_USER_ID),
        tenant_id=str(TEST_TENANT_ID),
    )

    monkeypatch.setattr(
        "app.presentation.api.v1.auth.SQLAlchemyUserRepository",
        _make_repo_class(None),  # user not found in DB
    )

    response = await async_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )

    assert response.status_code == 401
    data = response.json()
    assert "access_token" not in data
