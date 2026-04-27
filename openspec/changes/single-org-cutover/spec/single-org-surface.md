# Capability: single-org-surface

## Purpose

Defines the post-cutover user-facing surface for Nivel A of the CAINCO acquisition. Locks which HTTP endpoints and frontend routes are reachable (200-class) vs explicitly disabled (404), which links and UI elements are absent from the login and authenticated layouts, and the invariant that email verification is always presented as satisfied regardless of the database column value. This spec is the cosmetic-and-surface contract — implementation details are deferred to the design document.

## Requirements

### REQ-SOS-01: Unroute POST /api/v1/auth/signup
`POST /api/v1/auth/signup` MUST return 404 to any caller. The handler file MAY remain on disk; the router include in `main.py` MUST be removed (or the handler function deleted).

### REQ-SOS-02: Unroute email-verification and self-service password endpoints
`POST /api/v1/auth/verify-email`, `POST /api/v1/auth/resend-verification`, `POST /api/v1/auth/forgot-password`, and `POST /api/v1/auth/reset-password` MUST all return 404.

### REQ-SOS-03: Unroute tiers and usage API routers
`GET /api/v1/tiers/*` and `GET /api/v1/usage/*` (all paths under those prefixes) MUST return 404. The router source files MAY remain on disk; the `include_router` calls in `main.py` MUST be removed.

### REQ-SOS-04: Remove frontend /signup route
The frontend route `/signup` MUST NOT exist. Navigating to that URL after deploy MUST render the TanStack Router not-found component (or equivalent 404 UI).

### REQ-SOS-05: Remove frontend email-verification and self-service password routes
The frontend routes `/verify-email`, `/forgot-password`, and `/reset-password` MUST NOT exist. Navigating to any of those URLs MUST render the not-found component.

### REQ-SOS-06: Remove frontend subscription and usage routes
The frontend routes `/subscription` and `/usage` MUST NOT exist. Navigating to either URL MUST render the not-found component.

### REQ-SOS-07: Clean login page — no self-service links
The login page (`frontend/src/routes/login.tsx`) MUST NOT contain any "Regístrese", "¿No tiene cuenta?", or "¿Olvidaste tu contraseña?" text or links. The login form MUST contain only the credential fields and a submit action.

### REQ-SOS-08: Clean authenticated nav — no SaaS links
The authenticated layout (`frontend/src/routes/_authenticated.tsx`) MUST NOT render navigation links to `/subscription` or `/usage`.

### REQ-SOS-09: Remove VerificationBanner from authenticated layout
The `VerificationBanner` component MUST NOT render anywhere in the authenticated layout. The component file MAY be deleted.

### REQ-SOS-10: Remove QuotaExceededDialog wiring
The `QuotaExceededDialog` component MUST NOT be mounted in the authenticated layout. The 429 event listener in `frontend/src/shared/lib/api-client.ts` that dispatches the `QUOTA_EXCEEDED_EVENT` custom event MUST be removed.

### REQ-SOS-11: Delete frontend/src/features/subscription/ directory
The `frontend/src/features/subscription/` directory (6 files: `QuotaExceededDialog`, `TierCard`, `api/index.ts`, `api/keys.ts`, `api/queries.ts`, `index.ts`) MUST be deleted. No file in that directory MUST remain in the repository after this change.

### REQ-SOS-12: Delete frontend/src/features/usage/ directory
The `frontend/src/features/usage/` directory (6 files: `UsageWidget`, `TenantUsageTable`, `api/index.ts`, `api/keys.ts`, `api/queries.ts`, `index.ts`) MUST be deleted.

### REQ-SOS-13: Remove _require_verified_email dependency from documents.py
The `_require_verified_email` dependency function in `backend/src/app/presentation/api/v1/documents.py` (lines ~47–68) MUST be removed. Both call sites (single generate ~line 85, bulk generate ~line 170) MUST be removed. Both endpoints MUST accept any authenticated user subject to existing role gates.

### REQ-SOS-14: GET /api/v1/auth/me always returns email_verified true
`GET /api/v1/auth/me` MUST return `email_verified: true` for every authenticated user, regardless of the value stored in the database column.

### REQ-SOS-15: User domain entity default email_verified true
The `User` domain entity (`backend/src/app/domain/entities/user.py`) MUST default `email_verified` to `True`. This reinforces REQ-SOS-14 at construction time for any newly created user objects.

### REQ-SOS-16: User count badge — count only, no denominator
The user-count badge in `frontend/src/routes/_authenticated/users/index.tsx` MUST display only the count (e.g., "3 usuarios") with no slash and no denominator. The data source MUST be the existing `useUsers()` query result length, not the unrouted `/api/v1/tiers/tenant` response. The `useTenantTier` import MUST be removed from that file.

### REQ-SOS-17: TypeScript compilation clean after all deletions
`npx tsc --noEmit -p tsconfig.app.json` (run from the frontend directory) MUST exit 0 after all file deletions and modifications are applied. No new TypeScript errors MAY be introduced.

### REQ-SOS-18: ESLint clean after all changes
`npm run lint` MUST report 0 errors after this change. The 4 pre-existing warnings in shadcn primitives and `auth.tsx` are tolerated and MUST NOT be converted to errors.

### REQ-SOS-19: Admin user creation has no email side effects
`POST /api/v1/users` (admin-create-user) MUST NOT trigger any email-sending side effect. No call to `EmailVerificationService` or any SMTP operation MUST occur during admin user creation.

### REQ-SOS-20: Deprecated handler files carry DEPRECATED docstring
The service files `signup_service.py`, `email_verification_service.py`, and `password_reset_service.py` MUST each carry a module-level docstring of the form `"""DEPRECATED: route disabled per single-org-cutover; remove in Nivel B."""`. These files MUST NOT be deleted in this change.

## Scenarios

### SCEN-SOS-01: POST to unrouted signup endpoint returns 404
**Given**: The application is deployed after single-org-cutover  
**When**: A caller sends `POST /api/v1/auth/signup` with a valid JSON body  
**Then**: The response status MUST be 404  
*(Verifies REQ-SOS-01)*

### SCEN-SOS-02: POST to verify-email returns 404
**Given**: The application is deployed after single-org-cutover  
**When**: A caller sends `POST /api/v1/auth/verify-email` with a token  
**Then**: The response status MUST be 404  
*(Verifies REQ-SOS-02)*

### SCEN-SOS-03: POST to forgot-password returns 404
**Given**: The application is deployed after single-org-cutover  
**When**: A caller sends `POST /api/v1/auth/forgot-password` with an email  
**Then**: The response status MUST be 404  
*(Verifies REQ-SOS-02)*

### SCEN-SOS-04: GET tiers/tenant returns 404
**Given**: The application is deployed after single-org-cutover  
**When**: An authenticated user sends `GET /api/v1/tiers/tenant`  
**Then**: The response status MUST be 404  
*(Verifies REQ-SOS-03)*

### SCEN-SOS-05: GET usage/me returns 404
**Given**: The application is deployed after single-org-cutover  
**When**: An authenticated user sends `GET /api/v1/usage/me`  
**Then**: The response status MUST be 404  
*(Verifies REQ-SOS-03)*

### SCEN-SOS-06: Browser navigates to /signup — not-found page shown
**Given**: The frontend is deployed after single-org-cutover  
**When**: A browser navigates to `https://sigdoc.devrafaseros.com/signup`  
**Then**: The TanStack Router not-found component is rendered; no signup form is visible  
*(Verifies REQ-SOS-04)*

### SCEN-SOS-07: Login page has no self-service links
**Given**: The frontend is deployed after single-org-cutover  
**When**: A browser renders the `/login` page  
**Then**: The DOM MUST NOT contain any element with text "Regístrese", "¿No tiene cuenta?", or "¿Olvidaste tu contraseña?"  
*(Verifies REQ-SOS-07)*

### SCEN-SOS-08: Authenticated nav has no SaaS links
**Given**: An admin is authenticated and viewing any page in the authenticated layout  
**When**: The application renders the navigation header  
**Then**: The navigation MUST NOT contain links or text for "Suscripción" or "Uso"  
*(Verifies REQ-SOS-08)*

### SCEN-SOS-09: /auth/me returns email_verified true regardless of DB value
**Given**: A user exists in the database with `email_verified = false`  
**When**: That user sends `GET /api/v1/auth/me` with a valid JWT  
**Then**: The response body MUST include `"email_verified": true`  
*(Verifies REQ-SOS-14)*

### SCEN-SOS-10: User count badge shows count only
**Given**: There are 3 users in the system and admin is viewing `/users`  
**When**: The UsersPage renders  
**Then**: The badge displays "3 usuarios" with no slash and no denominator; `useTenantTier` is NOT called  
*(Verifies REQ-SOS-16)*

### SCEN-SOS-11: Admin creates user — no email sent
**Given**: An admin is authenticated  
**When**: Admin sends `POST /api/v1/users` with a valid user payload  
**Then**: The response is 201 Created AND no SMTP interaction (email send) occurs  
*(Verifies REQ-SOS-19)*

### SCEN-SOS-12: Document generation works without email-verification gate
**Given**: An authenticated user with role `document_generator` and `email_verified = false` in DB  
**When**: That user sends `POST /api/v1/documents/generate` with a valid template and variables  
**Then**: The response is 200 (or 202) with the generated document; no 403 is returned due to email verification  
*(Verifies REQ-SOS-13)*

### SCEN-SOS-13: TypeScript build is clean
**Given**: All file deletions and modifications from this change are applied  
**When**: `npx tsc --noEmit -p tsconfig.app.json` is run from the frontend directory  
**Then**: The command exits with code 0 and no errors are printed  
*(Verifies REQ-SOS-17)*

### SCEN-SOS-14: ESLint reports zero errors
**Given**: All file deletions and modifications from this change are applied  
**When**: `npm run lint` is run from the frontend directory  
**Then**: The command reports 0 errors (pre-existing warnings are tolerated)  
*(Verifies REQ-SOS-18)*
