#!/usr/bin/env bash
# Tournament wrapper for an antirez/ds4 (DeepSeek V4 Flash) backend.
#
# Prereq: start ds4-server in another terminal, e.g.
#   cd ~/src/ds4
#   ./ds4-server --ctx 32768 --port 8000 \
#     --kv-disk-dir /tmp/ds4-kv --kv-disk-space-mb 8192
#
# This wrapper just sets ds4-friendly defaults and execs tournament.sh.
# Override any of PROVIDER / LLM_ENDPOINT / MODELS / TURNS / RESULTS_DIR
# from the environment if you need to.
set -euo pipefail

export PROVIDER="${PROVIDER:-ds4}"
export LLM_ENDPOINT="${LLM_ENDPOINT:-http://localhost:8000/v1}"
export MODELS="${MODELS:-deepseek-v4-flash}"
export RESULTS_DIR="${RESULTS_DIR:-/tmp/beer-game-tournament-ds4}"

exec "$(dirname "$0")/tournament.sh" "$@"
