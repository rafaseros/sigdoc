#!/usr/bin/env bash
#
# Download the newest SigDoc backup bundle from the droplet to THIS machine.
#
# Usage:
#   SIGDOC_SSH=user@droplet infra/backup/fetch-backup.sh [--run]
#
#   --run   Generate a fresh bundle on the droplet first (runs backup-bundle.sh
#           over SSH), then download it. Without --run, downloads the newest
#           bundle that already exists on the droplet.
#
# Environment:
#   SIGDOC_SSH         ssh target, e.g. deploy@203.0.113.10   (required)
#   SIGDOC_BACKUP_DIR  local directory to save into (default: ./sigdoc-backups)
#   SIGDOC_APP_DIR     app dir on the droplet (default: /opt/docker/apps/sigdoc)
#
# The ssh user must be able to run docker (backup-bundle.sh needs it) when you
# pass --run; a plain download needs only read access to the bundles dir.
#
set -euo pipefail

RUN_FRESH=0
for arg in "$@"; do
  case "$arg" in
    --run) RUN_FRESH=1 ;;
    -h | --help)
      grep -E '^#( |$)' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *)
      echo "Unknown argument: $arg (try --help)" >&2
      exit 2
      ;;
  esac
done

SSH_TARGET="${SIGDOC_SSH:-}"
if [ -z "$SSH_TARGET" ]; then
  echo "Set SIGDOC_SSH to your droplet ssh target, e.g.:" >&2
  echo "  SIGDOC_SSH=deploy@your-droplet infra/backup/fetch-backup.sh" >&2
  exit 2
fi

APP_DIR="${SIGDOC_APP_DIR:-/opt/docker/apps/sigdoc}"
REMOTE_BUNDLE_DIR="/opt/docker/backups/sigdoc/bundles"
LOCAL_DIR="${SIGDOC_BACKUP_DIR:-./sigdoc-backups}"

if [ "$RUN_FRESH" -eq 1 ]; then
  echo "==> Generating a fresh bundle on the droplet..."
  ssh "$SSH_TARGET" "bash ${APP_DIR}/infra/backup/backup-bundle.sh"
fi

echo "==> Locating the newest bundle on the droplet..."
REMOTE_BUNDLE=$(ssh "$SSH_TARGET" "ls -1t ${REMOTE_BUNDLE_DIR}/sigdoc-backup_*.tar.gz 2>/dev/null | head -1")
if [ -z "$REMOTE_BUNDLE" ]; then
  echo "No bundle found in ${REMOTE_BUNDLE_DIR} on the droplet." >&2
  echo "Create one first: re-run with --run (or run backup-bundle.sh on the droplet)." >&2
  exit 1
fi

mkdir -p "$LOCAL_DIR"
BUNDLE_NAME="${REMOTE_BUNDLE##*/}"
echo "==> Downloading ${BUNDLE_NAME} ..."
if command -v rsync >/dev/null 2>&1; then
  rsync -avP "${SSH_TARGET}:${REMOTE_BUNDLE}" "${LOCAL_DIR}/"
else
  scp "${SSH_TARGET}:${REMOTE_BUNDLE}" "${LOCAL_DIR}/"
fi

LOCAL_FILE="${LOCAL_DIR}/${BUNDLE_NAME}"
LOCAL_SIZE=$(du -h "$LOCAL_FILE" | cut -f1)

cat <<EOF

Saved: ${LOCAL_FILE} (${LOCAL_SIZE})
Peek inside:   tar -tzf '${LOCAL_FILE}' | head
Read manifest: tar -xzO -f '${LOCAL_FILE}' MANIFEST.txt
EOF
