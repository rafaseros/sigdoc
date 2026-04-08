# Spec: audit-logging

**Change**: usage-tracking-and-audit  
**Domain**: audit-logging  
**Version**: 1.0  
**Status**: draft  
**Date**: 2026-04-07

---

## Overview

This domain provides an immutable, append-only audit trail of all significant actions performed in SigDoc. It is a compliance and operational visibility subsystem for multi-tenant SaaS. All requirements use RFC 2119 keywords.

---

## 1. Domain Entity — `AuditLog`

### 1.1 Fields

| Field | Type | Constraints | Notes |
|---|---|---|---|
| `id` | UUID | PK, auto-generated | |
| `actor_id` | UUID \| None | NULLABLE, FK → users.id | NULL for system-initiated actions |
| `tenant_id` | UUID | NOT NULL, FK → tenants.id | Tenant isolation |
| `action` | VARCHAR(50) | NOT NULL, must be a valid AuditAction | See section 2 |
| `resource_type` | VARCHAR(30) | NOT NULL | `"template"`, `"document"`, `"user"`, `"auth"` |
| `resource_id` | UUID \| None | NULLABLE | ID of the affected resource; NULL for auth actions |
| `details` | dict \| None | NULLABLE, stored as JSONB | Extra context (e.g. template name, variable count) |
| `ip_address` | str \| None | NULLABLE, max 45 chars | IPv4 or IPv6; extracted in presentation layer |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Immutable event timestamp |

### 1.2 Invariants

- `AuditLog` MUST be immutable after creation. No UPDATE or DELETE operations are permitted on this table by any code path.
- The `actor_id` field MAY be NULL only for system-generated events (currently not in scope; reserved for future use). All user-triggered actions MUST include a non-null `actor_id`.
- The `details` field MUST NOT contain sensitive data such as passwords, tokens, or full variable values. Template variable names are acceptable; values are not.

### 1.3 Python dataclass signature

```python
@dataclass
class AuditLog:
    id: UUID
    tenant_id: UUID
    action: str                    # AuditAction enum value
    resource_type: str
    actor_id: UUID | None = None
    resource_id: UUID | None = None
    details: dict | None = None
    ip_address: str | None = None
    created_at: datetime | None = None
```

---

## 2. Action Enum — `AuditAction`

The following 13 action constants MUST be defined as string literals in an `AuditAction` class or `Literal` type:

| Constant | Value | Triggered by |
|---|---|---|
| `TEMPLATE_UPLOAD` | `"template_upload"` | `TemplateService.upload_template()` |
| `TEMPLATE_DELETE` | `"template_delete"` | `TemplateService.delete_template()` |
| `TEMPLATE_VERSION` | `"template_version"` | `TemplateService.upload_new_version()` |
| `TEMPLATE_SHARE` | `"template_share"` | `TemplateService.share_template()` |
| `TEMPLATE_UNSHARE` | `"template_unshare"` | `TemplateService.unshare_template()` |
| `DOCUMENT_GENERATE` | `"document_generate"` | `DocumentService.generate_single()` |
| `DOCUMENT_GENERATE_BULK` | `"document_generate_bulk"` | `DocumentService.generate_bulk()` |
| `DOCUMENT_DELETE` | `"document_delete"` | `DocumentService.delete_document()` |
| `USER_CREATE` | `"user_create"` | `POST /api/v1/users` |
| `USER_UPDATE` | `"user_update"` | `PUT /api/v1/users/{id}` |
| `USER_DELETE` | `"user_delete"` | `DELETE /api/v1/users/{id}` |
| `USER_LOGIN` | `"user_login"` | `POST /api/v1/auth/login` (success) |
| `PASSWORD_CHANGE` | `"password_change"` | `POST /api/v1/auth/change-password` |

No other action values are valid. The repository MUST reject (raise ValueError) any `action` not in this set.

---

## 3. Domain Port — `AuditRepository`

```python
class AuditRepository(ABC):
    @abstractmethod
    async def create(self, log: AuditLog) -> AuditLog: ...

    @abstractmethod
    async def list_paginated(
        self,
        tenant_id: UUID,
        page: int = 1,
        size: int = 50,
        action: str | None = None,
        actor_id: UUID | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> tuple[list[AuditLog], int]:
        """Return paginated audit logs filtered by optional criteria.
        Results MUST be ordered by created_at DESC."""
        ...
```

The `AuditRepository` MUST NOT expose any `update()` or `delete()` method. Immutability is enforced at the port level.

---

## 4. Application Service — `AuditService`

### 4.1 Responsibilities

`AuditService.log()` is the single entry point for writing audit events. It MUST be called **fire-and-forget** via `asyncio.create_task()` by the calling service to avoid blocking the request path.

`AuditService.list_logs()` is called by the API router and delegates to `AuditRepository.list_paginated()`.

### 4.2 Signature

```python
class AuditService:
    def __init__(self, repository: AuditRepository): ...

    async def log(
        self,
        tenant_id: UUID,
        action: str,
        resource_type: str,
        actor_id: UUID | None = None,
        resource_id: UUID | None = None,
        details: dict | None = None,
        ip_address: str | None = None,
    ) -> None:
        """Write an audit log entry. MUST NOT raise — errors are logged as warnings."""
        ...

    async def list_logs(
        self,
        tenant_id: UUID,
        page: int = 1,
        size: int = 50,
        action: str | None = None,
        actor_id: UUID | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> tuple[list[AuditLog], int]: ...
```

### 4.3 Fire-and-forget pattern

The **caller** (DocumentService, TemplateService, router) MUST schedule the audit write via:

```python
import asyncio
asyncio.create_task(audit_service.log(...))
```

`AuditService.log()` itself MUST wrap the repository call in `try/except` and log a warning on failure. It MUST NOT re-raise. This ensures audit write failures are invisible to the user.

### 4.4 Integration with existing services

`AuditService` MUST be an **optional** constructor parameter in `DocumentService` and `TemplateService` (default `None`) for backward compatibility.

**IP address handling**: IP address is extracted in the **presentation layer** from `request.client.host` and passed as a parameter to the service method. The service layer MUST NOT import from FastAPI.

---

## 5. Integration Points — What Gets Logged and When

All integration points call `asyncio.create_task(audit_service.log(...))` immediately **after the business operation succeeds** (after return / after repo call). On exception, no audit log is created.

### 5.1 Template operations (TemplateService)

| Method | Action | resource_type | resource_id | details |
|---|---|---|---|---|
| `upload_template()` | `template_upload` | `"template"` | new template.id | `{name, variable_count}` |
| `delete_template()` | `template_delete` | `"template"` | template.id | `{name}` |
| `upload_new_version()` | `template_version` | `"template"` | template.id | `{new_version, variable_count}` |
| `share_template()` | `template_share` | `"template"` | template.id | `{shared_with_user_id}` |
| `unshare_template()` | `template_unshare` | `"template"` | template.id | `{unshared_user_id}` |

### 5.2 Document operations (DocumentService)

| Method | Action | resource_type | resource_id | details |
|---|---|---|---|---|
| `generate_single()` | `document_generate` | `"document"` | document.id | `{template_id}` |
| `generate_bulk()` | `document_generate_bulk` | `"document"` | batch_id | `{template_id, document_count, error_count}` |
| `delete_document()` | `document_delete` | `"document"` | document.id | `{file_name}` |

### 5.3 Auth operations (router level — `auth.py`)

| Endpoint | Action | resource_type | resource_id | details |
|---|---|---|---|---|
| `POST /auth/login` (success) | `user_login` | `"auth"` | user.id | `{email}` |
| `POST /auth/change-password` | `password_change` | `"user"` | user.id | `{}` |

Auth audit logs are created in the router (not a service) because auth does not go through a DI-injected service. `AuditService` MUST be injected via FastAPI `Depends()` for auth routes.

### 5.4 User CRUD operations (router level — `users.py`)

| Endpoint | Action | resource_type | resource_id | details |
|---|---|---|---|---|
| `POST /users` | `user_create` | `"user"` | created_user.id | `{email, role}` |
| `PUT /users/{id}` | `user_update` | `"user"` | user_id | `{updated_fields: [...]}` |
| `DELETE /users/{id}` | `user_delete` | `"user"` | user_id | `{}` |

User CRUD audit logs are created in the router, after the repository operation succeeds.

---

## 6. API — Audit Log Endpoint

### 6.1 GET /api/v1/audit-log

**Auth**: Admin only. Non-admin MUST receive HTTP 403.  
**Description**: Returns paginated, filterable audit logs for the admin's tenant.

**Query parameters**:

| Param | Type | Default | Description |
|---|---|---|---|
| `page` | integer ≥ 1 | 1 | Page number |
| `size` | integer 1–100 | 50 | Page size |
| `action` | string \| None | None | Filter by a specific AuditAction value |
| `actor_id` | UUID \| None | None | Filter by actor user ID |
| `date_from` | ISO 8601 datetime \| None | None | Inclusive lower bound on created_at |
| `date_to` | ISO 8601 datetime \| None | None | Inclusive upper bound on created_at |

**Response 200** — `AuditLogListResponse`:

```json
{
  "items": [
    {
      "id": "uuid",
      "actor_id": "uuid",
      "tenant_id": "uuid",
      "action": "template_upload",
      "resource_type": "template",
      "resource_id": "uuid",
      "details": {"name": "Contract v2", "variable_count": 5},
      "ip_address": "192.168.1.1",
      "created_at": "2026-04-07T14:30:00Z"
    }
  ],
  "total": 842,
  "page": 1,
  "size": 50
}
```

Results MUST be ordered by `created_at DESC` (newest first).

### SCENARIO 6.1.1 — Admin retrieves audit log (no filters)

```
Given tenant ACME has 842 audit entries
When admin calls GET /api/v1/audit-log
Then response is HTTP 200
And items contains 50 entries (default page size)
And total = 842
And items are ordered by created_at DESC
```

### SCENARIO 6.1.2 — Non-admin is rejected

```
Given a user with role "user"
When GET /api/v1/audit-log
Then response is HTTP 403
```

### SCENARIO 6.1.3 — Filter by action

```
Given tenant ACME has 10 template_upload events and 30 document_generate events
When GET /api/v1/audit-log?action=template_upload
Then response contains only 10 entries
And every item has action = "template_upload"
```

### SCENARIO 6.1.4 — Filter by actor_id

```
Given user Alice (actor_id=X) has performed 5 actions
When GET /api/v1/audit-log?actor_id=X
Then response contains exactly 5 entries
And every item has actor_id = X
```

### SCENARIO 6.1.5 — Filter by date range

```
Given events exist from 2026-04-01 to 2026-04-07
When GET /api/v1/audit-log?date_from=2026-04-05T00:00:00Z&date_to=2026-04-06T23:59:59Z
Then only events where created_at falls within [date_from, date_to] are returned
```

### SCENARIO 6.1.6 — Tenant isolation

```
Given two tenants: ACME (admin A) and BETA (admin B)
When admin A calls GET /api/v1/audit-log
Then only audit logs with tenant_id = ACME's tenant_id are returned
And BETA's audit data is NEVER included
```

### SCENARIO 6.1.7 — Invalid action filter

```
When GET /api/v1/audit-log?action=not_a_valid_action
Then response is HTTP 422
And the error references the invalid "action" parameter
```

### SCENARIO 6.1.8 — Pagination navigates correctly

```
Given 120 audit entries for tenant ACME
When GET /api/v1/audit-log?page=2&size=50
Then items contains entries 51–100 (by created_at DESC order)
And total = 120
```

---

## 7. Scenarios — Audit Write Correctness

### SCENARIO 7.1 — Template upload creates audit entry

```
Given a user uploads a valid template
When POST /templates succeeds and returns HTTP 201
Then an AuditLog entry exists with:
  - action = "template_upload"
  - resource_type = "template"
  - resource_id = newly created template.id
  - actor_id = uploading user's ID
  - tenant_id = user's tenant_id
  - details.name = template name
  - details.variable_count = count of extracted variables
```

### SCENARIO 7.2 — Document generate creates audit entry

```
Given a user generates a document successfully
When POST /documents/generate returns HTTP 201
Then an AuditLog entry exists with:
  - action = "document_generate"
  - resource_type = "document"
  - resource_id = generated document.id
  - actor_id = generating user's ID
  - details.template_id = the template ID used
```

### SCENARIO 7.3 — Bulk generate creates a single audit entry

```
Given a user uploads an Excel with 5 rows (4 succeed, 1 fails)
When POST /documents/generate-bulk completes
Then exactly ONE AuditLog entry exists for this operation with:
  - action = "document_generate_bulk"
  - resource_id = batch_id
  - details.document_count = 4
  - details.error_count = 1
```

### SCENARIO 7.4 — Failed operation does NOT create an audit entry

```
Given a request that causes a domain exception (e.g. TemplateAccessDeniedError)
When the endpoint returns a 4xx error
Then NO AuditLog entry is created for that failed operation
```

### SCENARIO 7.5 — Audit write failure does not fail the parent request

```
Given AuditRepository.create() raises an unexpected exception
When POST /templates succeeds
Then the endpoint MUST still return HTTP 201
And a warning MUST be logged with the error details
And the audit write failure MUST be invisible to the caller
```

### SCENARIO 7.6 — Login audit entry includes IP address

```
Given a user logs in successfully from IP 203.0.113.5
When POST /auth/login returns HTTP 200
Then an AuditLog entry exists with:
  - action = "user_login"
  - ip_address = "203.0.113.5"
  - actor_id = authenticated user's ID
```

### SCENARIO 7.7 — User create is logged by the router

```
Given an admin creates a new user
When POST /users returns HTTP 201
Then an AuditLog entry exists with:
  - action = "user_create"
  - resource_type = "user"
  - resource_id = new user's ID
  - actor_id = admin's user ID
  - details.email = new user's email
  - details.role = "user"
```

---

## 8. Database Schema

### Table: `audit_logs`

```sql
CREATE TABLE audit_logs (
    id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id     UUID        NOT NULL REFERENCES tenants(id),
    actor_id      UUID        REFERENCES users(id),
    action        VARCHAR(50) NOT NULL,
    resource_type VARCHAR(30) NOT NULL,
    resource_id   UUID,
    details       JSONB,
    ip_address    VARCHAR(45),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Indexes for filtering and pagination
CREATE INDEX ix_audit_logs_tenant_created ON audit_logs (tenant_id, created_at DESC);
CREATE INDEX ix_audit_logs_action         ON audit_logs (action);
CREATE INDEX ix_audit_logs_actor          ON audit_logs (actor_id);
```

**No `updated_at` column** — this table is append-only. The repository port MUST NOT expose UPDATE or DELETE methods.

---

## 9. Infrastructure Layer Conventions

The SQLAlchemy model (`AuditLogModel`) MUST follow the existing `TenantMixin` pattern. The `details` column MUST use SQLAlchemy's `JSON` type (PostgreSQL maps this to JSONB). The `SQLAlchemyAuditRepository` MUST implement `AuditRepository`. Query for `list_paginated` MUST apply all filters as WHERE clauses and use `ORDER BY created_at DESC` with LIMIT/OFFSET for pagination.

---

## 10. Test Coverage Requirements

| Test | Type |
|---|---|
| `AuditService.log()` creates correct entity | Unit |
| `AuditService.log()` does not raise on repository failure | Unit |
| `AuditService.log()` with invalid action value raises ValueError | Unit |
| `TemplateService.upload_template()` schedules audit log via create_task | Unit |
| `TemplateService.delete_template()` schedules audit log | Unit |
| `TemplateService.share_template()` schedules audit log | Unit |
| `DocumentService.generate_single()` schedules audit log with correct resource_id | Unit |
| `DocumentService.generate_bulk()` schedules single audit log with correct counts | Unit |
| `DocumentService.generate_single()` does NOT create audit log on access denied | Unit |
| `FakeAuditRepository` implements `AuditRepository` with no UPDATE/DELETE | Unit |
| `GET /api/v1/audit-log` returns 403 for non-admin | Integration |
| `GET /api/v1/audit-log` returns paginated entries ordered by created_at DESC | Integration |
| `GET /api/v1/audit-log?action=template_upload` filters correctly | Integration |
| `GET /api/v1/audit-log?actor_id=X` filters correctly | Integration |
| `GET /api/v1/audit-log?date_from=...&date_to=...` filters by date range | Integration |
| Tenant isolation: admin A cannot see tenant B's logs | Integration |
| `POST /auth/login` creates user_login audit entry with ip_address | Integration |
| `POST /users` creates user_create audit entry | Integration |

---

## 11. Out of Scope

- Audit log export (CSV / PDF)
- Email or webhook notifications on audit events
- Real-time audit streaming
- Audit log retention policies or archival
- `auth.login_failed` action (the proposal listed it but it is excluded from this spec — it requires capturing failed attempts before the user object is resolved, which adds complexity; defer to a dedicated auth-hardening change)
