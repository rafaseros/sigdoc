#!/usr/bin/env bash
#
# SigDoc portable backup bundle.
#
# Produces ONE downloadable archive with a full snapshot of both stateful
# services:
#   - Postgres : pg_dump of the sigdoc database (gzip)
#   - MinIO    : the templates + documents buckets
#
# The archive is written to /opt/docker/backups/sigdoc/bundles/ and the script
# prints a size breakdown so you can size an off-site / paid backup target
# (e.g. DigitalOcean Spaces) before committing to one.
#
# Runs ON THE DROPLET (reads /opt/docker/apps/sigdoc/.env directly), on the
# same host as the SigDoc stack. Download it with infra/backup/fetch-backup.sh.
#
set -euo pipefail

APP_DIR="/opt/docker/apps/sigdoc"
ENV_FILE="${APP_DIR}/.env"
BUNDLE_DIR="/opt/docker/backups/sigdoc/bundles"
MC_IMAGE="minio/mc:RELEASE.2025-08-13T08-35-41Z"
PG_CONTAINER="sigdoc-postgres"
RETENTION_BUNDLES=5 # keep the newest N bundles on the droplet

if [ ! -f "$ENV_FILE" ]; then
  echo "Environment file not found: $ENV_FILE" >&2
  exit 1
fi

# Parse only the variables we need, without sourcing (and executing) the .env.
POSTGRES_USER=$(grep -E '^POSTGRES_USER=' "$ENV_FILE" | tail -n1 | cut -d '=' -f2- || true)
POSTGRES_DB=$(grep -E '^POSTGRES_DB=' "$ENV_FILE" | tail -n1 | cut -d '=' -f2- || true)
MINIO_ROOT_USER=$(grep -E '^MINIO_ROOT_USER=' "$ENV_FILE" | tail -n1 | cut -d '=' -f2- || true)
MINIO_ROOT_PASSWORD=$(grep -E '^MINIO_ROOT_PASSWORD=' "$ENV_FILE" | tail -n1 | cut -d '=' -f2- || true)

if [ -z "$POSTGRES_USER" ] || [ -z "$POSTGRES_DB" ] || [ -z "$MINIO_ROOT_USER" ] || [ -z "$MINIO_ROOT_PASSWORD" ]; then
  echo "Missing POSTGRES_USER / POSTGRES_DB / MINIO_ROOT_USER / MINIO_ROOT_PASSWORD in $ENV_FILE" >&2
  exit 1
fi

SIGDOC_NETWORK=$(docker network ls --format '{{.Name}}' | grep sigdoc-network | head -1 || true)
if [ -z "$SIGDOC_NETWORK" ]; then
  echo "Could not detect the sigdoc-network Docker network (is the stack running?)." >&2
  exit 1
fi

TIMESTAMP=$(date +%Y%m%d-%H%M%S)
mkdir -p "$BUNDLE_DIR"
STAGING=$(mktemp -d "${BUNDLE_DIR}/.staging.XXXXXX")

# Always clean the staging dir, even on failure. Files written by the mc
# container are root-owned, so drop them via a throwaway container first in
# case we failed before reclaiming ownership below.
cleanup() {
  if [ -n "${STAGING:-}" ] && [ -d "$STAGING" ]; then
    docker run --rm -v "${STAGING}:/s" --entrypoint /bin/sh "$MC_IMAGE" \
      -c 'rm -rf /s/* /s/.[!.]* 2>/dev/null || true' >/dev/null 2>&1 || true
    rm -rf "$STAGING" 2>/dev/null || true
  fi
}
trap cleanup EXIT

mkdir -p "${STAGING}/postgres" "${STAGING}/minio/templates" "${STAGING}/minio/documents"

echo "==> Dumping Postgres database ($POSTGRES_DB)..."
docker exec "$PG_CONTAINER" pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
  | gzip >"${STAGING}/postgres/pg_${TIMESTAMP}.sql.gz"

echo "==> Copying MinIO buckets (templates, documents)..."
docker run --rm \
  --network "$SIGDOC_NETWORK" \
  -v "${STAGING}/minio:/backup" \
  --entrypoint /bin/sh \
  "$MC_IMAGE" \
  -c "
    mc alias set sigdoc http://minio:9000 '${MINIO_ROOT_USER}' '${MINIO_ROOT_PASSWORD}';
    mc mirror --overwrite sigdoc/templates /backup/templates;
    mc mirror --overwrite sigdoc/documents /backup/documents;
  "

# Reclaim ownership of the mirrored (root-owned) files for the invoking user so
# tar and the cleanup rm work without sudo.
docker run --rm -v "${STAGING}:/s" --entrypoint /bin/sh "$MC_IMAGE" \
  -c "chown -R $(id -u):$(id -g) /s" >/dev/null 2>&1 || true

# ---- sizes (the data you need to size an off-site target) -----------------
PG_SIZE=$(du -h "${STAGING}/postgres/pg_${TIMESTAMP}.sql.gz" | cut -f1)
TPL_SIZE=$(du -sh "${STAGING}/minio/templates" | cut -f1)
DOC_SIZE=$(du -sh "${STAGING}/minio/documents" | cut -f1)
TPL_COUNT=$(find "${STAGING}/minio/templates" -type f | wc -l | tr -d ' ')
DOC_COUNT=$(find "${STAGING}/minio/documents" -type f | wc -l | tr -d ' ')

# ---- manifest (travels inside the bundle) ---------------------------------
cat >"${STAGING}/MANIFEST.txt" <<EOF
SigDoc backup bundle
Created:          $(date -Iseconds)
Database:         ${POSTGRES_DB}
Postgres dump:    postgres/pg_${TIMESTAMP}.sql.gz (${PG_SIZE})
MinIO templates:  minio/templates (${TPL_SIZE}, ${TPL_COUNT} objects)
MinIO documents:  minio/documents (${DOC_SIZE}, ${DOC_COUNT} objects)

Restore instructions: infra/backup/README.md
EOF

BUNDLE="${BUNDLE_DIR}/sigdoc-backup_${TIMESTAMP}.tar.gz"
echo "==> Creating bundle..."
tar -czf "$BUNDLE" -C "$STAGING" postgres minio MANIFEST.txt
BUNDLE_SIZE=$(du -h "$BUNDLE" | cut -f1)

echo "==> Rotating bundles (keeping newest ${RETENTION_BUNDLES})..."
# shellcheck disable=SC2012  # controlled timestamped names; -t sorts by mtime
ls -1t "${BUNDLE_DIR}"/sigdoc-backup_*.tar.gz 2>/dev/null \
  | tail -n +$((RETENTION_BUNDLES + 1)) | xargs -r rm -f

cat <<EOF

================= SigDoc backup bundle =================
 Postgres dump   : ${PG_SIZE}
 MinIO templates : ${TPL_SIZE} (${TPL_COUNT} objects)
 MinIO documents : ${DOC_SIZE} (${DOC_COUNT} objects)
 -------------------------------------------------------
 Bundle (.tar.gz): ${BUNDLE_SIZE}
 Path            : ${BUNDLE}
========================================================
Download it to your machine with:
  SIGDOC_SSH=<user@droplet> infra/backup/fetch-backup.sh
Off-site sizing: compare the bundle size against a paid target such as
DigitalOcean Spaces (250 GB for ~US\$5/mo, S3-compatible).
EOF
