#!/usr/bin/env bash
# Start the ds4-server (DeepSeek V4 Flash) with Beer Game benchmark settings.
#
# Tuned for Apple Silicon (M3 Ultra, Metal backend).
# Flags:
#   --ctx 32768             Context window. ds4 thinking mode default "high"
#                           effort requires room; 32k is sane for our 1-2k
#                           prompts plus reasoning headroom. (Think Max would
#                           require --ctx >= 393216 which is wasteful here.)
#   --kv-disk-dir DIR       Enables disk KV cache; speeds up repeated prompts.
#   --kv-disk-space-mb 8192 8 GiB budget for the disk KV cache.
#   --metal                 Force Metal backend (default on macOS, explicit).
#
# Environment overrides:
#   DS4_DIR    Directory containing ds4-server binary + ds4flash.gguf
#              (default: $HOME/src/ds4)
#   DS4_PORT   Bind port (default: 8000)
#   DS4_CTX    Context size (default: 32768)
#
# Idempotent: if ds4-server is already serving on $DS4_PORT, exits 0.
# Writes the server PID to /tmp/beer-game-ds4.pid.
set -euo pipefail

DS4_DIR="${DS4_DIR:-$HOME/src/ds4}"
DS4_PORT="${DS4_PORT:-8000}"
DS4_CTX="${DS4_CTX:-32768}"
DS4_PID_FILE="/tmp/beer-game-ds4.pid"
DS4_LOG="/tmp/beer-game-ds4.log"
DS4_KV_DIR="/tmp/beer-game-ds4-kv"

is_up() {
  curl -fsS --max-time 2 "http://localhost:${DS4_PORT}/v1/models" >/dev/null 2>&1
}

if is_up; then
  echo "ds4-server already up on :${DS4_PORT}"
  if [[ -f "$DS4_PID_FILE" ]]; then
    echo "pid: $(cat "$DS4_PID_FILE")"
  fi
  exit 0
fi

if [[ ! -x "${DS4_DIR}/ds4-server" ]]; then
  echo "ERROR: ${DS4_DIR}/ds4-server not found or not executable" >&2
  exit 1
fi
if [[ ! -e "${DS4_DIR}/ds4flash.gguf" ]]; then
  echo "ERROR: ${DS4_DIR}/ds4flash.gguf not found" >&2
  exit 1
fi

mkdir -p "$DS4_KV_DIR"
echo "starting ds4-server (port=${DS4_PORT}, ctx=${DS4_CTX})..."
(
  cd "$DS4_DIR"
  nohup ./ds4-server \
    --ctx "$DS4_CTX" \
    --port "$DS4_PORT" \
    --metal \
    --kv-disk-dir "$DS4_KV_DIR" \
    --kv-disk-space-mb 8192 \
    > "$DS4_LOG" 2>&1 &
  echo $! > "$DS4_PID_FILE"
)

PID=$(cat "$DS4_PID_FILE")
echo "ds4-server pid $PID (log: $DS4_LOG)"

for i in $(seq 1 60); do
  if is_up; then echo "ds4-server ready at ${i}s"; exit 0; fi
  if ! kill -0 "$PID" 2>/dev/null; then
    echo "ERROR: ds4-server died during startup" >&2
    tail -20 "$DS4_LOG" >&2
    rm -f "$DS4_PID_FILE"
    exit 1
  fi
  sleep 1
done

echo "ERROR: ds4-server didn't become ready within 60s" >&2
tail -20 "$DS4_LOG" >&2
exit 1
