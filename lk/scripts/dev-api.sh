#!/bin/bash
# Локальный API ЛК для живой проверки входа.
# - БД: lk/data/world.sqlite (персистентная, не прод!)
# - BigBen: ключ берётся из корневого .env.local (BIGBEN_API_KEY_V1)
# - Подтверждение через бота обходится (LK_CONFIRM_BYPASS=1), т.к. мост
#   /world-bridge/phone-status ещё не задеплоен в прод-бот.
# Остановка: ./scripts/dev-api.sh stop
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$(cd ../ && pwd)"
PID_FILE=/tmp/lk_api.pid
LOG_FILE=/tmp/lk_api.log
DB_PATH="$PWD/data/world.sqlite"

case "${1:-start}" in
  stop)
    [ -f "$PID_FILE" ] && kill "$(cat "$PID_FILE")" 2>/dev/null && echo "остановлено"
    rm -f "$PID_FILE"
    exit 0
    ;;
esac

# shellcheck disable=SC1090
source "$ROOT/.env.local" 2>/dev/null || true
export BIGBEN_PUBLIC_API_KEY="${BIGBEN_PUBLIC_API_KEY:-${BIGBEN_API_KEY_V1:-}}"
export WORLD_DB_PATH="$DB_PATH"
export LK_CONFIRM_BYPASS=1
export LK_IMPORT_KEY="${LK_IMPORT_KEY:-}"
mkdir -p "$PWD/data"

if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  echo "уже запущен (pid $(cat "$PID_FILE"))"
  exit 0
fi

cd "$ROOT/world-backend"
nohup "$ROOT/bot/.venv313/bin/python" -m uvicorn main:app --host 127.0.0.1 --port 8010 \
  >"$LOG_FILE" 2>&1 &
echo $! > "$PID_FILE"
sleep 3
if curl -sS -m 5 http://127.0.0.1:8010/health | grep -q '"ok":true'; then
  echo "API ЛК запущен: http://127.0.0.1:8010 (health OK, pid $(cat "$PID_FILE"))"
else
  echo "не удалось запустить, лог: $LOG_FILE"; tail -5 "$LOG_FILE"; exit 1
fi
