# .ai-research

Research notes informing the evolution of beer-game into a local-model benchmarking tool.

All docs are static HTML (light, minimal theme). Open directly in a browser or serve the folder.

## Start here

- **[improvements.html](improvements.html)** — current improvement plan (v2). Bundle-format storage, OpenTelemetry GenAI telemetry, LiveBench-style release-date gating, Inspect-style epochs + reducers.

## Landscape

- **[benchmarks.html](benchmarks.html)** — 19 open-source AI benchmarks and frameworks with GitHub links, licenses, and suggested study order.
- **[evaluation-criteria.html](evaluation-criteria.html)** — 9-axis rubric for evaluating benchmark tooling, with weighting.

## Self-assessment

- **[beergame-eval.html](beergame-eval.html)** — current beer-game tool scored against the rubric (~2.5 composite), with comparison to AgentBench.

## Reference implementations studied

- **[agentbench-eval.html](agentbench-eval.html)** — AgentBench scored against the rubric (~2.9 composite).
- **[agentbench-patterns.html](agentbench-patterns.html)** — how AgentBench does (or doesn't) implement each of our 8 improvement areas.
- **[inspect-livebench-patterns.html](inspect-livebench-patterns.html)** — same analysis for Inspect AI and LiveBench, plus the best-of-three synthesis that drove the v2 plan.

## Repos referenced

- [THUDM/AgentBench](https://github.com/THUDM/AgentBench) — Apache 2.0
- [UKGovernmentBEIS/inspect_ai](https://github.com/UKGovernmentBEIS/inspect_ai) — MIT
- [LiveBench/LiveBench](https://github.com/LiveBench/LiveBench) — Apache 2.0
