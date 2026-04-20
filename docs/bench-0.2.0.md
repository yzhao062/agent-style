# agent-style bench — v0.2.0

- Model: Claude Code default (claude -p)
- Generations per condition: 2
- Date: 2026-04-20T07:15:31Z
- agent-style version: 0.2.0

## Per-task per-rule delta (mechanical + structural; semantic excluded)

| Task | Baseline total | Treatment total | Delta | Dominant rule |
|---|---|---|---|---|
| pr-01-redis-cache | 4 | 6 | 2 | — |
| pr-02-jwt-rotation | 2 | 0 | -2 | RULE-12 |
| pr-03-auth-middleware | 0 | 2 | 2 | — |
| pr-04-db-index | 4 | 3 | -1 | RULE-12 |
| pr-05-dependency-bump | 1 | 1 | 0 | — |
| design-01-incident-response | 9 | 0 | -9 | RULE-12 |
| design-02-rate-limiter | 14 | 11 | -3 | RULE-I |
| design-03-schema-migration | 12 | 6 | -6 | RULE-12 |
| commit-01-fix-timezone | 1 | 1 | 0 | — |
| commit-02-feat-pagination | 0 | 0 | 0 | — |

## Totals

| | Baseline | Treatment | Delta |
|---|---|---|---|
| total violations | 47 | 30 | -17 |

## Per-rule aggregate

| Rule | Baseline | Treatment | Delta |
|---|---|---|---|
| RULE-12 | 24 | 18 | -6 |
| RULE-B | 15 | 9 | -6 |
| RULE-G | 5 | 2 | -3 |
| RULE-I | 3 | 1 | -2 |

_Sanity benchmark; numbers are directional, not a claim of statistical significance. See `scripts/bench/tasks.md` and the generated drafts under `/tmp/as-bench-Jf4NOk` (ephemeral) for the underlying data._
