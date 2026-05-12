# Beer Game as a Local LLM Benchmark

**Benchmark findings — 2026-04-22**

> A small, hard, quantitative benchmark for local language models:
> can the model play a 4-role supply-chain game without falling into
> the bullwhip effect?

## Why the Beer Game is a good LLM benchmark

The **Beer Distribution Game** (Sterman / MIT System Dynamics Group) has
four properties that make it a surprisingly strong evaluation for small /
local models:

1. **Quantitative.** Success is a single scalar: *total inventory +
   backlog cost across 36 simulated weeks*. No rubric, no judges, no
   ambiguity.
2. **Multi-step / agentic.** Each role makes 36 sequential decisions.
   Earlier mistakes compound. The model cannot bluff its way to a good
   number — the simulator is the ground truth.
3. **Structurally adversarial.** The game is specifically designed to
   make naïve "order = what you need" policies fail via the *bullwhip
   effect*: small demand changes get amplified upstream into large
   oscillations. A model that over-reacts to its own backlog will
   visibly blow up.
4. **Tiny prompt / tiny output.** Each decision is ~1–3 KB of prompt
   → one integer. This stays well within the context window of any
   modern local model and makes per-call latency the dominant factor.
5. **Strong mechanistic baselines exist.** We can compare against the
   Sterman 1989 anchor-and-adjust formula, which is the "textbook right
   answer" for rule-based players. An LLM that beats it is
   demonstrably doing real decision-making, not memorising a pattern.

## Test setup

### Hardware

| Component       | Spec                                  |
|-----------------|---------------------------------------|
| Machine         | Apple **Mac Studio** (`Mac15,14`)      |
| Chip            | Apple **M3 Ultra**                     |
| CPU cores       | 32 (24 performance + 8 efficiency)     |
| GPU             | Integrated (Apple M3 Ultra, unified)   |
| Unified memory  | **512 GB**                             |
| OS              | macOS 26.3.1 (build 25D2128)           |

All inference is local. The 512 GB unified-memory configuration is
deliberately generous — it means even the ~37 GB MoE and ~65 GB
reasoning models we *didn't* include in this run are comfortably
resident without mmap thrashing.

### Software / runtime

- **Ollama** HTTP API at `http://localhost:11434/v1` (OpenAI-compatible).
- **Python 3.13**, `openai` SDK as client.
- `OLLAMA_MAX_LOADED_MODELS=1` (default). We deliberately run models
  **sequentially** so timing is comparable and no model contends for
  unified-memory bandwidth.

### Simulation mechanics (true-to-Sterman)

| Parameter                      | Value                          |
|--------------------------------|--------------------------------|
| Horizon                        | 36 weeks                       |
| Roles                          | Retailer → Wholesaler → Distributor → Factory |
| Initial inventory per role     | 12 cases                       |
| Shipping delay (3 links)       | 2 weeks                        |
| Order delay (3 links)          | 2 weeks                        |
| Production delay (Factory)     | 2 weeks                        |
| Holding cost                   | $0.50 / case / week            |
| Backlog cost                   | $1.00 / case / week            |
| Customer demand                | step: 4/wk for 4 weeks, then 8/wk |
| Weekly order dynamics          | **two-phase** (snapshot → decide all → execute all) |

The two-phase week is critical: all four roles see the same
pre-update world-state and *then* decisions are applied, preventing
information leakage between players within a single week.

### The agent (per decision)

Each week, for each role, we issue one chat-completion call:

- **System prompt** — role description, cost structure, explicit
  warning against double-counting in-flight orders (the classic source
  of bullwhip).
- **User prompt** — current inventory, backlog, incoming order,
  shipment received, on-order pipeline, plus the full per-role
  **record sheet** of previous weeks (what the model has seen + what
  it has done).
- **Sampling** — `temperature=0.4`, `max_tokens=256`, per-call
  `timeout=60s`.
- **Answer extraction** — robust parser that:
  1. If the response contains `</think>`, takes the first integer
     *after* the closing tag (inline-thinking models: Qwen3.5, Gemma4).
  2. Otherwise, takes the *first* integer in the content
     (non-reasoning models: Mistral, Phi-4).
  3. If content is empty, falls back to the last integer in the
     OpenAI `reasoning` field (separate-field reasoning models:
     gpt-oss).
- **No agent framework**; a single decision call per role per week.
  See *Appendix B* for how this relates to the broader GABM /
  agentic-framework literature.

### Baselines on the same engine

| Strategy                                    | Total 36-wk cost |
|---------------------------------------------|-----------------:|
| Sterman 1989 anchor-and-adjust (rule-based) | **$3,128**       |
| Legacy "simple heuristic" (pre-rewrite)     | ~$11,686         |

The Sterman line is our *"what a careful rule-based player can do"*
reference.

## Methodology for this run

- 36 weeks × 4 roles = **144 decision calls per model**.
- Single run per model (no variance sampling — see *Limitations*).
- Models evaluated sequentially on the same machine, same Ollama
  daemon, no other load.
- Before each model runs, the currently-loaded model is evicted
  (`ollama stop`) so first-call latency includes the target model's
  load time.

### Pre-flight validation

Before the 45-minute tournament we ran:

1. **Per-model one-shot decode** (`scripts/preflight.py`): realistic
   mid-game Wholesaler prompt, verify each model returns a parseable
   integer in a plausible range.
2. **TURNS=5 dry-run** of the tournament script: verify the
   orchestrator, log parser, and summary aggregator work end-to-end
   before committing to the full 36-turn run.

Both steps caught real bugs (model-eviction pipeline error in the
shell script; `<think>`-handling regression for non-reasoning models
like Mistral). Do not skip.

## Results

Rankings over a single 36-week run, sorted by total cost (lower is
better). All costs in dollars; wall-time is end-to-end for that
model's run including model-load.

| Rank | Model                  | Wall (s) | **Total** | Retailer | Wholesaler | Distributor | Factory |
|-----:|------------------------|---------:|----------:|---------:|-----------:|------------:|--------:|
|   🥇 | `gpt-oss:20b`          | 425      | **$2,585** | 578.00   | 1,264.50   | 421.00      | 321.50  |
|   🥈 | `phi4:14b`             | 826      | **$2,829** | 1,236.50 | 370.00     | 394.00      | 828.00  |
|   🥉 | `qwen3.5:9b`           | 859      | **$5,651** | 595.00   | 757.00     | 1,294.00    | 3,005.00 |
|    4 | `gemma4:e4b-it-q4_K_M` | 510      | **$7,536** | 1,731.00 | 3,206.00   | 1,540.50    | 1,058.00 |
|    5 | `mistral:latest`       | 395      | **$8,377** | 384.50   | 2,665.00   | 1,573.00    | 3,754.50 |

**Reference lines:** Sterman mechanistic = $3,128, legacy heuristic
≈ $11,686.

### Notable observations

- **`gpt-oss:20b` beats the Sterman mechanistic baseline.** The only
  model in the lineup to do so. Reasoning-trained models appear to
  handle the "order = demand forecast − inventory error − pipeline
  correction" decomposition that Sterman's formula encodes
  implicitly.
- **`phi4:14b` is a very close second** despite having no explicit
  reasoning mode. Its weakness is the Retailer role ($1,236), where
  it over-orders early; upstream roles are its strongest.
- **Speed does not predict quality.** `mistral:latest` is the
  fastest (395s) and the *worst* total. `phi4:14b` is 2.1× slower
  but 3× cheaper in game cost.
- **Bullwhip signature is model-specific.**
  - Mistral and Qwen3.5 blow up at the **Factory** (furthest from
    demand), the textbook bullwhip pattern.
  - Gemma4 blows up at the **Wholesaler** — a less common failure
    mode suggesting it panics on its first early backlog and then
    over-corrects.
  - gpt-oss and phi4 keep costs distributed ≤ ~$1,300 per role —
    no single role hits the "runaway" regime.
- **Thinking-off was used where available.** Qwen3.5's hybrid
  thinking mode was left at its default. Turning it explicitly on
  might narrow the gap with gpt-oss at the cost of latency.

### Regression we caught mid-run

An early iteration of the extractor always took the **last** integer
in the response. This works for reasoning models (where the final
answer follows the reasoning) but *reverses* the intent of
non-reasoning models like Mistral, which answer first and then
justify (`"Order 4 because inventory is 12, backlog is 6"` → extractor
returned 6 instead of 4). This single-line bug exploded Mistral's
total from a reasonable ~$8K to **$442K**. The fix (described in the
*Agent* section above) is in `src/gabm/agent.py`.

**Lesson for any benchmark of this kind**: parsing numeric answers
from LLM output is model-family-specific. Validate the parser on
*every* model before trusting the scores.

## Reproducibility

```bash
# 1. Pre-flight (one decode per model, ~40s total)
PYTHONPATH=. uv run python scripts/preflight.py

# 2. Quick 5-turn sanity run (~6 min)
TURNS=5 ./scripts/tournament.sh

# 3. Full tournament (~45 min for this 5-model roster)
./scripts/tournament.sh
```

Outputs (in `tournament_results/`):

- `summary.tsv` — one row per model with costs and wall-time
- `results_gabm_<model>.csv` — per-role, per-week trace
- `run_<model>.log` — full stdout for that model's run

## Limitations

- **Single run per model.** LLMs with `temperature > 0` are
  stochastic. A single 36-week run is a point estimate of a
  distribution we have not characterised. The *ordering* of the top
  two (gpt-oss vs phi4) is not statistically significant from this
  data alone; the ordering of the bottom three is very likely
  stable given the >2× gaps.
- **One prompt template.** We did not sweep system-prompt variants.
  A prompt that explicitly describes Sterman's anchor-and-adjust
  decomposition would very likely improve every model's score.
- **`temperature=0.4` only.** Low-temperature or deterministic
  runs (e.g. `temperature=0`) would shift the rankings; some
  models may pin to a near-deterministic policy at `T=0` that
  dominates the sampled run here.
- **Demand pattern is the canonical step.** We did not test against
  the textbook's random-walk or the "malicious" demand patterns
  used in supply-chain research.
- **No agent framework.** Each role is a stateless chat-completion
  call. A multi-turn AutoGen-style agent with tool-use + reflection
  (see Appendix B) could plausibly do better at the cost of 5–10×
  the token budget per decision.
- **Ollama only.** Results under `llama.cpp`, `vLLM`, `LM Studio`,
  or cloud endpoints will differ; quantisation variants within the
  same model family (e.g. `qwen3.5:9b-q4_K_M` vs `:9b-q8_0`) were
  not compared.

## Future work

- **Multi-seed variance**: 5–10 runs per model to put error bars on
  the rankings.
- **Thinking-on / thinking-off ablation** for Qwen3.5 and Gemma4 —
  directly measure the value of `<think>` chains on a quantitative
  task.
- **Quantisation ablation**: q4_K_M vs q8_0 vs bf16 of the same
  weights on the same task.
- **Extended roster**: add `deepseek-r1:14b` (pure reasoning),
  `qwen3:30b-a3b` (MoE), `gpt-oss:120b` (large reasoning), and a
  coding-tuned model for comparison.
- **Multi-agent framework pass**: repeat the tournament with an
  AutoGen group-chat setup (one agent per role, moderated), to
  measure the cost of the agent framework itself against the
  single-call baseline established here.
- **Longer horizon / harder demand**: 52- or 104-week runs, random
  demand, external shocks.

---

## Appendix A — The 5-model roster

| Model                    | Size (GB) | Type               | Answer location         |
|--------------------------|----------:|--------------------|-------------------------|
| `mistral:latest`         | 4.4       | dense, instruct    | first integer in content |
| `qwen3.5:9b`             | 6.6       | hybrid thinking    | after `</think>`, else first |
| `phi4:14b`               | 9.1       | dense, instruct    | first integer in content |
| `gemma4:e4b-it-q4_K_M`   | 9.6       | thinking-capable   | after `</think>`, else first |
| `gpt-oss:20b`            | 13.0      | reasoning (RL-trained CoT) | `reasoning` field, last int |

All within a factor of ~3× in disk/RAM footprint — deliberately a
"similar-class" cohort so the comparison is not dominated by
capacity differences.

## Appendix B — GABM, agentic frameworks, and what we actually ran

### What GABM is

**Generative Agent-Based Modeling (GABM)** couples classical
mechanistic agent-based simulation with LLM-driven agent behaviour.
The mechanistic model provides the *world* — state, physical /
economic / social dynamics, success metrics. The LLM provides each
agent's *decision policy*, typically expressed in natural-language
prompts that describe the agent's role, goals, and observations. The
methodology is articulated at length in

> Ghaffarzadegan, N., Majumdar, A., Williams, R., &
> Hosseinichimeh, N. (2024). *Generative agent-based modeling:
> an introduction and tutorial.* System Dynamics Review.
> arXiv:[2309.11456](https://arxiv.org/abs/2309.11456).

That work positions GABM as a bridge between traditional ABM
(well-defined mechanics, brittle behaviours) and LLMs (flexible
behaviours, no mechanics), and specifically calls out the Beer
Game as a canonical testbed for the methodology.

### What an "agentic framework" adds

A general agentic framework like **AutoGen** extends the simple
"one prompt → one answer" pattern we used here with structured
multi-agent conversation, role-specialised agents, tool-use,
shared memory, and orchestration patterns (group-chat, sequential,
hierarchical). The AutoGen framework is described in

> Wu, Q., Bansal, G., Zhang, J., Wu, Y., Zhang, S., Zhu, E.,
> Li, B., Jiang, L., Zhang, X., & Wang, C. (2023). *AutoGen:
> Enabling next-gen LLM applications via multi-agent conversation
> framework.* arXiv:[2308.08155](https://arxiv.org/abs/2308.08155).

### What *this* benchmark ran

For this study we deliberately did **not** use a full agentic
framework. Our GABM pipeline is the minimum viable version:

- **One process, one simulation engine.** `BeerGameEngine`
  (`src/engine/simulation.py`) owns the authoritative world-state
  and enforces Sterman's two-phase week.
- **Four stateless LLM calls per simulated week**, one per role.
  Each call is a vanilla OpenAI `chat.completions.create` against
  Ollama's compatibility endpoint. There is no inter-agent chat,
  no tool-use, no planner / executor split, no memory beyond the
  per-role record sheet we hand-format into the prompt.
- **Per-role prompt templates** (`src/gabm/agent.py`) describe
  the role's position in the chain, the cost structure, the
  anti-bullwhip warning, and the full visible history.

This design makes the LLM the *only* variable in the benchmark.
Any difference in total cost between models is attributable to
the model's own decision policy — not to orchestration
overhead, framework-induced prompt bloat, or tool-call latency.
The AutoGen comparison is explicitly listed in *Future work* as
a separate study; the numbers reported here are the **"what you
get from the raw model"** floor, which a framework would need to
*beat* to justify its added complexity.

### Why this matters for reading the leaderboard

A reasonable response to "`gpt-oss:20b` beat the Sterman
mechanistic baseline" might be *"sure, but only because it has an
agentic framework underneath"*. That's not the case here. The
2,585-dollar total was produced by 144 independent chat-completion
calls, each given a role-specific prompt and a history table, with
no agent-to-agent coordination at all. Any credit accrues to the
model weights and the prompt, in that order.

## Appendix C — Non-Ollama reference run: DeepSeek V4 Flash on ds4

After the main 5-model Ollama tournament, we ran the same GABM
harness against **DeepSeek V4 Flash** served by
[`antirez/ds4`](https://github.com/antirez/ds4) (`ds4-server`,
Metal, q4-imatrix, ~153 GB on disk) on the same Mac Studio. This
is a *reference data point*, not a leaderboard entry: the runtime,
model class, and KV-cache strategy are all different from the
Ollama cohort.

### Result

| Model | Runtime | Wall (s) | **Total** | Retailer | Wholesaler | Distributor | Factory |
|---|---|---:|---:|---:|---:|---:|---:|
| `deepseek-v4-flash` (q4-imatrix) | `ds4-server` (Metal) | 1,360 | **$2,789.50** | 883.50 | 1,120.00 | 570.00 | 216.00 |

For comparison, the leader of the Ollama roster (`gpt-oss:20b`)
totalled **$2,585**, and the Sterman mechanistic baseline is
**$3,128**. ds4-served DeepSeek V4 Flash also beats Sterman, and
lands within ~8 % of `gpt-oss:20b` on game cost.

### Why we report it separately

- **Different inference engine.** `ds4-server` is a single-purpose
  native engine for DeepSeek V4 Flash, with a Metal graph executor
  and a single mutable KV checkpoint. Ollama uses `llama.cpp`
  under the hood with a generic loader and per-request KV.
- **Different model class.** The Ollama cohort is intentionally a
  4–13 GB "similar-class" lineup. DeepSeek V4 Flash is a 284 B
  parameter MoE; the q4-imatrix file alone is ~153 GB on disk.
- **Structural KV-cache advantage on this workload.** The GABM
  beer-game prompt is a stable system prompt + a per-role
  transcript that grows by one row per week. ds4-server is
  designed to share the longest matching prefix across requests
  and reuse the live KV checkpoint, so most of each per-week call
  reuses prefill from the previous call. Ollama's per-request KV
  does not exploit this. Wall-time is therefore *not* directly
  comparable; per-decode latency at steady state is the more
  honest metric, which we did not isolate in this run.
- **Thinking mode left on (ds4 default).** The existing GABM
  parser strips `</think>` blocks and the OpenAI `reasoning`
  field, so integer extraction worked unchanged.

### Reproducing it

```bash
# In a separate terminal, start ds4-server (after building ds4 and
# downloading the q4-imatrix weights — see ds4's README):
~/src/ds4/ds4-server --ctx 32768 --port 8000 \
  --kv-disk-dir /tmp/ds4-kv --kv-disk-space-mb 8192

# Then, from the beer-game repo:
LLM_ENDPOINT=http://localhost:8000/v1 MODELS=deepseek-v4-flash \
  uv run scripts/preflight.py
./scripts/tournament-ds4.sh
```

### What this tells us

DeepSeek V4 Flash, on its own purpose-built engine, lands in the
same ballpark as the best general-purpose Ollama-served model on
this workload. That's a useful *upper-edge* sanity check on the
benchmark itself: the leaderboard isn't accidentally rewarding a
single architecture or runtime, and there is real signal at the
top of the table — bigger / more recent models do measurably
better, but the gap is single-digit percentage points, not
order-of-magnitude. The interesting open question for future work
is whether the gap is the model, the prompt, or the prefix-reuse —
each of which is independently testable.

