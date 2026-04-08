# Spec: Email Verification on Signup

**Change**: `admin-seed-and-email-workflows`
**Module**: `email-verification`
**Status**: specified

## Requirements

### REQ-VERIFY-01: Database Schema Changes

A new Alembic migration (009) SHALL add columns to the `users` table:

| Column | Type | Default | Nullable |
|--------|------|---------|----------|
| `email_verified` | `Boolean` | `false` | No |
| `email_verification_token` | `String(255)` | `NULL` | Yes |
| `email_verification_sent_at` | `DateTime(tz=true)` | `NULL` | Yes |
| `password_reset_token` | `String(255)` | `NULL` | Yes |
| `password_reset_sent_at` | `DateTime(tz=true)` | `NULL` | Yes |

**Migration note**: Existing users (including admin) SHALL have `email_verified` set to `true` (they are trusted, pre-existing users).

### REQ-VERIFY-02: Send Verification on Signup

After successful signup (in `SignupService`):
1. Generate a 32-byte hex token (`secrets.token_hex(32)`)
2. Store token and `sent_at` timestamp on the user record
3. Send verification email with link: `{frontend_url}/verify-email?token={token}`
4. Return signup response immediately (email is fire-and-forget)

The signup MUST succeed even if email sending fails. The user can resend later.

### REQ-VERIFY-03: Verify Email Endpoint

`GET /auth/verify-email?token={token}` SHALL:

1. Look up user by `email_verification_token`
2. If no user found: return HTTP 400 with `"Token invalido o expirado"`
3. If token is expired (> 24 hours since `email_verification_sent_at`): return HTTP 400
4. Set `email_verified = true`, clear `email_verification_token` and `email_verification_sent_at`
5. Return HTTP 200 with `{ "message": "Email verificado exitosamente" }`

### REQ-VERIFY-04: Resend Verification Endpoint

`POST /auth/resend-verification` (authenticated) SHALL:

1. Require authentication (Bearer token)
2. If user is already verified: return HTTP 400 with `"Email ya verificado"`
3. Generate a new token, update `sent_at`
4. Send verification email
5. Return HTTP 200 with `{ "message": "Email de verificacion reenviado" }`
6. Rate-limited: 3 requests per hour per user

### REQ-VERIFY-05: Document Generation Gate

Unverified users SHALL be blocked from generating documents:

- `POST /documents/generate` and `POST /documents/generate/bulk` SHALL check `email_verified`
- If `email_verified` is `false`: return HTTP 403 with `"Debes verificar tu email antes de generar documentos"`
- All other operations (templates, users, etc.) remain accessible

### REQ-VERIFY-06: Frontend Verification Banner

When `email_verified` is `false` in the `/auth/me` response:

- A dismissible but persistent banner SHALL appear at the top of the authenticated layout
- Banner text: "Tu email no esta verificado. Verifica tu email para poder generar documentos."
- Banner includes a "Reenviar email de verificacion" button
- Banner disappears after successful verification

### REQ-VERIFY-07: Frontend Verify Email Page

Route `/verify-email`:
- Reads `token` from query params
- Calls `GET /auth/verify-email?token={token}`
- On success: shows success message with link to login
- On failure: shows error with "Reenviar" option (if logged in)

### REQ-VERIFY-08: User Entity Update

Add to `User` domain entity:
- `email_verified: bool = False`
- `email_verification_token: str | None = None`
- `email_verification_sent_at: datetime | None = None`

Add to `UserModel`:
- Same three columns matching REQ-VERIFY-01

Add `email_verified` to auth `/me` response (`UserResponse`).

## Scenarios

### SCEN-VERIFY-01: Signup triggers verification email
**Given** a new user signs up with email `alice@example.com`
**When** the signup completes successfully
**Then** a verification email is sent to `alice@example.com`
**And** the user record has `email_verified=false` and a non-null token
**And** the signup response includes tokens (user is logged in)

### SCEN-VERIFY-02: Click verification link
**Given** a user with a valid verification token
**When** they visit `/verify-email?token={token}`
**Then** their `email_verified` is set to `true`
**And** the token is cleared
**And** a success message is shown

### SCEN-VERIFY-03: Expired verification token
**Given** a user with a verification token set 25 hours ago
**When** they visit `/verify-email?token={token}`
**Then** the response is HTTP 400 `"Token invalido o expirado"`

### SCEN-VERIFY-04: Unverified user blocked from document generation
**Given** a logged-in user with `email_verified=false`
**When** they call `POST /documents/generate`
**Then** the response is HTTP 403

### SCEN-VERIFY-05: Verified user can generate documents
**Given** a logged-in user with `email_verified=true`
**When** they call `POST /documents/generate`
**Then** the request proceeds normally

### SCEN-VERIFY-06: Resend verification
**Given** a logged-in unverified user
**When** they call `POST /auth/resend-verification`
**Then** a new token is generated
**And** a new verification email is sent
**And** the response is HTTP 200

### SCEN-VERIFY-07: Resend for already verified user
**Given** a logged-in verified user
**When** they call `POST /auth/resend-verification`
**Then** the response is HTTP 400 `"Email ya verificado"`

### SCEN-VERIFY-08: Existing users get email_verified=true
**Given** the database has existing users before migration 009
**When** migration 009 runs
**Then** all existing users have `email_verified=true`
