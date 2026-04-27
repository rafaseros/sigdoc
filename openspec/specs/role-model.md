# Capability: role-model

## Purpose

Defines the 3-role taxonomy (`admin`, `template_creator`, `document_generator`), the data migration that promotes existing `user` rows to `template_creator`, the `document_generator` default for all new non-signup users, role validation in request schemas, and the JWT refresh-from-DB contract that ensures role changes propagate immediately on the next token refresh.

## Requirements

### REQ-ROLE-01: Three-role taxonomy

The system MUST define exactly three valid role values: `admin`, `template_creator`, and `document_generator`. No other role string is accepted at any user-creation or user-update endpoint. Any value outside this set MUST be rejected with HTTP 422.

### REQ-ROLE-02: Migration 011 — data upgrade idempotency

Migration `011_role_expansion.py` upgrade MUST update all `users` rows where `role = 'user'` to `role = 'template_creator'`. The migration MUST be idempotent: re-running the upgrade on a database that has already been migrated has no effect because no rows with `role = 'user'` remain after the first run.

### REQ-ROLE-03: Migration 011 — column default change

Migration `011_role_expansion.py` upgrade MUST change the `users.role` column server default to `'document_generator'`. Downgrade MUST revert the server default to `'user'` and collapse both `template_creator` and `document_generator` rows back to `'user'` (lossy; acceptable for emergency rollback only).

### REQ-ROLE-04: Domain entity default

The `User` domain entity (at `backend/src/app/domain/entities/user.py`) MUST default `role` to `'document_generator'` when no role is provided at construction time.

### REQ-ROLE-05: SQLAlchemy model defaults

The `UserModel.role` column (at `backend/src/app/infrastructure/persistence/models/user.py`) MUST carry both `default='document_generator'` (Python-side) and `server_default='document_generator'` (DB-side).

### REQ-ROLE-06: Request schema validation

`UpdateUserRequest` (at `backend/src/app/presentation/schemas/user.py`) MUST accept `role` values of `"admin"`, `"template_creator"`, and `"document_generator"` only. Any other value MUST cause HTTP 422 with an error message that names the three allowed values. `CreateUserRequest` does not accept a `role` field (role is always assigned server-side).

### REQ-ROLE-07: Signup first-user role unchanged

The signup flow (`signup_service.py`) MUST continue to assign `role='admin'` to the first user of a new tenant. This is an explicit assignment and is unaffected by the default change.

### REQ-ROLE-08: Admin-created user default role

When an admin calls `POST /users` without a `role` field in the request body, the system MUST assign `role='document_generator'` to the created user (least-privilege default).

### REQ-ROLE-09: JWT refresh role re-fetch from DB

`POST /auth/refresh` MUST NOT use any `role` value carried in the refresh token payload. The endpoint MUST re-fetch the user record from the database using the `sub` claim and derive `role` from the live DB row. The issued access token MUST reflect the role stored in the database at the time of the refresh call.

### REQ-ROLE-10: Refresh rejects deleted/deactivated users

If the user identified by the refresh token's `sub` claim no longer exists in the database at refresh time, `POST /auth/refresh` MUST return HTTP 401 and MUST NOT issue a new access token.

## Scenarios

### SCEN-ROLE-01: Migration upgrade transforms legacy rows
**Given**: A database with rows having roles `['admin', 'user', 'user']`
**When**: Migration `011_role_expansion.py` `upgrade()` runs
**Then**: Roles become `['admin', 'template_creator', 'template_creator']`
**And**: No `'user'` role values remain in the table

### SCEN-ROLE-02: Migration downgrade collapses roles
**Given**: A database with rows having roles `['admin', 'template_creator', 'document_generator']`
**When**: Migration `011_role_expansion.py` `downgrade()` runs
**Then**: Roles become `['admin', 'user', 'user']`
**And**: The column server default reverts to `'user'`

### SCEN-ROLE-03: Admin creates user with explicit valid role
**Given**: An authenticated admin user
**When**: Admin POSTs `/users` with `role="document_generator"`
**Then**: HTTP 201 is returned
**And**: The created user has `role="document_generator"`

### SCEN-ROLE-04: Legacy role value rejected at creation time
**Given**: An authenticated admin user
**When**: Admin POSTs `/users` with `role="user"`
**Then**: HTTP 422 is returned
**And**: The error response names the three allowed role values

### SCEN-ROLE-05: Missing role defaults to document_generator (satisfies REQ-ROLE-08)
**Given**: An authenticated admin user
**When**: Admin POSTs `/users` with no `role` field in the request body
**Then**: HTTP 201 is returned
**And**: The created user has `role="document_generator"`

### SCEN-ROLE-06: Refreshed token carries DB-current role (satisfies REQ-ROLE-09)
**Given**: A user with `role='document_generator'` who holds a valid refresh token
**And**: An admin has since changed that user's role to `template_creator` in the DB
**When**: The user calls `POST /auth/refresh` with their existing refresh token
**Then**: The new access token carries `role="template_creator"` (from DB)
**And**: The old refresh-token role claim (if any) is ignored

### SCEN-ROLE-07: Refresh rejected for deleted user (satisfies REQ-ROLE-10)
**Given**: A user X who holds a valid refresh token
**And**: An admin has deleted user X from the database
**When**: User X calls `POST /auth/refresh`
**Then**: HTTP 401 is returned
**And**: No new access token is issued

### SCEN-ROLE-08: Signup creates admin; second user defaults to document_generator
**Given**: A brand-new tenant with no users
**When**: Signup endpoint creates the first user
**Then**: That user has `role="admin"`
**And**: When the admin subsequently creates a second user via `POST /users` without specifying a role, that user has `role="document_generator"`

### SCEN-ROLE-09: User entity instantiated with no role argument (satisfies REQ-ROLE-04)
**Given**: The `User` domain entity class
**When**: An instance is created with no `role` argument
**Then**: The instance's `role` attribute equals `"document_generator"`

### SCEN-ROLE-10: UpdateUserRequest rejects invalid role value (satisfies REQ-ROLE-06)
**Given**: A valid `UpdateUserRequest` payload
**When**: `role="invalid_value"` is passed
**Then**: Pydantic raises a validation error naming the three allowed values
**And**: No database write occurs
