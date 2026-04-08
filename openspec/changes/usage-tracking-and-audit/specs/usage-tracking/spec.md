# Spec: usage-tracking

**Change**: usage-tracking-and-audit  
**Domain**: usage-tracking  
**Version**: 1.0  
**Status**: draft  
**Date**: 2026-04-07

---

## Overview

This domain records every document generation event and exposes monthly aggregation endpoints. It is the prerequisite for subscription quota enforcement (next change). All requirements use RFC 2119 keywords.

---

## 1. Domain Entity — `UsageEvent`

### 1.1 Fields

| Field | Type | Constraints | Notes |
|---|---|---|---|
| `id` | UUID | PK, auto-generated | |
| `user_id` | UUID | NOT NULL, FK → users.id | Who triggered generation |
| `tenant_id` | UUID | NOT NULL, FK → tenants.id | Tenant isolation |
| `template_id` | UUID | NOT NULL, FK → templates.id | Which template was used |
| `generation_type` | VARCHAR(10) | NOT NULL, `"single"` or `"bulk"` | Mirrors Document.generation_type |
| `document_count` | INTEGER | NOT NULL, ≥ 1 | 1 for single; N for bulk (successful rows) |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Immutable event timestamp |

### 1.2 Invariants

- `UsageEvent` MUST be immutable after creation. No UPDATE operations are permitted on this table.
- `document_count` MUST reflect only **successfully** generated documents. Failed rows in a bulk operation MUST NOT be counted.
- `generation_type` MUST be exactly `"single"` or `"bulk"`. No other values are valid.

### 1.3 Python dataclass signature

```python
@dataclass
class UsageEvent:
    id: UUID
    user_id: UUID
    tenant_id: UUID
    template_id: UUID
    generation_type: str          # "single" | "bulk"
    document_count: int
    created_at: datetime | None = None
```

---

## 2. Domain Port — `UsageRepository`

The repository port MUST define the following abstract methods:

```python
class UsageRepository(ABC):
    @abstractmethod
    async def create(self, event: UsageEvent) -> UsageEvent: ...

    @abstractmethod
    async def get_monthly_stats_for_user(
        self,
        user_id: UUID,
        tenant_id: UUID,
        year: int,
        month: int,
    ) -> dict:
        """Return total document_count and per-template breakdown for a given user+month."""
        ...

    @abstractmethod
    async def get_monthly_stats_for_tenant(
        self,
        tenant_id: UUID,
        year: int,
        month: int,
    ) -> list[dict]:
        """Return per-user breakdown of document_count for all users in tenant for given month."""
        ...
```

Return shapes are defined in section 5 (API schemas).

---

## 3. Application Service — `UsageService`

### 3.1 Responsibilities

- `UsageService.record()` creates a `UsageEvent` record via the repository.
- `UsageService.get_user_monthly_stats()` delegates to `UsageRepository.get_monthly_stats_for_user()`.
- `UsageService.get_tenant_monthly_stats()` delegates to `UsageRepository.get_monthly_stats_for_tenant()`.

### 3.2 Signature

```python
class UsageService:
    def __init__(self, repository: UsageRepository): ...

    async def record(
        self,
        user_id: UUID,
        tenant_id: UUID,
        template_id: UUID,
        generation_type: str,   # "single" | "bulk"
        document_count: int,
    ) -> UsageEvent: ...

    async def get_user_monthly_stats(
        self,
        user_id: UUID,
        tenant_id: UUID,
        year: int,
        month: int,
    ) -> dict: ...

    async def get_tenant_monthly_stats(
        self,
        tenant_id: UUID,
        year: int,
        month: int,
    ) -> list[dict]: ...
```

### 3.3 Integration with `DocumentService`

`UsageService` MUST be an **optional** constructor parameter in `DocumentService` (default `None`) for backward compatibility:

```python
class DocumentService:
    def __init__(
        self,
        ...,
        usage_service: UsageService | None = None,
    ): ...
```

`DocumentService.generate_single()` MUST call `usage_service.record(...)` **after** the document record is persisted to the database and **only if** `usage_service is not None`.

`DocumentService.generate_bulk()` MUST call `usage_service.record(...)` **after** all document records are persisted via `create_batch()`, passing `document_count=len(successful_documents)`.

Usage recording MUST be **synchronous within the same async flow** (not fire-and-forget). If usage recording fails, the caller SHOULD log a warning but MUST NOT raise an exception that fails the generation request.

---

## 4. Scenarios — Core Event Recording

### SCENARIO 4.1 — Single generation records a usage event

```
Given a user with valid access to a template version
And UsageService is injected into DocumentService
When POST /documents/generate succeeds and returns HTTP 201
Then a UsageEvent record exists with:
  - user_id = requesting user's ID
  - tenant_id = requesting user's tenant ID
  - template_id = the parent template's ID
  - generation_type = "single"
  - document_count = 1
  - created_at is set to approximately the time of the request
```

### SCENARIO 4.2 — Bulk generation records a usage event with correct count

```
Given a user uploads an Excel file with 5 data rows
And 4 rows render successfully, 1 fails
When POST /documents/generate-bulk completes
Then a UsageEvent record exists with:
  - generation_type = "bulk"
  - document_count = 4  (successful only)
And the failed row is NOT counted
```

### SCENARIO 4.3 — Failed generation does NOT create a usage event

```
Given a user requests generation with an invalid template_version_id
When DocumentService raises TemplateVersionNotFoundError
Then NO UsageEvent record is created
```

### SCENARIO 4.4 — Access-denied generation does NOT create a usage event

```
Given a user without access to a template
When DocumentService raises TemplateAccessDeniedError
Then NO UsageEvent record is created
```

### SCENARIO 4.5 — Usage recording failure does not fail the generation

```
Given UsageService.record() raises an unexpected exception
When POST /documents/generate is called
Then the endpoint MUST still return HTTP 201
And a warning MUST be logged with the error details
And the generated document MUST be returned to the caller
```

### SCENARIO 4.6 — UsageService not injected (legacy/test mode)

```
Given DocumentService is constructed without usage_service
When POST /documents/generate succeeds
Then no usage recording attempt is made
And no exception is raised
```

---

## 5. API — Usage Endpoints

### 5.1 GET /api/v1/usage

**Auth**: Any authenticated user (returns own stats only).  
**Description**: Returns the current user's document generation stats for the current month.

**Query parameters** (all optional):

| Param | Type | Default | Description |
|---|---|---|---|
| `year` | integer | current year | Four-digit year |
| `month` | integer (1–12) | current month | Month number |

**Response 200** — `UserUsageResponse`:

```json
{
  "user_id": "uuid",
  "year": 2026,
  "month": 4,
  "total_documents": 47,
  "by_template": [
    {
      "template_id": "uuid",
      "template_name": "Contract Template",
      "document_count": 30
    },
    {
      "template_id": "uuid",
      "template_name": "NDA Template",
      "document_count": 17
    }
  ]
}
```

### SCENARIO 5.1.1 — User retrieves their own monthly stats

```
Given user A has generated 30 docs from template X and 17 from template Y in April 2026
When GET /api/v1/usage?year=2026&month=4
Then response is HTTP 200
And total_documents = 47
And by_template contains two entries with the correct counts
```

### SCENARIO 5.1.2 — No events in the requested month

```
Given user A has no usage events in March 2026
When GET /api/v1/usage?year=2026&month=3
Then response is HTTP 200
And total_documents = 0
And by_template = []
```

### SCENARIO 5.1.3 — Default to current month when no params given

```
Given today is 2026-04-07
When GET /api/v1/usage (no query params)
Then the response reflects year=2026 and month=4
```

### SCENARIO 5.1.4 — Invalid month value is rejected

```
When GET /api/v1/usage?month=13
Then response is HTTP 422
And the error references the invalid "month" parameter
```

---

### 5.2 GET /api/v1/usage/tenant

**Auth**: Admin only. Non-admin MUST receive HTTP 403.  
**Description**: Returns the current month's document generation stats for all users in the admin's tenant.

**Query parameters** (all optional):

| Param | Type | Default | Description |
|---|---|---|---|
| `year` | integer | current year | Four-digit year |
| `month` | integer (1–12) | current month | Month number |

**Response 200** — `TenantUsageResponse`:

```json
{
  "tenant_id": "uuid",
  "year": 2026,
  "month": 4,
  "total_documents": 120,
  "by_user": [
    {
      "user_id": "uuid",
      "user_email": "alice@acme.com",
      "full_name": "Alice Smith",
      "document_count": 80
    },
    {
      "user_id": "uuid",
      "user_email": "bob@acme.com",
      "full_name": "Bob Jones",
      "document_count": 40
    }
  ]
}
```

### SCENARIO 5.2.1 — Admin retrieves tenant-wide stats

```
Given tenant ACME has two users with 80 and 40 docs generated in April 2026
When admin calls GET /api/v1/usage/tenant?year=2026&month=4
Then response is HTTP 200
And total_documents = 120
And by_user contains two entries with correct counts
```

### SCENARIO 5.2.2 — Non-admin is rejected

```
Given a user with role "user"
When GET /api/v1/usage/tenant
Then response is HTTP 403
```

### SCENARIO 5.2.3 — Tenant isolation: admin only sees their own tenant

```
Given two tenants: ACME (admin A) and BETA (admin B)
When admin A calls GET /api/v1/usage/tenant
Then only usage events with tenant_id = ACME's tenant_id are returned
And BETA's data is never included in the response
```

---

## 6. Database Schema

### Table: `usage_events`

```sql
CREATE TABLE usage_events (
    id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id    UUID        NOT NULL REFERENCES tenants(id),
    user_id      UUID        NOT NULL REFERENCES users(id),
    template_id  UUID        NOT NULL REFERENCES templates(id),
    generation_type VARCHAR(10) NOT NULL CHECK (generation_type IN ('single', 'bulk')),
    document_count  INTEGER  NOT NULL CHECK (document_count >= 1),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Indexes for aggregation queries
CREATE INDEX ix_usage_events_tenant_created ON usage_events (tenant_id, created_at);
CREATE INDEX ix_usage_events_user_created   ON usage_events (user_id, created_at);
CREATE INDEX ix_usage_events_template       ON usage_events (template_id);
```

**No updated_at column** — this table is append-only. No UPDATE or DELETE operations are permitted by the repository layer.

---

## 7. Infrastructure Layer Conventions

The SQLAlchemy model (`UsageEventModel`) MUST follow the existing `TenantMixin` pattern. The `SQLAlchemyUsageRepository` MUST implement `UsageRepository`. Monthly aggregation queries MUST use `DATE_TRUNC('month', created_at)` or equivalent range filter (`created_at >= month_start AND created_at < month_end`) for portability.

---

## 8. Test Coverage Requirements

The following test scenarios MUST be covered:

| Test | Type |
|---|---|
| `UsageService.record()` creates correct entity | Unit |
| `UsageService.record()` with zero count raises ValueError | Unit |
| `DocumentService.generate_single()` calls `usage_service.record()` once after success | Unit |
| `DocumentService.generate_bulk()` calls `usage_service.record()` with successful count | Unit |
| `DocumentService.generate_single()` does not call record on TemplateVersionNotFoundError | Unit |
| `UsageService.record()` failure does not raise from `generate_single()` | Unit |
| `FakeUsageRepository` implements `UsageRepository` | Unit |
| `GET /api/v1/usage` returns correct stats | Integration |
| `GET /api/v1/usage/tenant` returns 403 for non-admin | Integration |
| `GET /api/v1/usage/tenant` returns correct per-user breakdown | Integration |
| Monthly boundary: events from prior month are excluded | Integration |

---

## 9. Out of Scope

- Quota enforcement or limit checking (next change: subscription-tiers)
- Usage alerts or notifications
- Usage export (CSV/PDF)
- Background aggregation jobs or rollup tables
- Historical data beyond what `usage_events` stores
