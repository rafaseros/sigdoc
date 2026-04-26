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

## Architecture

Hexagonal — domain ports define abstractions, infrastructure adapts them.

- `app/domain/ports/` — abstract interfaces (`StorageService`, `TemplateEngine`, `PdfConverter`, repositories)
- `app/domain/services/` — pure domain logic (`permissions.py` is the single source of truth for role-based capability checks)
- `app/infrastructure/` — concrete adapters (MinIO storage, docxtpl engine, Gotenberg PDF converter, SQLAlchemy repositories)
- `app/application/services/` — orchestration (`DocumentService` runs the atomic dual-format generate flow)
- `app/presentation/api/v1/` — FastAPI routers; permission gates use the helpers in `domain/services/permissions.py`
