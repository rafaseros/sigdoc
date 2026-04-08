"""Rate limiting middleware and utilities.

Design (ADR-2, ADR-3, ADR-4):
- Limiter key: tenant_id from JWT for authenticated routes; IP for login.
- Dynamic limits: zero-arg callables that read from a ContextVar populated by
  TierPreloadMiddleware. Falls back to Settings when tier is unavailable.
- TTLCache(maxsize=256, ttl=60): tier cached per tenant_id for 1 minute.

slowapi callable contract: limit_value callables MUST be zero-arg (no parameters).
The middleware stores the tier in a ContextVar; zero-arg closures read it.
"""

from __future__ import annotations

import logging
from contextvars import ContextVar
from typing import Optional

from cachetools import TTLCache
from jose import JWTError, jwt
from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from app.config import get_settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# ContextVar — stores the current request's tier for zero-arg limit callables
# ---------------------------------------------------------------------------

_current_tier: ContextVar[Optional[object]] = ContextVar("_current_tier", default=None)


# ---------------------------------------------------------------------------
# Tier cache — shared across middleware instances (process-level)
# ---------------------------------------------------------------------------

_tier_cache: TTLCache = TTLCache(maxsize=256, ttl=60)


# ---------------------------------------------------------------------------
# Task 2.1 — Tenant key function
# ---------------------------------------------------------------------------


def get_tenant_key(request: Request) -> str:
    """Return tenant_id from JWT if present and valid; otherwise return client IP.

    Spec: REQ-RL-03, REQ-RL-05
    - Authenticated routes: keyed per tenant (different tenants have separate counters)
    - Login / unauthenticated routes: keyed by IP (brute-force protection; ADR-5)
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return get_remote_address(request)

    token = auth_header[len("Bearer "):]
    try:
        settings = get_settings()
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        tenant_id = payload.get("tenant_id")
        if tenant_id:
            return str(tenant_id)
    except (JWTError, Exception):
        pass

    return get_remote_address(request)


# ---------------------------------------------------------------------------
# Task 2.4 — Limiter init using get_tenant_key
# ---------------------------------------------------------------------------

limiter = Limiter(key_func=get_tenant_key)


# ---------------------------------------------------------------------------
# Task 2.3 — Dynamic limit resolver functions (zero-arg callables for slowapi)
#
# slowapi calls these with NO arguments (see LimitGroup.__iter__).
# They read the current tier from the ContextVar set by TierPreloadMiddleware.
# Falls back to Settings values when no tier is available (REQ-RL-05).
# ---------------------------------------------------------------------------


def tier_limit_generate() -> str:
    """Return generate rate limit for the current request's tier.

    Zero-arg callable for slowapi. Reads tier from ContextVar.
    Fallback: Settings.rate_limit_generate (REQ-RL-05).
    """
    tier = _current_tier.get()
    if tier is not None:
        return tier.rate_limit_generate
    return get_settings().rate_limit_generate


def tier_limit_bulk() -> str:
    """Return bulk rate limit for the current request's tier.

    Zero-arg callable for slowapi. Reads tier from ContextVar.
    Fallback: Settings.rate_limit_generate_bulk (REQ-RL-05).
    """
    tier = _current_tier.get()
    if tier is not None:
        return tier.rate_limit_bulk
    return get_settings().rate_limit_generate_bulk


def tier_limit_refresh() -> str:
    """Return refresh rate limit for the current request's tier.

    Zero-arg callable for slowapi. Reads tier from ContextVar.
    Fallback: Settings.rate_limit_refresh (REQ-RL-05).
    """
    tier = _current_tier.get()
    if tier is not None:
        return tier.rate_limit_refresh
    return get_settings().rate_limit_refresh


# ---------------------------------------------------------------------------
# Helper for tests — read tier from request state with attribute fallback
# The test functions use request.state.tier directly (passed as argument)
# so we expose a thin helper used in test utilities only.
# ---------------------------------------------------------------------------


def resolve_tier_limit_generate(request: Request) -> str:
    """Resolve generate limit from request.state.tier (test/inspection helper)."""
    try:
        tier = request.state.tier
        return tier.rate_limit_generate
    except AttributeError:
        return get_settings().rate_limit_generate


def resolve_tier_limit_bulk(request: Request) -> str:
    """Resolve bulk limit from request.state.tier (test/inspection helper)."""
    try:
        tier = request.state.tier
        return tier.rate_limit_bulk
    except AttributeError:
        return get_settings().rate_limit_generate_bulk


def resolve_tier_limit_refresh(request: Request) -> str:
    """Resolve refresh limit from request.state.tier (test/inspection helper)."""
    try:
        tier = request.state.tier
        return tier.rate_limit_refresh
    except AttributeError:
        return get_settings().rate_limit_refresh


# ---------------------------------------------------------------------------
# Task 2.2 — TierPreloadMiddleware
# ---------------------------------------------------------------------------


class TierPreloadMiddleware(BaseHTTPMiddleware):
    """Decode JWT → resolve tenant's SubscriptionTier → store in ContextVar.

    Must run BEFORE slowapi's rate limit check (added AFTER SlowAPIMiddleware in
    main.py due to Starlette's LIFO middleware ordering).

    Also stores tier on request.state.tier for endpoints/tests that want it.

    Cache: TTLCache(256 entries, 60s TTL) keyed by tenant_id string.
    Falls back gracefully — if tier cannot be resolved, ContextVar stays None
    and limit callables fall back to Settings values.

    Spec: REQ-RL-04, REQ-RL-07, REQ-RL-05
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next) -> Response:
        # Attempt to resolve tier; failures are silently swallowed (REQ-RL-05)
        tier = None
        try:
            tier = await self._preload_tier(request)
        except Exception as exc:
            logger.debug("TierPreloadMiddleware: could not preload tier: %s", exc)

        # Store on ContextVar for zero-arg slowapi limit callables
        token = _current_tier.set(tier)
        # Also store on request.state for middleware/endpoint inspection
        if tier is not None:
            request.state.tier = tier

        try:
            return await call_next(request)
        finally:
            _current_tier.reset(token)

    async def _preload_tier(self, request: Request):
        """Decode JWT, look up tier (cache-first). Returns tier or None."""
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return None  # unauthenticated request — no tier to preload

        token = auth_header[len("Bearer "):]
        try:
            settings = get_settings()
            payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        except JWTError:
            return None  # invalid JWT — no tier

        tenant_id = payload.get("tenant_id")
        if not tenant_id:
            return None

        # Cache hit
        if tenant_id in _tier_cache:
            return _tier_cache[tenant_id]

        # Cache miss — load from DB
        tier = await self._load_tier_for_tenant(tenant_id)
        if tier is not None:
            _tier_cache[tenant_id] = tier
        return tier

    @staticmethod
    async def _load_tier_for_tenant(tenant_id: str):
        """Load the tier for a tenant from the DB via the app's session factory.

        Returns None on any error so callers fall back to Settings defaults.
        """
        from sqlalchemy import select
        from app.infrastructure.persistence.database import get_session
        from app.infrastructure.persistence.models.tenant import TenantModel
        from app.infrastructure.persistence.repositories.subscription_tier_repository import (
            SQLAlchemySubscriptionTierRepository,
        )

        try:
            import uuid as _uuid
            tenant_uuid = _uuid.UUID(tenant_id)
        except ValueError:
            return None

        try:
            async for session in get_session():
                stmt = select(TenantModel).where(TenantModel.id == tenant_uuid)
                result = await session.execute(stmt)
                tenant = result.scalar_one_or_none()

                if tenant is None or tenant.tier_id is None:
                    return None

                repo = SQLAlchemySubscriptionTierRepository(session)
                return await repo.get_by_id(tenant.tier_id)
        except Exception as exc:
            logger.debug("TierPreloadMiddleware: DB lookup failed: %s", exc)
            return None
