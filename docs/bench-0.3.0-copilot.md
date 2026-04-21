# agent-style bench — v0.2.0 (runner: GitHub Copilot CLI (gpt-5.4))

- Runner: GitHub Copilot CLI (gpt-5.4)
- Generations per condition: 2
- Date: 2026-04-21T08:08:17Z
- agent-style version: 0.2.0

## Per-task per-rule delta (mechanical + structural; semantic excluded)

| Task | Baseline total | Treatment total | Delta | Dominant rule |
|---|---|---|---|---|
| pr-01-redis-cache | 2 | 4 | 2 | RULE-12 |
| pr-03-auth-middleware | 0 | 1 | 1 | RULE-12 |
| design-02-rate-limiter | 8 | 8 | 0 | RULE-12 |
| commit-01-fix-timezone | 2 | 2 | 0 | — |
| paper-01-abstract-anomaly | 7 | 7 | 0 | RULE-12 |
| paper-02-methods-contrastive | 6 | 6 | 0 | RULE-12 |
| paper-03-experiments-benchmarks | 7 | 12 | 5 | RULE-12 |
| paper-04-related-work-agent-benchmarks | 10 | 8 | -2 | RULE-12 |
| product-01-schema-drift-watch | 6 | 6 | 0 | RULE-12 |
| grant-01-nsf-specific-aim | 13 | 9 | -4 | RULE-G |

## Totals

| | Baseline | Treatment | Delta |
|---|---|---|---|
| total violations | 61 | 63 | 2 |

## Per-rule aggregate

| Rule | Baseline | Treatment | Delta |
|---|---|---|---|
| RULE-12 | 56 | 58 | 2 |
| RULE-G | 3 | 2 | -1 |
| RULE-I | 2 | 3 | 1 |

_Sanity benchmark; numbers are directional, not a claim of statistical significance._
