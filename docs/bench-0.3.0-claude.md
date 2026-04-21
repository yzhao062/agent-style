# agent-style bench — v0.2.0 (runner: Claude Code CLI (claude-opus-4-7))

- Runner: Claude Code CLI (claude-opus-4-7)
- Generations per condition: 2
- Date: 2026-04-21T07:25:19Z
- agent-style version: 0.2.0

## Per-task per-rule delta (mechanical + structural; semantic excluded)

| Task | Baseline total | Treatment total | Delta | Dominant rule |
|---|---|---|---|---|
| pr-01-redis-cache | 6 | 2 | -4 | RULE-B |
| pr-03-auth-middleware | 2 | 1 | -1 | — |
| design-02-rate-limiter | 14 | 7 | -7 | RULE-B |
| commit-01-fix-timezone | 1 | 0 | -1 | — |
| paper-01-abstract-anomaly | 13 | 8 | -5 | RULE-B |
| paper-02-methods-contrastive | 10 | 7 | -3 | RULE-12 |
| paper-03-experiments-benchmarks | 8 | 7 | -1 | RULE-B |
| paper-04-related-work-agent-benchmarks | 20 | 8 | -12 | RULE-I |
| product-01-schema-drift-watch | 13 | 10 | -3 | RULE-12 |
| grant-01-nsf-specific-aim | 18 | 8 | -10 | RULE-12 |

## Totals

| | Baseline | Treatment | Delta |
|---|---|---|---|
| total violations | 105 | 58 | -47 |

## Per-rule aggregate

| Rule | Baseline | Treatment | Delta |
|---|---|---|---|
| RULE-12 | 62 | 45 | -17 |
| RULE-B | 27 | 0 | -27 |
| RULE-I | 14 | 10 | -4 |
| RULE-G | 2 | 3 | 1 |

_Sanity benchmark; numbers are directional, not a claim of statistical significance._
