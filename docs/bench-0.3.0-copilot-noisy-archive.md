# agent-style bench — v0.2.0 (runner: GitHub Copilot CLI (gpt-5.4))

- Runner: GitHub Copilot CLI (gpt-5.4)
- Generations per condition: 2
- Date: 2026-04-21T07:25:21Z
- agent-style version: 0.2.0

## Per-task per-rule delta (mechanical + structural; semantic excluded)

| Task | Baseline total | Treatment total | Delta | Dominant rule |
|---|---|---|---|---|
| pr-01-redis-cache | 2 | 1 | -1 | RULE-12 |
| pr-03-auth-middleware | 0 | 0 | 0 | — |
| design-02-rate-limiter | 6 | 8 | 2 | RULE-12 |
| commit-01-fix-timezone | 2 | 2 | 0 | — |
| paper-01-abstract-anomaly | 7 | 7 | 0 | RULE-12 |
| paper-02-methods-contrastive | 9 | 4 | -5 | RULE-12 |
| paper-03-experiments-benchmarks | 6 | 9 | 3 | — |
| paper-04-related-work-agent-benchmarks | 8 | 6 | -2 | RULE-12 |
| product-01-schema-drift-watch | 9 | 8 | -1 | RULE-12 |
| grant-01-nsf-specific-aim | 8 | 10 | 2 | RULE-12 |

## Totals

| | Baseline | Treatment | Delta |
|---|---|---|---|
| total violations | 57 | 55 | -2 |

## Per-rule aggregate

| Rule | Baseline | Treatment | Delta |
|---|---|---|---|
| RULE-12 | 53 | 51 | -2 |
| RULE-G | 2 | 2 | 0 |
| RULE-I | 2 | 2 | 0 |

_Sanity benchmark; numbers are directional, not a claim of statistical significance._
