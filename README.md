# Beer Game Simulation

A simple beer game simulation.

## Setup

```bash
uv sync
```

## Performing a Comparison

To compare the rule-based (mechanistic) approach with the Generative Agent-Based Modeling (GABM) approach:

1. **Run Mechanistic Simulation:**
   ```bash
   export PYTHONPATH=$PYTHONPATH:. && uv run src/main.py --mode mechanistic --output results_mech.csv
   ```

2. **Run GABM Simulation** (ensure Ollama is running):
   ```bash
   export LLM_ENDPOINT="http://localhost:11434/v1" && export LLM_MODEL="mistral:latest" && export PYTHONPATH=$PYTHONPATH:. && uv run src/main.py --mode gabm --output results_gabm.csv
   ```

3. **Visualize Comparison:**
   ```bash
   uv run scripts/plot_results.py results_mech.csv results_gabm.csv
   ```
   This will generate a `bullwhip_comparison.png` file showing the behavioral differences.

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
   export PYTHONPATH=$PYTHONPATH:.
   uv run src/main.py --mode gabm --output results_ds4.csv
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

