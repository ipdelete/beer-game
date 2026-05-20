# Beer Game Simulation

A simple beer game simulation.

## Documentation

- [Site](docs/index.html) — open the runbook (Beer Game Benchmark cosmic
  bowling alley) directly, or browse it locally.

## Setup

```bash
uv sync
```

## Performing a Comparison

To compare the rule-based (mechanistic) approach with the Generative Agent-Based Modeling (GABM) approach:

1. **Run Mechanistic Simulation:**
   ```bash
   mkdir -p /tmp/beer-game-comparison
   uv run src/main.py --mode mechanistic --output /tmp/beer-game-comparison/results_mech.csv
   ```

2. **Run GABM Simulation** (ensure Ollama is running):
   ```bash
   LLM_ENDPOINT="http://localhost:11434/v1" LLM_MODEL="mistral:latest" \
     uv run src/main.py --mode gabm --output /tmp/beer-game-comparison/results_gabm.csv
   ```

3. **Visualize Comparison:**
   ```bash
   uv run scripts/plot_results.py \
     /tmp/beer-game-comparison/results_mech.csv \
     /tmp/beer-game-comparison/results_gabm.csv \
     --output /tmp/beer-game-comparison/bullwhip_comparison.png
   ```
   This will generate a comparison plot under `/tmp/beer-game-comparison/`.

## Reproducing the benchmark bundles

The Beer Game Benchmark runs the classic Sterman `step_4_8_36w` scenario
across a mechanistic baseline plus three local model contenders, producing
one `.eval` bundle per contender that feeds the dashboard.

**Hardware target**: Apple Silicon with Metal (developed on M3 Ultra,
512 GB unified memory). For Linux+CUDA, the ds4 build path is different;
see [antirez/ds4](https://github.com/antirez/ds4).

**Prerequisites**:

1. [Ollama.app](https://ollama.com) installed, plus model pulls:
   ```bash
   ollama pull gemma4:e4b-it-q4_K_M
   ollama pull gpt-oss:20b
   ```

2. [antirez/ds4](https://github.com/antirez/ds4) cloned to `~/src/ds4`
   (override with `DS4_DIR=...`), built from **current source** with the
   model file present as `ds4flash.gguf`:
   ```bash
   git clone https://github.com/antirez/ds4.git ~/src/ds4
   cd ~/src/ds4
   ./download_model.sh q2-imatrix   # 96/128 GB Macs
   make clean && make -j8           # do NOT use stale binaries
   ```
   Older ds4 binaries (pre-May-20 2026) have a chat-rendering bug that
   produces nonsense output. Always rebuild from a fresh `git pull` before
   benchmarking.

**One-shot run** (mechanistic → gemma4 → gpt-oss → ds4, single-tenant):

```bash
./scripts/single-tenant-bench.sh
```

Output bundles land in `/tmp/beer-game-runs/*.eval` (override with
`RUNS_DIR=...`). Each bundle is self-describing (config hash, scenario,
prompt version, sampling params, git SHA in the manifest).

**What the driver pins for fairness**:

- All three models share `temperature 0.4`, `top_p 0.95`,
  `max_tokens 16384`, and the same prompts, scenarios, and seed.
- gpt-oss and ds4 run with `reasoning_effort: "medium"` (gemma4 has no
  native reasoning mode).
- Ollama runs with `OLLAMA_FLASH_ATTENTION=1`, `OLLAMA_KV_CACHE_TYPE=q8_0`,
  `OLLAMA_KEEP_ALIVE=15m`, `OLLAMA_NUM_PARALLEL=1` — set by
  `scripts/start-ollama.sh`.
- ds4 runs with `--ctx 32768 --metal --kv-disk-dir /tmp/beer-game-ds4-kv` —
  set by `scripts/start-ds4.sh`.
- Single-tenant: only one model server holds GPU at a time. Ollama is
  stopped before ds4 starts.
- The driver leaves any pre-existing server it didn't start untouched.

All configurations live under `configs/models/*.yaml` and
`configs/runs/*.yaml` — those files are the source of truth, and the
driver passes them via `bench run --config`. To change a knob, edit the
YAML and re-run; the response cache invalidates on any config change that
affects model output.

## Adding ds4 (DeepSeek V4 Flash) as a Target

[antirez/ds4](https://github.com/antirez/ds4) is a native inference engine for
DeepSeek V4 Flash that exposes an OpenAI-compatible HTTP API, so the existing
GABM agent can drive it without code changes — only env vars.

1. **Build ds4 and download the model** (Mac with Metal or Linux+CUDA; ds4's
   CPU path is not usable):
   ```bash
   git clone https://github.com/antirez/ds4.git ~/src/ds4
   cd ~/src/ds4
   ./download_model.sh q2-imatrix   # 96/128 GB Macs
   make
   ```

2. **Start the server** (in a separate terminal, leave it running):
   ```bash
   ./ds4-server --ctx 32768 --port 8000 \
     --kv-disk-dir /tmp/ds4-kv --kv-disk-space-mb 8192
   ```

3. **Run a single GABM game against ds4:**
   ```bash
   export LLM_ENDPOINT="http://localhost:8000/v1"
   export LLM_MODEL="deepseek-v4-flash"
   uv run src/main.py --mode gabm --output /tmp/beer-game-comparison/results_ds4.csv
   ```

4. **Run the tournament against ds4** (uses `scripts/tournament-ds4.sh`,
   which sets ds4-friendly defaults and execs the same `tournament.sh`):
   ```bash
   ./scripts/tournament-ds4.sh
   ```

5. **Preflight check** before a long run:
   ```bash
   LLM_ENDPOINT=http://localhost:8000/v1 MODELS=deepseek-v4-flash \
     uv run scripts/preflight.py
   ```

### Notes on fairness

ds4-server keeps a single mutable KV checkpoint and reuses the longest
shared prefix across requests. The beer-game GABM workload sends a stable
system prompt plus a growing per-role transcript, which is exactly the
shape that benefits most from prefix reuse. When comparing wall-clock
totals against Ollama models (which reload state each request), keep in
mind that ds4 has a structural advantage on this workload — per-decode
latency and final game cost are the more interpretable signals.

ds4 defaults to thinking mode. The GABM agent already strips
`</think>` blocks and the OpenAI `reasoning` field when extracting the
integer order, so no parser change is needed.
