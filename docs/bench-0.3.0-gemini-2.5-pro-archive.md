# agent-style bench — v0.2.0 (runner: Gemini CLI (gemini-2.5-pro))

- Runner: Gemini CLI (gemini-2.5-pro)
- Generations per condition: 2
- Date: 2026-04-21T07:25:23Z
- agent-style version: 0.2.0

## Per-task per-rule delta (mechanical + structural; semantic excluded)

| Task | Baseline total | Treatment total | Delta | Dominant rule |
|---|---|---|---|---|
| pr-01-redis-cache | 0 | 0 | 0 | — |
| pr-03-auth-middleware | 0 | 0 | 0 | — |
| design-02-rate-limiter | 4 | 8 | 4 | RULE-06 |
| commit-01-fix-timezone | 1 | 0 | -1 | RULE-I |
| paper-01-abstract-anomaly | 8 | 8 | 0 | RULE-05 |
| paper-02-methods-contrastive | 3 | 5 | 2 | RULE-12 |
| paper-03-experiments-benchmarks | 13 | 10 | -3 | RULE-B |
| paper-04-related-work-agent-benchmarks | 13 | 11 | -2 | RULE-12 |
| product-01-schema-drift-watch | 10 | 8 | -2 | RULE-12 |
| grant-01-nsf-specific-aim | 18 | 24 | 6 | RULE-I |

## Totals

| | Baseline | Treatment | Delta |
|---|---|---|---|
| total violations | 70 | 74 | 4 |

## Per-rule aggregate

| Rule | Baseline | Treatment | Delta |
|---|---|---|---|
| RULE-12 | 30 | 26 | -4 |
| RULE-G | 3 | 4 | 1 |
| RULE-I | 16 | 21 | 5 |
| RULE-05 | 12 | 14 | 2 |
| RULE-06 | 3 | 3 | 0 |
| RULE-B | 6 | 6 | 0 |

_Sanity benchmark; numbers are directional, not a claim of statistical significance._
