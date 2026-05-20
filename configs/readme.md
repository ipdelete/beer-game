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
