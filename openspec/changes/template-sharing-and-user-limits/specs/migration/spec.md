# migration Specification

## Purpose

Defines the Alembic migration required to introduce `template_shares` table and `users.bulk_generation_limit` column, plus the backfill strategy to avoid breaking existing data.

## Requirements

### Requirement: template_shares Table

The migration MUST create a `template_shares` table with the following columns:

| Column | Type | Constraints |
|--------|------|-------------|
| `id` | UUID | PK |
| `template_id` | UUID | FK → templates.id, ON DELETE CASCADE |
| `user_id` | UUID | FK → users.id, ON DELETE CASCADE |
| `tenant_id` | UUID | FK → tenants.id, NOT NULL |
| `shared_by` | UUID | FK → users.id, NOT NULL |
| `shared_at` | TIMESTAMP | NOT NULL, server_default=now() |

A unique constraint MUST exist on `(template_id, user_id)`.
An index MUST exist on `(template_id, user_id)` for fast lookup.

#### Scenario: Migration up creates table

- GIVEN a database with the current schema (no `template_shares`)
- WHEN the migration is applied (upgrade)
- THEN the `template_shares` table MUST exist with all specified columns and constraints

#### Scenario: Migration down drops table

- GIVEN a database with `template_shares` table
- WHEN the migration is downgraded
- THEN the `template_shares` table MUST be dropped without error

---

### Requirement: users.bulk_generation_limit Column

The migration MUST add a `bulk_generation_limit` nullable integer column to the `users` table.

| Column | Type | Constraints |
|--------|------|-------------|
| `bulk_generation_limit` | INTEGER | NULLABLE, no default |

#### Scenario: Migration up adds column

- GIVEN a database where `users` has no `bulk_generation_limit`
- WHEN the migration is applied
- THEN `users.bulk_generation_limit` MUST exist and all existing rows MUST have NULL

#### Scenario: Migration down removes column

- GIVEN a database where `users.bulk_generation_limit` exists
- WHEN the migration is downgraded
- THEN the column MUST be dropped without error

---

### Requirement: Backfill Strategy — Private by Default

Existing templates MUST NOT lose accessibility for their owners. The backfill MUST NOT insert shares for existing templates — instead, the repository's `list_accessible` query MUST always include templates where `created_by = requesting_user`. No data-fill is needed.

#### Scenario: Existing template owner still sees their template post-migration

- GIVEN template T was created by user A before the migration
- WHEN the migration is applied
- AND user A lists templates
- THEN template T MUST appear in user A's listing

#### Scenario: Existing template invisible to peers post-migration

- GIVEN template T was created by user A before the migration
- AND user B has never had a share
- WHEN the migration is applied
- AND user B lists templates
- THEN template T MUST NOT appear in user B's listing

#### Scenario: Admin still sees all templates post-migration

- GIVEN templates owned by multiple users before migration
- WHEN the migration is applied
- AND a tenant admin lists templates
- THEN all templates MUST appear in the admin listing

---

### Requirement: Migration Atomicity and Safety

The migration MUST be applied as a single Alembic revision. Both the `template_shares` table creation and the `bulk_generation_limit` column addition MUST be in the same revision file.

#### Scenario: Partial failure rolled back

- GIVEN a database where the migration is partially applied (e.g., table created but column not added)
- WHEN the migration fails mid-way
- THEN the entire migration MUST be rolled back (Alembic transactional DDL where DB supports it)
