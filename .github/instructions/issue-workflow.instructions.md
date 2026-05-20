---
applyTo: "**"
---

# Issue Workflow

Use this workflow when the user asks to work on a GitHub issue, the next issue,
or the backlog. GitHub Issues are the source of truth for backlog order and
priority; do not create or maintain a separate local backlog queue.

## Backlog selection

- Query live GitHub issues with `gh`.
- Prefer the highest priority label first: `P0`, then `P1`, then `P2`, then
  `P3`.
- Within the same priority, use issue/dependency order and the issue body to
  decide what should come next.
- Stop after one issue unless the user explicitly asks to continue.

## Per-issue workflow

1. Pull and inspect the current issue.
2. Create a branch from current `master`; base the branch name on the issue
   number and title.
3. Write a plan before coding.
4. Run an explicit alignment pass after the plan:
   - review `.ai-research/improvements.html`;
   - review the next two relevant GitHub issues;
   - update the plan so the current issue fits the roadmap and downstream
     consumers without overbuilding.
5. For non-trivial work, ask the rubber-duck agent to critique the plan before
   implementation.
6. Implement the current issue narrowly but completely.
7. Validate with:
   - `uv run pytest -q`;
   - formatter checks on touched Python files;
   - the real command path or artifact inspection relevant to the issue.
8. Commit, push, create a PR, squash-merge, delete the issue branch, and pull
   latest `master`.

## PR conventions

- PR body should include a concise summary, validation performed, and
  `Closes #<issue>`.
- Commit and squash merge messages should include:

```text
Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>
```

## Guardrails

- Preserve existing behavior unless the issue explicitly changes it.
- Do not duplicate backlog state in local files.
- Do not batch multiple backlog issues into one PR unless explicitly requested.
- Use follow-on issues to shape contracts and extension points, but keep code
  changes scoped to the current issue.
