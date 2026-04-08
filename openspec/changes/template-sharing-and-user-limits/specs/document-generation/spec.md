# Delta for document-generation

## MODIFIED Requirements

### Requirement: Bulk Generation Limit

The number of rows allowed in a single bulk generation request MUST be capped by a limit resolved in this priority order:

1. User's `bulk_generation_limit` (if set — non-null)
2. Global `Settings.bulk_generation_limit` (fallback)

Admins MUST be able to set a per-user limit. The effective limit MUST be communicated to the client so the UI can enforce it proactively.
(Previously: bulk limit was a single global setting applied to all users equally)

#### Scenario: User with no personal limit uses global default

- GIVEN user A has `bulk_generation_limit = NULL`
- AND global setting is `bulk_generation_limit = 10`
- WHEN user A parses an Excel with 10 data rows
- THEN the request MUST succeed

#### Scenario: User exceeds global default

- GIVEN user A has `bulk_generation_limit = NULL`
- AND global setting is `bulk_generation_limit = 10`
- WHEN user A parses an Excel with 11 data rows
- THEN the response MUST be 422 with `BulkLimitExceededError` indicating limit 10

#### Scenario: User's personal limit overrides global

- GIVEN user A has `bulk_generation_limit = 50`
- AND global setting is `bulk_generation_limit = 10`
- WHEN user A parses an Excel with 30 data rows
- THEN the request MUST succeed (personal limit 50 applies)

#### Scenario: User's personal limit is lower than global

- GIVEN user A has `bulk_generation_limit = 5`
- AND global setting is `bulk_generation_limit = 10`
- WHEN user A parses an Excel with 6 data rows
- THEN the response MUST be 422 with `BulkLimitExceededError` indicating limit 5

#### Scenario: Admin sets per-user limit

- GIVEN tenant admin and user A with `bulk_generation_limit = NULL`
- WHEN admin calls `PATCH /users/{A.id}` with `{ "bulk_generation_limit": 25 }`
- THEN the response MUST be 200
- AND user A's subsequent bulk requests MUST be capped at 25

#### Scenario: Admin clears per-user limit

- GIVEN user A has `bulk_generation_limit = 25`
- WHEN admin calls `PATCH /users/{A.id}` with `{ "bulk_generation_limit": null }`
- THEN user A's limit MUST revert to the global default

---

## ADDED Requirements

### Requirement: Expose Effective Bulk Limit to Client

The API MUST expose the requesting user's effective bulk generation limit so the frontend can enforce it before upload.

#### Scenario: Authenticated user retrieves own effective limit

- GIVEN user A with `bulk_generation_limit = 50`
- WHEN user A calls `GET /users/me`
- THEN the response MUST include `"effective_bulk_limit": 50`

#### Scenario: User with null limit sees global default

- GIVEN user A with `bulk_generation_limit = NULL`
- AND global setting is `bulk_generation_limit = 10`
- WHEN user A calls `GET /users/me`
- THEN the response MUST include `"effective_bulk_limit": 10`

---

### Requirement: Template Access Check Before Generation

Before generating a document (single or bulk), the service MUST verify the requesting user has access to the referenced template version (is owner, has share, or is admin).

#### Scenario: Shared user can generate from shared template

- GIVEN user B has shared access to template T (version V)
- WHEN user B calls `POST /documents/generate` with `template_version_id = V.id`
- THEN the response MUST be 201

#### Scenario: Unrelated user cannot generate

- GIVEN user C has no relation to template T
- WHEN user C calls `POST /documents/generate` with a version of T
- THEN the response MUST be 403
