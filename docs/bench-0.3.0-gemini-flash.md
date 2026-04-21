# agent-style bench — v0.2.0 (runner: Gemini CLI (flash))

- Runner: Gemini CLI (flash)
- Generations per condition: 2
- Date: 2026-04-21T07:56:53Z
- agent-style version: 0.2.0

## Per-task per-rule delta (mechanical + structural; semantic excluded)

| Task | Baseline total | Treatment total | Delta | Dominant rule |
|---|---|---|---|---|
| pr-01-redis-cache | 2 | 0 | -2 | RULE-I |
| pr-03-auth-middleware | 2 | 0 | -2 | — |
| design-02-rate-limiter | 7 | 0 | -7 | RULE-B |
| commit-01-fix-timezone | 0 | 0 | 0 | — |
| paper-01-abstract-anomaly | 9 | 1 | -8 | RULE-06 |
| paper-02-methods-contrastive | 13 | 2 | -11 | RULE-12 |
| paper-03-experiments-benchmarks | 13 | 0 | -13 | RULE-12 |
| paper-04-related-work-agent-benchmarks | 6 | 4 | -2 | RULE-12 |
| product-01-schema-drift-watch | 8 | 0 | -8 | RULE-12 |
| grant-01-nsf-specific-aim | 19 | 7 | -12 | RULE-12 |

## Totals

| | Baseline | Treatment | Delta |
|---|---|---|---|
| total violations | 79 | 14 | -65 |

## Per-rule aggregate

| Rule | Baseline | Treatment | Delta |
|---|---|---|---|
| RULE-12 | 40 | 6 | -34 |
| RULE-06 | 15 | 2 | -13 |
| RULE-B | 8 | 0 | -8 |
| RULE-I | 7 | 1 | -6 |
| RULE-05 | 7 | 5 | -2 |
| RULE-G | 2 | 0 | -2 |

_Sanity benchmark; numbers are directional, not a claim of statistical significance._
