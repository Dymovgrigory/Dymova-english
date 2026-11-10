#!/usr/bin/env bash
set -euo pipefail

HOST="${LMS_DEPLOY_HOST:-37.252.23.189}"
KEY="${LMS_DEPLOY_KEY:-$HOME/.ssh/id_ed25519}"
PACKAGE="${1:-/tmp/lms-runtime-slim.tar.gz}"
REMOTE="/tmp/lms-runtime-slim.tar.gz"

test -f "$PACKAGE"
scp -i "$KEY" -o StrictHostKeyChecking=no "$PACKAGE" "root@${HOST}:${REMOTE}"
ssh -i "$KEY" -o StrictHostKeyChecking=no "root@${HOST}" bash -s <<'REMOTE_SCRIPT'
set -euo pipefail
stage="$(mktemp -d /tmp/lms-runtime-stage.XXXXXX)"
tar -xzf /tmp/lms-runtime-slim.tar.gz -C "$stage"
test -f "$stage/server.js"
docker cp "$stage/.next" lk-web:/app/.next
docker cp "$stage/public/collection" lk-web:/app/public/collection
docker restart lk-web >/dev/null
sleep 5
curl -fsS http://127.0.0.1:7100/collection >/dev/null
docker ps --format '{{.Names}} {{.Status}}' | grep '^lk-web '
REMOTE_SCRIPT
