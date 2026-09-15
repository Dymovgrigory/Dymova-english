#!/usr/bin/env bash
# Foxinburg World — всегда одни и те же порты, без прыжков Next и без второго uvicorn.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
API_HOST="0.0.0.0"
API_PORT="8010"
WEB_HOST="127.0.0.1"
WEB_PORT="3002"
UVICORN="$ROOT/world-backend/.venv/bin/python"
NPM="$(command -v npm)"
daemon() {
  local cwd="$1" log="$2"
  shift 2
  /usr/bin/python3 - "$cwd" "$log" "$@" <<'PY'
import os, sys
cwd, log, *argv = sys.argv[1:]
if os.fork() > 0:
    raise SystemExit(0)
os.setsid()
if os.fork() > 0:
    os._exit(0)
os.chdir(cwd)
os.umask(0)
sys.stdout.flush()
sys.stderr.flush()
logf = os.open(log, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
os.dup2(logf, 1)
os.dup2(logf, 2)
devnull = os.open("/dev/null", os.O_RDONLY)
os.dup2(devnull, 0)
os.execvp(argv[0], argv)
PY
}

free_port() {
  local port="$1"
  local pids
  pids="$(lsof -nP -iTCP:"$port" -sTCP:LISTEN -t 2>/dev/null || true)"
  if [[ -z "$pids" ]]; then
    return 0
  fi
  kill $pids 2>/dev/null || true
  sleep 0.5
  pids="$(lsof -nP -iTCP:"$port" -sTCP:LISTEN -t 2>/dev/null || true)"
  if [[ -n "$pids" ]]; then
    kill -9 $pids 2>/dev/null || true
  fi
}

wait_http() {
  local url="$1"
  local n=0
  while (( n < 80 )); do
    if curl -sf "$url" >/dev/null; then
      return 0
    fi
    sleep 0.25
    n=$((n + 1))
  done
  return 1
}

cmd="${1:-start}"

case "$cmd" in
  stop)
    free_port "$API_PORT"
    free_port "$WEB_PORT"
    echo "Foxinburg World stopped ($API_HOST:$API_PORT + $WEB_HOST:$WEB_PORT)."
    ;;
  start|restart)
    if [[ ! -x "$UVICORN" ]]; then
      echo "Нет $UVICORN — создай venv в world-backend." >&2
      exit 1
    fi
    free_port "$API_PORT"
    free_port "$WEB_PORT"
    mkdir -p "$ROOT/world-backend/data"
    daemon "$ROOT/world-backend" "$ROOT/world-backend/data/uvicorn.log" \
      "$UVICORN" -m uvicorn main:app --host "$API_HOST" --port "$API_PORT"
    daemon "$ROOT/world" "$ROOT/world-backend/data/next-dev.log" \
      "$NPM" run dev
    if ! wait_http "http://127.0.0.1:$API_PORT/health"; then
      echo "API не поднялся на http://127.0.0.1:$API_PORT — см. world-backend/data/uvicorn.log" >&2
      exit 1
    fi
    if ! wait_http "http://127.0.0.1:$WEB_PORT"; then
      echo "Фронт не поднялся на http://127.0.0.1:$WEB_PORT — см. world-backend/data/next-dev.log" >&2
      exit 1
    fi
    echo "Foxinburg World:"
    echo "  UI    http://127.0.0.1:$WEB_PORT"
    echo "  API   http://127.0.0.1:$API_PORT"
    echo "  Learn http://127.0.0.1:$WEB_PORT/learn"
    ;;
  *)
    echo "Usage: $0 start|stop|restart" >&2
    exit 2
    ;;
esac
