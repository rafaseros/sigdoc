"""Unit tests for auth middleware (task 3.5)."""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from jose import jwt

from app.infrastructure.auth.jwt_handler import create_access_token, create_refresh_token
from app.presentation.middleware.tenant import CurrentUser, get_current_user


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_user_id() -> str:
    return str(uuid.uuid4())


def _make_tenant_id() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Valid access token → resolves to CurrentUser
# ---------------------------------------------------------------------------


class TestGetCurrentUserValid:
    async def test_valid_access_token_returns_current_user(self):
        user_id = _make_user_id()
        tenant_id = _make_tenant_id()
        token = create_access_token(user_id, tenant_id, "admin")

        result = await get_current_user(token=token)

        assert isinstance(result, CurrentUser)

    async def test_user_id_matches(self):
        user_id = _make_user_id()
        tenant_id = _make_tenant_id()
        token = create_access_token(user_id, tenant_id, "admin")

        result = await get_current_user(token=token)

        assert str(result.user_id) == user_id

    async def test_tenant_id_matches(self):
        user_id = _make_user_id()
        tenant_id = _make_tenant_id()
        token = create_access_token(user_id, tenant_id, "viewer")

        result = await get_current_user(token=token)

        assert str(result.tenant_id) == tenant_id

    async def test_role_matches(self):
        user_id = _make_user_id()
        tenant_id = _make_tenant_id()
        token = create_access_token(user_id, tenant_id, "manager")

        result = await get_current_user(token=token)

        assert result.role == "manager"

    async def test_default_role_is_user(self):
        """If 'role' claim missing from token, defaults to 'user'."""
        from app.config import get_settings

        settings = get_settings()
        # Manually craft a token without the role claim
        payload = {
            "sub": str(uuid.uuid4()),
            "tenant_id": str(uuid.uuid4()),
            "type": "access",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=30),
        }
        token = jwt.encode(payload, settings.secret_key, algorithm="HS256")

        result = await get_current_user(token=token)
        assert result.role == "user"


# ---------------------------------------------------------------------------
# Invalid tokens → 401
# ---------------------------------------------------------------------------


class TestGetCurrentUserInvalid:
    async def test_malformed_token_raises_401(self):
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(token="not.a.real.token")
        assert exc_info.value.status_code == 401

    async def test_empty_token_raises_401(self):
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(token="")
        assert exc_info.value.status_code == 401

    async def test_random_string_raises_401(self):
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(token="randomgarbage")
        assert exc_info.value.status_code == 401

    async def test_tampered_token_raises_401(self):
        token = create_access_token(_make_user_id(), _make_tenant_id(), "user")
        parts = token.split(".")
        parts[2] = "invalidsignature"
        tampered = ".".join(parts)

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(token=tampered)
        assert exc_info.value.status_code == 401

    async def test_expired_token_raises_401(self):
        from app.config import get_settings

        settings = get_settings()
        expired_payload = {
            "sub": str(uuid.uuid4()),
            "tenant_id": str(uuid.uuid4()),
            "role": "user",
            "type": "access",
            "exp": datetime.now(timezone.utc) - timedelta(seconds=5),
        }
        expired_token = jwt.encode(
            expired_payload, settings.secret_key, algorithm="HS256"
        )

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(token=expired_token)
        assert exc_info.value.status_code == 401

    async def test_refresh_token_as_access_raises_401(self):
        """Using a refresh token where an access token is required → 401."""
        user_id = _make_user_id()
        tenant_id = _make_tenant_id()
        refresh_token = create_refresh_token(user_id, tenant_id)

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(token=refresh_token)
        assert exc_info.value.status_code == 401

    async def test_missing_sub_raises_401(self):
        """Token without 'sub' claim → 401."""
        from app.config import get_settings

        settings = get_settings()
        payload = {
            # no 'sub'
            "tenant_id": str(uuid.uuid4()),
            "type": "access",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=30),
        }
        token = jwt.encode(payload, settings.secret_key, algorithm="HS256")

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(token=token)
        assert exc_info.value.status_code == 401

    async def test_missing_tenant_id_raises_401(self):
        """Token without 'tenant_id' claim → 401."""
        from app.config import get_settings

        settings = get_settings()
        payload = {
            "sub": str(uuid.uuid4()),
            # no 'tenant_id'
            "type": "access",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=30),
        }
        token = jwt.encode(payload, settings.secret_key, algorithm="HS256")

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(token=token)
        assert exc_info.value.status_code == 401
