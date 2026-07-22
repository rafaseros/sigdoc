#!/usr/bin/env bash
#
# rollback.sh — one-command production rollback to a prior immutable image build.
#
# SigDoc CI pushes an immutable per-commit tag for every build:
#   ghcr.io/rafaseros/sigdoc-api:sha-<gitsha>
#   ghcr.io/rafaseros/sigdoc-frontend:sha-<gitsha>
# docker-compose.prod.yml resolves the running tag from ${SIGDOC_IMAGE_TAG:-latest},
# so re-deploying an older build is just: pin SIGDOC_IMAGE_TAG and `up -d`.
#
# This script re-deploys a target commit's images on the droplet. It does NOT run
# database migrations: rolling back the schema is a deliberate, manual decision
# (`alembic upgrade` only moves forward, never downgrades), so a rollback swaps the
# running code only. If the target predates a migration, downgrade the schema by
# hand before rolling back.
#
# Usage (on the droplet host):
#   ./scripts/rollback.sh <git-sha>        # e.g. ./scripts/rollback.sh 7a71b0d
#   ./scripts/rollback.sh sha-<git-sha>    # a leading "sha-" is accepted too
#
# Usage (over SSH from your workstation):
#   ssh <user>@<host> 'bash -s' -- <git-sha> < scripts/rollback.sh
#
# Environment overrides:
#   SIGDOC_APP_DIR     compose project dir on the host (default /opt/docker/apps/sigdoc)
#   SIGDOC_COMPOSE     compose file name (default docker-compose.prod.yml)
#
set -euo pipefail

if [ "$#" -ne 1 ] || [ -z "${1:-}" ]; then
  echo "usage: $(basename "$0") <git-sha>" >&2
  echo "  re-deploys ghcr.io/rafaseros/sigdoc-{api,frontend}:sha-<git-sha> on the droplet" >&2
  exit 2
fi

# Accept either "<sha>" or "sha-<sha>"; normalize to the bare sha, then the tag.
raw_sha="$1"
bare_sha="${raw_sha#sha-}"
image_tag="sha-${bare_sha}"

app_dir="${SIGDOC_APP_DIR:-/opt/docker/apps/sigdoc}"
compose_file="${SIGDOC_COMPOSE:-docker-compose.prod.yml}"

if [ ! -d "$app_dir" ]; then
  echo "error: app dir '$app_dir' not found (set SIGDOC_APP_DIR)" >&2
  exit 1
fi
cd "$app_dir"

echo "==> Rolling back SigDoc to ${image_tag}"
export SIGDOC_IMAGE_TAG="${image_tag}"

# Fetch the target build. Recent tags usually remain on the host (deploy prunes
# only dangling images), so if the pull fails we continue when the images already
# exist locally, and abort with guidance otherwise.
if ! docker compose -f "$compose_file" pull api frontend; then
  echo "warn: pull failed — checking for locally cached images" >&2
  for svc in api frontend; do
    img="ghcr.io/rafaseros/sigdoc-${svc}:${image_tag}"
    if ! docker image inspect "$img" >/dev/null 2>&1; then
      echo "error: '$img' is not available locally and could not be pulled." >&2
      echo "       Log in first:  docker login ghcr.io" >&2
      exit 1
    fi
  done
  echo "==> Using locally cached images for ${image_tag}"
fi

# Recreate containers on the pinned tag. Only api/frontend changed, so the other
# services (db, minio, gotenberg) are left running untouched.
docker compose -f "$compose_file" up -d

# Smoke test — mirror the deploy health check so a bad rollback is caught here.
sleep 5
api_status="$(docker compose -f "$compose_file" exec -T api \
  curl -s -o /dev/null -w '%{http_code}' http://localhost:8000/api/v1/health || true)"
if [ "$api_status" != "200" ]; then
  echo "error: API health check failed after rollback (HTTP ${api_status:-none})" >&2
  exit 1
fi

echo "OK: SigDoc rolled back to ${image_tag} (API healthy)"
