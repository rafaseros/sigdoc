# Spec: Admin Seed Unification

**Change**: `admin-seed-and-email-workflows`
**Module**: `admin-seed`
**Status**: specified

## Requirements

### REQ-SEED-01: Idempotent Admin Seed Migration

A new Alembic migration (008) SHALL ensure the canonical admin user exists in the "default" tenant.

**Canonical admin identity**:
- Email: `devrafaseros@gmail.com`
- Full name: `Jose Rafael Gallegos Rojas`
- Role: `admin`
- Password: value of `ADMIN_PASSWORD` env var (REQUIRED — migration fails if not set)

**Idempotent behavior**:
- If a user with email `devrafaseros@gmail.com` already exists (in ANY tenant):
  - Update `full_name` to `Jose Rafael Gallegos Rojas`
  - Update `role` to `admin`
  - Do NOT change `hashed_password`
  - Do NOT change `tenant_id`
  - Do NOT change `is_active`
- If NO user with that email exists:
  - Find or create the "default" tenant (by slug `default`)
  - Create the user with hashed `ADMIN_PASSWORD`

### REQ-SEED-02: Config Cleanup

Remove the following defaults from `Settings`:
- `admin_email` default `"admin@sigdoc.local"` — remove the field entirely
- `admin_password` default `"admin123"` — remove the field entirely

These fields are no longer needed in the application config. The seed migration reads `ADMIN_PASSWORD` directly from `os.environ`.

### REQ-SEED-03: Migration Safety

- The migration MUST NOT fail if the user already exists (upsert semantics)
- The migration MUST fail fast with a clear error if `ADMIN_PASSWORD` env var is missing AND no user exists yet (cannot create without password)
- The migration MUST be re-runnable (downgrade is a no-op for the upsert; it does NOT delete the admin user)

## Scenarios

### SCEN-SEED-01: Fresh database (no admin exists)
**Given** no user with email `devrafaseros@gmail.com` exists
**And** `ADMIN_PASSWORD` env var is set to `"mysecurepass"`
**And** a tenant with slug `default` exists
**When** migration 008 runs
**Then** a new user is created with email `devrafaseros@gmail.com`, name `Jose Rafael Gallegos Rojas`, role `admin`, hashed password from `"mysecurepass"`, in the default tenant

### SCEN-SEED-02: Admin already exists with old email (prod scenario)
**Given** a user with email `devrafaseros@gmail.com` exists with `full_name="System Admin"` and `role="admin"`
**When** migration 008 runs
**Then** `full_name` is updated to `Jose Rafael Gallegos Rojas`
**And** `hashed_password` is NOT changed
**And** `role` remains `admin`

### SCEN-SEED-03: Admin exists but was demoted
**Given** a user with email `devrafaseros@gmail.com` exists with `role="user"`
**When** migration 008 runs
**Then** `role` is updated to `admin`

### SCEN-SEED-04: No ADMIN_PASSWORD and no existing user
**Given** no user with email `devrafaseros@gmail.com` exists
**And** `ADMIN_PASSWORD` env var is NOT set
**When** migration 008 runs
**Then** the migration fails with a clear error message

### SCEN-SEED-05: No ADMIN_PASSWORD but user already exists
**Given** a user with email `devrafaseros@gmail.com` already exists
**And** `ADMIN_PASSWORD` env var is NOT set
**When** migration 008 runs
**Then** the migration succeeds (password not needed for update)
