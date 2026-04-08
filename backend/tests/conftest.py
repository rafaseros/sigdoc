"""Root conftest.py — sets test environment variables BEFORE any app imports.

IMPORTANT: This module must be imported (and os.environ patched) before any
`app.*` module is loaded so that pydantic-settings picks up these values when
`Settings()` is first constructed.  pytest collects conftest.py files before
collecting test modules, so this runs first.
"""
import os

# ---------------------------------------------------------------------------
# Set env vars before any app code is imported
# ---------------------------------------------------------------------------
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/sigdoc_test")
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production")
os.environ.setdefault("MINIO_ENDPOINT", "fake-minio:9000")
os.environ.setdefault("MINIO_EXTERNAL_ENDPOINT", "fake-minio:9000")
os.environ.setdefault("MINIO_ACCESS_KEY", "fakeaccesskey")
os.environ.setdefault("MINIO_SECRET_KEY", "fakesecretkey")
os.environ.setdefault("MINIO_SECURE", "false")
os.environ.setdefault("BULK_GENERATION_LIMIT", "10")
os.environ.setdefault("ADMIN_PASSWORD", "test-admin-password")
os.environ.setdefault("EMAIL_BACKEND", "console")
os.environ.setdefault("FRONTEND_URL", "http://localhost:5173")

import pytest  # noqa: E402 — after os.environ setup


@pytest.fixture(autouse=True)
def clear_settings_cache() -> None:
    """Clear the lru_cache on get_settings() before every test.

    This ensures each test gets a fresh Settings instance that reads the
    current os.environ state, preventing config bleed between tests.
    """
    from app.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
