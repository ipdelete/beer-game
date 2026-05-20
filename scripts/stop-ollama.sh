#!/usr/bin/env bash
# Stop Ollama.app and all child processes (serve + runners).
# Idempotent.
set -euo pipefail

OLLAMA_PID_FILE="/tmp/beer-game-ollama.pid"

runner_pids=$(ps -ef | grep "ollama runner" | grep -v grep | awk '{print $2}' || true)
for pid in $runner_pids; do kill "$pid" 2>/dev/null || true; done
sleep 1

serve_pids=$(ps -ef | grep "Ollama.app/Contents/Resources/ollama serve" | grep -v grep | awk '{print $2}' || true)
for pid in $serve_pids; do kill "$pid" 2>/dev/null || true; done
sleep 1

app_pid=$(pgrep -x Ollama | head -1 || true)
[[ -n "$app_pid" ]] && kill "$app_pid" 2>/dev/null || true

rm -f "$OLLAMA_PID_FILE"
sleep 2

if pgrep -x Ollama >/dev/null 2>&1; then
  echo "WARNING: Ollama still running after stop attempt" >&2
  exit 1
fi
echo "ollama stopped"
