# Spec: Forgot Password Flow

**Change**: `admin-seed-and-email-workflows`
**Module**: `forgot-password`
**Status**: specified

## Requirements

### REQ-RESET-01: Forgot Password Endpoint

`POST /auth/forgot-password` (public, unauthenticated) SHALL:

1. Accept `{ "email": "user@example.com" }`
2. Look up user by email (active users only)
3. If user exists:
   - Generate a 32-byte hex token (`secrets.token_hex(32)`)
   - Store `password_reset_token` and `password_reset_sent_at` on the user record
   - Send password reset email with link: `{frontend_url}/reset-password?token={token}`
4. ALWAYS return HTTP 200 with `{ "message": "Si el email existe, se envio un enlace de restablecimiento" }`
   - This prevents email enumeration attacks
5. Rate-limited: 5 requests per minute per IP

### REQ-RESET-02: Reset Password Endpoint

`POST /auth/reset-password` (public, unauthenticated) SHALL:

1. Accept `{ "token": "...", "new_password": "..." }`
2. Validate `new_password` (minimum 8 characters)
3. Look up user by `password_reset_token`
4. If no user found: return HTTP 400 with `"Token invalido o expirado"`
5. If token is expired (> 1 hour since `password_reset_sent_at`): return HTTP 400
6. Hash the new password and update `hashed_password`
7. Clear `password_reset_token` and `password_reset_sent_at`
8. Return HTTP 200 with `{ "message": "Contrasena restablecida exitosamente" }`

### REQ-RESET-03: Token One-Time Use

After a reset token is used to change the password:
- The token is cleared from the DB
- The same token cannot be reused
- Any previous token is overwritten when a new forgot-password request is made

### REQ-RESET-04: Frontend Forgot Password Page

Route `/forgot-password`:
- Simple form with email input
- Submit calls `POST /auth/forgot-password`
- On response: shows "Si tu email esta registrado, recibiras un enlace" message
- Link back to login page

### REQ-RESET-05: Frontend Reset Password Page

Route `/reset-password`:
- Reads `token` from query params
- Form with `new_password` and `confirm_password` fields
- Client-side validation: passwords match, minimum 8 chars
- Submit calls `POST /auth/reset-password`
- On success: shows success message with link to login
- On failure: shows error message

### REQ-RESET-06: Login Page Link

The login page SHALL include a "Olvide mi contrasena" link that navigates to `/forgot-password`.

### REQ-RESET-07: Password Reset Email Template

The password reset email SHALL use the `password_reset.html` template with:
- Subject: `"SigDoc - Restablecer contrasena"`
- Body includes: user name, reset link, expiry notice ("1 hora")
- Plain text fallback

### REQ-RESET-08: Audit Logging

Successful password resets SHALL create an audit log entry with:
- Action: `auth.reset_password` (new AuditAction constant)
- Resource: user who reset their password

## Scenarios

### SCEN-RESET-01: Request reset for existing user
**Given** a user with email `alice@example.com` exists
**When** `POST /auth/forgot-password` with `{ "email": "alice@example.com" }`
**Then** a reset email is sent to `alice@example.com`
**And** the response is HTTP 200

### SCEN-RESET-02: Request reset for non-existent email
**Given** no user with email `nobody@example.com` exists
**When** `POST /auth/forgot-password` with `{ "email": "nobody@example.com" }`
**Then** NO email is sent
**And** the response is STILL HTTP 200 (same message)

### SCEN-RESET-03: Reset with valid token
**Given** a user with a valid reset token (created 30 minutes ago)
**When** `POST /auth/reset-password` with `{ "token": "...", "new_password": "newsecure123" }`
**Then** the password is updated
**And** the token is cleared
**And** an audit log entry is created

### SCEN-RESET-04: Reset with expired token
**Given** a user with a reset token created 2 hours ago
**When** `POST /auth/reset-password` with `{ "token": "...", "new_password": "newsecure123" }`
**Then** the response is HTTP 400 `"Token invalido o expirado"`
**And** the password is NOT changed

### SCEN-RESET-05: Reset with already-used token
**Given** a reset token that was already used
**When** `POST /auth/reset-password` with `{ "token": "...", "new_password": "newsecure123" }`
**Then** the response is HTTP 400 `"Token invalido o expirado"`

### SCEN-RESET-06: New reset request overwrites old token
**Given** a user with an existing reset token
**When** `POST /auth/forgot-password` with their email
**Then** a NEW token is generated (old one is invalidated)
**And** a new reset email is sent

### SCEN-RESET-07: Short password rejected
**Given** a valid reset token
**When** `POST /auth/reset-password` with `{ "token": "...", "new_password": "short" }`
**Then** the response is HTTP 422 (validation error)
