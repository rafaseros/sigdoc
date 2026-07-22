from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.config import get_settings
from app.domain.exceptions import QuotaExceededError
from app.presentation.api.v1 import auth, templates, documents, health, users, audit, dev, folders
from app.presentation.middleware.body_size_limit import BodySizeLimitMiddleware
from app.presentation.middleware.rate_limit import TierPreloadMiddleware, limiter


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    yield
    # Shutdown


async def _quota_exceeded_handler(request: Request, exc: QuotaExceededError) -> JSONResponse:
    """Map QuotaExceededError to HTTP 429 with structured error body."""
    return JSONResponse(
        status_code=429,
        content={
            "error": "quota_exceeded",
            "detail": str(exc),
            "limit_type": exc.limit_type,
            "limit_value": exc.limit_value,
            "current_usage": exc.current_usage,
            "tier_name": exc.tier_name,
        },
    )


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version="4.0.0",  # Keep in sync with pyproject.toml and frontend/src/shared/version.ts
        lifespan=lifespan,
    )

    # Rate limiting
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)
    # TierPreloadMiddleware added AFTER SlowAPIMiddleware → runs BEFORE it (LIFO ordering)
    # Decodes JWT, resolves tenant's tier from DB (with TTL cache), stores on request.state.tier
    app.add_middleware(TierPreloadMiddleware)

    # Body-size cap: reject oversized uploads (HTTP 413) before the body is read.
    # Added AFTER TierPreloadMiddleware but BEFORE CORSMiddleware so that, with
    # Starlette's LIFO ordering, the execution chain is:
    #   CORS → BodySizeLimit → TierPreload → SlowAPI → route
    # CORS stays OUTERMOST so it answers OPTIONS/preflight itself (which never
    # reach this middleware) and so the 413 response still carries CORS headers;
    # yet BodySizeLimit runs BEFORE the tier DB probe, rate-limit check, and the
    # route's `await file.read()`, rejecting oversized bodies as early as possible.
    app.add_middleware(BodySizeLimitMiddleware, max_upload_bytes=settings.max_upload_bytes)

    # Quota exceeded → HTTP 429
    app.add_exception_handler(QuotaExceededError, _quota_exceeded_handler)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register routers
    app.include_router(health.router, prefix=settings.api_v1_prefix)
    app.include_router(auth.router, prefix=f"{settings.api_v1_prefix}/auth", tags=["auth"])
    app.include_router(templates.router, prefix=f"{settings.api_v1_prefix}/templates", tags=["templates"])
    app.include_router(folders.router, prefix=f"{settings.api_v1_prefix}/folders", tags=["folders"])
    app.include_router(documents.router, prefix=f"{settings.api_v1_prefix}/documents", tags=["documents"])
    app.include_router(users.router, prefix=f"{settings.api_v1_prefix}/users", tags=["users"])
    app.include_router(audit.router, prefix=f"{settings.api_v1_prefix}/audit-log", tags=["audit"])

    if settings.enable_dev_reset:
        app.include_router(dev.router, prefix=f"{settings.api_v1_prefix}/dev", tags=["dev"])

    return app


app = create_app()
