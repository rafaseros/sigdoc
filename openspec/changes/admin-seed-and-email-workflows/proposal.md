# Proposal: Admin Seed Unification & Email Workflows

**Change**: `admin-seed-and-email-workflows`
**Status**: proposed
**Date**: 2026-04-07

## Problem Statement

SigDoc has three interrelated gaps that block production-readiness:

1. **Admin seed divergence**: The admin user is hardcoded in migration 001 using `ADMIN_EMAIL`/`ADMIN_PASSWORD` env vars with weak defaults (`admin@sigdoc.local` / `admin123`). Dev and prod environments have drifted apart — different emails, passwords, and names. There is no way to converge them to a canonical admin identity without manual DB intervention.

2. **No email infrastructure**: The platform has zero email sending capability. This blocks email verification, password reset, and any future transactional notifications.

3. **Missing auth flows**: Signup has no email verification (users can register with fake emails and immediately use the system). There is no "forgot password" flow, forcing admins to manually reset passwords via DB.

## Intent

Unify the admin user across all environments via an idempotent seed mechanism, add SMTP-based email sending infrastructure, implement email verification on signup, and add a complete forgot-password/reset-password flow.

## Scope

### In Scope

1. **Admin Seed Unification** (Migration/CLI)
   - New Alembic migration (008) that ensures the canonical admin exists
   - Email: `devrafaseros@gmail.com`, Name: `Jose Rafael Gallegos Rojas`, Role: `admin`
   - Password: configurable via `ADMIN_PASSWORD` env var
   - Idempotent: if user exists by email, update name/role but NOT password
   - Remove `admin_email` and `admin_password` defaults from `Settings` (keep `admin_password` as required for seed only)
   - Both dev and prod converge after running migration

2. **Admin Management Enhancements**
   - Allow admins to change user roles (promote/demote) via `UpdateUserRequest`
   - Add `role` field to `UpdateUserRequest` schema
   - Guard: the LAST admin in a tenant cannot be demoted (prevent lockout)
   - Frontend: role selector in `EditUserDialog`

3. **Email Infrastructure** (Port/Adapter)
   - New domain port: `EmailService` (send_email, send_template_email)
   - SMTP adapter using `aiosmtplib` (async, non-blocking)
   - Config in `Settings`: `smtp_host`, `smtp_port`, `smtp_user`, `smtp_password`, `smtp_from_address`, `smtp_tls`
   - Console adapter for dev/test (logs to stdout instead of sending)
   - HTML email templates (Jinja2) for verification and password reset

4. **Email Verification on Signup**
   - New DB columns on `users`: `email_verified` (bool, default false), `email_verification_token` (str), `email_verification_sent_at` (timestamp)
   - After signup: send verification email with token/link
   - `GET /auth/verify-email?token=...` endpoint to verify
   - Token expires after 24 hours
   - Unverified users can log in but see a "verify your email" banner; cannot generate documents
   - `POST /auth/resend-verification` endpoint (rate-limited)
   - Frontend: verification banner component, verify-email page

5. **Forgot Password Flow**
   - `POST /auth/forgot-password` with `{ email }` — sends reset email if user exists (always 200)
   - `POST /auth/reset-password` with `{ token, new_password }` — resets password
   - Token stored in `password_reset_token` / `password_reset_sent_at` columns, expires after 1 hour
   - Frontend: `/forgot-password` page and `/reset-password` page
   - Link from login page to forgot-password page

### Out of Scope (Deferred)
- OAuth / social login
- CAPTCHA / advanced bot protection
- Email templates for other events (document generated, etc.)
- Multi-admin approval workflows
- Email service provider integration (Resend, SendGrid) — SMTP first
- Admin dashboard for email delivery metrics

## Approach

### Phase Strategy
This change is large but the pieces build on each other cleanly:

1. **Admin Seed** (standalone, no dependencies) — migration 008 + config cleanup
2. **Admin Management** (standalone) — small schema + endpoint + frontend changes
3. **Email Infrastructure** (foundation for 4 and 5) — port, adapter, config, templates
4. **Email Verification** (depends on 3) — migration 009, service logic, endpoints, frontend
5. **Forgot Password** (depends on 3) — service logic, endpoints, frontend

### Key Technical Decisions

- **SMTP over email service**: For MVP, SMTP is simpler, zero vendor lock-in, works with any provider. Can swap adapter later.
- **aiosmtplib**: Async SMTP library — fits the async FastAPI stack. No blocking the event loop.
- **Token storage in DB** (not JWT): Verification and reset tokens are stored in the users table. This allows invalidation (one-time use) and is simpler than stateless JWTs for this purpose.
- **Columns on users table** (not separate table): For MVP, adding columns to users is simpler. A separate `email_tokens` table could be a future refactor if we need multiple pending verifications.
- **Console email adapter for dev/test**: Avoids needing a real SMTP server in dev. Tests can assert on the console adapter's log.

## Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Migration 008 on prod with existing admin | Medium | Idempotent upsert by email — safe to re-run |
| SMTP misconfiguration blocks signup | High | Email sending is async fire-and-forget; signup succeeds even if email fails. User can resend verification. |
| Token brute-force | Medium | Tokens are 32-byte hex (256-bit entropy). Rate limiting on verification/reset endpoints. |
| Unverified users stuck | Low | Resend endpoint + clear UI messaging. Admin can manually verify via user management. |

## Success Criteria

- [ ] Single canonical admin exists across all environments after running migrations
- [ ] Admin can promote/demote users; last-admin guard works
- [ ] Verification email sent on signup; unverified users see banner
- [ ] Verified users can generate documents; unverified cannot
- [ ] Forgot password flow works end-to-end (request → email → reset)
- [ ] All new features have unit + integration tests
- [ ] Console email adapter works in dev/test without SMTP server
