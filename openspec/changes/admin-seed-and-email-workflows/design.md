# Design: Admin Seed Unification & Email Workflows

**Change**: `admin-seed-and-email-workflows`
**Status**: designed
**Date**: 2026-04-07

## Architecture Decisions

### ADR-ASEW-01: Email as a Domain Port (Hexagonal Architecture)

**Decision**: Email sending is a domain port (`EmailService`) with infrastructure adapters.

**Context**: The codebase follows hexagonal architecture — domain ports in `domain/ports/`, infrastructure adapters in `infrastructure/`. Storage (`StorageService`), templating (`TemplateEngine`), and repositories all follow this pattern.

**Consequences**:
- `app/domain/ports/email_service.py` — abstract interface
- `app/infrastructure/email/smtp_adapter.py` — production SMTP implementation
- `app/infrastructure/email/console_adapter.py` — dev/test implementation
- Application services depend on the port, not the adapter
- Tests inject `ConsoleEmailService` (or a fake) — no SMTP needed

### ADR-ASEW-02: Token Storage in Users Table (Not JWT, Not Separate Table)

**Decision**: Verification and reset tokens are stored as columns on the `users` table.

**Context**: Three options considered:
1. **JWT tokens (stateless)** — Cannot be invalidated after use. Would require a blocklist, adding complexity.
2. **Separate tokens table** — More flexible but over-engineered for MVP. Only one active token per type per user.
3. **Columns on users** — Simple, one active token per type, easy to invalidate by NULLing.

**Consequences**:
- 5 new columns on `users` table (REQ-VERIFY-01)
- Only ONE active verification token and ONE active reset token per user at a time
- Token rotation is trivial (overwrite the column)
- Migration adds columns with defaults for existing rows

### ADR-ASEW-03: Fire-and-Forget Email Pattern

**Decision**: Email sending is fire-and-forget. Signup/reset endpoints return immediately; email delivery happens asynchronously.

**Context**: The codebase already uses fire-and-forget for audit logging (`audit_svc.log()`). Email follows the same pattern.

**Implementation**: The service calls `await email_service.send_email(...)` but the endpoint doesn't fail if email fails. The `send_email` method returns `bool` — callers can log failures but don't propagate them.

**Consequences**:
- Signup never fails due to email issues
- Users who don't receive email can use the resend endpoint
- No email queue or retry mechanism for MVP (acceptable trade-off)

### ADR-ASEW-04: Email Backend Selection via Config

**Decision**: A string config `email_backend` selects between `"smtp"` and `"console"` adapters.

**Context**: Dev environments don't have SMTP. Tests shouldn't send real emails. Production needs real SMTP.

**Implementation**: Factory function `get_email_service()` reads `Settings.email_backend` and returns the appropriate adapter.

**Consequences**:
- Dev defaults to console (no SMTP config needed)
- Production sets `EMAIL_BACKEND=smtp` in `.env`
- Tests can inject `ConsoleEmailService` directly or rely on default

### ADR-ASEW-05: Last Admin Guard at Service Level

**Decision**: The last-admin protection check lives in the API endpoint (`users.py`), not in a separate service.

**Context**: The check requires a count query (`count admins WHERE tenant_id = X AND is_active = true`). The existing `update_user` endpoint already has the session and can perform this check inline.

**Implementation**: Before applying a role change to non-admin, count active admins. If count <= 1 and the target user is currently admin, reject.

**Consequences**:
- Simple, no new service needed
- The guard also applies to `deactivate_user` (same pattern)
- The user repository gets a new method: `count_admins_by_tenant(tenant_id)`

### ADR-ASEW-06: Frontend URL in Config for Email Links

**Decision**: A new config field `frontend_url` provides the base URL for email links.

**Context**: Verification and reset emails contain links like `{frontend_url}/verify-email?token=...`. The backend needs to know the frontend URL.

**Implementation**: `Settings.frontend_url` defaults to `"http://localhost:5173"` (Vite dev server). Production overrides via `FRONTEND_URL` env var.

## Component Map

```
domain/
  ports/
    email_service.py          [NEW] EmailService ABC
  entities/
    user.py                   [MOD] +email_verified, +verification/reset token fields

infrastructure/
  email/                      [NEW] entire directory
    __init__.py
    smtp_adapter.py           SmtpEmailService
    console_adapter.py        ConsoleEmailService
    templates/
      verification.html
      password_reset.html

  persistence/
    models/
      user.py                 [MOD] +5 columns
    repositories/
      user_repository.py      [MOD] +get_by_verification_token, +get_by_reset_token, +count_admins_by_tenant

  auth/
    jwt_handler.py            [NO CHANGE] — tokens are NOT JWTs

application/
  services/
    signup_service.py          [MOD] send verification email after signup
    email_verification_service.py  [NEW] verify, resend logic
    password_reset_service.py      [NEW] forgot, reset logic

presentation/
  api/v1/
    auth.py                   [MOD] +verify-email, +resend-verification, +forgot-password, +reset-password
    users.py                  [MOD] +role in UpdateUserRequest, +last-admin guard
    documents.py              [MOD] +email_verified gate on generate endpoints
  schemas/
    auth.py                   [MOD] +ForgotPasswordRequest, +ResetPasswordRequest, +email_verified in UserResponse
    user.py                   [MOD] +role in UpdateUserRequest (with validation)
  middleware/
    tenant.py                 [MOD] +email_verified in CurrentUser (optional)

config.py                     [MOD] -admin_email, -admin_password, +smtp_*, +email_backend, +frontend_url

alembic/versions/
  008_admin_seed_canonical.py     [NEW]
  009_email_verification_fields.py [NEW]
```

## Database Changes

### Migration 008: Admin Seed Canonical

```sql
-- Upsert canonical admin
-- If exists by email: UPDATE full_name, role
-- If not exists: INSERT with hashed ADMIN_PASSWORD
INSERT INTO users (id, tenant_id, email, hashed_password, full_name, role, is_active)
SELECT
    gen_random_uuid(),
    t.id,
    'devrafaseros@gmail.com',
    :hashed_password,
    'Jose Rafael Gallegos Rojas',
    'admin',
    true
FROM tenants t WHERE t.slug = 'default'
ON CONFLICT ON CONSTRAINT uq_users_email_global
DO UPDATE SET
    full_name = 'Jose Rafael Gallegos Rojas',
    role = 'admin',
    updated_at = now();
```

Note: The `ON CONFLICT` uses the global email unique index from migration 007. Password is only set on INSERT, not on UPDATE.

### Migration 009: Email Verification Fields

```sql
ALTER TABLE users
    ADD COLUMN email_verified BOOLEAN NOT NULL DEFAULT false,
    ADD COLUMN email_verification_token VARCHAR(255),
    ADD COLUMN email_verification_sent_at TIMESTAMPTZ,
    ADD COLUMN password_reset_token VARCHAR(255),
    ADD COLUMN password_reset_sent_at TIMESTAMPTZ;

-- Existing users are trusted — mark as verified
UPDATE users SET email_verified = true;

-- Index for token lookups
CREATE INDEX ix_users_verification_token ON users (email_verification_token)
    WHERE email_verification_token IS NOT NULL;
CREATE INDEX ix_users_reset_token ON users (password_reset_token)
    WHERE password_reset_token IS NOT NULL;
```

## New Endpoints Summary

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/auth/verify-email` | Public | Verify email via token query param |
| POST | `/auth/resend-verification` | Bearer | Resend verification email |
| POST | `/auth/forgot-password` | Public | Request password reset |
| POST | `/auth/reset-password` | Public | Reset password via token |

## Frontend Routes

| Route | Component | Auth |
|-------|-----------|------|
| `/verify-email` | `VerifyEmailPage` | Public |
| `/forgot-password` | `ForgotPasswordPage` | Public |
| `/reset-password` | `ResetPasswordPage` | Public |

## Dependencies (New)

### Backend
- `aiosmtplib>=2.0.0` — async SMTP client
- `jinja2>=3.1.0` — email HTML templates (already a transitive dep via docxtpl, but add explicitly)

### Frontend
- No new dependencies (uses existing shadcn/ui components)

## Security Considerations

1. **Token entropy**: 32-byte hex = 256 bits of randomness. Brute-force infeasible.
2. **Token expiry**: Verification 24h, reset 1h. Short windows reduce exposure.
3. **One-time use**: Tokens cleared after use. Cannot be reused.
4. **Email enumeration**: Forgot-password always returns 200 regardless of email existence.
5. **Rate limiting**: Resend verification (3/hr), forgot-password (5/min). Prevents abuse.
6. **SMTP credentials**: Stored in env vars, not in code.

## Test Strategy

### Unit Tests
- `test_email_verification_service.py` — verify, resend, token expiry logic
- `test_password_reset_service.py` — forgot, reset, token expiry, one-time use
- `test_admin_seed.py` — migration logic (if testable; otherwise integration only)
- `test_last_admin_guard.py` — demotion/deactivation protection

### Integration Tests
- `test_auth_api.py` — new endpoints (verify-email, resend, forgot-password, reset-password)
- `test_users_api.py` — role change, last-admin guard
- `test_documents_api.py` — email_verified gate on generate

### Fakes
- `FakeEmailService` — in-memory email service for unit tests (similar to ConsoleEmailService)
