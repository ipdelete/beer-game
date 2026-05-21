#!/usr/bin/env bash
# Stop ds4-server started by start-ds4.sh.
# Uses /tmp/beer-game-ds4.pid; falls back to lsof on the port.
set -euo pipefail

DS4_PORT="${DS4_PORT:-8000}"
DS4_PID_FILE="/tmp/beer-game-ds4.pid"

if [[ -f "$DS4_PID_FILE" ]]; then
  PID=$(cat "$DS4_PID_FILE")
  if kill -0 "$PID" 2>/dev/null; then
    kill "$PID" 2>/dev/null || true
    sleep 2
  fi
  rm -f "$DS4_PID_FILE"
fi

# Fallback: anything still listening on the port
PORT_PID=$(lsof -ti ":${DS4_PORT}" 2>/dev/null | head -1 || true)
if [[ -n "$PORT_PID" ]]; then
  kill "$PORT_PID" 2>/dev/null || true
  sleep 2
fi

if lsof -ti ":${DS4_PORT}" >/dev/null 2>&1; then
  echo "WARNING: something still listening on :${DS4_PORT}" >&2
  exit 1
fi
echo "ds4-server stopped"
