"""Integration tests — rate limiting (HTTP 429).

These tests verify that the slowapi rate limiter correctly returns 429 when the
configured limit is exceeded.  Unlike other integration tests, we do NOT rely on
the autouse reset_rate_limiter fixture to clear state between requests within a
single test — the whole point is to exhaust the limit in one shot.

Strategy
--------
- Patch get_settings() in auth.py to return a Settings object with rate_limit_login="3/minute"
  so we only need 4 requests to trigger a 429 (instead of 6 with the default 5/minute).
- Clear the lru_cache on get_settings BEFORE monkeypatching (so the cached real instance
  is evicted).  After the test, monkeypatch automatically restores the original function.
- Monkeypatch SQLAlchemyUserRepository the same way the auth tests do.

For tier-specific rate limit tests (SC-RL-01 through SC-RL-06):
- Monkeypatch tier_limit_generate / tier_limit_bulk / tier_limit_refresh in the
  documents module to return a low limit string for fast/deterministic testing.
- These functions are zero-arg ContextVar-based callables in rate_limit.py.
"""

from __future__ import annotations

import uuid

import pytest

from app.domain.entities import User
from app.infrastructure.auth.jwt_handler import hash_password
from tests.fakes import FakeUserRepository


TEST_EMAIL = "ratelimit_test@example.com"
TEST_PASSWORD = "supersecret123"
TEST_TENANT_ID = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
TEST_USER_ID = uuid.UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")


def _make_fake_repo_class(user: User | None):
    """Return a fake repo class whose constructor accepts a session argument (ignored)."""
    repo = FakeUserRepository()
    if user is not None:
        repo._users[user.id] = user
        repo._by_email[user.email] = user.id

    class _Repo:
        def __init__(self, session):
            self._fake = repo

        async def get_by_email(self, email: str):
            return await self._fake.get_by_email(email)

        async def get_by_id(self, user_id):
            return await self._fake.get_by_id(user_id)

    return _Repo


@pytest.mark.asyncio
async def test_login_returns_429_when_rate_limit_exceeded(async_client, monkeypatch):
    """Hitting the login endpoint more than the configured limit returns HTTP 429."""
    import app.config as config_module
    from app.config import Settings

    # Use a very low limit so the test is fast and deterministic.
    low_limit_settings = Settings.model_construct(
        rate_limit_login="3/minute",
        rate_limit_refresh="10/minute",
        rate_limit_generate="20/minute",
        rate_limit_generate_bulk="5/minute",
        database_url="postgresql+asyncpg://test:test@localhost/test",
        secret_key="test-secret-key-for-testing-only-not-real",
        minio_access_key="minioadmin",
        minio_secret_key="minioadmin",
    )

    # Clear the lru_cache BEFORE patching so the cached real instance is evicted.
    config_module.get_settings.cache_clear()

    # Patch get_settings in the auth module (where the lambda reads it).
    # monkeypatch restores the original automatically after the test.
    monkeypatch.setattr(
        "app.presentation.api.v1.auth.get_settings",
        lambda: low_limit_settings,
    )

    user = User(
        id=TEST_USER_ID,
        tenant_id=TEST_TENANT_ID,
        email=TEST_EMAIL,
        hashed_password=hash_password(TEST_PASSWORD),
        full_name="Rate Limit Test User",
        role="user",
    )

    monkeypatch.setattr(
        "app.presentation.api.v1.auth.SQLAlchemyUserRepository",
        _make_fake_repo_class(user),
    )

    payload = {"email": TEST_EMAIL, "password": TEST_PASSWORD}

    # First 3 calls should succeed (limit is 3/minute).
    for i in range(3):
        response = await async_client.post("/api/v1/auth/login", json=payload)
        assert response.status_code == 200, f"Request {i + 1} unexpectedly failed: {response.status_code}"

    # 4th call must be rate-limited.
    response = await async_client.post("/api/v1/auth/login", json=payload)
    assert response.status_code == 429, f"Expected 429, got {response.status_code}"


# ---------------------------------------------------------------------------
# SC-RL-01: Free tier generate — hits limit at 10/min, 11th → 429
# SC-RL-05: Fallback to Settings when tier unavailable
# SC-RL-06: Different tenants have separate rate limit counters (per-tenant keying)
# ---------------------------------------------------------------------------


def _patch_limiter_dynamic_limit(limiter, endpoint_name_fragment: str, new_provider):
    """Directly patch the LimitGroup's __limit_provider for a given endpoint.

    slowapi stores callables by reference in _dynamic_route_limits[endpoint_name].
    Monkeypatching the module attribute doesn't affect the stored reference.
    This helper swaps the LimitGroup's private __limit_provider field directly.
    Returns a list of (LimitGroup, original_provider) tuples for restoration.
    """
    patched = []
    for key, groups in limiter._dynamic_route_limits.items():
        if endpoint_name_fragment in key:
            for lg in groups:
                original = lg._LimitGroup__limit_provider
                lg._LimitGroup__limit_provider = new_provider
                patched.append((lg, original))
    return patched


def _restore_limiter_providers(patched_list):
    """Restore LimitGroup.__limit_provider values from a patch list."""
    for lg, original in patched_list:
        lg._LimitGroup__limit_provider = original


@pytest.mark.asyncio
async def test_generate_returns_429_with_low_tier_limit(async_client):
    """SC-RL-01: When generate limit is 2/minute, 3rd request returns 429.

    We directly patch the LimitGroup's stored callable in the limiter's
    _dynamic_route_limits. This is the only reliable approach since slowapi
    captures function references at decoration time.
    """
    from app.presentation.middleware.rate_limit import limiter

    # Temporarily set the generate limit to 2/minute
    patched = _patch_limiter_dynamic_limit(limiter, "generate_document", lambda: "2/minute")
    try:
        for i in range(2):
            r = await async_client.post(
                "/api/v1/documents/generate",
                json={"template_version_id": str(uuid.uuid4()), "variables": {}},
            )
            assert r.status_code in (404, 422, 403, 201), f"Request {i+1}: {r.status_code}"

        r = await async_client.post(
            "/api/v1/documents/generate",
            json={"template_version_id": str(uuid.uuid4()), "variables": {}},
        )
        assert r.status_code == 429, f"Expected 429, got {r.status_code}"
    finally:
        _restore_limiter_providers(patched)


@pytest.mark.asyncio
async def test_bulk_generate_returns_429_with_low_tier_limit(async_client):
    """SC-RL-03: When bulk limit is 2/minute, 3rd request returns 429."""
    import io
    from app.presentation.middleware.rate_limit import limiter

    try:
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["name"])
        ws.append(["Alice"])
        buf = io.BytesIO()
        wb.save(buf)
        xlsx_bytes = buf.getvalue()
    except ImportError:
        pytest.skip("openpyxl not available")

    patched = _patch_limiter_dynamic_limit(limiter, "generate_bulk", lambda: "2/minute")
    try:
        for i in range(2):
            response = await async_client.post(
                "/api/v1/documents/generate-bulk",
                files={"file": ("test.xlsx", xlsx_bytes, "application/octet-stream")},
                data={"template_version_id": str(uuid.uuid4())},
            )
            assert response.status_code in (404, 422, 403, 201, 400), (
                f"Request {i+1} unexpected: {response.status_code}"
            )

        response = await async_client.post(
            "/api/v1/documents/generate-bulk",
            files={"file": ("test.xlsx", xlsx_bytes, "application/octet-stream")},
            data={"template_version_id": str(uuid.uuid4())},
        )
        assert response.status_code == 429, f"Expected 429, got {response.status_code}"
    finally:
        _restore_limiter_providers(patched)


@pytest.mark.asyncio
async def test_fallback_to_settings_when_no_tier():
    """SC-RL-05: When ContextVar is None (no tier loaded), fallback to Settings limit.

    This is a unit-level assertion: the zero-arg callable reads from ContextVar.
    """
    import app.presentation.middleware.rate_limit as rl_module
    from app.config import get_settings

    # Set ContextVar to None (no active tier)
    token = rl_module._current_tier.set(None)
    try:
        result = rl_module.tier_limit_generate()
        assert result == get_settings().rate_limit_generate
    finally:
        rl_module._current_tier.reset(token)


@pytest.mark.asyncio
async def test_fallback_bulk_to_settings_when_no_tier():
    """SC-RL-05: bulk fallback to Settings when no tier in ContextVar."""
    import app.presentation.middleware.rate_limit as rl_module
    from app.config import get_settings

    token = rl_module._current_tier.set(None)
    try:
        result = rl_module.tier_limit_bulk()
        assert result == get_settings().rate_limit_generate_bulk
    finally:
        rl_module._current_tier.reset(token)
