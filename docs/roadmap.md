# Beer Game benchmark roadmap

This repository treats the benchmark bundle as the durable interface: each run
should produce an Inspect-style `.eval` artifact with stable schemas, scenario
provenance, model telemetry, and queryable results.

## Current architecture direction

1. **Bundle output format** - keep `manifest.json`, JSONL metadata, Parquet
   decision/state tables, and optional traces together as one portable artifact.
2. **Telemetry** - keep model-call telemetry in stable Beer Game columns even
   when upstream GenAI/OpenTelemetry conventions evolve.
3. **Scenario gating** - version scenarios with release/removal metadata so
   benchmark runs can pin an active release.
4. **Metric registry** - add new benchmark metrics as registered functions
   rather than one-off report code.
5. **Bullwhip and recovery metrics** - prefer supply-chain dynamics metrics over
   generic model leaderboard scores.
6. **Epochs and reducers** - run repeated epochs and report mean, standard
   deviation, standard error, and bootstrap intervals.
7. **Parser strategy tracking** - record which parse strategy produced each
   order so model-family quirks stay auditable.
8. **Response cache** - cache model responses by model, config, prompt, scenario,
   seed, epoch, and materialized demand.
9. **YAML configuration** - keep benchmark inputs explicit, reviewable, and
   reproducible.
10. **Procedural scenarios** - keep demand generators deterministic and seeded.
11. **Statistical comparison** - compare models with paired bootstrap over shared
   scenarios and seeds.

## Guardrails

- Preserve the Beer Game mechanics documented in
  [`beer-game-instructions.md`](./beer-game-instructions.md).
- Treat generated run output as disposable unless it is intentionally checked in
  as a small fixture under `docs/examples/`.
- Prefer temporary validation output under `/tmp`.
- Keep historical research notes in git history, not in the active tree.
