#!/usr/bin/env bash
#
# Production admin recovery — SERVER-SIDE ONLY (run on the droplet host).
#
# This is the ONLY supported way to recover an admin account in production. The
# HTTP dev-reset endpoint (scripts/dev-reset-admin.sh) is local-dev only and is
# pinned OFF in docker-compose.prod.yml, so it can never be mounted on the VPS.
# Requiring host access here IS the security boundary.
#
# What it does:
#   1. Computes the password hash INSIDE the api container using the app's own
#      hash_password(), so the hash always matches the running code.
#   2. Applies an UPDATE to the users table via `docker exec` into postgres,
#      promoting the target to role=admin / is_active=true / email_verified=true
#      and clearing any pending reset / verification tokens.
#
# Usage:
#   ./scripts/reset-admin.sh                       # prompts for email, generates a password
#   ./scripts/reset-admin.sh <email>               # generates a random password, prints it once
#   ./scripts/reset-admin.sh <email> <password>    # uses the supplied password
#
# Container/DB names come from docker-compose.prod.yml (sigdoc-api, sigdoc-postgres)
# and are overridable via API_CONTAINER / PG_CONTAINER. POSTGRES_USER / POSTGRES_DB
# are read from the running postgres container's environment.
set -euo pipefail

API_CONTAINER="${API_CONTAINER:-sigdoc-api}"
PG_CONTAINER="${PG_CONTAINER:-sigdoc-postgres}"

email="${1:-}"
password="${2:-}"
password_generated=0

# ── Resolve target email ──────────────────────────────────────────────────────
if [[ -z "${email}" ]]; then
  read -r -p "Admin email to reset: " email
fi
if [[ -z "${email}" ]]; then
  echo "error: an email is required" >&2
  exit 1
fi

# ── Ensure containers are running ─────────────────────────────────────────────
for container in "${API_CONTAINER}" "${PG_CONTAINER}"; do
  if ! docker inspect -f '{{.State.Running}}' "${container}" >/dev/null 2>&1; then
    echo "error: container '${container}' is not running" >&2
    exit 1
  fi
done

# ── Resolve a password (generate a strong one inside the api container if none) ─
if [[ -z "${password}" ]]; then
  password="$(docker exec "${API_CONTAINER}" python -c 'import secrets; print(secrets.token_urlsafe(24))')"
  password_generated=1
fi

# ── Compute the hash with the app's own function, inside the api container ─────
# The plaintext is passed via an env var (never interpolated into the -c string)
# so passwords with quotes or shell metacharacters are handled safely.
hashed="$(docker exec -e RESET_ADMIN_PASSWORD="${password}" "${API_CONTAINER}" \
  python -c 'import os; from app.infrastructure.auth.jwt_handler import hash_password; print(hash_password(os.environ["RESET_ADMIN_PASSWORD"]))')"

if [[ -z "${hashed}" ]]; then
  echo "error: failed to compute password hash in '${API_CONTAINER}'" >&2
  exit 1
fi

# ── Read DB credentials from the postgres container's own environment ─────────
pg_user="$(docker exec "${PG_CONTAINER}" printenv POSTGRES_USER)"
pg_db="$(docker exec "${PG_CONTAINER}" printenv POSTGRES_DB)"

# ── Apply the UPDATE. psql :'var' quoting is injection-safe (values below are
#    passed as psql variables, never spliced into the SQL text by the shell). ──
updated_email="$(docker exec -i "${PG_CONTAINER}" \
  psql -qtA -v ON_ERROR_STOP=1 \
  -U "${pg_user}" -d "${pg_db}" \
  -v email="${email}" \
  -v hash="${hashed}" <<'SQL'
UPDATE users
SET hashed_password = :'hash',
    role = 'admin',
    is_active = true,
    email_verified = true,
    password_reset_token = NULL,
    password_reset_sent_at = NULL,
    email_verification_token = NULL,
    email_verification_sent_at = NULL
WHERE email = :'email'
RETURNING email;
SQL
)"

if [[ -z "${updated_email}" ]]; then
  echo "error: no user found with email '${email}' — nothing was changed" >&2
  exit 1
fi

echo "Admin reset OK for '${updated_email}' (role=admin, is_active=true, email_verified=true)."
if [[ "${password_generated}" -eq 1 ]]; then
  echo "Generated password (shown once): ${password}"
fi
