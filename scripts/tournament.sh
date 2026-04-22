#!/usr/bin/env bash
# Runs the GABM beer-game simulation sequentially across a roster of local
# Ollama models and tabulates per-model total costs + wall-clock latency.
#
# Sequential is intentional: Ollama loads at most one model into memory at a
# time (OLLAMA_MAX_LOADED_MODELS=1 by default). Running in parallel would
# cause constant model swaps, hurting both speed and fairness of timing.
set -euo pipefail

cd "$(dirname "$0")/.."

export PYTHONPATH=.
export LLM_ENDPOINT="${LLM_ENDPOINT:-http://localhost:11434/v1}"
TURNS="${TURNS:-36}"

MODELS=(
  "mistral:latest"
  "qwen3.5:9b"
  "phi4:14b"
  "gemma4:e4b-it-q4_K_M"
  "gpt-oss:20b"
)

RESULTS_DIR="tournament_results"
mkdir -p "$RESULTS_DIR"
SUMMARY="$RESULTS_DIR/summary.tsv"
printf "model\twall_seconds\ttotal_cost\tretailer\twholesaler\tdistributor\tfactory\n" > "$SUMMARY"

for MODEL in "${MODELS[@]}"; do
  SLUG="$(echo "$MODEL" | tr '/:.' '___')"
  CSV="$RESULTS_DIR/results_gabm_${SLUG}.csv"
  LOG="$RESULTS_DIR/run_${SLUG}.log"

  echo ""
  echo "============================================================"
  echo ">>> Running $MODEL  (turns=$TURNS)"
  echo "============================================================"

  # Warm up: stop whatever is loaded, then ensure the target is resident so
  # first-call latency doesn't dominate the timing. Guard with || true so
  # pipefail + set -e don't abort when nothing is loaded.
  { ollama ps 2>/dev/null | awk 'NR>1 && $1!="" {print $1}' | while read -r m; do
      [[ -n "$m" ]] && ollama stop "$m" 2>/dev/null || true
    done; } || true

  export LLM_MODEL="$MODEL"

  START=$(date +%s)
  if uv run src/main.py --mode gabm --turns "$TURNS" --output "$CSV" 2>&1 | tee "$LOG"; then
    STATUS="ok"
  else
    STATUS="fail"
  fi
  END=$(date +%s)
  ELAPSED=$((END - START))

  if [[ "$STATUS" == "ok" ]]; then
    # Parse the "Final Costs" block from the log.
    R=$(grep -E "^\s*Retailer:"    "$LOG" | awk -F'\\$' '{print $2}' | tr -d ' ')
    W=$(grep -E "^\s*Wholesaler:"  "$LOG" | awk -F'\\$' '{print $2}' | tr -d ' ')
    D=$(grep -E "^\s*Distributor:" "$LOG" | awk -F'\\$' '{print $2}' | tr -d ' ')
    F=$(grep -E "^\s*Factory:"     "$LOG" | awk -F'\\$' '{print $2}' | tr -d ' ')
    TOTAL=$(python3 -c "print(round(sum(float(x) for x in ['${R:-0}','${W:-0}','${D:-0}','${F:-0}']), 2))")
    printf "%s\t%d\t%s\t%s\t%s\t%s\t%s\n" \
      "$MODEL" "$ELAPSED" "$TOTAL" "${R:-NA}" "${W:-NA}" "${D:-NA}" "${F:-NA}" >> "$SUMMARY"
  else
    printf "%s\t%d\tFAILED\tNA\tNA\tNA\tNA\n" "$MODEL" "$ELAPSED" >> "$SUMMARY"
  fi
done

echo ""
echo "============================================================"
echo "Tournament complete. Summary:"
echo "============================================================"
column -t -s $'\t' "$SUMMARY"
echo ""
echo "Per-model CSVs + logs in: $RESULTS_DIR/"
