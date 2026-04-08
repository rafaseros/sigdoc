# Proposal: Self-Service Tenant Onboarding

**Change**: `tenant-onboarding`
**Status**: proposed
**Date**: 2026-04-07

## Problem Statement

SigDoc currently requires manual tenant/user creation (seed scripts or admin intervention). This blocks self-service SaaS adoption — new customers cannot sign up and start using the product without operator involvement. This is the last missing piece for a fully functional SaaS product.

## Intent

Enable self-service tenant registration via a public signup endpoint and frontend signup page, so new organizations can create an account and begin using SigDoc immediately without admin intervention.

## Scope

### In Scope
1. **Public signup endpoint** (`POST /auth/signup`) — atomic tenant + admin user creation
2. **Global email uniqueness** — DB constraint ensuring email is unique across ALL tenants (not just per-tenant)
3. **Unique organization names** — tenant name uniqueness constraint
4. **Signup rate limiting** — 3 requests/hour per IP to prevent abuse
5. **Frontend signup page** — `/signup` public route with form + redirect to `/templates`
6. **Welcome toast** — first-time user experience after signup
7. **Alembic migration** — add global email unique index, adjust constraints
8. **Audit logging** — `auth.signup` action recorded on successful signup
9. **Tests** — unit + integration tests following existing patterns (TDD)

### Out of Scope (Deferred)
- Email verification flow
- CAPTCHA / bot protection beyond rate limiting
- Social login (OAuth/OIDC)
- Custom onboarding wizard / multi-step setup
- Invitation-based signup (join existing tenant)
- Admin approval workflow

## Approach

### Backend
- Add `SignupRequest` schema (email, password, full_name, organization_name) with pydantic validation (password min 8 chars)
- Create `SignupService` (application layer) that orchestrates: create tenant → assign Free tier → create admin user → audit log — all in a single DB transaction
- Add `POST /auth/signup` endpoint in `auth.py` router, rate-limited to `3/hour` per IP
- Alembic migration 007: add `uq_users_email_global` unique index on `users.email`, add `uq_tenants_name` unique constraint on `tenants.name`
- Slug generation: derive tenant slug from organization_name (lowercase, hyphenated, deduped with suffix if collision)
- New `AuditAction.AUTH_SIGNUP = "auth.signup"` constant
- New `TenantRepository` port + SQLAlchemy implementation (currently missing — needed to create tenants and check name uniqueness)

### Frontend
- New `/signup` route (public, same pattern as `/login`)
- Form: email, password, full_name, organization_name
- Client-side validation (required fields, email format, password min length)
- On success: store tokens → redirect to `/templates` with welcome toast
- Link between login ↔ signup pages
- Add `signup` method to `useAuth` context

### Database Migration
- Add unique index on `users.email` (global, not per-tenant)
- Add unique constraint on `tenants.name`
- Both are additive and non-breaking for existing data (assuming no email duplicates exist across tenants)

## Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Existing email duplicates across tenants | Low | High | Migration checks for duplicates before adding constraint; fail-safe |
| Slug collisions on concurrent signups | Low | Medium | Unique constraint on slug + retry with suffix |
| Abuse via automated signups | Medium | Medium | Rate limit 3/hour per IP; future: CAPTCHA |
| Tenant name squatting | Low | Low | Admin can rename; future: reserved name list |

## Success Criteria

- [ ] New user can sign up at `/signup` and land on `/templates` within 5 seconds
- [ ] Duplicate email returns clear 409 error
- [ ] Duplicate org name returns clear 409 error
- [ ] Rate limit enforced (4th signup in 1 hour returns 429)
- [ ] Signup creates tenant with Free tier assigned
- [ ] Signup creates user with role=admin
- [ ] Audit log entry created for signup
- [ ] All new code covered by tests (TDD — tests written first)
- [ ] 264+ existing tests still pass
