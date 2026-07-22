#!/usr/bin/env bash
# Local-dev ONLY: reset the canonical admin (devrafaseros@gmail.com) via the
# HTTP dev-reset endpoint. NEVER for production — the endpoint is pinned OFF in
# docker-compose.prod.yml. For production recovery use scripts/reset-admin.sh.
#
# Requires, in your LOCAL .env, ENABLE_DEV_RESET=true and DEV_RESET_TOKEN=<secret>,
# and a restart of the api container. The same secret must be passed here so it
# can be echoed in the X-Dev-Reset-Token header.
#
# Usage:
#   DEV_RESET_TOKEN=<secret> ./scripts/dev-reset-admin.sh
#   ./scripts/dev-reset-admin.sh <secret>
#
# On success the endpoint returns a freshly generated random password ONCE, in
# the JSON response printed below — copy it to log in. There is no hardcoded
# password anymore.
set -euo pipefail

BASE_URL="${DEV_RESET_BASE_URL:-http://localhost:8000}"
TOKEN="${1:-${DEV_RESET_TOKEN:-}}"

if [[ -z "${TOKEN}" ]]; then
  echo "error: dev reset token required (arg 1 or DEV_RESET_TOKEN env)" >&2
  exit 1
fi

curl -fsSL -X POST "${BASE_URL}/api/v1/dev/reset-admin" \
  -H "X-Dev-Reset-Token: ${TOKEN}"
echo
