# Technical Design: hardening-and-testing

## Overview

This document defines the technical architecture for hardening the sigdoc backend: test infrastructure, CI pipeline, MinIO async wrapping, configurable bulk limits, rate limiting, and environment documentation. Every decision is grounded in what the codebase actually does today.

---

## ADR-1: Test Database Strategy — PostgreSQL Only, No SQLite

### Context

The proposal left the test database choice open: SQLite async vs PostgreSQL service container. After reviewing all ORM models, the answer is unambiguous.

### Decision

**PostgreSQL only. No SQLite. Not even for local dev.**

### Rationale

The codebase uses PostgreSQL-specific features that SQLite cannot support:

1. **`JSONB` columns** — `DocumentModel.variables_snapshot`, `TemplateVersionModel.variables`, `TemplateVersionModel.variables_meta` all use `sqlalchemy.dialects.postgresql.JSONB`. SQLite has no JSONB type. You would need to either: (a) create a custom type that switches between JSONB and JSON depending on dialect, or (b) maintain separate model definitions. Both are maintenance nightmares for zero benefit.

2. **PostgreSQL-specific indexes** — `DocumentModel.__table_args__` includes `postgresql_using="btree"` and `postgresql_where="batch_id IS NOT NULL"` (partial index). SQLite ignores these silently, meaning your tests would never catch index-related query plan issues.

3. **UUID primary keys** — While SQLAlchemy handles UUID mapping, PostgreSQL has a native `uuid` type. SQLite stores UUIDs as strings. This creates subtle behavior differences in comparisons and ordering.

4. **`TenantMixin` + `do_orm_execute` event** — The tenant filtering relies on SQLAlchemy's `with_loader_criteria` applied at the ORM event level. This is dialect-agnostic in theory, but the query patterns (joins, subqueries) can behave differently across dialects. Testing against a different dialect than production is testing a different system.

**Unit tests do not need ANY database.** They use in-memory fakes. Only integration tests need PostgreSQL, and they get it from a service container in CI and from the existing docker-compose PostgreSQL in local dev.

### Consequences

- `aiosqlite` is NOT added as a dependency
- Local integration tests require a running PostgreSQL (already available via `docker/docker-compose.yml`)
- CI uses a PostgreSQL 16 service container
- Test isolation is achieved via transaction rollback, not separate databases

---

## ADR-2: In-Memory Fakes over unittest.mock for Port Implementations

### Context

The project has 5 abstract ports. Tests need substitutes for these ports. The choice is between `unittest.mock.AsyncMock` and hand-written in-memory fakes.

### Decision

**Hand-written in-memory fakes that implement the abstract port interfaces.**

### Rationale

1. **Contract enforcement** — Fakes implement the same ABC. If a port method signature changes, the fake breaks at import time, not at runtime deep inside a test.

2. **Behavior, not call verification** — `AsyncMock` tests that a method was called with certain arguments. Fakes test that business logic produces correct results. The service tests should assert on outcomes ("document was created with this path"), not on interactions ("storage.upload_file was called once with these args").

3. **Reusability** — The same fakes are used across all unit tests. With mocks, each test recreates its own mock configuration, leading to fragile, repetitive setup.

4. **Readability** — `fake_storage.files[("documents", path)]` is immediately understandable. `mock_storage.upload_file.assert_called_once_with(bucket="documents", ...)` is test machinery, not domain language.

5. **No external dependency** — No `pytest-mock` needed. The fakes are plain Python classes.

### Where mocks ARE appropriate

- **`get_settings()` override** — Use `@pytest.fixture` + `monkeypatch` to override `app.config.get_settings` for tests that need specific config values. This is simpler than creating a fake Settings class.
- **JWT time manipulation** — Use `freezegun` or `time_machine` to test token expiry, OR use `monkeypatch` on `datetime.now` in the jwt_handler module.

### Consequences

- Fakes live in `backend/tests/fakes/` (one file per port)
- `backend/tests/fakes/__init__.py` re-exports all fakes for easy import
- Fakes are tested implicitly through service tests (if a fake is wrong, service tests fail)

---

## ADR-3: Integration Test Strategy — Override App Dependencies via `app.dependency_overrides`

### Context

Integration tests need a real HTTP request cycle (FastAPI app + httpx.AsyncClient) but with a test database and fake storage/engine.

### Decision

**Use `app.dependency_overrides` to replace the DI functions, combined with a test PostgreSQL database.**

### Rationale

FastAPI's `dependency_overrides` is the idiomatic way to swap dependencies in tests. The current app uses `Depends(get_tenant_session)` and `Depends(get_document_service)` etc. We override these at the app level.

### Design

```
Integration test setup:
1. create_app() returns the FastAPI app
2. Override get_session → yields a test session (from test engine, with rollback)
3. Override get_tenant_session → yields a test session with tenant_id set
4. Override get_storage_service → returns FakeStorageService
5. Override get_template_engine → returns FakeTemplateEngine
6. Override get_template_service → returns TemplateService with real repo + fake storage + fake engine
7. Override get_document_service → returns DocumentService with real repo + fake storage + fake engine
8. httpx.AsyncClient(transport=ASGITransport(app=app))
```

This means:
- **Repositories use real SQLAlchemy** against test PostgreSQL (validates SQL, ORM mappings, tenant filtering)
- **Storage and engine use fakes** (no MinIO needed in tests)
- **Services are real** but wired to test repos + fake infra

### Consequences

- Integration tests validate the full request-response cycle including middleware, serialization, and error handling
- They do NOT test MinIO or docxtpl (those are infrastructure concerns tested in isolation or not at all)
- Each test runs in a transaction that is rolled back after the test (fast, isolated)

---

## ADR-4: Rate Limiting — slowapi with In-Memory Backend

### Context

Auth and generation endpoints need rate limiting for brute-force and abuse protection.

### Decision

**`slowapi` with the default in-memory backend, keyed by client IP.**

### Rationale

1. `slowapi` wraps the `limits` library and integrates natively with Starlette/FastAPI
2. The default in-memory storage is per-process — acceptable for single-worker deployment (current setup: single uvicorn process behind docker)
3. No Redis dependency needed for MVP
4. The rate limiter is attached to the app state and registered as middleware for 429 error handling

### Future consideration

When scaling to multiple workers, switch to Redis backend:
```python
from slowapi import Limiter
from slowapi.util import get_remote_address
limiter = Limiter(key_func=get_remote_address, storage_uri="redis://...")
```

This is a one-line change. The decorator-based limits on endpoints don't change.

### Consequences

- `slowapi>=0.1.9` added to production dependencies
- Limiter instance created in a new `app/presentation/middleware/rate_limit.py`
- Registered in `create_app()` via `app.state.limiter` + `SlowAPIMiddleware`
- Per-endpoint decorators on target routes

---

## 1. Test Architecture

### 1.1 Directory Structure

```
backend/
  tests/
    __init__.py
    conftest.py                    # Root conftest: settings override, event loop
    fakes/
      __init__.py                  # Re-exports all fakes
      fake_storage_service.py      # FakeStorageService
      fake_template_engine.py      # FakeTemplateEngine
      fake_template_repository.py  # FakeTemplateRepository
      fake_document_repository.py  # FakeDocumentRepository
      fake_user_repository.py      # FakeUserRepository
    unit/
      __init__.py
      conftest.py                  # Unit-specific fixtures (fake instances)
      test_exceptions.py
      test_jwt_handler.py
      test_document_service.py
      test_template_service.py
      test_middleware.py
    integration/
      __init__.py
      conftest.py                  # DB engine, test session, app overrides, test client
      test_auth_api.py
      test_templates_api.py
      test_documents_api.py
      test_health_api.py
```

### 1.2 Root conftest.py — Settings Override

```python
import os
import pytest

# Set test environment BEFORE any app imports
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://sigdoc_test:sigdoc_test@localhost:5432/sigdoc_test")
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production")
os.environ.setdefault("MINIO_ACCESS_KEY", "test-access-key")
os.environ.setdefault("MINIO_SECRET_KEY", "test-secret-key")

@pytest.fixture(autouse=True)
def _clear_settings_cache():
    """Clear lru_cache on get_settings between tests."""
    from app.config import get_settings
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
```

**Why `os.environ` instead of `.env.test`?** The `Settings` class uses `pydantic_settings` which reads from `.env` automatically. In tests, we need to override BEFORE the settings singleton is created. Setting env vars at the top of conftest.py (which is loaded before tests) ensures this. The `cache_clear` fixture ensures each test gets fresh settings.

### 1.3 Fake Implementations

Each fake implements the corresponding ABC from `app.domain.ports`. Key design principles:

- **State is a simple dict/list** — no SQLAlchemy, no async session
- **All methods are `async def`** — matches the port interface
- **Fakes raise the same domain exceptions** as real implementations would (e.g., not found returns `None`, let the service raise)
- **Fakes are stateful within a test** — each test gets a fresh instance via fixture

#### FakeStorageService

```python
from app.domain.ports.storage_service import StorageService

class FakeStorageService(StorageService):
    def __init__(self):
        self.files: dict[tuple[str, str], bytes] = {}  # (bucket, path) -> bytes

    async def upload_file(self, bucket: str, path: str, data: bytes, content_type: str) -> str:
        self.files[(bucket, path)] = data
        return path

    async def download_file(self, bucket: str, path: str) -> bytes:
        if (bucket, path) not in self.files:
            raise Exception(f"File not found: {bucket}/{path}")
        return self.files[(bucket, path)]

    async def get_presigned_url(self, bucket: str, path: str, expires_hours: int = 1) -> str:
        return f"https://fake-storage/{bucket}/{path}?expires={expires_hours}h"

    async def delete_file(self, bucket: str, path: str) -> None:
        self.files.pop((bucket, path), None)
```

#### FakeTemplateEngine

```python
from app.domain.ports.template_engine import TemplateEngine

class FakeTemplateEngine(TemplateEngine):
    def __init__(self):
        self.variables_to_return: list[dict] = [
            {"name": "nombre", "contexts": ["Estimado {{ nombre }}"]},
            {"name": "empresa", "contexts": ["Empresa: {{ empresa }}"]},
        ]
        self.render_result: bytes = b"rendered-document-bytes"
        self.should_fail: bool = False

    async def extract_variables(self, file_bytes: bytes) -> list[dict]:
        if self.should_fail:
            raise ValueError("Invalid template")
        return self.variables_to_return

    async def render(self, file_bytes: bytes, variables: dict[str, str]) -> bytes:
        if self.should_fail:
            raise ValueError("Render failed")
        return self.render_result

    async def validate(self, file_bytes: bytes) -> dict:
        if self.should_fail:
            return {"valid": False, "errors": [{"type": "syntax", "message": "Bad template"}], "fixable": []}
        return {"valid": True, "errors": [], "fixable": []}

    async def auto_fix(self, file_bytes: bytes) -> bytes:
        return file_bytes
```

#### FakeTemplateRepository

```python
from uuid import UUID
from app.domain.ports.template_repository import TemplateRepository

class FakeTemplateRepository(TemplateRepository):
    def __init__(self):
        self.templates: dict[UUID, object] = {}
        self.versions: dict[UUID, object] = {}

    async def create(self, template):
        self.templates[template.id] = template
        return template

    async def get_by_id(self, template_id: UUID):
        return self.templates.get(template_id)

    async def list_paginated(self, page=1, size=20, search=None, created_by=None):
        items = list(self.templates.values())
        if search:
            items = [t for t in items if search.lower() in t.name.lower()]
        if created_by:
            items = [t for t in items if t.created_by == created_by]
        total = len(items)
        start = (page - 1) * size
        return items[start:start + size], total

    async def delete(self, template_id: UUID):
        self.templates.pop(template_id, None)

    async def create_version(self, version):
        self.versions[version.id] = version
        return version

    async def get_version(self, template_id: UUID, version: int):
        for v in self.versions.values():
            if v.template_id == template_id and v.version == version:
                return v
        return None

    async def get_version_by_id(self, version_id: UUID):
        return self.versions.get(version_id)

    async def create_template_with_version(self, *, template_id, version_id, name,
                                            description, tenant_id, created_by,
                                            version, minio_path, variables,
                                            variables_meta=None, file_size):
        from dataclasses import dataclass, field
        # Use domain entities for consistency
        from app.domain.entities import Template, TemplateVersion
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        tv = TemplateVersion(
            id=version_id, tenant_id=tenant_id, template_id=template_id,
            version=version, minio_path=minio_path, variables=variables,
            file_size=file_size, created_at=now,
        )
        self.versions[version_id] = tv

        tpl = Template(
            id=template_id, tenant_id=tenant_id, name=name,
            description=description, created_by=created_by,
            current_version=version, versions=[tv],
            created_at=now, updated_at=now,
        )
        self.templates[template_id] = tpl
        return tpl
```

#### FakeDocumentRepository and FakeUserRepository

Follow the same pattern: dict-backed storage, async methods matching the ABC, returns `None` for not-found.

### 1.4 Unit Test Fixtures (tests/unit/conftest.py)

```python
import pytest
from tests.fakes import (
    FakeStorageService,
    FakeTemplateEngine,
    FakeTemplateRepository,
    FakeDocumentRepository,
    FakeUserRepository,
)

@pytest.fixture
def fake_storage():
    return FakeStorageService()

@pytest.fixture
def fake_engine():
    return FakeTemplateEngine()

@pytest.fixture
def fake_template_repo():
    return FakeTemplateRepository()

@pytest.fixture
def fake_document_repo():
    return FakeDocumentRepository()

@pytest.fixture
def fake_user_repo():
    return FakeUserRepository()
```

### 1.5 Integration Test Fixtures (tests/integration/conftest.py)

```python
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings
from app.infrastructure.persistence.models.base import Base
from app.main import create_app
from tests.fakes import FakeStorageService, FakeTemplateEngine


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="session")
async def test_engine():
    """Create a test database engine. Tables are created once per session."""
    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def test_session(test_engine):
    """
    Each test gets a session wrapped in a transaction that is rolled back.
    This provides test isolation without truncating tables.
    """
    async with test_engine.connect() as conn:
        transaction = await conn.begin()
        session_factory = async_sessionmaker(bind=conn, expire_on_commit=False)
        async with session_factory() as session:
            yield session
        await transaction.rollback()


@pytest.fixture
def fake_storage():
    return FakeStorageService()


@pytest.fixture
def fake_engine():
    return FakeTemplateEngine()


@pytest.fixture
async def client(test_session, fake_storage, fake_engine):
    """
    AsyncClient wired to the FastAPI app with overridden dependencies.
    """
    from app.infrastructure.persistence.database import get_session
    from app.presentation.middleware.tenant import get_tenant_session
    from app.infrastructure.storage import get_storage_service
    from app.infrastructure.templating import get_template_engine

    app = create_app()

    async def override_get_session():
        yield test_session

    async def override_get_tenant_session():
        # Set a default test tenant_id
        test_session.info["tenant_id"] = TEST_TENANT_ID
        yield test_session

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_tenant_session] = override_get_tenant_session
    app.dependency_overrides[get_storage_service] = lambda: fake_storage
    app.dependency_overrides[get_template_engine] = lambda: fake_engine

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
```

### 1.6 Transaction Rollback Isolation Pattern

```
Test start
  └── BEGIN (savepoint)
        └── test runs (INSERT, UPDATE, SELECT against real PostgreSQL)
        └── assertions
  └── ROLLBACK (savepoint)
Test end — database is clean
```

**Why savepoints, not TRUNCATE?**
- TRUNCATE requires knowing all tables and runs DDL (slow, can conflict with FK constraints)
- Savepoint rollback is instant and guaranteed clean
- No risk of forgetting a table

The `test_engine` fixture creates tables once per test session. The `test_session` fixture wraps each test in a nested transaction (savepoint) that rolls back.

---

## 2. CI Pipeline Design

### 2.1 Workflow Structure

```yaml
# .github/workflows/deploy.yml
name: Test & Deploy

on:
  push:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_USER: sigdoc_test
          POSTGRES_PASSWORD: sigdoc_test
          POSTGRES_DB: sigdoc_test
        ports:
          - 5432:5432
        options: >-
          --health-cmd="pg_isready -U sigdoc_test"
          --health-interval=10s
          --health-timeout=5s
          --health-retries=5

    env:
      DATABASE_URL: postgresql+asyncpg://sigdoc_test:sigdoc_test@localhost:5432/sigdoc_test
      SECRET_KEY: ci-test-secret-key
      MINIO_ACCESS_KEY: ci-test-access
      MINIO_SECRET_KEY: ci-test-secret

    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: pip

      - name: Install dependencies
        working-directory: backend
        run: pip install -e ".[dev]"

      - name: Run tests
        working-directory: backend
        run: pytest --tb=short -q

  deploy:
    needs: [test]
    if: success()
    runs-on: ubuntu-latest
    permissions:
      contents: read
    steps:
      - name: Deploy to VPS
        uses: appleboy/ssh-action@v1
        with:
          host: ${{ secrets.VPS_HOST }}
          username: ${{ secrets.VPS_USER }}
          key: ${{ secrets.VPS_SSH_KEY }}
          script: |
            cd /opt/docker/apps/sigdoc
            git pull origin main
            docker compose -f docker-compose.prod.yml up --build -d
            docker compose -f docker-compose.prod.yml exec -T api alembic upgrade head
            docker image prune -f
```

### 2.2 Key Decisions

| Decision | Rationale |
|----------|-----------|
| PostgreSQL service container, NOT SQLite | JSONB columns, partial indexes, UUID native type (see ADR-1) |
| No MinIO service container | All storage operations are tested through FakeStorageService. Real MinIO integration is manual/smoke only. |
| `pip install -e ".[dev]"` | Installs the package in editable mode with dev deps. The `[dev]` group already includes pytest, pytest-asyncio, httpx. |
| `pip cache` via `actions/setup-python` | Speeds up repeated runs by caching pip downloads |
| `deploy.needs: [test]` | Deploy is blocked until tests pass. `if: success()` is redundant (default behavior) but makes intent explicit. |
| Single workflow file | Lower maintenance than separate test.yml + deploy.yml. The `needs` dependency is clean and visible. |

### 2.3 What is NOT in CI

- No coverage reporting (add later with `pytest-cov` when baseline is established)
- No linting (can be added as a parallel job later)
- No MinIO container (fakes are sufficient)
- No frontend tests (separate concern, separate workflow later)

---

## 3. MinIO Async Wrapping

### 3.1 Current Problem

`MinioStorageService` has 4 `async def` methods that call synchronous `minio-py` methods directly. This blocks the asyncio event loop for the duration of each I/O operation (network round-trip to MinIO).

### 3.2 Solution: `asyncio.to_thread()`

Wrap each synchronous call in `asyncio.to_thread()`. This runs the blocking call in the default thread pool executor, freeing the event loop.

### 3.3 Detailed Changes to `minio_storage.py`

```python
import asyncio
import io
from datetime import timedelta

from minio import Minio

from app.config import get_settings
from app.domain.ports.storage_service import StorageService


class MinioStorageService(StorageService):
    def __init__(self) -> None:
        settings = get_settings()
        self._client = Minio(
            endpoint=settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )
        self._internal_endpoint = settings.minio_endpoint
        self._external_endpoint = settings.minio_external_endpoint

    async def upload_file(
        self, bucket: str, path: str, data: bytes, content_type: str
    ) -> str:
        await asyncio.to_thread(
            self._client.put_object,
            bucket_name=bucket,
            object_name=path,
            data=io.BytesIO(data),
            length=len(data),
            content_type=content_type,
        )
        return path

    async def download_file(self, bucket: str, path: str) -> bytes:
        def _download():
            response = self._client.get_object(bucket_name=bucket, object_name=path)
            try:
                return response.read()
            finally:
                response.close()
                response.release_conn()

        return await asyncio.to_thread(_download)

    async def get_presigned_url(
        self, bucket: str, path: str, expires_hours: int = 1
    ) -> str:
        return await asyncio.to_thread(
            self._client.presigned_get_object,
            bucket_name=bucket,
            object_name=path,
            expires=timedelta(hours=expires_hours),
        )

    async def delete_file(self, bucket: str, path: str) -> None:
        await asyncio.to_thread(
            self._client.remove_object,
            bucket_name=bucket,
            object_name=path,
        )
```

### 3.4 Why `download_file` Uses a Closure

The `get_object` response must be read AND released in the same thread context. If we did `response = await asyncio.to_thread(self._client.get_object, ...)` and then `data = response.read()`, the `read()` would run in the main thread (blocking the event loop). The closure ensures the entire read-close-release cycle happens in the thread pool.

### 3.5 Port Interface — No Changes

The `StorageService` ABC already defines `async def` methods. The port interface does not change. This is purely an infrastructure implementation detail, which is exactly how Clean Architecture should work.

### 3.6 Thread Pool Sizing

The default `asyncio` thread pool has `min(32, os.cpu_count() + 4)` threads. For a single-worker uvicorn handling typical sigdoc load (document generation, not high-frequency trading), this is more than sufficient. If needed later, configure a dedicated executor:

```python
import asyncio
from concurrent.futures import ThreadPoolExecutor
executor = ThreadPoolExecutor(max_workers=8, thread_name_prefix="minio")
loop = asyncio.get_event_loop()
loop.set_default_executor(executor)
```

This is NOT needed for MVP and should not be done preemptively.

---

## 4. Bulk Limit Configuration

### 4.1 Current State

- `Settings.bulk_generation_limit = 10` exists in `config.py` but is never read
- `DocumentService.parse_excel_data` hardcodes `if len(rows) > 10`
- `BulkLimitExceededError.__init__` hardcodes `limit: int = 10`

### 4.2 Changes

#### DocumentService Constructor

```python
class DocumentService:
    TEMPLATES_BUCKET = "templates"
    DOCUMENTS_BUCKET = "documents"

    def __init__(
        self,
        document_repository: DocumentRepository,
        template_repository: TemplateRepository,
        storage: StorageService,
        engine: TemplateEngine,
        bulk_generation_limit: int = 10,  # NEW
    ):
        self._doc_repo = document_repository
        self._tpl_repo = template_repository
        self._storage = storage
        self._engine = engine
        self._bulk_limit = bulk_generation_limit  # NEW
```

#### parse_excel_data

```python
if len(rows) > self._bulk_limit:
    raise BulkLimitExceededError(limit=self._bulk_limit)
```

#### Service Factory (application/services/__init__.py)

```python
from app.config import get_settings

async def get_document_service(
    session: AsyncSession = Depends(get_tenant_session),
) -> DocumentService:
    settings = get_settings()
    return DocumentService(
        document_repository=SQLAlchemyDocumentRepository(session),
        template_repository=SQLAlchemyTemplateRepository(session),
        storage=get_storage_service(),
        engine=get_template_engine(),
        bulk_generation_limit=settings.bulk_generation_limit,  # NEW
    )
```

#### BulkLimitExceededError — No Change Needed

The `limit` parameter is already dynamic: `def __init__(self, limit: int = 10)`. The default `10` is only a fallback. Since the caller now always passes `self._bulk_limit`, the default is irrelevant but harmless.

---

## 5. Rate Limiting Architecture

### 5.1 New File: `app/presentation/middleware/rate_limit.py`

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
```

This module is the single source of truth for the rate limiter instance. Routers import `limiter` from here.

### 5.2 Registration in `create_app()`

```python
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from app.presentation.middleware.rate_limit import limiter

def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, lifespan=lifespan)

    # Rate limiting
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # CORS (existing)
    app.add_middleware(CORSMiddleware, ...)

    # Routers (existing)
    ...

    return app
```

### 5.3 Endpoint Decorators

```python
# auth.py
from app.presentation.middleware.rate_limit import limiter

@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/minute")
async def login(request: Request, login_data: LoginRequest, ...):
    ...

@router.post("/refresh", response_model=TokenResponse)
@limiter.limit("10/minute")
async def refresh_token(request: Request, refresh_data: RefreshRequest):
    ...
```

```python
# documents.py
from app.presentation.middleware.rate_limit import limiter

@router.post("/generate", ...)
@limiter.limit("20/minute")
async def generate_document(request: Request, ...):
    ...

@router.post("/generate-bulk", ...)
@limiter.limit("5/minute")
async def generate_bulk(request: Request, ...):
    ...
```

### 5.4 Important: `Request` Parameter

`slowapi` requires the first parameter of the endpoint function to be a `Request` object (or the function must accept `request: Request`). The existing endpoints don't have this. Each rate-limited endpoint must add `request: Request` as the first parameter.

### 5.5 Rate Limits Summary

| Endpoint | Limit | Key |
|----------|-------|-----|
| `POST /api/v1/auth/login` | 5/minute | Client IP |
| `POST /api/v1/auth/refresh` | 10/minute | Client IP |
| `POST /api/v1/documents/generate` | 20/minute | Client IP |
| `POST /api/v1/documents/generate-bulk` | 5/minute | Client IP |

### 5.6 Testing Rate Limits

Rate limiting is NOT tested in unit tests (it is middleware/infrastructure). In integration tests, we can optionally test that the 429 response is returned by hitting an endpoint more than the limit. However, this is low priority — the `slowapi` library itself is well-tested. If we do test it, we test ONE endpoint to verify wiring:

```python
async def test_login_rate_limit(client):
    """Verify rate limiting returns 429 after exceeding limit."""
    for _ in range(5):
        await client.post("/api/v1/auth/login", json={"email": "a@b.com", "password": "wrong"})
    response = await client.post("/api/v1/auth/login", json={"email": "a@b.com", "password": "wrong"})
    assert response.status_code == 429
```

---

## 6. Test Coverage Strategy

### 6.1 What to Test

| Layer | What | How |
|-------|------|-----|
| **Domain exceptions** | All 6 exceptions instantiate correctly, messages are correct, `BulkLimitExceededError.limit` attribute works | Unit test, no deps |
| **JWT handler** | `hash_password` + `verify_password` round-trip, `create_access_token` produces decodable JWT with correct claims, `create_refresh_token` has type=refresh, `decode_token` rejects expired/tampered/wrong-algo tokens | Unit test, needs `monkeypatch` for settings |
| **DocumentService** | `generate_single` happy path + version-not-found, `parse_excel_data` limit enforcement + variable mismatch + empty rows, `generate_bulk` happy path + partial failures, `get_document` + `delete_document` + `list_documents` | Unit test with fakes |
| **TemplateService** | `upload_template` happy path + invalid template, `upload_new_version` happy path + not found, `get_template` + `list_templates` + `delete_template` | Unit test with fakes |
| **Middleware** | `get_current_user` with valid token, expired token, tampered token, token with wrong type (refresh instead of access), missing claims | Unit test, needs `monkeypatch` for settings |
| **Auth API** | Login success + wrong password + nonexistent user, refresh success + invalid token, /me with valid auth, change-password success + wrong current password | Integration test |
| **Templates API** | Upload + list + get + delete + version upload, error cases (invalid file, duplicate name, not found) | Integration test |
| **Documents API** | Generate single + list + get + delete + download, bulk generate + bulk download, error cases | Integration test |
| **Health API** | GET /health returns 200 | Integration test (trivial) |

### 6.2 What NOT to Test

| Skip | Reason |
|------|--------|
| `MinioStorageService` | Infrastructure adapter. The `asyncio.to_thread` wrapping is mechanical. Testing it requires a running MinIO instance — not worth the CI complexity. The port interface is tested through fakes. |
| `DocxTemplateEngine` | Infrastructure adapter. Requires real .docx files. The `docxtpl` library is the SUT, not our code. If we wanted to test this, we would need fixture .docx files — defer to a separate "engine smoke test" later. |
| SQLAlchemy repository implementations (directly) | Tested indirectly through integration tests. The integration tests use real repos against test PostgreSQL. Direct repo tests would duplicate the integration tests without adding value. |
| Alembic migrations | Out of scope. Migration correctness is validated by `create_all` in tests (schema must be valid) and by `alembic upgrade head` in deploy. |
| Pydantic schemas | Validated by FastAPI automatically. If a schema is wrong, integration tests will catch serialization errors. |
| `slowapi` library behavior | Third-party, well-tested. We test wiring (one 429 test), not the library itself. |

### 6.3 Coverage Target

**No enforced minimum percentage.** Rationale:

Coverage percentages are vanity metrics when applied to a project starting from zero. The goal is meaningful coverage of business logic (services, domain, auth), not hitting an arbitrary number. A 90% coverage target would incentivize testing trivial getters and `__init__` methods while missing edge cases in `parse_excel_data`.

After the initial test suite is written, measure actual coverage with `pytest-cov` to establish a baseline. Then set a minimum that is 5% below the baseline as a ratchet (prevents regression without forcing busywork).

---

## 7. .env.example

### 7.1 Content

```env
# ─── App ───────────────────────────────────────────
APP_NAME=SigDoc
DEBUG=false
API_V1_PREFIX=/api/v1
CORS_ORIGINS=["http://localhost:5173"]
BULK_GENERATION_LIMIT=10

# ─── Database ──────────────────────────────────────
DATABASE_URL=postgresql+asyncpg://sigdoc:sigdoc@db:5432/sigdoc

# ─── Auth ──────────────────────────────────────────
SECRET_KEY=change-me-to-a-random-string
ADMIN_EMAIL=admin@sigdoc.local
ADMIN_PASSWORD=change-me
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# ─── MinIO ─────────────────────────────────────────
MINIO_ENDPOINT=minio:9000
MINIO_EXTERNAL_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=change-me
MINIO_SECRET_KEY=change-me
MINIO_SECURE=false
```

---

## 8. Dependency Changes

### 8.1 pyproject.toml

```toml
[project]
dependencies = [
    # ... existing ...
    "slowapi>=0.1.9",          # NEW: rate limiting
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",           # existing
    "pytest-asyncio>=0.24.0",  # existing
    "httpx>=0.27.0",           # existing
]
```

No new dev dependencies. `pytest`, `pytest-asyncio`, and `httpx` are already present. `aiosqlite` is NOT needed (ADR-1).

---

## 9. Sequence Diagrams

### 9.1 Unit Test Execution Flow

```
pytest discovers test_document_service.py
  │
  ├── conftest.py (root): set env vars, clear settings cache
  ├── conftest.py (unit): create FakeStorageService, FakeTemplateEngine, etc.
  │
  └── test_generate_single_happy_path(fake_storage, fake_engine, fake_template_repo, fake_document_repo)
        │
        ├── Arrange: seed fake_template_repo with a TemplateVersion
        ├── Arrange: seed fake_storage with template bytes
        ├── Act: DocumentService(...fakes...).generate_single(...)
        │     ├── calls fake_template_repo.get_version_by_id() → returns seeded version
        │     ├── calls fake_storage.download_file() → returns seeded bytes
        │     ├── calls fake_engine.render() → returns fake rendered bytes
        │     ├── calls fake_storage.upload_file() → stores in memory dict
        │     ├── calls fake_document_repo.create() → stores in memory dict
        │     └── calls fake_storage.get_presigned_url() → returns fake URL
        └── Assert: result contains document with correct attributes
```

### 9.2 Integration Test Execution Flow

```
pytest discovers test_auth_api.py
  │
  ├── conftest.py (root): set env vars, clear settings cache
  ├── conftest.py (integration): create test_engine, test_session (with savepoint), app with overrides, AsyncClient
  │
  └── test_login_success(client, test_session)
        │
        ├── Arrange: INSERT a tenant + user into test PostgreSQL via test_session
        ├── Act: client.post("/api/v1/auth/login", json={...})
        │     ├── FastAPI routes to auth.login()
        │     ├── get_session dependency → yields test_session (overridden)
        │     ├── SQLAlchemyUserRepository(test_session).get_by_email() → real SQL against test PG
        │     ├── verify_password() → bcrypt comparison
        │     ├── create_access_token() + create_refresh_token()
        │     └── returns TokenResponse
        ├── Assert: response.status_code == 200
        ├── Assert: response body has access_token and refresh_token
        ├── Assert: decoded access_token has correct sub, tenant_id, role
        │
        └── test ends → savepoint ROLLBACK → tenant + user removed
```

### 9.3 CI Pipeline Flow

```
push to main
  │
  └── GitHub Actions triggers deploy.yml
        │
        ├── Job: test
        │     ├── Start PostgreSQL 16 service container
        │     ├── Checkout code
        │     ├── Setup Python 3.12 (cached pip)
        │     ├── pip install -e ".[dev]" (in backend/)
        │     ├── pytest --tb=short -q (in backend/)
        │     │     ├── Unit tests: all pass (no infra needed)
        │     │     └── Integration tests: use PG service container
        │     └── Exit 0 (success) or Exit 1 (failure)
        │
        └── Job: deploy (needs: test, if: success)
              ├── SSH into VPS
              ├── git pull origin main
              ├── docker compose up --build -d
              ├── alembic upgrade head
              └── docker image prune -f
```

---

## 10. Risk Mitigations

| Risk | Mitigation |
|------|------------|
| `DocumentService.generate_single` imports `DocumentModel` from infrastructure layer (leaky abstraction) | Out of scope for this change, but noted. The service should create domain `Document` entities, not ORM models. The fakes will need to accept whatever the service passes — initially, they will work with domain entities while the service still uses ORM models. This discrepancy is tracked but not fixed here. |
| `get_settings()` uses `lru_cache` — tests could leak config between test cases | Root conftest fixture calls `get_settings.cache_clear()` before and after each test |
| Rate limiter state persists between integration tests | Each integration test gets a fresh app instance (the `client` fixture creates a new app). State does not leak. |
| `TenantMixin` `do_orm_execute` event is registered at module import — could affect test sessions | The event checks `session.info.get("tenant_id")`. In tests where tenant_id is not set, the filter is not applied. In integration tests, the fixture explicitly sets tenant_id on the session. |
| `DocumentService` and `TemplateService` import ORM models inside methods (lazy imports) | The fakes for repos accept and return domain entities. In unit tests, the services will fail if they try to instantiate ORM models. **Mitigation**: Unit tests for `generate_single` and `generate_bulk` will need to monkeypatch the ORM model import, OR the service must be refactored to use domain entities. Recommended: refactor the service to create domain `Document` dataclasses in `generate_single`/`generate_bulk`, then have the repository's `create()` accept domain entities and map to ORM models internally. This is the correct Clean Architecture pattern and should be done as part of the apply phase. |

---

## 11. Implementation Priority

The implementation order follows the dependency graph:

```
1. Test infrastructure (conftest, fakes)           ← everything depends on this
   │
   ├── 2a. Unit tests (domain, jwt, services, middleware)
   │
   ├── 2b. MinIO async wrapping                     ← independent, can parallel
   │
   ├── 2c. Bulk limit from settings                  ← independent, can parallel
   │
   └── 2d. .env.example                              ← independent, can parallel
       │
       3. Integration tests (auth, templates, documents, health)
       │
       4. Rate limiting (slowapi)
       │
       5. CI pipeline (test job + deploy gate)        ← must be last (needs all tests passing)
```

Steps 2a-2d can be done in parallel. Step 3 depends on step 1 (conftest). Step 5 depends on everything else passing.

---

## 12. Files Modified / Created Summary

### New Files

| File | Purpose |
|------|---------|
| `backend/tests/__init__.py` | Package marker |
| `backend/tests/conftest.py` | Root conftest (env vars, settings cache clear) |
| `backend/tests/fakes/__init__.py` | Re-exports all fakes |
| `backend/tests/fakes/fake_storage_service.py` | In-memory StorageService |
| `backend/tests/fakes/fake_template_engine.py` | Predictable TemplateEngine |
| `backend/tests/fakes/fake_template_repository.py` | Dict-backed TemplateRepository |
| `backend/tests/fakes/fake_document_repository.py` | Dict-backed DocumentRepository |
| `backend/tests/fakes/fake_user_repository.py` | Dict-backed UserRepository |
| `backend/tests/unit/__init__.py` | Package marker |
| `backend/tests/unit/conftest.py` | Unit fixtures (fake instances) |
| `backend/tests/unit/test_exceptions.py` | Domain exception tests |
| `backend/tests/unit/test_jwt_handler.py` | JWT function tests |
| `backend/tests/unit/test_document_service.py` | DocumentService tests |
| `backend/tests/unit/test_template_service.py` | TemplateService tests |
| `backend/tests/unit/test_middleware.py` | get_current_user tests |
| `backend/tests/integration/__init__.py` | Package marker |
| `backend/tests/integration/conftest.py` | DB fixtures, app overrides, test client |
| `backend/tests/integration/test_auth_api.py` | Auth endpoint tests |
| `backend/tests/integration/test_templates_api.py` | Template endpoint tests |
| `backend/tests/integration/test_documents_api.py` | Document endpoint tests |
| `backend/tests/integration/test_health_api.py` | Health endpoint test |
| `backend/.env.example` | Environment variable documentation |
| `backend/src/app/presentation/middleware/rate_limit.py` | slowapi limiter instance |

### Modified Files

| File | Change |
|------|--------|
| `backend/pyproject.toml` | Add `slowapi>=0.1.9` to dependencies, add `[tool.pytest.ini_options]` |
| `backend/src/app/infrastructure/storage/minio_storage.py` | Wrap all 4 methods with `asyncio.to_thread()` |
| `backend/src/app/application/services/document_service.py` | Add `bulk_generation_limit` param to `__init__`, use `self._bulk_limit` in `parse_excel_data` |
| `backend/src/app/application/services/__init__.py` | Pass `settings.bulk_generation_limit` to `DocumentService` |
| `backend/src/app/main.py` | Register slowapi limiter + exception handler |
| `backend/src/app/presentation/api/v1/auth.py` | Add `@limiter.limit()` decorators, add `request: Request` param |
| `backend/src/app/presentation/api/v1/documents.py` | Add `@limiter.limit()` decorators, add `request: Request` param |
| `.github/workflows/deploy.yml` | Add `test` job with PostgreSQL service, add `needs: [test]` to deploy |
