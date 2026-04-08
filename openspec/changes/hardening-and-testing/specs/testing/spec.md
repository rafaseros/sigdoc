# Testing Specification

## Purpose

Define requirements for the test infrastructure and coverage across domain exceptions, auth utilities, service layer, middleware, and API integration for sigdoc.

## Requirements

### Requirement: Test Infrastructure

The project MUST have a `backend/tests/` directory with `conftest.py` providing async-compatible fixtures and in-memory fake implementations for all domain ports (`StorageService`, `TemplateEngine`, `TemplateRepository`, `DocumentRepository`, `UserRepository`).

`pyproject.toml` MUST include `[tool.pytest.ini_options]` with `testpaths = ["tests"]` and `asyncio_mode = "auto"`.

All fake port implementations MUST satisfy the same abstract interface as the real implementations.

#### Scenario: Fake ports honour interface contract

- GIVEN all five fake port classes are instantiated
- WHEN each method defined on the abstract port is called with valid arguments
- THEN the call completes without raising `NotImplementedError` or `TypeError`
- AND the return value matches the type declared by the abstract port

#### Scenario: pytest discovers all tests

- GIVEN `pyproject.toml` configures `testpaths = ["tests"]` and `asyncio_mode = "auto"`
- WHEN `pytest --collect-only` is run from `backend/`
- THEN all test files under `tests/unit/` and `tests/integration/` are collected

---

### Requirement: Unit Tests — Domain Exceptions

The project MUST have unit tests covering all domain exception classes (`BulkLimitExceededError`, `VariablesMismatchError`, and any other domain-level exceptions).

#### Scenario: BulkLimitExceededError carries limit value

- GIVEN `BulkLimitExceededError` is instantiated with `limit=5`
- WHEN the exception is raised and caught
- THEN `str(exception)` contains `"5"`
- AND `exception.limit == 5`

#### Scenario: VariablesMismatchError captures field info

- GIVEN `VariablesMismatchError` is instantiated with missing and extra variable lists
- WHEN the exception is raised and caught
- THEN the exception exposes both lists on its attributes

---

### Requirement: Unit Tests — Auth Utilities

The project MUST have unit tests for `hash_password`, `verify_password`, `create_access_token`, `create_refresh_token`, and `decode_token`.

#### Scenario: Password round-trip

- GIVEN a plaintext password
- WHEN `hash_password` is called and the result passed to `verify_password`
- THEN `verify_password` returns `True`

#### Scenario: Access token encodes expected claims

- GIVEN a user payload dict
- WHEN `create_access_token` is called and the result passed to `decode_token`
- THEN `decode_token` returns a payload containing the original user ID and `type == "access"`

#### Scenario: Expired token rejected

- GIVEN an access token created with `expires_delta` in the past
- WHEN `decode_token` is called
- THEN it raises an expiry-related exception

#### Scenario: Token with wrong type rejected

- GIVEN a refresh token
- WHEN it is passed to a context that expects an access token
- THEN the system raises a token-type mismatch error

#### Scenario: Tampered token rejected

- GIVEN a valid access token with one character modified
- WHEN `decode_token` is called
- THEN it raises a signature-verification error

---

### Requirement: Unit Tests — DocumentService

The project MUST have unit tests for `DocumentService` covering `generate_single`, `parse_excel_data`, `generate_bulk`, `get`, `list_paginated`, and `delete`, using only in-memory fakes.

#### Scenario: generate_single stores document and returns metadata

- GIVEN a valid template version exists in `FakeTemplateRepository`
- AND `FakeStorageService` and `FakeDocumentRepository` are empty
- WHEN `generate_single` is called with matching variable values
- THEN a document record appears in `FakeDocumentRepository`
- AND `FakeStorageService` contains the rendered bytes under the expected key

#### Scenario: parse_excel_data rejects rows exceeding bulk limit

- GIVEN `DocumentService` is configured with `bulk_generation_limit=3`
- WHEN `parse_excel_data` is called with a spreadsheet containing 4 rows
- THEN `BulkLimitExceededError` is raised with `limit=3`

#### Scenario: parse_excel_data accepts rows within limit

- GIVEN `DocumentService` is configured with `bulk_generation_limit=3`
- WHEN `parse_excel_data` is called with a spreadsheet containing 3 rows
- THEN it returns a list of 3 variable-value dicts without error

#### Scenario: delete removes document from storage and repository

- GIVEN a document exists in `FakeDocumentRepository` and `FakeStorageService`
- WHEN `delete` is called with the document ID
- THEN the document is absent from both fakes

---

### Requirement: Unit Tests — TemplateService

The project MUST have unit tests for `TemplateService` covering `upload`, `upload_new_version`, `get`, `list_paginated`, and `delete`, using only in-memory fakes.

#### Scenario: upload stores file and creates template record

- GIVEN `FakeStorageService` and `FakeTemplateRepository` are empty
- WHEN `upload` is called with valid template bytes
- THEN a template record exists in `FakeTemplateRepository`
- AND `FakeStorageService` contains the uploaded bytes

#### Scenario: upload_new_version increments version number

- GIVEN a template with version 1 exists in `FakeTemplateRepository`
- WHEN `upload_new_version` is called
- THEN a version record with version number 2 is created

---

### Requirement: Unit Tests — Middleware

The project MUST have unit tests for `get_current_user` dependency with valid, invalid, expired, and wrong-type tokens.

#### Scenario: Valid access token resolves user

- GIVEN a valid access token for an existing user in `FakeUserRepository`
- WHEN `get_current_user` is called
- THEN it returns the matching user object

#### Scenario: Invalid token raises 401

- GIVEN a malformed token string
- WHEN `get_current_user` is called
- THEN an HTTP 401 exception is raised

#### Scenario: Expired token raises 401

- GIVEN an expired access token
- WHEN `get_current_user` is called
- THEN an HTTP 401 exception is raised

#### Scenario: Refresh token used as access token raises 401

- GIVEN a valid refresh token
- WHEN `get_current_user` is called (which expects access type)
- THEN an HTTP 401 exception is raised

---

### Requirement: API Integration Tests

The project MUST have integration tests using `httpx.AsyncClient` + the FastAPI `app` instance covering auth, template, document, and health endpoints.

Integration tests MUST run against a real PostgreSQL database (via CI service container or a dedicated test DB URL).

#### Scenario: Login with valid credentials returns tokens

- GIVEN a user exists in the test database
- WHEN `POST /auth/login` is called with correct credentials
- THEN the response is HTTP 200 with `access_token` and `refresh_token` fields

#### Scenario: Login with invalid credentials returns 401

- GIVEN no user matches the provided credentials
- WHEN `POST /auth/login` is called
- THEN the response is HTTP 401

#### Scenario: Authenticated template upload succeeds

- GIVEN a valid access token and a `.docx` file
- WHEN `POST /templates` is called with the file and auth header
- THEN the response is HTTP 201 and the template appears in `GET /templates`

#### Scenario: Unauthenticated request returns 401

- GIVEN no Authorization header is provided
- WHEN any protected endpoint is called
- THEN the response is HTTP 401

#### Scenario: Health check returns 200

- GIVEN the application is running
- WHEN `GET /health` is called
- THEN the response is HTTP 200
