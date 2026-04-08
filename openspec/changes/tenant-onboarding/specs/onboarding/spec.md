# Spec: Self-Service Tenant Onboarding

**Change**: `tenant-onboarding`
**Status**: specified
**Date**: 2026-04-07

---

## Requirements

### REQ-SIGNUP-01: Public Signup Endpoint
`POST /api/v1/auth/signup` accepts a JSON body and creates a new tenant + admin user atomically.

**Input schema** (`SignupRequest`):
| Field | Type | Constraints |
|-------|------|------------|
| `email` | string | Required, valid email format, max 255 chars |
| `password` | string | Required, min 8 chars, max 128 chars |
| `full_name` | string | Required, min 1 char, max 255 chars |
| `organization_name` | string | Required, min 2 chars, max 255 chars |

**Success response** (201 Created):
```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer"
}
```

**Error responses**:
| Status | Condition | Body |
|--------|-----------|------|
| 409 | Email already registered | `{"detail": "Email already registered"}` |
| 409 | Organization name taken | `{"detail": "Organization name already taken"}` |
| 422 | Validation error | Standard pydantic 422 |
| 429 | Rate limit exceeded | Standard slowapi 429 |

### REQ-SIGNUP-02: Atomic Transaction
Tenant creation, user creation, tier assignment, and audit logging MUST happen in a single database transaction. If any step fails, ALL changes are rolled back.

### REQ-SIGNUP-03: Global Email Uniqueness
User emails MUST be globally unique across all tenants. The `users` table gains a unique index on `email` (in addition to the existing `uq_users_tenant_email` composite constraint).

### REQ-SIGNUP-04: Organization Name Uniqueness
Tenant names MUST be unique (case-insensitive comparison). The `tenants` table gains a unique constraint on `name`.

### REQ-SIGNUP-05: Tenant Slug Generation
The tenant slug is derived from `organization_name`:
1. Lowercase
2. Replace non-alphanumeric characters with hyphens
3. Collapse consecutive hyphens
4. Strip leading/trailing hyphens
5. Truncate to 80 chars
6. If slug already exists, append `-{n}` (n=2,3,...)

### REQ-SIGNUP-06: Free Tier Auto-Assignment
New tenants are automatically assigned the Free tier (`uuid5(NAMESPACE_DNS, "sigdoc.tier.free")`).

### REQ-SIGNUP-07: Admin Role
The user created during signup is assigned `role="admin"` for their new tenant.

### REQ-SIGNUP-08: Immediate Authentication
On successful signup, the response includes valid JWT tokens (same format as `/auth/login`). The user is immediately logged in.

### REQ-SIGNUP-09: Signup Rate Limit
`POST /auth/signup` is rate-limited to `3/hour` per IP address (using `get_remote_address`). This is a fixed limit, NOT tier-dependent.

### REQ-SIGNUP-10: Audit Log
Successful signup creates an audit log entry:
- `action`: `"auth.signup"`
- `actor_id`: new user's UUID
- `tenant_id`: new tenant's UUID
- `resource_type`: `"tenant"`
- `resource_id`: new tenant's UUID
- `ip_address`: request client IP

### REQ-SIGNUP-11: Password Hashing
Password is hashed using bcrypt (same `hash_password()` from `jwt_handler.py`) before storage. Plain-text password is never stored or logged.

### REQ-SIGNUP-12: Signup Page (Frontend)
Public route at `/signup` with:
- Form fields: email, password, full_name, organization_name
- Client-side validation (required, email format, password min 8 chars)
- Submit → call `POST /auth/signup`
- On 201: store tokens in localStorage, redirect to `/templates`, show welcome toast
- On 409: show specific error message
- On 429: show rate limit error
- Link to `/login` for existing users

### REQ-SIGNUP-13: Login Page Link
The existing `/login` page gains a link: "¿No tiene cuenta? Regístrese" pointing to `/signup`.

### REQ-SIGNUP-14: Auth Context Signup Method
`useAuth` gains a `signup(email, password, full_name, organization_name)` method that:
1. Calls `POST /auth/signup`
2. Stores tokens in localStorage
3. Fetches user profile via `GET /auth/me`
4. Updates auth context state

---

## Scenarios

### SC-01: Happy Path Signup
**Given** no user with email "new@example.com" exists
**And** no tenant named "Acme Corp" exists
**When** POST `/auth/signup` with `{email: "new@example.com", password: "securepass1", full_name: "Jane Doe", organization_name: "Acme Corp"}`
**Then** response status is 201
**And** response contains valid `access_token` and `refresh_token`
**And** a tenant "Acme Corp" with slug "acme-corp" exists with Free tier
**And** a user "new@example.com" exists with role "admin" in tenant "Acme Corp"
**And** audit log entry with action "auth.signup" is created

### SC-02: Duplicate Email
**Given** a user with email "taken@example.com" already exists
**When** POST `/auth/signup` with `{email: "taken@example.com", ...}`
**Then** response status is 409
**And** detail is "Email already registered"
**And** no tenant or user is created

### SC-03: Duplicate Organization Name
**Given** a tenant named "Acme Corp" already exists
**When** POST `/auth/signup` with `{organization_name: "Acme Corp", ...}`
**Then** response status is 409
**And** detail is "Organization name already taken"
**And** no tenant or user is created

### SC-04: Weak Password
**When** POST `/auth/signup` with `{password: "short", ...}`
**Then** response status is 422 (validation error)

### SC-05: Rate Limit
**Given** 3 signup requests from IP 1.2.3.4 in the last hour
**When** a 4th POST `/auth/signup` from IP 1.2.3.4
**Then** response status is 429

### SC-06: Slug Collision
**Given** a tenant with slug "acme-corp" already exists
**When** POST `/auth/signup` with `{organization_name: "Acme Corp!", ...}`
**Then** the new tenant gets slug "acme-corp-2"

### SC-07: Frontend Happy Path
**Given** user is on `/signup` page
**When** they fill all fields with valid data and submit
**Then** they are redirected to `/templates`
**And** a success toast "¡Bienvenido a SigDoc!" is displayed
**And** localStorage contains `access_token` and `refresh_token`

### SC-08: Frontend Duplicate Email
**Given** user is on `/signup` page
**When** they submit with an already-registered email
**Then** error toast "El correo electrónico ya está registrado" is displayed
**And** they remain on `/signup`

---

## Non-Functional Requirements

- **NFR-01**: Signup response time < 500ms (p95) for single concurrent request
- **NFR-02**: Transaction isolation level: READ COMMITTED (PostgreSQL default) — sufficient since email uniqueness is enforced by DB unique index
- **NFR-03**: No PII logged (password never appears in logs or audit details)
