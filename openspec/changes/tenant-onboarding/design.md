# Design: Self-Service Tenant Onboarding

**Change**: `tenant-onboarding`
**Status**: designed
**Date**: 2026-04-07

---

## Architecture Overview

The signup flow follows the existing hexagonal architecture pattern: presentation (API) → application (service) → domain (entities/ports) → infrastructure (repos/DB).

```
┌─────────────────────────────────────────────────────────────┐
│  POST /auth/signup                                          │
│  (rate limit: 3/hour per IP)                                │
└──────────────┬──────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────┐
│  SignupService.signup(email, password, full_name, org_name) │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ Single transaction:                                    │ │
│  │  1. Check email uniqueness (UserRepo.get_by_email)     │ │
│  │  2. Check org name uniqueness (TenantRepo.get_by_name) │ │
│  │  3. Generate slug (slugify + dedup)                    │ │
│  │  4. Resolve Free tier ID (TierRepo.get_by_slug)        │ │
│  │  5. Create TenantModel (with tier_id)                  │ │
│  │  6. Create UserModel (role=admin, tenant_id)           │ │
│  │  7. Audit log (auth.signup)                            │ │
│  └────────────────────────────────────────────────────────┘ │
└──────────────┬──────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────┐
│  Return JWT tokens (access + refresh)                       │
└─────────────────────────────────────────────────────────────┘
```

## New Components

### 1. Domain Layer

#### `domain/ports/tenant_repository.py` (NEW)
```python
class TenantRepository(ABC):
    async def create(self, tenant: TenantModel) -> TenantModel
    async def get_by_name(self, name: str) -> TenantModel | None
    async def get_by_slug(self, slug: str) -> TenantModel | None
```

**Rationale**: No TenantRepository exists yet. The signup flow needs to create tenants and check for name/slug uniqueness. Kept minimal — only methods needed for onboarding.

#### `domain/entities/audit_log.py` (MODIFY)
Add: `AUTH_SIGNUP = "auth.signup"` to `AuditAction` class.

### 2. Infrastructure Layer

#### `infrastructure/persistence/repositories/tenant_repository.py` (NEW)
SQLAlchemy implementation of `TenantRepository`. Uses case-insensitive comparison for `get_by_name` (via `func.lower()`).

#### Alembic Migration `007_tenant_onboarding.py` (NEW)
1. Add unique index `uq_users_email_global` on `users.email`
2. Add unique constraint `uq_tenants_name` on `tenants.name`

**Safety check**: Migration verifies no duplicate emails exist before creating the index. If duplicates found, raises a clear error message (manual resolution required).

### 3. Application Layer

#### `application/services/signup_service.py` (NEW)
```python
class SignupService:
    def __init__(self, session: AsyncSession):
        # Creates repos internally (same pattern as auth endpoints)
        
    async def signup(
        self, email: str, password: str, full_name: str, organization_name: str
    ) -> tuple[TenantModel, UserModel]:
        """Create tenant + admin user atomically. Raises HTTPException on conflict."""
```

**Design decisions**:
- Service receives the raw `AsyncSession` and creates repos internally (consistent with how `auth.py` creates `SQLAlchemyUserRepository(session)` directly)
- The service does NOT commit — the `get_session()` context manager handles commit/rollback
- Conflict detection: check before create (application-level) + DB unique constraints (safety net for races)
- Returns `(tenant, user)` tuple — caller produces JWT tokens

#### Slug generation utility: `application/services/slug_utils.py` (NEW)
```python
def slugify(name: str) -> str:
    """Convert organization name to URL-safe slug."""

async def unique_slug(name: str, tenant_repo: TenantRepository) -> str:
    """Generate a unique slug, appending -N suffix if collisions exist."""
```

### 4. Presentation Layer

#### `presentation/api/v1/auth.py` (MODIFY)
Add `POST /signup` endpoint:
- Rate limited: `3/hour` per IP (`get_remote_address`)
- Creates `SignupService(session)`
- Calls `signup_service.signup(...)` 
- Produces JWT tokens on success
- Maps `IntegrityError` / conflict to 409

#### `presentation/schemas/auth.py` (MODIFY)
Add `SignupRequest` schema:
```python
class SignupRequest(BaseModel):
    email: EmailStr
    password: str  # min_length=8, max_length=128
    full_name: str  # min_length=1, max_length=255
    organization_name: str  # min_length=2, max_length=255
```

### 5. Settings

#### `config.py` (MODIFY)
Add: `rate_limit_signup: str = "3/hour"`

### 6. Frontend

#### `routes/signup.tsx` (NEW)
Public route at `/signup`. Same visual pattern as `login.tsx`:
- Card with form fields
- Submit calls `useAuth().signup(...)`
- Error handling for 409 (duplicate email/org) and 429 (rate limit)
- Link to `/login`

#### `shared/lib/auth.tsx` (MODIFY)
Add `signup` method to `AuthContextType` and `AuthProvider`:
```typescript
signup: (email: string, password: string, full_name: string, organization_name: string) => Promise<void>
```
Implementation: POST to `/auth/signup`, store tokens, fetch `/auth/me`.

#### `routes/login.tsx` (MODIFY)
Add link: `<Link to="/signup">¿No tiene cuenta? Regístrese</Link>`

### 7. Test Infrastructure

#### `tests/fakes/fake_tenant_repository.py` (NEW)
In-memory `TenantRepository` implementation for unit/integration tests.

#### `tests/fakes/__init__.py` (MODIFY)
Export `FakeTenantRepository`.

---

## Key Design Decisions

### ADR-SIGNUP-01: Service Pattern (Direct Session, Not DI)
**Decision**: `SignupService` receives `AsyncSession` directly in the endpoint (same as login/me endpoints), NOT via FastAPI DI.
**Rationale**: Consistency with existing `auth.py` pattern. Auth endpoints already create `SQLAlchemyUserRepository(session)` inline. Adding DI for just one endpoint would be inconsistent.

### ADR-SIGNUP-02: Email Uniqueness — Global Index
**Decision**: Add a unique index on `users.email` (global), keeping the existing `uq_users_tenant_email` composite constraint.
**Rationale**: Since email is the login credential and `get_by_email` already searches without tenant filter, emails MUST be globally unique. The composite constraint remains for backward compatibility.

### ADR-SIGNUP-03: Conflict Detection — Check Then Create
**Decision**: Application-level pre-check (query before insert) + DB constraint as safety net.
**Rationale**: Pre-checks provide clear, user-friendly error messages ("Email already registered" vs generic IntegrityError). DB constraints catch race conditions. Both are needed.

### ADR-SIGNUP-04: No Separate Signup Use Case Class
**Decision**: `SignupService` is a single-purpose service class, not a generic use case.
**Rationale**: Signup is a compound operation (tenant + user + tier + audit) that doesn't fit neatly into existing service classes. A dedicated service keeps it cohesive and testable.

### ADR-SIGNUP-05: Free Tier Resolution
**Decision**: Look up Free tier by slug (`"free"`) at signup time, not hardcode UUID.
**Rationale**: The deterministic UUID (`uuid5(NAMESPACE_DNS, "sigdoc.tier.free")`) is an implementation detail of the migration. Looking up by slug is more robust and decoupled.

---

## File Impact Summary

| File | Action | Description |
|------|--------|-------------|
| `domain/ports/tenant_repository.py` | NEW | TenantRepository port |
| `domain/entities/audit_log.py` | MODIFY | Add AUTH_SIGNUP constant |
| `infrastructure/persistence/repositories/tenant_repository.py` | NEW | SQLAlchemy TenantRepository |
| `application/services/signup_service.py` | NEW | Signup orchestration service |
| `application/services/slug_utils.py` | NEW | Slug generation utilities |
| `application/services/__init__.py` | MODIFY | Export signup service factory |
| `presentation/api/v1/auth.py` | MODIFY | Add /signup endpoint |
| `presentation/schemas/auth.py` | MODIFY | Add SignupRequest schema |
| `config.py` | MODIFY | Add rate_limit_signup setting |
| `alembic/versions/007_tenant_onboarding.py` | NEW | DB migration |
| `tests/fakes/fake_tenant_repository.py` | NEW | Fake for tests |
| `tests/fakes/__init__.py` | MODIFY | Export FakeTenantRepository |
| `tests/unit/test_signup_service.py` | NEW | Unit tests |
| `tests/unit/test_slug_utils.py` | NEW | Slug utility tests |
| `tests/integration/test_signup_api.py` | NEW | Integration tests |
| `frontend/src/routes/signup.tsx` | NEW | Signup page |
| `frontend/src/shared/lib/auth.tsx` | MODIFY | Add signup method |
| `frontend/src/routes/login.tsx` | MODIFY | Add signup link |
