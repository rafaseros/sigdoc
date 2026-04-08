# Proposal: hardening-and-testing

## Intent

Harden the sigdoc backend for production readiness by introducing a comprehensive test suite, making security and operational parameters configurable, wrapping blocking I/O properly, adding rate limiting on sensitive endpoints, and gating deployments behind passing tests.

**Priority order**: Tests (foundation) > CI gate > MinIO async > Bulk limit config > CORS config completion > Rate limiting.

## Problem Statement

sigdoc is a document template management and generation system currently deployed to production via GitHub Actions on push to `main` with ZERO tests and NO quality gate. Several hardcoded values and blocking I/O patterns exist that would cause issues under real concurrency. Specifically:

1. **No tests**: Zero test files exist. Any regression ships directly to production.
2. **No CI gate**: The deploy workflow runs on every push to `main` without any quality check.
3. **Blocking MinIO calls**: `MinioStorageService` uses synchronous `minio-py` inside `async def` methods, blocking the event loop on every file upload/download/delete/presign operation.
4. **Hardcoded bulk limit**: `DocumentService.parse_excel_data()` and `BulkLimitExceededError` both hardcode `10` despite `Settings.bulk_generation_limit` existing in config.
5. **CORS partially configured**: `config.py` has `cors_origins` and `main.py` reads it, but no `.env.example` documents this setting.
6. **No rate limiting**: Auth endpoints (`/login`, `/refresh`) and generation endpoints have no protection against brute-force or abuse.

## Scope

### In Scope

| Area | What changes |
|------|-------------|
| **Test infrastructure** | `conftest.py` with async fixtures, in-memory fakes for all ports, test database setup with SQLite (async) or test PostgreSQL, `pytest.ini`/`pyproject.toml` config |
| **Unit tests — Domain** | Test `BulkLimitExceededError`, `VariablesMismatchError`, all domain exceptions |
| **Unit tests — Auth** | Test `hash_password`, `verify_password`, `create_access_token`, `create_refresh_token`, `decode_token` (valid, expired, tampered, wrong type) |
| **Unit tests — Services** | `DocumentService` (generate_single, parse_excel_data, generate_bulk, get/list/delete), `TemplateService` (upload, upload_new_version, get, list, delete) — all using in-memory fakes for ports |
| **Unit tests — Middleware** | `get_current_user` with valid/invalid/expired/wrong-type tokens |
| **API integration tests** | Full request cycle for auth (`/login`, `/refresh`, `/me`, `/change-password`), templates (CRUD + version upload), documents (generate, bulk, download, list, delete), health check — using `httpx.AsyncClient` + `app` |
| **MinIO async wrapping** | Wrap all 4 methods in `MinioStorageService` with `asyncio.to_thread()` |
| **Bulk limit from settings** | Inject `bulk_generation_limit` from `Settings` into `DocumentService`; update `BulkLimitExceededError` default; update `parse_excel_data` to use injected value |
| **CORS .env.example** | Create `.env.example` documenting `CORS_ORIGINS` and `BULK_GENERATION_LIMIT` alongside existing env vars |
| **Rate limiting** | Add `slowapi` dependency; configure rate limiter in `main.py`; apply limits to `/auth/login` (5/min), `/auth/refresh` (10/min), `/documents/generate` (20/min), `/documents/generate-bulk` (5/min) |
| **CI test gate** | Add `test` job to `.github/workflows/deploy.yml` that runs `pytest` before `deploy`; `deploy` job gets `needs: [test]` |

### Out of Scope

- Frontend tests (separate change)
- E2E / Playwright tests
- Load testing / performance benchmarks
- Database migration changes
- New features or API endpoints
- Authentication model changes (still JWT simple)
- MinIO bucket policy / lifecycle rules

## Approach

### 1. Test Infrastructure (Foundation)

**Test structure:**
```
backend/
  tests/
    __init__.py
    conftest.py              # Shared fixtures, fakes, test app factory
    unit/
      __init__.py
      test_exceptions.py     # Domain exceptions
      test_jwt_handler.py    # Auth functions
      test_document_service.py
      test_template_service.py
      test_middleware.py      # get_current_user
    integration/
      __init__.py
      conftest.py            # DB fixtures, test client
      test_auth_api.py
      test_templates_api.py
      test_documents_api.py
      test_health_api.py
```

**Fake implementations for ports:**
- `FakeStorageService(StorageService)` — in-memory dict `{(bucket, path): bytes}`
- `FakeTemplateEngine(TemplateEngine)` — returns predictable bytes, extracts fake variables
- `FakeTemplateRepository(TemplateRepository)` — in-memory dict storage
- `FakeDocumentRepository(DocumentRepository)` — in-memory dict storage
- `FakeUserRepository(UserRepository)` — in-memory dict storage

These fakes live in `tests/conftest.py` (or `tests/fakes/` if they grow large) and are the foundation for all unit tests. They exercise the SAME abstract interface as the real implementations, so the tests validate business logic without infrastructure dependencies.

**Test database strategy for integration tests:**
- Use a separate PostgreSQL database via `DATABASE_URL` override in test fixtures, OR
- Use SQLite async (`aiosqlite`) for speed if schema is compatible
- Decision deferred to spec/design phase based on schema compatibility analysis

**pyproject.toml additions:**
```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
```

### 2. MinIO Async Wrapping

Wrap all synchronous `minio-py` calls with `asyncio.to_thread()`. This is a mechanical change to all 4 methods in `MinioStorageService`:

```python
# Before
async def upload_file(self, bucket, path, data, content_type):
    self._client.put_object(...)

# After
async def upload_file(self, bucket, path, data, content_type):
    await asyncio.to_thread(
        self._client.put_object,
        bucket_name=bucket,
        object_name=path,
        data=io.BytesIO(data),
        length=len(data),
        content_type=content_type,
    )
```

**Why `asyncio.to_thread()` and not an async MinIO client?** There is no official async MinIO Python client. `asyncio.to_thread()` is the standard stdlib approach — zero new dependencies, simple, proven. Each sync call runs in the default thread pool executor, freeing the event loop.

### 3. Bulk Limit Configuration

**Current state:** `Settings.bulk_generation_limit = 10` exists but is not used.

**Changes:**
1. `DocumentService.__init__` receives `bulk_generation_limit: int` parameter
2. `parse_excel_data` uses `self._bulk_limit` instead of hardcoded `10`
3. `BulkLimitExceededError.__init__` keeps its `limit` param but the DEFAULT is no longer important — the caller always passes the configured value
4. `get_document_service()` in `services/__init__.py` passes `settings.bulk_generation_limit` to `DocumentService`

### 4. CORS Configuration Completion

**Current state:** Already working (`config.py` has `cors_origins`, `main.py` reads it).

**Remaining:** Create `.env.example` with all environment variables documented, including `CORS_ORIGINS` and `BULK_GENERATION_LIMIT`.

### 5. Rate Limiting

**Library:** `slowapi` (built on `limits`, works with FastAPI/Starlette natively).

**Configuration:**
- Add `slowapi>=0.1.9` to `pyproject.toml` dependencies
- Add `rate_limit_login`, `rate_limit_generation` settings to `config.py` (with sane defaults)
- Create rate limiter instance in `main.py` (or dedicated middleware file)
- Apply `@limiter.limit()` decorators to target endpoints
- Rate limit key: client IP (from `request.client.host`)

**Limits:**
| Endpoint | Limit | Rationale |
|----------|-------|-----------|
| `POST /auth/login` | 5/minute | Brute-force protection |
| `POST /auth/refresh` | 10/minute | Token refresh abuse |
| `POST /documents/generate` | 20/minute | Resource-intensive operation |
| `POST /documents/generate-bulk` | 5/minute | Heavy operation (multiple renders + ZIP) |

### 6. CI Test Gate

**Current deploy.yml:** Single `deploy` job that SSHs into VPS.

**New structure:**
```yaml
jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16
        env: ...
    steps:
      - checkout
      - setup-python 3.12
      - pip install -e ".[dev]"
      - pytest --tb=short -q

  deploy:
    needs: [test]
    if: success()
    runs-on: ubuntu-latest
    # ... existing deploy steps
```

**Key decisions:**
- Tests run in CI with a real PostgreSQL service container (not SQLite) to match production
- MinIO is NOT needed in CI — unit tests use fakes, integration tests mock storage
- The `deploy` job only runs if `test` passes (`needs: [test]`)

## Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| SQLite async may not support all PostgreSQL-specific column types (UUID, JSONB, ARRAY) | Medium | Use PostgreSQL service container in CI; if SQLite is used locally, test with limited schema |
| `slowapi` state is per-process (not shared across workers) | Low | Acceptable for MVP with single uvicorn process; document that Redis backend needed for multi-worker |
| `asyncio.to_thread()` uses the default executor with limited threads | Low | Default pool size is adequate for MVP concurrency; can be tuned via `loop.set_default_executor()` if needed |
| Integration tests require careful fixture setup for multi-tenant isolation | Medium | Each test creates its own tenant + user; teardown truncates tables |
| Adding `needs: [test]` blocks ALL deploys if tests flake | Medium | Start with robust tests only; add `pytest-retry` later if flakiness appears |

## Alternatives Considered

| Alternative | Why not |
|-------------|---------|
| `miniopy-async` (async MinIO client) | Unofficial, low maintenance, adds dependency. `asyncio.to_thread()` is stdlib and sufficient |
| `ratelimit` decorator library | Not FastAPI-aware; `slowapi` integrates with Starlette middleware for proper error responses |
| Separate test workflow file | Adds maintenance burden; single file with `needs` dependency is cleaner |
| Docker-based test execution in CI | Overkill — `pip install` + pytest is faster and simpler for a Python-only test suite |
| `factory_boy` for test data | Premature complexity — simple fixture functions are sufficient for current model count |

## Dependencies

- `slowapi>=0.1.9` — new production dependency
- `pytest>=8.0.0`, `pytest-asyncio>=0.24.0`, `httpx>=0.27.0` — already in `[dev]` optional deps
- `aiosqlite>=0.20.0` — potential dev dependency if SQLite test strategy is chosen

## Success Criteria

1. `pytest` runs from `backend/` and discovers all tests
2. All unit tests pass with in-memory fakes (no infrastructure needed)
3. All integration tests pass with test database
4. CI `test` job passes and gates the `deploy` job
5. MinIO operations no longer block the event loop
6. Bulk generation limit reads from `Settings.bulk_generation_limit`
7. Rate limiting returns `429 Too Many Requests` when limits are exceeded
8. `.env.example` documents all configurable environment variables
