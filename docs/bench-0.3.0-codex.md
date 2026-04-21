# agent-style bench — v0.2.0 (runner: Codex CLI (gpt-5.4))

- Runner: Codex CLI (gpt-5.4)
- Generations per condition: 2
- Date: 2026-04-21T07:25:22Z
- agent-style version: 0.2.0

## Per-task per-rule delta (mechanical + structural; semantic excluded)

| Task | Baseline total | Treatment total | Delta | Dominant rule |
|---|---|---|---|---|
| pr-01-redis-cache | 2 | 0 | -2 | RULE-12 |
| pr-03-auth-middleware | 1 | 1 | 0 | RULE-12 |
| design-02-rate-limiter | 7 | 5 | -2 | — |
| commit-01-fix-timezone | 2 | 2 | 0 | — |
| paper-01-abstract-anomaly | 7 | 3 | -4 | RULE-12 |
| paper-02-methods-contrastive | 4 | 1 | -3 | RULE-12 |
| paper-03-experiments-benchmarks | 7 | 2 | -5 | RULE-12 |
| paper-04-related-work-agent-benchmarks | 7 | 6 | -1 | — |
| product-01-schema-drift-watch | 6 | 3 | -3 | RULE-12 |
| grant-01-nsf-specific-aim | 8 | 5 | -3 | RULE-12 |

## Totals

| | Baseline | Treatment | Delta |
|---|---|---|---|
| total violations | 51 | 28 | -23 |

## Per-rule aggregate

| Rule | Baseline | Treatment | Delta |
|---|---|---|---|
| RULE-12 | 47 | 24 | -23 |
| RULE-G | 2 | 2 | 0 |
| RULE-I | 2 | 2 | 0 |

_Sanity benchmark; numbers are directional, not a claim of statistical significance._
