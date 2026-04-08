# Infrastructure Specification

## Purpose

Define requirements for making MinIO I/O non-blocking, making the bulk generation limit configurable via settings, and completing CORS configuration documentation.

## Requirements

### Requirement: Non-Blocking MinIO Operations

All four methods of `MinioStorageService` (`upload_file`, `download_file`, `get_presigned_url`, `delete_file`) MUST NOT call synchronous `minio-py` methods directly inside `async def` bodies.

Each method MUST delegate the synchronous call to `asyncio.to_thread()` so the event loop is not blocked.

No new external dependencies MAY be introduced for this change — `asyncio.to_thread()` from the standard library MUST be used.

#### Scenario: Upload does not block the event loop

- GIVEN `MinioStorageService.upload_file` is called concurrently with other coroutines
- WHEN the upload executes
- THEN the event loop remains unblocked during the synchronous MinIO call
- AND other coroutines can progress while the upload runs in a thread

#### Scenario: Download returns correct bytes

- GIVEN a file previously uploaded to MinIO
- WHEN `download_file` is called via `asyncio.to_thread()`
- THEN the returned bytes match the originally uploaded content

#### Scenario: Presigned URL generated successfully

- GIVEN a valid bucket and object path
- WHEN `get_presigned_url` is called
- THEN a non-empty URL string is returned without error

#### Scenario: Delete removes object

- GIVEN an object exists in MinIO
- WHEN `delete_file` is called
- THEN the object is no longer accessible in the bucket

---

### Requirement: Configurable Bulk Generation Limit

`DocumentService` MUST receive `bulk_generation_limit: int` as a constructor parameter injected from `Settings.bulk_generation_limit`.

`DocumentService.parse_excel_data` MUST use the injected limit value instead of any hardcoded integer.

`BulkLimitExceededError` MUST be raised with the configured limit value when the row count exceeds it.

The `get_document_service()` factory function MUST pass `settings.bulk_generation_limit` to `DocumentService`.

#### Scenario: Limit read from settings at runtime

- GIVEN `Settings.bulk_generation_limit = 25`
- WHEN `DocumentService` is instantiated via `get_document_service()`
- THEN its internal limit is `25`

#### Scenario: Bulk limit enforced from settings value

- GIVEN `DocumentService` is configured with `bulk_generation_limit=5`
- AND a spreadsheet with 6 rows is provided
- WHEN `parse_excel_data` is called
- THEN `BulkLimitExceededError` is raised with `limit=5`

#### Scenario: Rows at the limit are accepted

- GIVEN `DocumentService` is configured with `bulk_generation_limit=5`
- AND a spreadsheet with exactly 5 rows is provided
- WHEN `parse_excel_data` is called
- THEN it returns a list of 5 variable-value dicts without error

---

### Requirement: CORS and Environment Variable Documentation

A `.env.example` file MUST exist at the project root (or `backend/` root) documenting all configurable environment variables.

The file MUST include `CORS_ORIGINS` and `BULK_GENERATION_LIMIT` alongside all other existing env vars.

Each entry SHOULD include a comment explaining the variable's purpose and acceptable format.

#### Scenario: .env.example documents CORS_ORIGINS

- GIVEN the `.env.example` file exists
- WHEN it is opened
- THEN a `CORS_ORIGINS` entry is present with a sample value (e.g. `http://localhost:3000,https://app.example.com`)

#### Scenario: .env.example documents BULK_GENERATION_LIMIT

- GIVEN the `.env.example` file exists
- WHEN it is opened
- THEN a `BULK_GENERATION_LIMIT` entry is present with a sample integer value
