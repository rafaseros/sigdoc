# SigDoc Backend

Document template management and generation system. FastAPI + SQLAlchemy + MinIO + Gotenberg (PDF).

## Local development

The full stack runs via `docker/docker-compose.yml`:

```bash
docker compose -f docker/docker-compose.yml up -d
```

Services: `db` (Postgres 16), `minio`, `gotenberg` (LibreOffice PDF converter), `api`, `nginx`. Hot-reload mounts `backend/src` and `backend/alembic` into the api container, so source edits don't require a rebuild.

API: `http://localhost:8000` · MinIO console: `http://localhost:9001` · Frontend dev server (separate): `npm run dev` from `frontend/`.

## Running tests

The api container does NOT include test dependencies or the `tests/` tree by default. Two options:

- **Host pytest** — fastest for unit tests; integration tests that need DB/MinIO will fail to collect without the runtime env. Run from `backend/`:
  ```bash
  pytest
  ```
- **Container pytest** — required for the full suite. The runtime image has pytest available; copy the test tree in if needed:
  ```bash
  docker compose -f docker/docker-compose.yml exec -T api pytest -q
  ```

The `tests/` directory not being mounted in `docker-compose.yml` is a known dev-env gap; mount it if you run the full suite frequently.

## Deploy checklist

Before promoting from a dev container to a fresh build (CI image, prod, staging), do these in order:

1. **Rebuild the api image.** `httpx` was promoted from dev to production deps in migration `010_pdf_export.py`'s phase. A dev container built before that change keeps working only because `pip install httpx` was run manually — a fresh image needs the rebuild:
   ```bash
   docker compose -f docker/docker-compose.yml build api
   ```
2. **Apply migrations.** Alembic head must match application code:
   ```bash
   docker compose -f docker/docker-compose.yml exec -T api alembic upgrade head
   ```
3. **Verify Gotenberg is healthy.** The api `depends_on` Gotenberg with `condition: service_healthy`. If the dependency hangs, check the Gotenberg container logs and `/health` endpoint.
4. **nginx upstream timeouts.** `docker/nginx/nginx.conf` sets `proxy_read_timeout` and `proxy_send_timeout` to `300s` on `/api/`. The bulk PDF download path can take ~150s worst-case (50-row legacy backfill); for production under heavier load consider raising to `600s`.
5. **Required environment variables** (see `.env.example`). Critical ones for the PDF flow:
   - `GOTENBERG_URL` (default `http://gotenberg:3000` inside the compose network)
   - `GOTENBERG_TIMEOUT` (default `60`, seconds)
   - `ADMIN_PASSWORD` — required for the canonical admin seed migration `008` on first deploy.

## Role model

Three roles are active as of migration `011_role_expansion.py`:

| Role | Capabilities | Download formats |
|------|-------------|-----------------|
| `admin` | All capabilities — user management, audit, usage, templates, generate | `docx` + `pdf` |
| `template_creator` | Upload templates, add versions, generate from own/shared templates | `pdf` only |
| `document_generator` | Generate from shared templates only | `pdf` only |

**Default role** for new users: `document_generator` (set in `domain/entities/user.py`, `infrastructure/persistence/models/user.py`, and `presentation/api/v1/users.py`).

**Key helpers** (all in `domain/services/permissions.py`):
- `can_manage_own_templates(role)` → `True` for `admin` and `template_creator`
- `can_manage_users`, `can_view_audit`, `can_view_tenant_usage` → `True` for `admin` only

**FastAPI dependencies** (in `presentation/api/dependencies.py`):
- `require_template_manager` — gates `POST /templates/upload` and `POST /templates/{id}/versions`; returns 403 for `document_generator`
- `require_user_manager`, `require_audit_viewer`, `require_tenant_usage_viewer` — admin-only gates

**Migration `011_role_expansion.py`** (ordering caveat — per ADR-ROLE-02):
- `upgrade()`: `UPDATE users SET role='template_creator' WHERE role='user'` **BEFORE** `ALTER COLUMN role SET DEFAULT 'document_generator'` — data must be migrated before the default changes to avoid partial state.
- `downgrade()`: `ALTER COLUMN role SET DEFAULT 'user'` **BEFORE** `UPDATE` that collapses both new roles back to `'user'` — default must revert first. Downgrade is **lossy**: `template_creator` and `document_generator` are both collapsed to `'user'`; the original role cannot be recovered.

**Download format permissions** (`domain/services/document_permissions.py`):
- `admin` → `docx` + `pdf`; all other roles (including unknown/legacy tokens) → `pdf` only.
- The legacy `"user"` key is intentionally absent from `DOWNLOAD_FORMAT_PERMISSIONS`; stale tokens with `role="user"` resolve to PDF-only via the safe-default.

## VPS deployment notes (sigdoc.devrafaseros.com)

### .env location

The production environment file lives at `/opt/docker/apps/sigdoc/.env` on the VPS. It is a hidden file — use `ls -la /opt/docker/apps/sigdoc/` to see it.

### Required variables

The following variables must be present in `.env` for a functioning deployment:

```
# PostgreSQL
POSTGRES_DB=<db name>
POSTGRES_USER=<db user>
POSTGRES_PASSWORD=<db password>

# MinIO object storage
MINIO_ROOT_USER=<access key>
MINIO_ROOT_PASSWORD=<secret key>

# Auth
SECRET_KEY=<long random string>
ADMIN_EMAIL=<initial admin email>
ADMIN_PASSWORD=<initial admin password>

# Optional — token lifetimes
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7
```

### Demo / PDF / email variables

The prod compose uses `env_file: .env` on the `api` service, which forwards ALL variables from `.env` into the container. The explicit `environment:` block in `docker-compose.prod.yml` only overrides compose-computed values (internal Docker hostnames, `MINIO_SECURE=false`, etc.).

Variables relevant to demo and production features:

```
# PDF generation (Gotenberg)
GOTENBERG_URL=http://gotenberg:3000   # default — internal Docker network
GOTENBERG_TIMEOUT=60                  # seconds

# Dev reset endpoint — ONLY enable if you need the one-shot admin recovery endpoint
ENABLE_DEV_RESET=false                # never true in a real production deployment

# Email
EMAIL_BACKEND=smtp                    # or "console" for local/debug
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=<smtp user>
SMTP_PASSWORD=<smtp password>
SMTP_FROM_ADDRESS=noreply@sigdoc.local
FRONTEND_URL=https://sigdoc.devrafaseros.com
```

Note: the app config key is `SMTP_FROM_ADDRESS`, not `SMTP_FROM`. If your `.env` has `SMTP_FROM`, rename it to `SMTP_FROM_ADDRESS` to avoid a pydantic-settings extra-field validation error inside the container.

### Activating the dev reset endpoint in production

The `POST /api/v1/dev/reset-admin` endpoint is gated behind `ENABLE_DEV_RESET=true`. To use it temporarily on the demo VPS:

1. Edit `/opt/docker/apps/sigdoc/.env` and set `ENABLE_DEV_RESET=true`.
2. Restart the api container: `docker compose -f /opt/docker/apps/sigdoc/docker-compose.prod.yml restart api`.
3. Issue the reset request.
4. Set `ENABLE_DEV_RESET=false` again and restart.

### Common .env hygiene

**Duplicate `ADMIN_PASSWORD` keys**: If your `.env` has two `ADMIN_PASSWORD` entries (e.g., one from the initial bootstrap and a later override), only the LAST value is read by the shell — but this is fragile and confusing. Remove the first occurrence manually with your editor. Example of what to clean up:

```
# REMOVE THIS:
ADMIN_PASSWORD=8b487fdf2f793420ccaf8e3b
# KEEP ONLY THIS:
ADMIN_PASSWORD='Doit.Sigdoc1991'
```

After editing `.env`, restart the api container for the change to take effect.

### Migration 012 — one-shot demo reset

`backend/alembic/versions/012_demo_reset.py` is a destructive, irreversible migration intended exclusively for the CAINCO demo on the demo VPS.

**What it does:**
1. Checks that there are 10 or fewer users (safety guard — refuses to run on a populated database).
2. Deletes all rows from every user-data table in FK-safe order: `audit_logs`, `usage_events`, `template_shares`, `documents`, `template_versions`, `templates`, `users`, `tenants`.
3. Re-seeds a single demo tenant (`SigDoc Demo` / slug `sigdoc-demo`) and one admin user (`devrafaseros@gmail.com` / `admin123!` / role `admin`).

**Tables NOT touched:** `subscription_tiers` and its rate-limit columns (seeded by migrations 005 and 006 — must survive), `alembic_version` (Alembic internal).

**Safety guard:** If `SELECT COUNT(*) FROM users` returns more than 10, the migration aborts with a `RuntimeError`. To override intentionally, raise `SAFETY_THRESHOLD` in the migration file first.

**Downgrade:** `downgrade()` is a no-op. The wipe cannot be reversed. If you need to recover, restore from a DB snapshot taken before running this migration.

**After it runs once:** The revision `012` is recorded in `alembic_version`. Future `alembic upgrade head` calls see it as already applied and skip it — the wipe does NOT re-run on subsequent deploys.

## Architecture

Hexagonal — domain ports define abstractions, infrastructure adapts them.

- `app/domain/ports/` — abstract interfaces (`StorageService`, `TemplateEngine`, `PdfConverter`, repositories)
- `app/domain/services/` — pure domain logic (`permissions.py` is the single source of truth for role-based capability checks)
- `app/infrastructure/` — concrete adapters (MinIO storage, docxtpl engine, Gotenberg PDF converter, SQLAlchemy repositories)
- `app/application/services/` — orchestration (`DocumentService` runs the atomic dual-format generate flow)
- `app/presentation/api/v1/` — FastAPI routers; permission gates use the helpers in `domain/services/permissions.py`
