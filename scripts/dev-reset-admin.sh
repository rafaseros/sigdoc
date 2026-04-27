#!/usr/bin/env bash
# Dev-only: reset the canonical admin (devrafaseros@gmail.com) to admin123!
# Requires ENABLE_DEV_RESET=true in .env and a restart of the api container.
set -euo pipefail
curl -fsSL -X POST http://localhost:8000/api/v1/dev/reset-admin
echo
