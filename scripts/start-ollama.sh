#!/usr/bin/env bash
# Start Ollama.app with the Beer Game benchmark's tuned environment.
#
# Tuned for Apple Silicon (M3 Ultra, 80-core GPU, 512 GB unified memory).
# Settings:
#   OLLAMA_FLASH_ATTENTION=1   Metal flash attention (large speedup, free)
#   OLLAMA_KV_CACHE_TYPE=q8_0  Half-size KV cache, negligible quality loss
#   OLLAMA_KEEP_ALIVE=15m      Avoid mid-run model unload between scenarios
#   OLLAMA_NUM_PARALLEL=1      Single-tenant; serial requests; no fragmentation
#
# Idempotent: if Ollama is already running with these settings, exits 0.
# Writes the parent Ollama.app PID to /tmp/beer-game-ollama.pid.
set -euo pipefail

OLLAMA_PID_FILE="/tmp/beer-game-ollama.pid"
OLLAMA_URL="http://localhost:11434"

want_env() {
  launchctl setenv OLLAMA_FLASH_ATTENTION 1
  launchctl setenv OLLAMA_KV_CACHE_TYPE q8_0
  launchctl setenv OLLAMA_KEEP_ALIVE 15m
  launchctl setenv OLLAMA_NUM_PARALLEL 1
}

env_matches() {
  [[ "$(launchctl getenv OLLAMA_FLASH_ATTENTION 2>/dev/null)" == "1" ]] && \
  [[ "$(launchctl getenv OLLAMA_KV_CACHE_TYPE 2>/dev/null)"  == "q8_0" ]] && \
  [[ "$(launchctl getenv OLLAMA_KEEP_ALIVE 2>/dev/null)"     == "15m" ]] && \
  [[ "$(launchctl getenv OLLAMA_NUM_PARALLEL 2>/dev/null)"   == "1" ]]
}

is_up() {
  curl -fsS --max-time 2 "${OLLAMA_URL}/api/version" >/dev/null 2>&1
}

current_app_pid() {
  pgrep -x Ollama | head -1
}

stop_ollama() {
  local app_pid serve_pid runner_pid
  runner_pid=$(ps -ef | grep "ollama runner" | grep -v grep | awk '{print $2}')
  for pid in $runner_pid; do kill "$pid" 2>/dev/null || true; done
  sleep 1
  serve_pid=$(ps -ef | grep "Ollama.app/Contents/Resources/ollama serve" | grep -v grep | awk '{print $2}')
  for pid in $serve_pid; do kill "$pid" 2>/dev/null || true; done
  sleep 1
  app_pid=$(current_app_pid)
  [[ -n "$app_pid" ]] && kill "$app_pid" 2>/dev/null || true
  sleep 3
}

if is_up && env_matches; then
  echo "ollama already running with tuned env"
  current_app_pid > "$OLLAMA_PID_FILE" 2>/dev/null || true
  exit 0
fi

if is_up; then
  echo "ollama running with stale env; restarting"
  stop_ollama
fi

want_env
echo "starting Ollama.app..."
open -a Ollama

for i in $(seq 1 30); do
  if is_up; then echo "ollama ready at ${i}s"; break; fi
  sleep 1
done

if ! is_up; then
  echo "ERROR: ollama failed to start" >&2
  exit 1
fi

current_app_pid > "$OLLAMA_PID_FILE"
echo "ollama pid $(cat "$OLLAMA_PID_FILE") (saved to $OLLAMA_PID_FILE)"
