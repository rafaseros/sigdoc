from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.presentation.api.v1 import auth, templates, documents, health, users


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    yield
    # Shutdown


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Restrict in production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register routers
    app.include_router(health.router, prefix=settings.api_v1_prefix)
    app.include_router(auth.router, prefix=f"{settings.api_v1_prefix}/auth", tags=["auth"])
    app.include_router(templates.router, prefix=f"{settings.api_v1_prefix}/templates", tags=["templates"])
    app.include_router(documents.router, prefix=f"{settings.api_v1_prefix}/documents", tags=["documents"])
    app.include_router(users.router, prefix=f"{settings.api_v1_prefix}/users", tags=["users"])

    return app


app = create_app()
