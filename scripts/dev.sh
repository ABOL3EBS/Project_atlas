#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PID_DIR="$ROOT/.dev"
BACKEND_PID="$PID_DIR/backend.pid"
FRONTEND_PID="$PID_DIR/frontend.pid"

PORT_BACKEND=8000
PORT_FRONTEND=5173

log() { printf '\033[1;36m[atlas]\033[0m %s\n' "$*"; }
err() { printf '\033[1;31m[atlas]\033[0m %s\n' "$*" >&2; }

kill_pid() {
  local pid_file="$1" name="$2"
  if [ -f "$pid_file" ]; then
    local pid
    pid="$(cat "$pid_file")"
    if kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
      pkill -TERM -P "$pid" 2>/dev/null || true
      for _ in $(seq 1 10); do
        kill -0 "$pid" 2>/dev/null || break
        sleep 0.3
      done
      kill -KILL "$pid" 2>/dev/null || true
      log "$name stopped (pid $pid)"
    else
      log "$name already stopped (stale pid file)"
    fi
    rm -f "$pid_file"
  else
    log "$name not running (no pid file)"
  fi
}

port_in_use() { nc -z localhost "$1" 2>/dev/null; }

start() {
  if [ -f "$BACKEND_PID" ] || port_in_use "$PORT_BACKEND"; then
    err "backend already running on :$PORT_BACKEND — run 'scripts/dev.sh stop' first"
    return 1
  fi
  if [ -f "$FRONTEND_PID" ] || port_in_use "$PORT_FRONTEND"; then
    err "frontend already running on :$PORT_FRONTEND — run 'scripts/dev.sh stop' first"
    return 1
  fi

  mkdir -p "$PID_DIR"
  : > /tmp/atlas_backend.log
  : > /tmp/atlas_vite.log

  (cd "$ROOT/backend" && exec uv run uvicorn app.main:app --port "$PORT_BACKEND") > /tmp/atlas_backend.log 2>&1 &
  echo $! > "$BACKEND_PID"

  (cd "$ROOT/frontend" && exec ./node_modules/.bin/vite) > /tmp/atlas_vite.log 2>&1 &
  echo $! > "$FRONTEND_PID"

  log "starting backend (:8000) + frontend (:5173)…"
  local ok=1
  for _ in $(seq 1 60); do
    if [ "$(curl -s -m 1 -o /dev/null -w '%{http_code}' http://localhost:$PORT_BACKEND/api/health 2>/dev/null)" = "200" ] &&
       curl -s -m 1 -o /dev/null http://localhost:$PORT_FRONTEND/ 2>/dev/null; then
      ok=0
      break
    fi
    if ! kill -0 "$(cat "$BACKEND_PID")" 2>/dev/null || ! kill -0 "$(cat "$FRONTEND_PID")" 2>/dev/null; then
      break
    fi
    sleep 0.5
  done

  if [ "$ok" -ne 0 ]; then
    err "failed to start — check /tmp/atlas_backend.log and /tmp/atlas_vite.log"
    stop
    return 1
  fi

  log "backend is up: http://localhost:$PORT_BACKEND (providers: $(curl -s -m 1 http://localhost:$PORT_BACKEND/api/health 2>/dev/null | grep -o '"llm_available":[a-z]*\|"embedding_available":[a-z]*' | tr '\n' ' '))"
  log "frontend is up: http://localhost:$PORT_FRONTEND"
  log "logs: tail -f /tmp/atlas_backend.log /tmp/atlas_vite.log"
  log "stop everything with: scripts/dev.sh stop"
}

stop() {
  kill_pid "$FRONTEND_PID" frontend
  kill_pid "$BACKEND_PID" backend
  log "all stopped"
}

status() {
  [ -f "$BACKEND_PID" ] && kill -0 "$(cat "$BACKEND_PID")" 2>/dev/null && echo "backend: running (:8000)" || echo "backend: stopped"
  [ -f "$FRONTEND_PID" ] && kill -0 "$(cat "$FRONTEND_PID")" 2>/dev/null && echo "frontend: running (:5173)" || echo "frontend: stopped"
}

case "${1:-start}" in
  start) start ;;
  stop) stop ;;
  status) status ;;
  restart) stop; start ;;
  *) err "usage: scripts/dev.sh {start|stop|status|restart}"; exit 1 ;;
esac