# Beer Game `.eval` Bundle Schema

This document defines the storage contract for Beer Game evaluation bundles.
It is the source of truth for the bundle writer, telemetry exporter, metrics,
and reports.

## Goals

One run produces one schema-versioned artifact under `runs/`. The v1 artifact
is a directory so writers can append files without ZIP complexity:

```text
runs/<run_id>.eval/
  manifest.json
  scenarios.jsonl
  games.jsonl
  decisions.parquet
  states.parquet
  traces/
    <game_id>.jsonl
```

The internal file names and schemas are intended to remain stable if the
directory is later wrapped as a ZIP archive.

A minimal checked-in example bundle is available at
[`docs/examples/minimal.eval/`](./examples/minimal.eval/).

Bundles can be opened through the DuckDB helper:

```python
from src.bench.query import open_bundle

con = open_bundle("runs/<run_id>.eval")
con.execute("SELECT count(*) FROM decisions").fetchone()
```

For a first plain-text summary, run:

```bash
uv run python -m bench.report runs/<run_id>.eval
```

The report intentionally uses plain ASCII tables so it works in terminals,
logs, and CI without extra rendering support.

Metric functions live in `src.bench.metrics` and register themselves with the
`@metric()` decorator. Registered metrics accept a DuckDB connection from
`open_bundle()` or `open_bundles()` and return scalar values for reports and
future reducers. The built-in metrics are:

| Metric | Definition | Edge cases |
|---|---|---|
| `total_cost` | Sum of `states.cost_week` across all rows. | `None` for empty state views. |
| `bullwhip_ratio` | Mean per-game `Var(factory order_placed) / Var(retailer customer_demand)`. | Skips games with missing or zero customer-demand variance; `None` if no valid games remain. |
| `parse_success_rate` | Fraction of decision rows where `parse_ok` is true. | `NULL` parse flags count as failures; `None` for empty decision views. |
| `recovery_time` | Mean elapsed weeks from a step demand shock until system pressure stabilizes. | Only step scenarios are considered; `None` if no game recovers. |

Runs can repeat the same scenario/model pair across epochs:

```bash
uv run python -m bench.run --mode mechanistic --turns 6 --epochs 5
```

Each epoch writes a separate `games.jsonl` row and carries the epoch number into
`decisions.parquet`. The report reduces per-epoch metric values with `mean` and
Inspect-style `bootstrap_stderr`, printing `value +/- stderr (n=K)` when more
than one epoch has a valid metric value. With one epoch, it keeps the plain
single-value metric output. The current step demand is deterministic, so
`demand_seed` is recorded for future procedural scenarios but does not yet alter
the generated demand series.

## Schema versioning

`manifest.json.schema_version` uses semantic versioning.

| Change | Version bump | Examples |
|---|---:|---|
| Backward-compatible clarification | Patch | Better field description, extra example query |
| Backward-compatible schema addition | Minor | Add an optional nullable column with a default reader behavior |
| Backward-incompatible schema change | Major | Rename/remove a field, change a type, make nullable data required |

Readers should reject bundles with an unsupported major version and may warn on
newer minor versions.

## Release tags

Scenario release tags use `YYYY-Qn`, where `n` is `1`, `2`, `3`, or `4`. Runs
pin `active_release` in `manifest.json`. Scenario loading includes scenarios
where:

```text
release_date <= active_release
and (removal_date is null or removal_date > active_release)
```

## File schemas

### `manifest.json`

One object per bundle.

| Name | Type | Nullable | Source | Description | Consumer |
|---|---|---:|---|---|---|
| `schema_version` | string | no | bundle writer constant | Bundle schema semver, for example `"1.0.0"`. | All readers |
| `run_id` | string | no | bundle writer | Unique sortable run id; matches the bundle directory name prefix. | Joins, reports |
| `started_at` | string, ISO-8601 UTC | no | bundle writer | Run start timestamp. | Reports |
| `ended_at` | string, ISO-8601 UTC | yes | bundle writer | Run completion timestamp; null until `finish()`. | Reports |
| `git_sha` | string | yes | `git rev-parse HEAD` | Source revision used for the run; null outside a Git checkout. | Provenance |
| `git_dirty` | bool | no | `git status --porcelain` | Whether the worktree had uncommitted changes. | Provenance |
| `prompt_version` | string | yes | prompt file hash | Hash or version of prompt templates used by GABM players. | Reproducibility |
| `config_hash` | string | no | resolved config hash | Hash of the normalized run configuration. | Cache keys, provenance |
| `config` | object | no | resolved config | Full run configuration snapshot. | Reproducibility |
| `active_release` | string, `YYYY-Qn` | no | CLI/config | Scenario release pin used for filtering. | Scenario loader, reports |
| `run_seed` | int64 | no | CLI/random source | Top-level seed used to derive game seeds. | Reproducibility |
| `models` | array<object> | no | CLI/config | Models requested for the run; each entry includes `id`, `provider`, `endpoint`, and sampling params when known. | Runner, reports |
| `scenario_ids` | array<string> | no | scenario loader | Scenarios actually included after release gating. | Runner, reports |
| `tool_versions` | object | no | runtime | Tool versions, including at least `beer-game` and `python` when available. | Provenance |

### `scenarios.jsonl`

One JSON object per scenario used in the run.

| Name | Type | Nullable | Source | Description | Consumer |
|---|---|---:|---|---|---|
| `scenario_id` | string | no | scenario definition | Stable scenario id. | Joins, release gating |
| `demand_pattern` | string | no | scenario definition | Demand generator name, for example `step`, `constant`, `ramp`, `sinusoid`, or `bounded_random`. | Runner |
| `params` | object | no | scenario definition | Pattern-specific parameters, such as `{"low":4,"high":8,"step_week":5}`. | Demand generator |
| `weeks` | int32 | no | scenario definition | Number of simulated weeks. | Runner, validation |
| `costs` | object | no | scenario definition | Cost parameters, for example `{"holding":0.5,"backlog":1.0}`. | Engine, reports |
| `scenario_seed` | int64 | no | scenario definition | Scenario-level seed used in `demand_seed` derivation. | Seed derivation |
| `release_date` | string, `YYYY-Qn` | no | scenario definition | First active release for the scenario. | Release gating |
| `removal_date` | string, `YYYY-Qn` | yes | scenario definition | First release where the scenario is retired; null if still active. | Release gating |

### `games.jsonl`

One JSON object per game, where a game is one scenario, model, and epoch.

| Name | Type | Nullable | Source | Description | Consumer |
|---|---|---:|---|---|---|
| `game_id` | string | no | bundle writer | Unique sortable game id. | Joins |
| `run_id` | string | no | manifest | Parent run id. | Joins |
| `scenario_id` | string | no | scenario row | Scenario played by this game. | Joins, metrics |
| `model` | string | no | run config | Requested model id. | Leaderboards |
| `epoch` | int32 | no | runner | Zero-based repeated-run index. | Variance reducers |
| `demand_seed` | int64 | no | seed derivation | Model-independent seed for demand generation. | Paired comparisons |
| `llm_seed` | int64 | no | seed derivation | Model-specific seed sent to providers that support seeded sampling. | Reproducibility |
| `started_at` | string, ISO-8601 UTC | no | runner | Game start timestamp. | Reports |
| `ended_at` | string, ISO-8601 UTC | yes | runner | Game completion timestamp; null for interrupted games. | Reports |
| `status` | string | no | runner | `ok`, `error`, or `cancelled`. | Reports, failure filtering |
| `error` | string | yes | exception handler | Exception class and message when `status` is `error`; otherwise null. | Debugging |
| `demand_hash` | string | no | demand generator | MD5 of the materialized demand array. | Paired-comparison validation |
| `total_cost` | float64 | yes | engine | Final total inventory plus backlog cost; null if game did not finish. | Leaderboards |
| `wall_seconds` | float64 | yes | runner | End-to-end game duration; null if unavailable. | Runtime reports |

### `decisions.parquet`

One row per LLM decision call. Columns use stable Beer Game names. The
OpenTelemetry span processor is the only component that maps raw OTel GenAI
attributes into these names.

| Name | Type | Nullable | Source | Description | Consumer |
|---|---|---:|---|---|---|
| `run_id` | string | no | `beergame.run_id` | Parent run id. | Joins |
| `game_id` | string | no | `beergame.game_id` | Parent game id. | Joins |
| `scenario_id` | string | no | `beergame.scenario_id` | Scenario id for direct filtering without joining. | Reports |
| `epoch` | int32 | no | `beergame.epoch` | Zero-based epoch. | Variance reducers |
| `week` | int32 | no | `beergame.week` | Simulated week for the decision. | Timelines |
| `role` | string | no | `beergame.role` | One of `retailer`, `wholesaler`, `distributor`, or `factory`. | Per-role reports |
| `model_request` | string | no | `gen_ai.request.model` | Requested model name. | Model reports |
| `model_response` | string | yes | `gen_ai.response.model` | Actual model reported by provider. | Provider debugging |
| `provider` | string | no | `gen_ai.provider.name` | Provider/runtime name, for example `ollama`, `openai`, or `vllm`. | Provider reports |
| `temperature` | float64 | yes | `gen_ai.request.temperature` | Sampling temperature. | Reproducibility |
| `top_p` | float64 | yes | `gen_ai.request.top_p` | Nucleus sampling parameter. | Reproducibility |
| `seed_request` | int64 | yes | `gen_ai.request.seed` | Seed sent to provider, if supported. | Reproducibility |
| `input_tokens` | int64 | yes | `gen_ai.usage.input_tokens` | Prompt token count; null if provider omits usage. | Token reports |
| `output_tokens` | int64 | yes | `gen_ai.usage.output_tokens` | Completion token count; null if provider omits usage. | Token reports |
| `reasoning_tokens` | int64 | yes | `gen_ai.usage.reasoning.output_tokens` | Reasoning-token count when reported. | Token reports |
| `cache_read_input_tokens` | int64 | yes | `gen_ai.usage.cache_read.input_tokens` | Cached prompt tokens read by provider when reported. | Cache reports |
| `finish_reason` | string | yes | `gen_ai.response.finish_reasons[0]` | First finish reason from the provider. | Failure analysis |
| `response_id` | string | yes | `gen_ai.response.id` | Provider response id. | Debugging |
| `latency_ms` | int64 | yes | span duration | End-to-end call latency in milliseconds. | Latency reports |
| `time_to_first_chunk_ms` | int64 | yes | `gen_ai.response.time_to_first_chunk` | Streaming time to first chunk in milliseconds; null for non-streaming calls. | Latency reports |
| `parse_ok` | bool | yes | parser | Whether response parsing produced an order. | Parser metrics |
| `parse_strategy` | string | yes | parser | Parser strategy that succeeded, or `failed`. | Parser metrics |
| `decision_int` | int32 | yes | parser | Parsed order quantity; null when parsing failed or the call errored. | State validation |
| `context_used` | int64 | yes | local model/runtime | Estimated context tokens used, when available. | Context reports |
| `context_window` | int64 | yes | local model/runtime | Model context window, when known. | Context reports |
| `cache_hit` | bool | yes | `beergame.cache_hit` | Whether the Beer Game response cache served this decision. | Cache reports |
| `error_type` | string | yes | `error.type` | Exception class when the span records an error. | Failure analysis |
| `raw_response_ref` | string | yes | trace writer | Relative path under `traces/` for persisted raw response text. | Debugging |

Token and latency columns are nullable so issue #4 can write schema-conformant
placeholder rows before issue #5 adds OTel instrumentation.

### `states.parquet`

One row per game, week, and role.

| Name | Type | Nullable | Source | Description | Consumer |
|---|---|---:|---|---|---|
| `run_id` | string | no | manifest | Parent run id. | Joins |
| `game_id` | string | no | game row | Parent game id. | Joins |
| `week` | int32 | no | engine | Simulated week. | Timelines |
| `role` | string | no | engine | One of `retailer`, `wholesaler`, `distributor`, or `factory`. | Per-role reports |
| `inventory` | int32 | no | engine state | Ending inventory for this role and week. | Cost analysis |
| `backlog` | int32 | no | engine state | Ending backlog for this role and week. | Cost analysis |
| `order_placed` | int32 | no | engine/decision | Order placed by this role in this week. | Bullwhip metrics |
| `shipment_received` | int32 | no | engine state | Shipment received by this role in this week. | Flow analysis |
| `customer_demand` | int32 | yes | demand generator | Exogenous customer demand for retailer rows; null for non-retailer rows. This is the canonical source for bullwhip computation. | Bullwhip metrics |
| `cost_week` | float64 | no | engine | Holding plus backlog cost for this role and week. | Cost reports |
| `cost_cum` | float64 | no | engine | Cumulative cost for this role through this week. | Cost reports |

## Seed derivation

The schema separates demand randomness from model sampling randomness so model
comparisons can share demand while retaining model-specific LLM sampling.

```python
run_seed: int       # from CLI/config or generated once per run
scenario_seed: int  # from scenarios.jsonl

demand_seed = stable_hash((run_seed, scenario_id, scenario_seed, epoch)) % 2**32
llm_seed = stable_hash((run_seed, scenario_id, model, epoch)) % 2**32
```

`demand_seed` is model-independent: the same scenario and epoch should produce
the same demand series for every model. `llm_seed` is model-specific and is the
value sent as `gen_ai.request.seed` when a provider honors seeded sampling.

`stable_hash` must be deterministic across Python processes and platforms. Do
not use Python's built-in `hash()`.

## Minimal examples

### `manifest.json`

```json
{
  "schema_version": "1.0.0",
  "run_id": "2026-05-19T160000Z-01HXABCDEF",
  "started_at": "2026-05-19T16:00:00Z",
  "ended_at": "2026-05-19T16:03:42Z",
  "git_sha": "0123456789abcdef0123456789abcdef01234567",
  "git_dirty": false,
  "prompt_version": "sha256:6f1b0d",
  "config_hash": "sha256:5d4140",
  "config": {
    "active_release": "2026-Q2",
    "weeks": 36,
    "epochs": 1
  },
  "active_release": "2026-Q2",
  "run_seed": 12345,
  "models": [
    {
      "id": "mistral:latest",
      "provider": "ollama",
      "endpoint": "http://localhost:11434/v1",
      "temperature": 0.4,
      "top_p": null
    }
  ],
  "scenario_ids": ["step_4_8_36w"],
  "tool_versions": {
    "beer-game": "0.1.0",
    "python": "3.13"
  }
}
```

### `scenarios.jsonl`

```json
{"scenario_id":"step_4_8_36w","demand_pattern":"step","params":{"low":4,"high":8,"step_week":5},"weeks":36,"costs":{"holding":0.5,"backlog":1.0},"scenario_seed":42,"release_date":"2026-Q2","removal_date":null}
```

### `games.jsonl`

```json
{"game_id":"2026-05-19T160000Z-01HXGAME01","run_id":"2026-05-19T160000Z-01HXABCDEF","scenario_id":"step_4_8_36w","model":"mistral:latest","epoch":0,"demand_seed":2882400001,"llm_seed":305419896,"started_at":"2026-05-19T16:00:01Z","ended_at":"2026-05-19T16:03:42Z","status":"ok","error":null,"demand_hash":"d41d8cd98f00b204e9800998ecf8427e","total_cost":8377.0,"wall_seconds":221.4}
```

## DuckDB examples

`src.bench.query.open_bundle(path)` registers the canonical views `manifest`,
`scenarios`, `games`, `decisions`, and `states` for one bundle.
`src.bench.query.open_bundles(glob_pattern)` registers the same views across
multiple bundle directories and adds a `bundle_id` column derived from each
bundle directory name without the `.eval` suffix.

Cost per model:

```sql
SELECT
  model,
  avg(total_cost) AS mean_total_cost,
  count(*) AS games
FROM 'runs/*.eval/games.jsonl'
WHERE status = 'ok'
GROUP BY model
ORDER BY mean_total_cost;
```

Mean latency per role:

```sql
SELECT
  role,
  avg(latency_ms) AS mean_latency_ms,
  count(*) AS calls
FROM 'runs/*.eval/decisions.parquet'
WHERE latency_ms IS NOT NULL
GROUP BY role
ORDER BY role;
```

Bullwhip computation using `states.customer_demand`:

```sql
WITH demand AS (
  SELECT game_id, stddev_samp(customer_demand) AS demand_std
  FROM 'runs/*.eval/states.parquet'
  WHERE role = 'retailer' AND customer_demand IS NOT NULL
  GROUP BY game_id
),
factory_orders AS (
  SELECT game_id, stddev_samp(order_placed) AS factory_order_std
  FROM 'runs/*.eval/states.parquet'
  WHERE role = 'factory'
  GROUP BY game_id
)
SELECT
  g.model,
  avg(factory_order_std / nullif(demand_std, 0)) AS bullwhip_ratio
FROM 'runs/*.eval/games.jsonl' AS g
JOIN demand USING (game_id)
JOIN factory_orders USING (game_id)
WHERE g.status = 'ok'
GROUP BY g.model
ORDER BY bullwhip_ratio;
```

## Open questions and current decisions

| Question | Current v1 decision | Reason |
|---|---|---|
| Directory or ZIP? | Directory now; ZIP later may wrap the same members. | The first writer needs simple append/finalize behavior. ZIP packaging should not change member schemas. |
| Is `report.html` part of the bundle contract? | Not required in v1. A generated report may be added as an optional member later. | Reports consume bundles; the core contract should not require report generation. |
| How should huge bundles be partitioned? | No partitioning in v1. If needed, partition Parquet by logical shards such as `decisions/<game_id>.parquet` while preserving a compatible view. | Single files are simpler for early runs and DuckDB examples. |
| Should raw conversations always be stored? | No. `traces/` is optional and enabled only when requested. | Full text can make bundles large; `raw_response_ref` links rows to traces when present. |
