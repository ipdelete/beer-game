# AGENTS.md

## Project overview

This repository implements a Beer Game simulation and benchmark. The Beer Game
is a four-tier supply-chain simulation: retailer, wholesaler, distributor, and
factory. Its educational purpose is to show how structure produces behavior,
especially the bullwhip effect.

Use `docs/beer-game-instructions.md` as the canonical reference for complete
game mechanics, rules, and educational framing.

Preserve the core game constraints:

- Four roles: retailer, wholesaler, distributor, factory.
- Inventory cost is `$0.50` per case per week.
- Backlog cost is `$1.00` per case per week.
- Players cannot communicate outside the modeled order/shipment flow.
- Customer demand follows the classic step pattern: 4 cases/week, then 8.
- Shipping, order, and production delays are central to the dynamics.

## Setup commands

```bash
uv sync
```

Run the main simulation:

```bash
uv run src/main.py
```

Run a benchmark bundle:

```bash
uv run python -m src.bench.run --turns 1
```

## Testing instructions

Run the full test suite before finishing code changes:

```bash
uv run pytest -q
```

Run Black on touched Python files:

```bash
uv run black --fast --check <paths>
```

Do not run Black on TOML, Markdown, Parquet, or generated data files.

For bundle/telemetry changes, also run the real command path and inspect the
generated `.eval` artifact:

```bash
uv run python -m src.bench.run --mode mechanistic --turns 1 --root /tmp/beer-game-check --run-id check-mech
uv run python -m src.bench.run --mode gabm --turns 1 --root /tmp/beer-game-check --run-id check-gabm
```

## Code style and conventions

- Keep changes scoped to the current issue.
- Preserve existing behavior unless the issue explicitly changes it.
- Prefer explicit schemas and stable column names for benchmark artifacts.
- Do not silently swallow invalid input; surface errors consistently with the
  surrounding code.
- Keep role names normalized at bundle/reporting boundaries:
  `retailer`, `wholesaler`, `distributor`, `factory`.
- Use lowercase filenames for documentation.

## Issue workflow

When asked to work a GitHub issue, the next issue, or backlog work:

1. Query live GitHub issues with `gh`; GitHub Issues are the backlog source of
   truth. Do not create or maintain a local backlog queue.
2. Prefer priority labels in order: `P0`, `P1`, `P2`, `P3`; use issue bodies and
   dependency notes to choose within a priority.
3. Create one branch per issue from current `master`; base the branch name on
   the issue number and title.
4. Write a plan before coding.
5. After the plan, run an explicit alignment pass:
   - review `docs/roadmap.md`;
   - review the next two relevant GitHub issues;
   - update the plan so this issue fits downstream consumers without
     overbuilding.
6. For non-trivial implementation, ask the rubber-duck agent to critique the
   plan before coding.
7. Implement narrowly but completely.
8. Validate with tests, formatter checks, and any real artifact/command path
   relevant to the issue.
9. Commit, push, create a PR, squash-merge, delete the issue branch, and pull
   latest `master`.
10. Stop after one issue unless explicitly told to continue.

## PR and commit conventions

PR bodies should include:

- concise summary;
- validation performed;
- `Closes #<issue-number>` when applicable.

Commit and squash-merge messages should include:

```text
Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>
```

## Security and artifacts

- Do not commit secrets, tokens, local `.env` files, or model credentials.
- Do not commit generated run output; default it to `/tmp`.
- Temporary validation artifacts should go under `/tmp` unless the issue asks
  for a checked-in fixture.
