# agent-style bench — v0.2.0

*This is a placeholder. Populate by running the sanity benchmark on the release commit:*

```bash
# Local (maintainer):
export ANTHROPIC_API_KEY=...
bash scripts/bench/run.sh --generations 2

# CI (recommended):
gh workflow run bench.yml --field generations=2 --field install_from=pypi --ref main
gh run download --name bench-0.2.0       # download the scorecard artifact
cp bench-0.2.0.md docs/bench-0.2.0.md    # commit alongside v0.2.0
```

See [`scripts/bench/tasks.md`](../scripts/bench/tasks.md) for the 10 task prompts and [`scripts/bench/run.sh`](../scripts/bench/run.sh) for the runner.

## Methodology (for readers of the final scorecard)

- Ten fixed tasks (5 PR descriptions, 3 design-doc sections, 2 commit messages)
- For each task, the bench generates `N` baseline drafts (no agent-style loaded in the project) and `N` treatment drafts (`agent-style enable claude-code` active) using the same Claude Code model and prompt.
- Each draft is scored with `agent-style review --mechanical-only --audit-only` — deterministic by construction; semantic rules are excluded from the benchmark to keep the per-run numbers reproducible.
- Per-rule deltas aggregate across all drafts; the per-task row shows the single most-improved rule ID for that task.

## Why "sanity" and not a ship gate

The PLAN marks this benchmark as a **sanity signal**, not a statistical claim. Ten tasks at two generations each is small enough that prompt variance can dominate any single-task row. The aggregate "total violations" delta is a directional read on whether the ruleset moves the needle at all, not a guarantee of a specific percentage. The benchmark's real job: catch regressions between releases by rerunning with the same task set and watching the baseline→treatment delta shape stay roughly stable.
