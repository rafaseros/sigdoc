# Spec: quota-enforcement

**Change**: subscription-tiers
**Domain**: quota-enforcement
**Status**: draft
**Date**: 2026-04-07

---

## Overview

This domain introduces `QuotaService` — the central enforcement point for all tier-based resource limits. It is called by `DocumentService`, `TemplateService`, and the user-creation router **before** the operation is performed (fail-fast). It also introduces `QuotaExceededError`, mapped to HTTP 429 at the presentation layer.

---

## Definitions

| Term | Definition |
|------|-----------|
| `QuotaService` | Application-layer service that checks all tier limits. |
| `QuotaExceededError` | Domain exception raised when a limit is breached. Carries structured details (limit type, limit value, current usage). |
| `effective_bulk_limit` | `min(user.bulk_generation_limit, tier.bulk_generation_limit)` when `user.bulk_generation_limit` is set; otherwise `tier.bulk_generation_limit`. |
| `current_month_docs` | Sum of `document_count` from `usage_events` for this `tenant_id` where `created_at` is in the current calendar month (UTC). |
| `resource_type` | Enum/literal discriminating what limit was hit: `"documents"`, `"templates"`, `"users"`, `"bulk"`, `"shares"`. |

---

## REQ-QE-01: QuotaExceededError Domain Exception

**The system MUST add `QuotaExceededError` to `domain/exceptions.py` with the following fields:**

```python
class QuotaExceededError(DomainError):
    resource_type: str        # "documents" | "templates" | "users" | "bulk" | "shares"
    limit_value: int | None   # The tier's limit (None if computed dynamically)
    current_usage: int        # How many are currently in use
    message: str              # Human-readable reason
```

**The presentation layer MUST map `QuotaExceededError` to HTTP 429** with a structured JSON body:

```json
{
  "error": "quota_exceeded",
  "resource_type": "documents",
  "limit_value": 50,
  "current_usage": 50,
  "message": "Monthly document limit of 50 reached. Upgrade your plan to generate more documents."
}
```

**`BulkLimitExceededError` MUST remain** for backward compatibility with existing tests. The quota-enforcement path raises `QuotaExceededError(resource_type="bulk", ...)` instead, but `BulkLimitExceededError` is not removed.

---

## REQ-QE-02: QuotaService Interface

**The system MUST implement `QuotaService` in `application/services/quota_service.py`.**

**Constructor dependencies:**
```python
class QuotaService:
    def __init__(
        self,
        tier_repository: SubscriptionTierRepository,
        usage_repository: UsageRepository,
        template_repository: TemplateRepository,
        user_repository: UserRepository,
    ): ...
```

**All methods MUST be `async`.** All methods MUST raise `QuotaExceededError` when the limit is breached. When a limit field is `None` on the tier, the method MUST return immediately without raising (unlimited).

---

## REQ-QE-03: check_document_quota

**Signature:**
```python
async def check_document_quota(
    self,
    tenant_id: UUID,
    user_id: UUID,
    additional: int = 1,
) -> None
```

**Logic:**
1. Load tenant's tier via `tier_repository.get_by_id(tenant.tier_id)`.
2. If `tier.monthly_document_limit is None` → return (unlimited).
3. Query `usage_repository.get_monthly_count(tenant_id, current_month)` → `current`.
4. If `current + additional > tier.monthly_document_limit` → raise `QuotaExceededError(resource_type="documents", limit_value=tier.monthly_document_limit, current_usage=current)`.

**The `additional` parameter defaults to `1` for single-document generation. For bulk generation it MUST be `len(rows)`.**

The method MUST load the tenant's `tier_id` via the `TenantRepository` (injected or passed as argument — see REQ-QE-07 for DI details).

---

## REQ-QE-04: check_template_limit

**Signature:**
```python
async def check_template_limit(self, tenant_id: UUID) -> None
```

**Logic:**
1. Load tier for tenant.
2. If `tier.max_templates is None` → return.
3. Count templates owned by tenant: `template_repository.count_by_tenant(tenant_id)` → `current`.
4. If `current >= tier.max_templates` → raise `QuotaExceededError(resource_type="templates", limit_value=tier.max_templates, current_usage=current)`.

---

## REQ-QE-05: check_user_limit

**Signature:**
```python
async def check_user_limit(self, tenant_id: UUID) -> None
```

**Logic:**
1. Load tier for tenant.
2. If `tier.max_users is None` → return.
3. Count active users in tenant: `user_repository.count_active_by_tenant(tenant_id)` → `current`.
4. If `current >= tier.max_users` → raise `QuotaExceededError(resource_type="users", limit_value=tier.max_users, current_usage=current)`.

---

## REQ-QE-06: check_bulk_limit

**Signature:**
```python
async def check_bulk_limit(
    self,
    tenant_id: UUID,
    user_id: UUID,
    requested_count: int,
) -> None
```

**Logic:**
1. Load tier for tenant.
2. Load user to check `user.bulk_generation_limit`.
3. Compute `effective_limit`:
   - If `user.bulk_generation_limit is not None` → `effective_limit = min(user.bulk_generation_limit, tier.bulk_generation_limit)`
   - Else → `effective_limit = tier.bulk_generation_limit`
4. If `requested_count > effective_limit` → raise `QuotaExceededError(resource_type="bulk", limit_value=effective_limit, current_usage=requested_count)`.

**Note**: `bulk_generation_limit` on the tier is NOT nullable. Enterprise tier has value `100`. There is no "unlimited" for bulk — even Enterprise has a cap (preventing runaway single requests).

---

## REQ-QE-07: check_share_limit

**Signature:**
```python
async def check_share_limit(self, tenant_id: UUID, template_id: UUID) -> None
```

**Logic:**
1. Load tier for tenant.
2. If `tier.max_template_shares is None` → return.
3. Count active shares for this tenant: `template_repository.count_shares_by_tenant(tenant_id)` → `current`.
4. If `current >= tier.max_template_shares` → raise `QuotaExceededError(resource_type="shares", limit_value=tier.max_template_shares, current_usage=current)`.

**Rationale**: shares are counted tenant-wide, not per-template. A Free tenant with 5 share slots can distribute them across any templates, but the total cannot exceed 5.

---

## REQ-QE-08: QuotaService Dependency Injection

**`QuotaService` MUST be optional in `DocumentService` and `TemplateService` constructors** to preserve backward compatibility with existing tests:

```python
# DocumentService.__init__ (new parameter, keyword-only, default None)
quota_service: QuotaService | None = None

# TemplateService.__init__ (new parameter, keyword-only, default None)
quota_service: QuotaService | None = None
```

**When `quota_service is None`**, the service MUST skip quota checks and proceed as before. This is not the production path — in production, `QuotaService` is always injected via `services/__init__.py` (the DI factory).

**For user creation**, `QuotaService` MUST be injected via FastAPI `Depends()` in the users router.

---

## REQ-QE-09: Integration into DocumentService

**`DocumentService.generate_single()` MUST call `quota_service.check_document_quota(tenant_id, user_id, additional=1)` as the FIRST operation** (before any template or storage access):

```python
if self._quota_service is not None:
    await self._quota_service.check_document_quota(
        uuid.UUID(tenant_id), uuid.UUID(created_by)
    )
```

**`DocumentService.generate_bulk()` MUST call both checks as the FIRST operations:**

```python
if self._quota_service is not None:
    await self._quota_service.check_document_quota(
        uuid.UUID(tenant_id), uuid.UUID(created_by), additional=len(rows)
    )
    await self._quota_service.check_bulk_limit(
        uuid.UUID(tenant_id), uuid.UUID(created_by), len(rows)
    )
```

**`DocumentService.parse_excel_data()` MUST replace the hardcoded `self._bulk_limit` check** with a call to `check_bulk_limit` when `quota_service` is present. The old path (`self._bulk_limit`) MUST remain when `quota_service is None`:

```python
if self._quota_service is not None:
    # bulk limit is checked here during parsing, before generate_bulk is called
    # tenant_id and user_id must be passed to parse_excel_data
    await self._quota_service.check_bulk_limit(tenant_id, user_id, len(rows))
else:
    if len(rows) > self._bulk_limit:
        raise BulkLimitExceededError(limit=self._bulk_limit)
```

**Impact**: `parse_excel_data` signature MUST be extended with `tenant_id: UUID | None = None` and `user_id: UUID | None = None` to support this check. These are optional to maintain backward compatibility.

---

## REQ-QE-10: Integration into TemplateService

**`TemplateService.upload_template()` MUST call `quota_service.check_template_limit(tenant_id)` as the FIRST operation:**

```python
if self._quota_service is not None:
    await self._quota_service.check_template_limit(uuid.UUID(tenant_id))
```

**`TemplateService.share_template()` MUST call `quota_service.check_share_limit(tenant_id, template_id)` BEFORE calling `self._repository.add_share()`:**

```python
if self._quota_service is not None:
    await self._quota_service.check_share_limit(tenant_id, template_id)
```

---

## REQ-QE-11: Repository Port Extensions

The following methods MUST be added to existing ports (or implemented in fakes for tests):

| Port | New Method | Return Type |
|------|-----------|-------------|
| `TemplateRepository` | `count_by_tenant(tenant_id: UUID) -> int` | `int` — count of templates owned by tenant |
| `TemplateRepository` | `count_shares_by_tenant(tenant_id: UUID) -> int` | `int` — count of active shares for tenant |
| `UserRepository` | `count_active_by_tenant(tenant_id: UUID) -> int` | `int` — count of users with `is_active=True` |
| `UsageRepository` | `get_monthly_count(tenant_id: UUID, year: int, month: int) -> int` | `int` — sum of `document_count` for the calendar month |

**All methods MUST be `async`.**

---

## REQ-QE-12: FakeQuotaService (Test Double)

**The system MUST provide `FakeQuotaService` in `tests/fakes/`** with the following behavior:

```python
class FakeQuotaService:
    """Configurable quota service for testing.

    By default: all checks pass. Set exceeded_resource to simulate a failure.
    """
    exceeded_resource: str | None = None  # "documents" | "templates" | "users" | "bulk" | "shares"

    async def check_document_quota(self, tenant_id, user_id, additional=1): ...
    async def check_template_limit(self, tenant_id): ...
    async def check_user_limit(self, tenant_id): ...
    async def check_bulk_limit(self, tenant_id, user_id, requested_count): ...
    async def check_share_limit(self, tenant_id, template_id): ...
```

When `exceeded_resource` matches the check being performed, the fake MUST raise `QuotaExceededError` with deterministic test values. This allows service tests to verify that the service correctly surfaces quota errors to callers.

---

## Scenarios

### SC-QE-01: Document quota passes when under limit

```
Given a tenant on the Free plan (monthly_document_limit = 50)
And the tenant has generated 30 documents this month
When QuotaService.check_document_quota(tenant_id, user_id, additional=1) is called
Then no exception is raised
```

### SC-QE-02: Document quota fails when at limit

```
Given a tenant on the Free plan (monthly_document_limit = 50)
And the tenant has generated 50 documents this month
When QuotaService.check_document_quota(tenant_id, user_id, additional=1) is called
Then QuotaExceededError is raised
And error.resource_type = "documents"
And error.limit_value = 50
And error.current_usage = 50
```

### SC-QE-03: Document quota fails for bulk that would exceed limit

```
Given a tenant on the Free plan (monthly_document_limit = 50)
And the tenant has generated 45 documents this month
When QuotaService.check_document_quota(tenant_id, user_id, additional=10) is called
Then QuotaExceededError is raised
And error.current_usage = 45
And error.limit_value = 50
```

### SC-QE-04: Enterprise tenant has no document quota

```
Given a tenant on the Enterprise plan (monthly_document_limit = 5000)
And the tenant has generated 4999 documents this month
When QuotaService.check_document_quota(tenant_id, user_id, additional=1) is called
Then no exception is raised
```

### SC-QE-05: Template limit blocks upload when at max

```
Given a tenant on the Free plan (max_templates = 5)
And the tenant owns 5 templates
When QuotaService.check_template_limit(tenant_id) is called
Then QuotaExceededError is raised
And error.resource_type = "templates"
And error.current_usage = 5
And error.limit_value = 5
```

### SC-QE-06: Enterprise tenant has unlimited templates

```
Given a tenant on the Enterprise plan (max_templates = NULL)
And the tenant owns 10000 templates
When QuotaService.check_template_limit(tenant_id) is called
Then no exception is raised
```

### SC-QE-07: User limit blocks creation when at max

```
Given a tenant on the Free plan (max_users = 3)
And the tenant has 3 active users
When QuotaService.check_user_limit(tenant_id) is called
Then QuotaExceededError is raised
And error.resource_type = "users"
And error.limit_value = 3
And error.current_usage = 3
```

### SC-QE-08: Bulk limit — tier limit applies (no per-user override)

```
Given a tenant on the Free plan (bulk_generation_limit = 5)
And the user has bulk_generation_limit = NULL (no override)
When QuotaService.check_bulk_limit(tenant_id, user_id, requested_count=6) is called
Then QuotaExceededError is raised
And error.resource_type = "bulk"
And error.limit_value = 5
```

### SC-QE-09: Bulk limit — per-user override is lower than tier

```
Given a tenant on the Pro plan (bulk_generation_limit = 25)
And the user has bulk_generation_limit = 10
When QuotaService.check_bulk_limit(tenant_id, user_id, requested_count=15) is called
Then QuotaExceededError is raised
And error.limit_value = 10
```

### SC-QE-10: Bulk limit — per-user override is higher (but capped at tier)

```
Given a tenant on the Free plan (bulk_generation_limit = 5)
And the user has bulk_generation_limit = 100
When QuotaService.check_bulk_limit(tenant_id, user_id, requested_count=6) is called
Then QuotaExceededError is raised
And error.limit_value = 5
```

### SC-QE-11: Share limit blocks sharing when at max

```
Given a tenant on the Free plan (max_template_shares = 5)
And the tenant has 5 active template shares across all templates
When QuotaService.check_share_limit(tenant_id, template_id) is called
Then QuotaExceededError is raised
And error.resource_type = "shares"
And error.limit_value = 5
And error.current_usage = 5
```

### SC-QE-12: Share limit — Enterprise has unlimited shares

```
Given a tenant on the Enterprise plan (max_template_shares = NULL)
And the tenant has 1000 active shares
When QuotaService.check_share_limit(tenant_id, template_id) is called
Then no exception is raised
```

### SC-QE-13: DocumentService.generate_single raises HTTP 429 on quota breach

```
Given a tenant on the Free plan with monthly limit exhausted
And QuotaService is injected into DocumentService
When POST /api/v1/documents is called
Then the response status is 429
And the response body has error = "quota_exceeded"
And resource_type = "documents"
```

### SC-QE-14: DocumentService with no QuotaService skips check (backward compat)

```
Given DocumentService is instantiated without quota_service (quota_service=None)
And a tenant whose document limit would be exceeded
When DocumentService.generate_single() is called
Then no QuotaExceededError is raised
And the document is generated normally
```

### SC-QE-15: Template upload fails with 429 when template limit exceeded

```
Given a tenant on the Free plan with 5/5 templates used
And QuotaService is injected into TemplateService
When POST /api/v1/templates is called
Then the response status is 429
And resource_type = "templates"
```

### SC-QE-16: User creation fails with 429 when user limit exceeded

```
Given a tenant on the Free plan with 3/3 users active
And QuotaService is injected in the users router via Depends()
When POST /api/v1/users is called
Then the response status is 429
And resource_type = "users"
```

### SC-QE-17: Template sharing fails with 429 when share limit exceeded

```
Given a tenant on the Free plan with 5/5 shares used
And QuotaService is injected into TemplateService
When POST /api/v1/templates/{id}/share is called
Then the response status is 429
And resource_type = "shares"
```

### SC-QE-18: parse_excel_data check_bulk_limit (with quota service)

```
Given a tenant on the Free plan (bulk_generation_limit = 5)
And QuotaService is injected into DocumentService
When DocumentService.parse_excel_data() is called with an Excel file containing 6 rows
Then QuotaExceededError is raised with resource_type = "bulk"
And BulkLimitExceededError is NOT raised
```

---

## Test Requirements

| Test ID | Type | Description |
|---------|------|-------------|
| `test_quota_service_doc_under_limit` | Unit | SC-QE-01: passes when under limit. |
| `test_quota_service_doc_at_limit` | Unit | SC-QE-02: raises on exact limit. |
| `test_quota_service_doc_bulk_would_exceed` | Unit | SC-QE-03: additional pushes over limit. |
| `test_quota_service_doc_unlimited` | Unit | SC-QE-04: unlimited tier always passes. |
| `test_quota_service_template_at_limit` | Unit | SC-QE-05: template limit raises. |
| `test_quota_service_template_unlimited` | Unit | SC-QE-06: unlimited templates. |
| `test_quota_service_user_at_limit` | Unit | SC-QE-07: user limit raises. |
| `test_quota_service_bulk_tier_limit` | Unit | SC-QE-08: tier cap, no user override. |
| `test_quota_service_bulk_user_override_lower` | Unit | SC-QE-09: user override wins when lower. |
| `test_quota_service_bulk_user_override_higher` | Unit | SC-QE-10: tier still caps when user override is higher. |
| `test_quota_service_share_at_limit` | Unit | SC-QE-11: share limit raises. |
| `test_quota_service_share_unlimited` | Unit | SC-QE-12: unlimited shares. |
| `test_document_service_quota_called_before_generation` | Unit | generate_single calls quota before template fetch. |
| `test_document_service_no_quota_service_compat` | Unit | SC-QE-14: no quota_service, no check performed. |
| `test_document_service_bulk_quota_called` | Unit | generate_bulk calls both doc quota + bulk limit. |
| `test_parse_excel_data_quota_service_bulk_limit` | Unit | SC-QE-18: parse_excel_data uses QuotaService. |
| `test_template_service_upload_quota_called` | Unit | upload_template calls check_template_limit first. |
| `test_template_service_share_quota_called` | Unit | share_template calls check_share_limit before add_share. |
| `test_quota_exceeded_maps_to_429` | Integration | HTTP 429 returned with correct body shape. |
| `test_user_creation_quota_enforced` | Integration | POST /users returns 429 when user limit exhausted. |
