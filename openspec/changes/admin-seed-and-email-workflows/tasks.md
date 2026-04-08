# Tasks: Admin Seed Unification & Email Workflows

**Change**: `admin-seed-and-email-workflows`
**Status**: tasks-ready
**Date**: 2026-04-07
**Total tasks**: 32

## Phase 1: Admin Seed Unification (standalone — no dependencies)

### 1.1 Config Cleanup
- [x] **T-SEED-01**: Remove `admin_email` and `admin_password` fields from `Settings` in `config.py`. Update any references in tests that depend on these fields.
  - Files: `backend/src/app/config.py`, `backend/tests/**`
  - Spec: REQ-SEED-02

### 1.2 Migration 008
- [x] **T-SEED-02**: Create Alembic migration `008_admin_seed_canonical.py`. Upsert canonical admin (`devrafaseros@gmail.com`, `Jose Rafael Gallegos Rojas`, role `admin`). Read `ADMIN_PASSWORD` from `os.environ`. Use `ON CONFLICT` on `uq_users_email_global`. Fail if no password and no existing user.
  - Files: `backend/alembic/versions/008_admin_seed_canonical.py`
  - Spec: REQ-SEED-01, REQ-SEED-03
  - Design: ADR-ASEW-06 (migration 008 SQL)

### 1.3 Tests
- [x] **T-SEED-03**: Write unit test for migration 008 logic: fresh DB scenario, existing user update, missing password error.
  - Files: `backend/tests/unit/test_admin_seed.py`
  - Spec: SCEN-SEED-01 through SCEN-SEED-05

## Phase 2: Admin Management Enhancements (standalone)

### 2.1 Backend
- [x] **T-ADMIN-01**: Add `role` field (optional, validated against `Literal["admin", "user"]`) to `UpdateUserRequest` in `schemas/user.py`.
  - Files: `backend/src/app/presentation/schemas/user.py`
  - Spec: REQ-ADMIN-01

- [x] **T-ADMIN-02**: Add `count_admins_by_tenant(tenant_id: UUID) -> int` method to `UserRepository` port and `SQLAlchemyUserRepository`. Counts active users with `role="admin"` in the given tenant.
  - Files: `backend/src/app/domain/ports/user_repository.py`, `backend/src/app/infrastructure/persistence/repositories/user_repository.py`
  - Design: ADR-ASEW-05

- [x] **T-ADMIN-03**: Add last-admin guard to `update_user` endpoint in `users.py`. Before applying `role` change away from `admin`: count admins, reject with 409 if <= 1.
  - Files: `backend/src/app/presentation/api/v1/users.py`
  - Spec: REQ-ADMIN-02

- [x] **T-ADMIN-04**: Add last-admin guard to `deactivate_user` endpoint. Before deactivating an admin: count admins, reject with 409 if <= 1.
  - Files: `backend/src/app/presentation/api/v1/users.py`
  - Spec: REQ-ADMIN-02 (edge case)

- [x] **T-ADMIN-05**: Add `AUTH_RESET_PASSWORD` constant to `AuditAction` class. Value: `"auth.reset_password"`.
  - Files: `backend/src/app/domain/entities/audit_log.py`
  - Spec: REQ-RESET-08

### 2.2 Frontend
- [ ] **T-ADMIN-06**: Add role selector (dropdown: `Admin` / `Usuario`) to `EditUserDialog`. Include logic to disable the selector when the user is the last admin (fetch admin count or pass it as prop).
  - Files: `frontend/src/features/users/components/EditUserDialog.tsx`
  - Spec: REQ-ADMIN-04

- [ ] **T-ADMIN-07**: Update `useUpdateUser` mutation to include `role` in the payload type.
  - Files: `frontend/src/features/users/api/mutations.ts`
  - Spec: REQ-ADMIN-01

### 2.3 Tests
- [x] **T-ADMIN-08**: Write integration tests for role change via `PUT /users/{id}`: promote, demote, last-admin guard (409), invalid role (422).
  - Files: `backend/tests/integration/test_users_api.py`
  - Spec: SCEN-ADMIN-01 through SCEN-ADMIN-05

- [x] **T-ADMIN-09**: Write integration test for deactivate last admin (409).
  - Files: `backend/tests/integration/test_users_api.py`
  - Spec: SCEN-ADMIN-04

## Phase 3: Email Infrastructure (foundation — blocks Phase 4 and 5)

### 3.1 Config
- [x] **T-EMAIL-01**: Add email config fields to `Settings`: `smtp_host`, `smtp_port`, `smtp_user`, `smtp_password`, `smtp_from_address`, `smtp_tls`, `email_backend`, `frontend_url`.
  - Files: `backend/src/app/config.py`
  - Spec: REQ-EMAIL-04
  - Design: ADR-ASEW-04, ADR-ASEW-06

### 3.2 Domain Port
- [x] **T-EMAIL-02**: Create `EmailService` abstract port at `domain/ports/email_service.py`. Single method: `send_email(to, subject, html_body, text_body) -> bool`.
  - Files: `backend/src/app/domain/ports/email_service.py`
  - Spec: REQ-EMAIL-01
  - Design: ADR-ASEW-01

- [x] **T-EMAIL-03**: Export `EmailService` from `domain/ports/__init__.py`.
  - Files: `backend/src/app/domain/ports/__init__.py`

### 3.3 Infrastructure Adapters
- [x] **T-EMAIL-04**: Create `ConsoleEmailService` adapter at `infrastructure/email/console_adapter.py`. Logs to stdout, stores in `sent_emails` list, always returns `True`.
  - Files: `backend/src/app/infrastructure/email/__init__.py`, `backend/src/app/infrastructure/email/console_adapter.py`
  - Spec: REQ-EMAIL-03

- [x] **T-EMAIL-05**: Create `SmtpEmailService` adapter at `infrastructure/email/smtp_adapter.py`. Uses `aiosmtplib`. Returns `False` on failure (no exceptions). Logs errors.
  - Files: `backend/src/app/infrastructure/email/smtp_adapter.py`
  - Spec: REQ-EMAIL-02
  - Design: ADR-ASEW-03

- [x] **T-EMAIL-06**: Create factory function `get_email_service()` that reads `Settings.email_backend` and returns the appropriate adapter. Make it usable as FastAPI dependency.
  - Files: `backend/src/app/infrastructure/email/__init__.py`
  - Spec: REQ-EMAIL-06

### 3.4 Email Templates
- [x] **T-EMAIL-07**: Create Jinja2 HTML template `verification.html` at `infrastructure/email/templates/`. Variables: `app_name`, `user_name`, `action_url`, `expires_in`.
  - Files: `backend/src/app/infrastructure/email/templates/verification.html`
  - Spec: REQ-EMAIL-05

- [x] **T-EMAIL-08**: Create Jinja2 HTML template `password_reset.html` at `infrastructure/email/templates/`. Same variable pattern.
  - Files: `backend/src/app/infrastructure/email/templates/password_reset.html`
  - Spec: REQ-EMAIL-05

### 3.5 Dependencies
- [x] **T-EMAIL-09**: Add `aiosmtplib>=2.0.0` and `jinja2>=3.1.0` to `pyproject.toml` dependencies.
  - Files: `backend/pyproject.toml`

### 3.6 Tests
- [x] **T-EMAIL-10**: Create `FakeEmailService` in `tests/fakes/fake_email_service.py`. In-memory, stores calls, configurable success/failure.
  - Files: `backend/tests/fakes/fake_email_service.py`, `backend/tests/fakes/__init__.py`

- [x] **T-EMAIL-11**: Write unit tests for `ConsoleEmailService`: sends email, stores in list, returns True.
  - Files: `backend/tests/unit/test_email_service.py`
  - Spec: SCEN-EMAIL-03

## Phase 4: Email Verification on Signup (depends on Phase 3)

### 4.1 Database
- [x] **T-VERIFY-01**: Create Alembic migration `009_email_verification_fields.py`. Add 5 columns to users table. Set `email_verified=true` for existing users. Add partial indexes on token columns.
  - Files: `backend/alembic/versions/009_email_verification_fields.py`
  - Spec: REQ-VERIFY-01
  - Design: Migration 009 SQL

### 4.2 Domain & Model Updates
- [x] **T-VERIFY-02**: Add `email_verified`, `email_verification_token`, `email_verification_sent_at`, `password_reset_token`, `password_reset_sent_at` to `User` entity and `UserModel`.
  - Files: `backend/src/app/domain/entities/user.py`, `backend/src/app/infrastructure/persistence/models/user.py`
  - Spec: REQ-VERIFY-08

- [x] **T-VERIFY-03**: Add `get_by_verification_token(token: str) -> User | None` and `get_by_reset_token(token: str) -> User | None` to `UserRepository` port and `SQLAlchemyUserRepository`.
  - Files: `backend/src/app/domain/ports/user_repository.py`, `backend/src/app/infrastructure/persistence/repositories/user_repository.py`

### 4.3 Application Services
- [x] **T-VERIFY-04**: Create `EmailVerificationService` at `application/services/email_verification_service.py`. Methods: `send_verification(user, email_service)`, `verify_token(token, user_repo)`, `resend_verification(user, email_service, user_repo)`. Uses Jinja2 to render email template.
  - Files: `backend/src/app/application/services/email_verification_service.py`
  - Spec: REQ-VERIFY-02, REQ-VERIFY-03, REQ-VERIFY-04

- [x] **T-VERIFY-05**: Modify `SignupService.signup()` to accept an `email_service` parameter. After creating the user, call `EmailVerificationService.send_verification()`. Handle failures gracefully (signup still succeeds).
  - Files: `backend/src/app/application/services/signup_service.py`
  - Spec: REQ-VERIFY-02
  - Design: ADR-ASEW-03

### 4.4 API Endpoints
- [x] **T-VERIFY-06**: Add `GET /auth/verify-email?token=...` endpoint. Calls `EmailVerificationService.verify_token()`.
  - Files: `backend/src/app/presentation/api/v1/auth.py`
  - Spec: REQ-VERIFY-03

- [x] **T-VERIFY-07**: Add `POST /auth/resend-verification` endpoint (authenticated, rate-limited 3/hr).
  - Files: `backend/src/app/presentation/api/v1/auth.py`
  - Spec: REQ-VERIFY-04

- [x] **T-VERIFY-08**: Add `email_verified` field to `UserResponse` in `schemas/auth.py`. Update `/auth/me` to include it.
  - Files: `backend/src/app/presentation/schemas/auth.py`, `backend/src/app/presentation/api/v1/auth.py`
  - Spec: REQ-VERIFY-08

- [x] **T-VERIFY-09**: Add email verification gate to document generation endpoints (`generate` and `generate_bulk`). Check `email_verified` on the current user; return 403 if false.
  - Files: `backend/src/app/presentation/api/v1/documents.py`
  - Spec: REQ-VERIFY-05

### 4.5 Frontend
- [ ] **T-VERIFY-10**: Create `/verify-email` public route. Reads token from query, calls API, shows success/error.
  - Files: `frontend/src/routes/verify-email.tsx`
  - Spec: REQ-VERIFY-07

- [ ] **T-VERIFY-11**: Create `VerificationBanner` component. Shows when `email_verified=false` in user data. Includes "Reenviar" button.
  - Files: `frontend/src/features/auth/components/VerificationBanner.tsx`
  - Spec: REQ-VERIFY-06

- [ ] **T-VERIFY-12**: Add `VerificationBanner` to the authenticated layout (`_authenticated.tsx`). Conditionally render based on `/auth/me` response.
  - Files: `frontend/src/routes/_authenticated.tsx`
  - Spec: REQ-VERIFY-06

### 4.6 Tests
- [x] **T-VERIFY-13**: Write unit tests for `EmailVerificationService`: send verification, verify valid token, expired token, resend, already-verified user.
  - Files: `backend/tests/unit/test_email_verification_service.py`
  - Spec: SCEN-VERIFY-01 through SCEN-VERIFY-07

- [x] **T-VERIFY-14**: Write integration tests for verify-email, resend-verification endpoints.
  - Files: `backend/tests/integration/test_auth_api.py`
  - Spec: SCEN-VERIFY-01 through SCEN-VERIFY-07

- [x] **T-VERIFY-15**: Write integration test for document generation gate (403 for unverified users).
  - Files: `backend/tests/integration/test_documents_api.py`
  - Spec: SCEN-VERIFY-04, SCEN-VERIFY-05

- [x] **T-VERIFY-16**: Update existing signup tests to account for verification email being sent (mock/fake email service).
  - Files: `backend/tests/unit/test_signup_service.py`, `backend/tests/integration/test_signup_api.py`

## Phase 5: Forgot Password Flow (depends on Phase 3; can parallel with Phase 4)

### 5.1 Application Service
- [x] **T-RESET-01**: Create `PasswordResetService` at `application/services/password_reset_service.py`. Methods: `request_reset(email, email_service, user_repo)`, `reset_password(token, new_password, user_repo)`. Token generation (32-byte hex), expiry check (1 hour), audit logging.
  - Files: `backend/src/app/application/services/password_reset_service.py`
  - Spec: REQ-RESET-01, REQ-RESET-02, REQ-RESET-03

### 5.2 API Endpoints
- [x] **T-RESET-02**: Add `POST /auth/forgot-password` endpoint (public, rate-limited 5/min). Always returns 200.
  - Files: `backend/src/app/presentation/api/v1/auth.py`
  - Spec: REQ-RESET-01

- [x] **T-RESET-03**: Add `POST /auth/reset-password` endpoint (public). Validates new password (>= 8 chars). Returns 200 on success, 400 on invalid/expired token.
  - Files: `backend/src/app/presentation/api/v1/auth.py`, `backend/src/app/presentation/schemas/auth.py`
  - Spec: REQ-RESET-02

### 5.3 Frontend
- [ ] **T-RESET-04**: Create `/forgot-password` public route. Email form, calls API, shows confirmation message. Link back to login.
  - Files: `frontend/src/routes/forgot-password.tsx`
  - Spec: REQ-RESET-04

- [ ] **T-RESET-05**: Create `/reset-password` public route. Reads token from query, password + confirm form, calls API, shows success/error.
  - Files: `frontend/src/routes/reset-password.tsx`
  - Spec: REQ-RESET-05

- [ ] **T-RESET-06**: Add "Olvide mi contrasena" link to login page.
  - Files: `frontend/src/routes/login.tsx`
  - Spec: REQ-RESET-06

### 5.4 Tests
- [x] **T-RESET-07**: Write unit tests for `PasswordResetService`: request reset (existing user, non-existent user), reset with valid token, expired token, already-used token, new request overwrites old token.
  - Files: `backend/tests/unit/test_password_reset_service.py`
  - Spec: SCEN-RESET-01 through SCEN-RESET-06

- [x] **T-RESET-08**: Write integration tests for forgot-password and reset-password endpoints.
  - Files: `backend/tests/integration/test_auth_api.py`
  - Spec: SCEN-RESET-01 through SCEN-RESET-07

## Dependency Graph

```
Phase 1 (Admin Seed)    ─────────────────────────────────┐
Phase 2 (Admin Mgmt)    ─────────────────────────────────┤
Phase 3 (Email Infra)   ──┬──────────────────────────────┤
                           ├── Phase 4 (Email Verify)  ──┤
                           └── Phase 5 (Forgot Password) ┘
```

Phases 1, 2, and 3 can run in parallel. Phases 4 and 5 depend on Phase 3 but can run in parallel with each other.

## Estimated Effort

| Phase | Tasks | Complexity |
|-------|-------|------------|
| 1. Admin Seed | 3 | Low |
| 2. Admin Management | 9 | Medium |
| 3. Email Infrastructure | 11 | Medium |
| 4. Email Verification | 16 | High |
| 5. Forgot Password | 8 | Medium |
| **Total** | **32** | — |
