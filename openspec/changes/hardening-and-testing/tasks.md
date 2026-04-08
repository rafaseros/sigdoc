# Tasks: hardening-and-testing

## Phase 1: Infrastructure Fixes (already partially done)

- [x] 1.1 Update `backend/.env.example` — document all env vars: DATABASE_URL, SECRET_KEY, MINIO_*, CORS_ORIGINS (sample: http://localhost:3000,http://localhost:5173), BULK_GENERATION_LIMIT (sample: 10), JWT_*, with one comment per var.
  _Files_: `backend/.env.example` (new)

- [x] 1.2 Add `bulk_generation_limit: int` param to `DocumentService.__init__`; store as `self._bulk_limit`; replace hardcoded `10` in `parse_excel_data` with `self._bulk_limit`. Raise `BulkLimitExceededError(limit=self._bulk_limit)`.
  _Files_: `backend/src/app/application/services/document_service.py`
  _Note_: `config.py` and `main.py` already done — skip those.

- [x] 1.3 Update `get_document_service()` factory to pass `bulk_generation_limit=settings.bulk_generation_limit`.
  _Files_: `backend/src/app/application/services/__init__.py`

- [x] 1.4 Wrap all 4 `MinioStorageService` methods with `asyncio.to_thread()`: `upload_file`, `download_file`, `get_presigned_url`, `delete_file`. For `download_file`, keep read+close inside the thread closure.
  _Files_: `backend/src/app/infrastructure/storage/minio_storage.py`

- [x] 1.5 Add `slowapi>=0.1.9` to `[project.dependencies]` in `pyproject.toml`. Add `pytest-asyncio`, `httpx`, `pytest` to `[dev]` (already present — verify versions). Add `[tool.pytest.ini_options]` with `testpaths = ["tests"]`, `asyncio_mode = "auto"`.
  _Files_: `backend/pyproject.toml`

- [x] 1.6 Create rate limiter module: `backend/src/app/presentation/middleware/rate_limit.py` — instantiate `Limiter(key_func=get_remote_address)`, export `limiter`.
  _Files_: `backend/src/app/presentation/middleware/rate_limit.py` (new)

- [x] 1.7 Register slowapi in `create_app()`: add `SlowAPIMiddleware`, register `RateLimitExceeded` handler returning HTTP 429.
  _Files_: `backend/src/app/main.py`

- [x] 1.8 Add `@limiter.limit(...)` decorators + `request: Request` param to 4 endpoints: `/auth/login` (5/min), `/auth/refresh` (10/min), `/documents/generate` (20/min), `/documents/generate-bulk` (5/min).
  _Files_: `backend/src/app/presentation/api/v1/auth.py`, `backend/src/app/presentation/api/v1/documents.py`

---

## Phase 2: Test Infrastructure (TDD — write before implementation)

- [x] 2.1 Create test directory skeleton with `__init__.py` files:
  `backend/tests/`, `backend/tests/fakes/`, `backend/tests/unit/`, `backend/tests/integration/`
  _Files_: 4 `__init__.py` files (new)

- [x] 2.2 Write `FakeStorageService` — implements `StorageService` ABC; stores `files: dict[tuple[str,str], bytes]`; returns presigned URL as `f"http://fake/{bucket}/{path}"`.
  _Files_: `backend/tests/fakes/fake_storage_service.py` (new)

- [x] 2.3 Write `FakeTemplateEngine` — implements `TemplateEngine` ABC; configurable `variables_to_return: list[str]`, `render_result: bytes`, `should_fail: bool`.
  _Files_: `backend/tests/fakes/fake_template_engine.py` (new)

- [x] 2.4 Write `FakeTemplateRepository` and `FakeDocumentRepository` — dict-backed, implement full CRUD matching their ABC signatures, including `list_paginated` and `create_batch`.
  _Files_: `backend/tests/fakes/fake_template_repository.py`, `backend/tests/fakes/fake_document_repository.py` (new)

- [x] 2.5 Write `FakeUserRepository` — dict-backed, implements `UserRepository` ABC.
  _Files_: `backend/tests/fakes/fake_user_repository.py` (new)

- [x] 2.6 Write `backend/tests/fakes/__init__.py` re-exporting all five fakes.
  _Files_: `backend/tests/fakes/__init__.py`

- [x] 2.7 Write root `backend/tests/conftest.py` — sets test env vars (`DATABASE_URL`, `SECRET_KEY`, etc.) BEFORE app imports via `os.environ`; clears `get_settings.cache_clear()` between tests via `autouse` fixture.
  _Files_: `backend/tests/conftest.py` (new)

- [x] 2.8 Write `backend/tests/unit/conftest.py` — provides all five fake instances as `pytest.fixture` objects, scoped to `function`.
  _Files_: `backend/tests/unit/conftest.py` (new)

---

## Phase 3: Unit Tests

- [x] 3.1 **[RED]** Write `test_exceptions.py`: assert `BulkLimitExceededError(limit=25).limit == 25` and `"25" in str(...)`. Assert `VariablesMismatchError` can be raised and is a `DomainError`.
  _Files_: `backend/tests/unit/test_exceptions.py` (new)

- [x] 3.2 **[RED]** Write `test_jwt_handler.py`: test `hash_password`/`verify_password` round-trip; `create_access_token` → `decode_token` returns correct `sub` + `type`; expired token raises `ExpiredSignatureError`; wrong-type token (refresh used as access) raises error; tampered token raises error. Use `monkeypatch` for time travel.
  _Files_: `backend/tests/unit/test_jwt_handler.py` (new)

- [x] 3.3 **[RED]** Write `test_document_service.py`: test `parse_excel_data` rejects >limit rows (`BulkLimitExceededError`), accepts ≤limit rows; test `generate_single` stores file in `FakeStorageService.files` and creates record in `FakeDocumentRepository`; test `delete_document` removes from both fake repo and fake storage.
  _Files_: `backend/tests/unit/test_document_service.py` (new)

- [x] 3.4 **[RED]** Write `test_template_service.py`: test `upload` creates record in fake repo + stores bytes in fake storage; test `upload_new_version` increments version; test `delete` removes from both.
  _Files_: `backend/tests/unit/test_template_service.py` (new)

- [x] 3.5 **[RED]** Write `test_middleware.py`: test `get_current_user` with valid token → returns user object; malformed header → `HTTPException(401)`; expired token → `HTTPException(401)`; refresh token used as access → `HTTPException(401)`.
  _Files_: `backend/tests/unit/test_middleware.py` (new)

- [x] 3.6 **[GREEN]** Run `pytest backend/tests/unit/ -x` — fix any failures due to the `DocumentModel` import inside `generate_single`/`generate_bulk` (leaky abstraction flagged in design). Refactor if needed so unit tests pass with fakes only.
  _Files_: `backend/src/app/application/services/document_service.py` (possible refactor)

---

## Phase 4: Integration Tests

- [ ] 4.1 Write `backend/tests/integration/conftest.py` — create async test engine against `TEST_DATABASE_URL`; create all tables; provide `test_session` fixture with transaction rollback; override `get_session`, `get_tenant_session`, `get_storage_service`, `get_template_engine`, `get_document_service`, `get_template_service` via `app.dependency_overrides`; provide `async_client` as `httpx.AsyncClient(transport=ASGITransport(app=app))`.
  _Files_: `backend/tests/integration/conftest.py` (new)

- [ ] 4.2 Write `test_health_api.py`: `GET /health` → 200 and `{"status": "ok"}`.
  _Files_: `backend/tests/integration/test_health_api.py` (new)

- [ ] 4.3 Write `test_auth_api.py`: `POST /auth/login` with valid credentials → 200 + `access_token` + `refresh_token`; with invalid credentials → 401; `POST /auth/refresh` with valid refresh token → 200 + new access token.
  _Files_: `backend/tests/integration/test_auth_api.py` (new)

- [ ] 4.4 Write `test_templates_api.py`: unauthenticated `POST /templates/` → 401; authenticated upload → 201 + appears in `GET /templates/` list.
  _Files_: `backend/tests/integration/test_templates_api.py` (new)

- [ ] 4.5 Write `test_documents_api.py`: unauthenticated `POST /documents/generate` → 401; authenticated generate → 200 + `download_url` present.
  _Files_: `backend/tests/integration/test_documents_api.py` (new)

- [ ] 4.6 Run full suite `pytest backend/tests/ --tb=short -q` — all tests must pass.

---

## Phase 5: CI Gate

- [x] 5.1 Add `test` job to `.github/workflows/deploy.yml` — runs on `ubuntu-latest`; PostgreSQL 16 service container (`POSTGRES_*` env vars, health check); steps: checkout, setup Python 3.12, `pip install -e ".[dev]"`, `pytest --tb=short -q`.
  _Files_: `.github/workflows/deploy.yml`

- [x] 5.2 Add `needs: [test]` (and `if: success()`) to the existing `deploy` job.
  _Files_: `.github/workflows/deploy.yml`
