# Beer Game benchmark configs

Benchmark runs can be described with layered YAML. Use `bench run --config
configs/runs/smoke.yaml` to run a resolved config.

## `import`

`import` loads another YAML file relative to the current file. Imported values
are merged first, and local sibling keys override or extend them.

```yaml
import: "../default.yaml"
models:
  - import: "../models/mechanistic.yaml"
```

`import` can appear at the root or inside nested dict/list entries.

## `default`

`default` is merged before local values, so local keys can override it.

```yaml
default:
  runner:
    parallel: 1
runner:
  parallel: 2
```

## `overwrite`

`overwrite` is merged last and always wins.

```yaml
overwrite:
  cache:
    enabled: true
```

## List merge policy

Lists concatenate by default. To replace a sibling list, add `_list_policy` at
the same mapping level:

```yaml
_list_policy:
  models: replace
models:
  - import: "../models/mechanistic.yaml"
```

`_list_policy` is reserved and stripped from the resolved config before it is
validated, snapshotted into `manifest.json`, or hashed.

## Secrets

Configs are snapshotted into shareable `.eval` bundles. Do not put API keys,
authorization headers, tokens, or secrets in YAML. Use environment variables for
credentials.

## Response cache

GABM runs use a JSON response cache by default. Set `cache.enabled: false` in a
config or pass `bench run --no-cache` to disable it for a run. Pass
`--refresh-cache` to ignore existing entries while writing fresh successful
responses. `--cache-dir` overrides `BEERGAME_CACHE_DIR`; otherwise the cache
defaults to `~/.cache/beer-game`.

## Matrix runs

A config can include multiple scenarios and models. `bench run --config ...`
runs the full `scenarios x models x epochs` matrix into one `.eval` bundle.
`runner.parallel` controls worker count; `bench run --parallel N` can override
it for a single invocation. Reusing the same `--run-id` resumes compatible
bundles by skipping successful cells, while `--force` reruns from scratch.

Use `bench compare <bundle> --baseline <model> --challenger <model>` to compare
matrix results with paired bootstrap significance. The comparison pairs models
by scenario and epoch, so keep matrix configs balanced when possible.

## Demand patterns

Scenarios choose a built-in `demand_pattern` and validated `params`:

| Pattern | Params |
|---|---|
| `constant` | `value` |
| `step` | `low`, `high`, `step_week` |
| `ramp` | `start`, `end`, `start_week`, `end_week` |
| `sinusoid` | `mean`, `amplitude`, `period_weeks`, optional `phase` |
| `bounded_random` | `low`, `high` inclusive integer bounds |

Random scenarios are seeded from `(run_seed, scenario_id, scenario_seed, epoch)`
so models see the same demand for each scenario/epoch pair.

## Scenario releases

Every scenario must declare `release_date` in `YYYY-Qn` format. `removal_date`
is optional; `null` means the scenario is still active.

```yaml
release_date: "2026-Q1"
removal_date: null
```

`bench run --active-release 2026-Q1 --config configs/runs/smoke.yaml` pins a
run to a release. If the flag is omitted, the config's `active_release` is used;
if the config also omits it, the latest release among configured scenarios is
used. A scenario is active when `release_date <= active_release` and
`removal_date` is absent or greater than `active_release`.

To retire a scenario, set the first release where it should no longer appear:

```yaml
removal_date: "2027-Q2"
```
