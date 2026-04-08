# Spec: tier-management

**Change**: subscription-tiers
**Domain**: tier-management
**Status**: draft
**Date**: 2026-04-07

---

## Overview

This domain introduces the `SubscriptionTier` entity and its persistence layer. Every tenant is assigned exactly one tier. Tiers govern all resource limits across the system. The seed migration creates three canonical tiers: Free, Pro, and Enterprise. Tier management is read-only for this change; admin CRUD is out of scope.

---

## Definitions

| Term | Definition |
|------|-----------|
| `SubscriptionTier` | Domain entity representing a named plan with resource limits. |
| `slug` | URL-safe lowercase identifier for a tier (e.g. `"free"`, `"pro"`, `"enterprise"`). Unique and stable — used for deterministic UUID generation. |
| `NULL limit` | When any `max_*` or `monthly_document_limit` field is `None` / `NULL` in the DB, it means the limit is **unlimited**. |
| `deterministic UUID` | UUID v5 derived from `uuid.NAMESPACE_DNS + slug`. Identical on every run, enabling the FK default in the migration. |
| `tier_id` | Foreign key on `tenants` pointing to `subscription_tiers.id`. |

---

## REQ-TM-01: SubscriptionTier Entity

**The system MUST define a `SubscriptionTier` dataclass in `domain/entities/subscription_tier.py` with the following fields:**

| Field | Type | Nullable | Description |
|-------|------|----------|-------------|
| `id` | `UUID` | No | Primary key. |
| `name` | `str` | No | Display name (e.g. `"Free"`, `"Pro"`, `"Enterprise"`). Max 100 chars. |
| `slug` | `str` | No | Unique, URL-safe identifier. Max 50 chars. |
| `monthly_document_limit` | `int \| None` | Yes | Max documents generated in a calendar month. `None` = unlimited. |
| `max_templates` | `int \| None` | Yes | Max templates a tenant may own. `None` = unlimited. |
| `max_users` | `int \| None` | Yes | Max users in a tenant. `None` = unlimited. |
| `bulk_generation_limit` | `int` | No | Max rows per bulk generation call. Default `10`. |
| `max_template_shares` | `int \| None` | Yes | Max active shares per tenant. `None` = unlimited. |
| `is_active` | `bool` | No | Soft-delete flag. Default `True`. |
| `created_at` | `datetime \| None` | Yes | Set by DB on INSERT. |
| `updated_at` | `datetime \| None` | Yes | Set by DB on UPDATE. |

**The entity MUST NOT contain any persistence or business logic.** It is a pure data container.

---

## REQ-TM-02: Seed Tier Values

**The migration MUST seed exactly three tiers with the following limits:**

| Field | Free | Pro | Enterprise |
|-------|------|-----|------------|
| `name` | `"Free"` | `"Pro"` | `"Enterprise"` |
| `slug` | `"free"` | `"pro"` | `"enterprise"` |
| `monthly_document_limit` | `50` | `500` | `5000` |
| `max_templates` | `5` | `50` | `NULL` |
| `max_users` | `3` | `20` | `NULL` |
| `bulk_generation_limit` | `5` | `25` | `100` |
| `max_template_shares` | `5` | `50` | `NULL` |
| `is_active` | `True` | `True` | `True` |

**The IDs for seed tiers MUST be deterministic UUIDs** computed as `uuid.uuid5(uuid.NAMESPACE_DNS, slug)`.

Free tier UUID: `uuid.uuid5(uuid.NAMESPACE_DNS, "free")`
Pro tier UUID: `uuid.uuid5(uuid.NAMESPACE_DNS, "pro")`
Enterprise tier UUID: `uuid.uuid5(uuid.NAMESPACE_DNS, "enterprise")`

---

## REQ-TM-03: Database Table

**The system MUST create a `subscription_tiers` table with the following DDL (Alembic migration `005_subscription_tiers`):**

```sql
CREATE TABLE subscription_tiers (
    id                      UUID        PRIMARY KEY,
    name                    VARCHAR(100) NOT NULL,
    slug                    VARCHAR(50)  NOT NULL UNIQUE,
    monthly_document_limit  INTEGER      NULL,
    max_templates           INTEGER      NULL,
    max_users               INTEGER      NULL,
    bulk_generation_limit   INTEGER      NOT NULL DEFAULT 10,
    max_template_shares     INTEGER      NULL,
    is_active               BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at              TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ  NOT NULL DEFAULT now()
);
```

**The migration MUST:**
1. Create `subscription_tiers` FIRST.
2. Insert all three seed rows BEFORE altering `tenants`.
3. Add `tier_id UUID NOT NULL REFERENCES subscription_tiers(id) DEFAULT '<free_uuid>'` to `tenants`.
4. Backfill any existing tenant rows that somehow lack `tier_id` with the Free tier UUID.

**The migration MUST be reversible** (downgrade removes the column and drops the table).

---

## REQ-TM-04: Tenant-Tier Association

**The `Tenant` entity MUST be updated to include `tier_id: UUID`.**

Existing field set (from `domain/entities/tenant.py`):
```python
id, name, slug, is_active, created_at, updated_at
```

New field: `tier_id: UUID` — required, no default at the domain layer (the DB default handles the migration).

**The `TenantModel` ORM model MUST add the `tier_id` column and FK relationship.**

**All existing tenants MUST be backfilled to the Free tier UUID during migration.** No tenant may have a NULL `tier_id` after migration.

---

## REQ-TM-05: SubscriptionTierRepository Port

**The system MUST define an abstract base class `SubscriptionTierRepository` in `domain/ports/subscription_tier_repository.py` with the following interface:**

```python
class SubscriptionTierRepository(ABC):
    @abstractmethod
    async def get_by_id(self, tier_id: UUID) -> SubscriptionTier | None: ...

    @abstractmethod
    async def get_by_slug(self, slug: str) -> SubscriptionTier | None: ...

    @abstractmethod
    async def list_active(self) -> list[SubscriptionTier]: ...
```

`list_active` MUST return only tiers where `is_active = True`, ordered by `monthly_document_limit ASC NULLS LAST` (Free first, Enterprise last).

---

## REQ-TM-06: SQLAlchemy Repository Adapter

**The system MUST implement `SQLAlchemySubscriptionTierRepository` in `infrastructure/persistence/repositories/subscription_tier_repository.py`** that satisfies the port above using SQLAlchemy async session.

**The ORM model `SubscriptionTierModel` MUST be placed in `infrastructure/persistence/models/subscription_tier.py`** and registered in the metadata / mapper configuration so Alembic detects it automatically.

---

## REQ-TM-07: FakeSubscriptionTierRepository (Test Double)

**The system MUST provide `FakeSubscriptionTierRepository` in `tests/fakes/` or `tests/unit/`** that stores tiers in memory and satisfies the `SubscriptionTierRepository` port. This fake MUST be used in all unit tests for `QuotaService` and tier-related service tests.

---

## Scenarios

### SC-TM-01: Seed tiers exist after migration

```
Given a fresh database with migration 005 applied
When the application queries subscription_tiers for all active tiers
Then exactly 3 rows are returned: Free, Pro, Enterprise
And each row has the limits defined in REQ-TM-02
And the Free tier UUID equals uuid.uuid5(uuid.NAMESPACE_DNS, "free")
```

### SC-TM-02: All existing tenants assigned Free tier on migration

```
Given a database with 5 existing tenants before migration 005
When migration 005 is applied
Then all 5 tenants have tier_id = Free tier UUID
And no tenant has tier_id = NULL
```

### SC-TM-03: New tenant defaults to Free tier

```
Given migration 005 is applied
When a new tenant is created without specifying tier_id
Then the tenant's tier_id equals the Free tier UUID
And a subsequent GET /api/v1/tenant/tier returns plan_name = "Free"
```

### SC-TM-04: get_by_slug returns correct tier

```
Given the Free tier exists in the database
When SubscriptionTierRepository.get_by_slug("free") is called
Then the returned entity has name = "Free", monthly_document_limit = 50
```

### SC-TM-05: Inactive tier excluded from list_active

```
Given the Pro tier exists with is_active = False
When SubscriptionTierRepository.list_active() is called
Then the Pro tier is NOT in the results
And Free and Enterprise are returned
```

### SC-TM-06: Deterministic UUIDs are stable across invocations

```
Given uuid.uuid5(uuid.NAMESPACE_DNS, "free") computed at any time
Then the result is always the same UUID
And this UUID matches the id stored in subscription_tiers for slug "free"
```

---

## Test Requirements

| Test ID | Type | Description |
|---------|------|-------------|
| `test_subscription_tier_entity` | Unit | SubscriptionTier dataclass fields, None defaults for unlimited fields. |
| `test_seed_tier_values` | Unit | Verify Free/Pro/Enterprise limit constants match REQ-TM-02. |
| `test_fake_tier_repo_get_by_slug` | Unit | FakeSubscriptionTierRepository.get_by_slug returns correct entity. |
| `test_fake_tier_repo_list_active` | Unit | FakeSubscriptionTierRepository.list_active filters inactive tiers. |
| `test_migration_005_idempotent` | Integration | Migration 005 up/down/up runs without error. |
| `test_migration_005_backfills_tenants` | Integration | Existing tenants get Free tier UUID after migration. |
