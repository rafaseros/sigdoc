"""Unit tests — rate limit resolver functions (Task 5.1).

Tests get_tenant_key, tier_limit_generate, tier_limit_bulk, tier_limit_refresh
with various request states: authenticated, unauthenticated, cache hit, fallback.

Spec: REQ-RL-03, REQ-RL-04, REQ-RL-05

Note: slowapi limit callables (tier_limit_generate/bulk/refresh) are zero-arg
and read from a ContextVar. We use the resolve_tier_limit_* helper functions
for request-based testing, and set the ContextVar directly for callable testing.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from tests.fakes.fake_subscription_tier_repository import (
    FREE_TIER,
    PRO_TIER,
    ENTERPRISE_TIER,
)


# ---------------------------------------------------------------------------
# Helpers — build fake Request objects
# ---------------------------------------------------------------------------


def _make_request(
    bearer_token: str | None = None,
    tier=None,
    client_host: str = "1.2.3.4",
) -> MagicMock:
    """Build a minimal fake starlette Request."""
    req = MagicMock()
    req.client = SimpleNamespace(host=client_host)

    # Authorization header
    if bearer_token is not None:
        req.headers = {"Authorization": f"Bearer {bearer_token}"}
    else:
        req.headers = {}

    # request.state.tier
    if tier is not None:
        req.state = SimpleNamespace(tier=tier)
    else:
        # state has no 'tier' attribute
        req.state = SimpleNamespace()

    return req


def _make_valid_token(tenant_id: str | None = None) -> str:
    """Create a real JWT with the test secret key."""
    from app.infrastructure.auth.jwt_handler import create_access_token
    return create_access_token(
        user_id=str(uuid.uuid4()),
        tenant_id=tenant_id or str(uuid.uuid4()),
        role="user",
    )


# ---------------------------------------------------------------------------
# Tests — get_tenant_key (Task 2.1)
# ---------------------------------------------------------------------------


class TestGetTenantKey:
    """get_tenant_key should return tenant_id for authenticated requests, IP otherwise."""

    def test_returns_tenant_id_from_valid_jwt(self):
        from app.presentation.middleware.rate_limit import get_tenant_key

        tenant_id = str(uuid.uuid4())
        token = _make_valid_token(tenant_id=tenant_id)
        req = _make_request(bearer_token=token)

        result = get_tenant_key(req)
        assert result == tenant_id

    def test_falls_back_to_ip_when_no_authorization_header(self):
        from app.presentation.middleware.rate_limit import get_tenant_key

        req = _make_request(bearer_token=None, client_host="10.0.0.1")
        result = get_tenant_key(req)
        assert result == "10.0.0.1"

    def test_falls_back_to_ip_for_invalid_jwt(self):
        from app.presentation.middleware.rate_limit import get_tenant_key

        req = _make_request(bearer_token="not-a-valid-jwt", client_host="192.168.1.1")
        result = get_tenant_key(req)
        assert result == "192.168.1.1"

    def test_falls_back_to_ip_for_non_bearer_scheme(self):
        """If Authorization header uses a non-Bearer scheme, fall back to IP."""
        from app.presentation.middleware.rate_limit import get_tenant_key

        req = MagicMock()
        req.client = SimpleNamespace(host="5.5.5.5")
        req.headers = {"Authorization": "Basic dXNlcjpwYXNz"}
        req.state = SimpleNamespace()

        result = get_tenant_key(req)
        assert result == "5.5.5.5"


# ---------------------------------------------------------------------------
# Tests — request-state resolver helpers (Task 2.3)
# Used to verify the resolver logic; the actual slowapi callables are zero-arg.
# ---------------------------------------------------------------------------


class TestResolveTierLimitGenerate:
    """resolve_tier_limit_generate reads from request.state.tier or falls back to Settings."""

    def test_returns_tier_specific_limit_when_tier_available(self):
        from app.presentation.middleware.rate_limit import resolve_tier_limit_generate

        req = _make_request(tier=FREE_TIER)
        result = resolve_tier_limit_generate(req)
        assert result == "10/minute"  # FREE_TIER.rate_limit_generate

    def test_returns_pro_tier_limit(self):
        from app.presentation.middleware.rate_limit import resolve_tier_limit_generate

        req = _make_request(tier=PRO_TIER)
        result = resolve_tier_limit_generate(req)
        assert result == "30/minute"  # PRO_TIER.rate_limit_generate

    def test_falls_back_to_settings_when_no_tier(self):
        """REQ-RL-05: Must fall back to global Settings, must NOT 500."""
        from app.presentation.middleware.rate_limit import resolve_tier_limit_generate
        from app.config import get_settings

        req = _make_request(tier=None)
        result = resolve_tier_limit_generate(req)
        assert result == get_settings().rate_limit_generate

    def test_enterprise_tier_generous_limit(self):
        from app.presentation.middleware.rate_limit import resolve_tier_limit_generate

        req = _make_request(tier=ENTERPRISE_TIER)
        result = resolve_tier_limit_generate(req)
        assert result == "60/minute"  # ENTERPRISE_TIER.rate_limit_generate


class TestResolveTierLimitBulk:
    """resolve_tier_limit_bulk reads from request.state.tier or falls back to Settings."""

    def test_returns_free_tier_bulk_limit(self):
        from app.presentation.middleware.rate_limit import resolve_tier_limit_bulk

        req = _make_request(tier=FREE_TIER)
        result = resolve_tier_limit_bulk(req)
        assert result == "2/minute"  # FREE_TIER.rate_limit_bulk

    def test_returns_enterprise_bulk_limit(self):
        from app.presentation.middleware.rate_limit import resolve_tier_limit_bulk

        req = _make_request(tier=ENTERPRISE_TIER)
        result = resolve_tier_limit_bulk(req)
        assert result == "20/minute"  # ENTERPRISE_TIER.rate_limit_bulk

    def test_falls_back_to_settings_when_no_tier(self):
        from app.presentation.middleware.rate_limit import resolve_tier_limit_bulk
        from app.config import get_settings

        req = _make_request(tier=None)
        result = resolve_tier_limit_bulk(req)
        assert result == get_settings().rate_limit_generate_bulk


class TestResolveTierLimitRefresh:
    """resolve_tier_limit_refresh reads from request.state.tier or falls back to Settings."""

    def test_returns_free_tier_refresh_limit(self):
        from app.presentation.middleware.rate_limit import resolve_tier_limit_refresh

        req = _make_request(tier=FREE_TIER)
        result = resolve_tier_limit_refresh(req)
        assert result == "10/minute"  # FREE_TIER.rate_limit_refresh

    def test_returns_pro_tier_refresh_limit(self):
        from app.presentation.middleware.rate_limit import resolve_tier_limit_refresh

        req = _make_request(tier=PRO_TIER)
        result = resolve_tier_limit_refresh(req)
        assert result == "20/minute"  # PRO_TIER.rate_limit_refresh

    def test_falls_back_to_settings_when_no_tier(self):
        from app.presentation.middleware.rate_limit import resolve_tier_limit_refresh
        from app.config import get_settings

        req = _make_request(tier=None)
        result = resolve_tier_limit_refresh(req)
        assert result == get_settings().rate_limit_refresh


# ---------------------------------------------------------------------------
# Tests — zero-arg ContextVar callables (slowapi contract)
# ---------------------------------------------------------------------------


class TestContextVarLimitCallables:
    """tier_limit_* are zero-arg callables that read from ContextVar."""

    def test_tier_limit_generate_returns_settings_when_no_context(self):
        """Without middleware context, falls back to Settings (REQ-RL-05)."""
        from app.presentation.middleware.rate_limit import (
            tier_limit_generate,
            _current_tier,
        )
        from app.config import get_settings

        # Reset ContextVar to None (no active request context)
        token = _current_tier.set(None)
        try:
            result = tier_limit_generate()
            assert result == get_settings().rate_limit_generate
        finally:
            _current_tier.reset(token)

    def test_tier_limit_generate_returns_tier_value_from_context(self):
        """With tier in ContextVar, returns tier-specific limit."""
        from app.presentation.middleware.rate_limit import (
            tier_limit_generate,
            _current_tier,
        )

        token = _current_tier.set(FREE_TIER)
        try:
            result = tier_limit_generate()
            assert result == "10/minute"  # FREE_TIER.rate_limit_generate
        finally:
            _current_tier.reset(token)

    def test_tier_limit_bulk_returns_tier_value_from_context(self):
        from app.presentation.middleware.rate_limit import (
            tier_limit_bulk,
            _current_tier,
        )

        token = _current_tier.set(ENTERPRISE_TIER)
        try:
            result = tier_limit_bulk()
            assert result == "20/minute"  # ENTERPRISE_TIER.rate_limit_bulk
        finally:
            _current_tier.reset(token)

    def test_tier_limit_refresh_returns_tier_value_from_context(self):
        from app.presentation.middleware.rate_limit import (
            tier_limit_refresh,
            _current_tier,
        )

        token = _current_tier.set(PRO_TIER)
        try:
            result = tier_limit_refresh()
            assert result == "20/minute"  # PRO_TIER.rate_limit_refresh
        finally:
            _current_tier.reset(token)

    def test_tier_limit_bulk_falls_back_when_no_context(self):
        from app.presentation.middleware.rate_limit import (
            tier_limit_bulk,
            _current_tier,
        )
        from app.config import get_settings

        token = _current_tier.set(None)
        try:
            result = tier_limit_bulk()
            assert result == get_settings().rate_limit_generate_bulk
        finally:
            _current_tier.reset(token)
