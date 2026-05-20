#!/usr/bin/env bash
# Single-tenant Beer Game benchmark driver.
#
# Runs one model server at a time so a single GPU never has to swap.
# Order: mechanistic baseline → ollama (gemma4, gpt-oss) → ds4 (DeepSeek V4).
#
# Server lifecycle is delegated to:
#   scripts/start-ollama.sh / scripts/stop-ollama.sh
#   scripts/start-ds4.sh    / scripts/stop-ds4.sh
# Those scripts encode the tuned env (Flash Attention, KV q8_0, keep-alive, etc.)
# and are sandbox-safe (PID-tracked kill, no pkill).
#
# Each model produces its own `.eval` bundle under $RUNS_DIR. The dashboard
# (later PR) aggregates across bundles.
#
# Ownership-aware: if Ollama (or ds4) was already running when this script
# started, we leave it running at the end — we only stop what we started.
#
# Configurable via env:
#   RUNS_DIR        bundle output dir          (default: /tmp/beer-game-runs)
#   TAG             suffix for run-ids         (default: v1)
#   SKIP            space-separated stage list to skip
#                   stages: mechanistic gemma4 gpt-oss ds4
#   DS4_DIR         ds4 server checkout        (default: $HOME/src/ds4)
#   DS4_CTX         ds4 context window         (default: 32768)
#   DS4_PORT        ds4 listen port            (default: 8000)
#
# Turns and epochs are fixed by the YAML configs under configs/runs/ (the
# config file wins over any CLI --turns/--epochs when --config is given).
#
# Examples:
#   ./scripts/single-tenant-bench.sh
#   SKIP="ds4" ./scripts/single-tenant-bench.sh
#   TAG=v2 SKIP="mechanistic gemma4 gpt-oss" ./scripts/single-tenant-bench.sh
set -euo pipefail

cd "$(dirname "$0")/.."

RUNS_DIR="${RUNS_DIR:-/tmp/beer-game-runs}"
TAG="${TAG:-v1}"
SKIP="${SKIP:-}"
DS4_DIR="${DS4_DIR:-$HOME/src/ds4}"
DS4_CTX="${DS4_CTX:-32768}"
DS4_PORT="${DS4_PORT:-8000}"

mkdir -p "$RUNS_DIR"

# Track what *we* started so we only stop what we started.
WE_STARTED_OLLAMA=0
WE_STARTED_DS4=0

skipped() { [[ " $SKIP " == *" $1 "* ]]; }

banner() {
  echo
  echo "============================================================"
  echo "  $1"
  echo "============================================================"
}

ollama_running() { curl -fsS --max-time 2 http://localhost:11434/api/tags >/dev/null 2>&1; }
ds4_running()    { curl -fsS --max-time 2 "http://localhost:${DS4_PORT}/v1/models" >/dev/null 2>&1; }

cleanup() {
  local ec=$?
  if [[ $WE_STARTED_DS4 -eq 1 ]] && ds4_running; then
    echo
    echo "[cleanup] stopping ds4 (we started it)"
    "$(dirname "$0")/stop-ds4.sh" || true
  fi
  if [[ $WE_STARTED_OLLAMA -eq 1 ]] && ollama_running; then
    echo "[cleanup] stopping ollama (we started it)"
    "$(dirname "$0")/stop-ollama.sh" || true
  fi
  exit $ec
}
trap cleanup EXIT INT TERM

start_ollama() {
  if ollama_running; then
    echo "ollama already up (left running by user — will leave it up after)."
    "$(dirname "$0")/start-ollama.sh"  # ensures tuned env even if user pre-started
    return
  fi
  banner "Starting Ollama via scripts/start-ollama.sh"
  "$(dirname "$0")/start-ollama.sh"
  WE_STARTED_OLLAMA=1
}

stop_ollama_if_ours() {
  if [[ $WE_STARTED_OLLAMA -ne 1 ]]; then
    echo "ollama left running (we did not start it)."
    return
  fi
  banner "Stopping Ollama (we started it)"
  # Unload anything we loaded
  ollama ps 2>/dev/null | awk 'NR>1 {print $1}' | while read -r m; do
    [[ -n "$m" ]] && ollama stop "$m" 2>/dev/null || true
  done
  "$(dirname "$0")/stop-ollama.sh" || echo "WARN: stop-ollama.sh failed"
}

unload_ollama_model() {
  local m="$1"
  ollama stop "$m" 2>/dev/null || true
}

start_ds4() {
  if ds4_running; then
    echo "ds4 already up (left running by user — will leave it up after)."
    return 0
  fi
  banner "Starting ds4-server via scripts/start-ds4.sh"
  if DS4_DIR="$DS4_DIR" DS4_PORT="$DS4_PORT" DS4_CTX="$DS4_CTX" \
       "$(dirname "$0")/start-ds4.sh"; then
    WE_STARTED_DS4=1
    return 0
  fi
  echo "WARN: start-ds4.sh failed"
  return 1
}

stop_ds4_if_ours() {
  if [[ $WE_STARTED_DS4 -ne 1 ]]; then
    echo "ds4 left running (we did not start it)."
    return
  fi
  banner "Stopping ds4-server (we started it)"
  DS4_PORT="$DS4_PORT" "$(dirname "$0")/stop-ds4.sh" || echo "WARN: stop-ds4.sh failed"
}

# Warmup ping using the OpenAI-compatible chat endpoint. Tiny prompt, ignore
# output. Loads the weights into memory before we start timing.
warmup_openai() {
  local base_url="$1" model="$2"
  echo "[warmup] $model @ $base_url"
  curl -fsS --max-time 120 \
    -H "Content-Type: application/json" \
    "${base_url}/chat/completions" \
    -d "{\"model\":\"${model}\",\"messages\":[{\"role\":\"user\",\"content\":\"ok\"}],\"max_tokens\":4}" \
    >/dev/null 2>&1 || echo "[warmup] warning: ping failed (will still try the run)"
}

run_bench() {
  local config="$1" run_id="$2"
  banner "bench run --config $config  →  $run_id.eval"
  uv run bench run \
    --config "$config" \
    --runs-dir "$RUNS_DIR" \
    --run-id "$run_id" \
    --force
  postcheck_bundle "$RUNS_DIR/$run_id.eval"
  echo
  echo "--- bench report $run_id.eval ---"
  uv run bench report "$RUNS_DIR/$run_id.eval" || true
}

# Verify every game in the bundle finished cleanly.
postcheck_bundle() {
  local bundle="$1"
  local games_file="$bundle/games.jsonl"
  if [[ ! -f "$games_file" ]]; then
    echo "POSTCHECK FAIL: $games_file missing"
    exit 1
  fi
  local total ok
  total=$(wc -l <"$games_file" | tr -d ' ')
  ok=$(grep -c '"status": *"ok"' "$games_file" || true)
  echo "[postcheck] $bundle: $ok / $total games ok"
  if [[ "$ok" != "$total" ]] || [[ "$total" -eq 0 ]]; then
    echo "POSTCHECK FAIL: not all games ok in $bundle"
    grep -v '"status": *"ok"' "$games_file" | head -5
    exit 1
  fi
}

# ----------------------------------------------------------------------------
# Stage 1: mechanistic baseline (no server, no VRAM)
# ----------------------------------------------------------------------------
if skipped mechanistic; then
  echo "[skip] mechanistic"
else
  run_bench configs/runs/mechanistic-baseline.yaml "mechanistic-${TAG}"
fi

# ----------------------------------------------------------------------------
# Stage 2-3: ollama models (gemma4, gpt-oss)
# ----------------------------------------------------------------------------
if skipped gemma4 && skipped gpt-oss; then
  echo "[skip] all ollama stages"
else
  start_ollama

  if skipped gemma4; then
    echo "[skip] gemma4"
  else
    warmup_openai "http://localhost:11434/v1" "gemma4:e4b-it-q4_K_M"
    run_bench configs/runs/gemma4-e4b.yaml "gemma4-e4b-${TAG}"
    unload_ollama_model "gemma4:e4b-it-q4_K_M"
  fi

  if skipped gpt-oss; then
    echo "[skip] gpt-oss"
  else
    warmup_openai "http://localhost:11434/v1" "gpt-oss:20b"
    run_bench configs/runs/gpt-oss-20b.yaml "gpt-oss-20b-${TAG}"
    unload_ollama_model "gpt-oss:20b"
  fi

  stop_ollama_if_ours
fi

# ----------------------------------------------------------------------------
# Stage 4: ds4
# ----------------------------------------------------------------------------
if skipped ds4; then
  echo "[skip] ds4"
else
  if start_ds4; then
    warmup_openai "http://localhost:${DS4_PORT}/v1" "deepseek-v4-flash"
    run_bench configs/runs/ds4.yaml "ds4-${TAG}"
    stop_ds4_if_ours
  else
    echo "[warn] ds4 stage skipped (server unavailable)"
  fi
fi

banner "Done"
echo "Bundles in: $RUNS_DIR"
ls -d "$RUNS_DIR"/*.eval 2>/dev/null || echo "(no .eval bundles found)"
