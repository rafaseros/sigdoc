#!/usr/bin/env bash
#
# SigDoc backup script — Postgres dump + MinIO bucket mirror.
# Runs on the droplet (reads /opt/docker/apps/sigdoc/.env directly).
# See README.md in this directory for cron setup and restore steps.
set -euo pipefail

APP_DIR="/opt/docker/apps/sigdoc"
ENV_FILE="${APP_DIR}/.env"
BACKUP_ROOT="/opt/docker/backups/sigdoc"
MINIO_BACKUP_DIR="${BACKUP_ROOT}/minio"
MC_IMAGE="minio/mc:RELEASE.2025-08-13T08-35-41Z"
RETENTION_DAYS=7

if [ ! -f "$ENV_FILE" ]; then
  echo "Environment file not found: $ENV_FILE" >&2
  exit 1
fi

# Parse only the variables we need, without sourcing (and executing) the rest of the file.
POSTGRES_USER=$(grep -E '^POSTGRES_USER=' "$ENV_FILE" | tail -n1 | cut -d '=' -f2- || true)
POSTGRES_DB=$(grep -E '^POSTGRES_DB=' "$ENV_FILE" | tail -n1 | cut -d '=' -f2- || true)
MINIO_ROOT_USER=$(grep -E '^MINIO_ROOT_USER=' "$ENV_FILE" | tail -n1 | cut -d '=' -f2- || true)
MINIO_ROOT_PASSWORD=$(grep -E '^MINIO_ROOT_PASSWORD=' "$ENV_FILE" | tail -n1 | cut -d '=' -f2- || true)

if [ -z "$POSTGRES_USER" ] || [ -z "$POSTGRES_DB" ] || [ -z "$MINIO_ROOT_USER" ] || [ -z "$MINIO_ROOT_PASSWORD" ]; then
  echo "Missing one or more required variables (POSTGRES_USER, POSTGRES_DB, MINIO_ROOT_USER, MINIO_ROOT_PASSWORD) in $ENV_FILE" >&2
  exit 1
fi

mkdir -p "$BACKUP_ROOT" "$MINIO_BACKUP_DIR"

echo "==> Backing up Postgres database ($POSTGRES_DB)..."
PG_DUMP_FILE="${BACKUP_ROOT}/pg_$(date +%F).sql.gz"
docker exec sigdoc-postgres pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" | gzip > "$PG_DUMP_FILE"
echo "    -> $PG_DUMP_FILE"

echo "==> Backing up MinIO buckets (templates, documents)..."
SIGDOC_NETWORK=$(docker network ls --format '{{.Name}}' | grep sigdoc-network | head -1 || true)
if [ -z "$SIGDOC_NETWORK" ]; then
  echo "Could not detect the sigdoc-network Docker network (is the stack running?)." >&2
  exit 1
fi

mkdir -p "${MINIO_BACKUP_DIR}/templates" "${MINIO_BACKUP_DIR}/documents"

docker run --rm \
  --network "$SIGDOC_NETWORK" \
  -v "${MINIO_BACKUP_DIR}:/backup" \
  --entrypoint /bin/sh \
  "$MC_IMAGE" \
  -c "
    mc alias set sigdoc http://minio:9000 '${MINIO_ROOT_USER}' '${MINIO_ROOT_PASSWORD}';
    mc mirror --overwrite sigdoc/templates /backup/templates;
    mc mirror --overwrite sigdoc/documents /backup/documents;
  "

echo "==> Rotating Postgres dumps older than ${RETENTION_DAYS} days..."
find "$BACKUP_ROOT" -maxdepth 1 -name 'pg_*.sql.gz' -mtime "+${RETENTION_DAYS}" -delete

echo "Backup completed at $(date -Iseconds)"
