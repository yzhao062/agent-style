# agent-style bench — v0.2.0 (multi-model matrix)

- Task set: 10 fixed prose tasks (see `scripts/bench/tasks.md`)
- Generations per condition: 2
- Models compared: 2
- Date: 2026-04-21

## Totals across models

| Model | Baseline | Treatment | Δ | Δ% |
|---|---|---|---|---|
| Claude Code CLI (claude-opus-4-7) | 62 | 33 | -29 | -47% |
| OpenAI Agents SDK (gpt-5.4) | 26 | 20 | -6 | -23% |

## Per-rule Δ across models (treatment − baseline)

| Rule | Claude Code CLI (claude-opus-4-7) | OpenAI Agents SDK (gpt-5.4) |
|---|---|---|
| RULE-12 | -10 | -2 |
| RULE-B | -13 | 0 |
| RULE-G | -2 | -6 |
| RULE-I | -4 | +2 |

<details>
<summary><b>Per-model detail (full per-task scorecards)</b></summary>

### Claude Code CLI (claude-opus-4-7)

- Runner: Claude Code CLI (claude-opus-4-7)
- Generations per condition: 2
- Date: 2026-04-21T03:06:54Z
- agent-style version: 0.2.0

## Per-task per-rule delta (mechanical + structural; semantic excluded)

| Task | Baseline total | Treatment total | Delta | Dominant rule |
|---|---|---|---|---|
| pr-01-redis-cache | 12 | 3 | -9 | RULE-12 |
| pr-02-jwt-rotation | 10 | 4 | -6 | RULE-I |
| pr-03-auth-middleware | 4 | 1 | -3 | RULE-12 |
| pr-04-db-index | 2 | 2 | 0 | — |
| pr-05-dependency-bump | 1 | 1 | 0 | RULE-12 |
| design-01-incident-response | 8 | 7 | -1 | — |
| design-02-rate-limiter | 13 | 8 | -5 | RULE-B |
| design-03-schema-migration | 11 | 6 | -5 | RULE-B |
| commit-01-fix-timezone | 1 | 1 | 0 | — |
| commit-02-feat-pagination | 0 | 0 | 0 | — |

## Totals

| | Baseline | Treatment | Delta |
|---|---|---|---|
| total violations | 62 | 33 | -29 |

## Per-rule aggregate

| Rule | Baseline | Treatment | Delta |
|---|---|---|---|
| RULE-12 | 33 | 23 | -10 |
| RULE-B | 13 | 0 | -13 |
| RULE-G | 8 | 6 | -2 |
| RULE-I | 8 | 4 | -4 |

_Sanity benchmark; numbers are directional, not a claim of statistical significance._

### OpenAI Agents SDK (gpt-5.4)

- Runner: OpenAI Agents SDK (gpt-5.4)
- Generations per condition: 2
- Date: 2026-04-21T03:07:02Z
- agent-style version: 0.2.0

## Per-task per-rule delta (mechanical + structural; semantic excluded)

| Task | Baseline total | Treatment total | Delta | Dominant rule |
|---|---|---|---|---|
| pr-01-redis-cache | 2 | 2 | 0 | — |
| pr-02-jwt-rotation | 2 | 2 | 0 | RULE-12 |
| pr-03-auth-middleware | 1 | 0 | -1 | RULE-12 |
| pr-04-db-index | 2 | 2 | 0 | — |
| pr-05-dependency-bump | 0 | 0 | 0 | — |
| design-01-incident-response | 6 | 6 | 0 | RULE-G |
| design-02-rate-limiter | 7 | 3 | -4 | RULE-12 |
| design-03-schema-migration | 4 | 3 | -1 | RULE-G |
| commit-01-fix-timezone | 2 | 2 | 0 | — |
| commit-02-feat-pagination | 0 | 0 | 0 | — |

## Totals

| | Baseline | Treatment | Delta |
|---|---|---|---|
| total violations | 26 | 20 | -6 |

## Per-rule aggregate

| Rule | Baseline | Treatment | Delta |
|---|---|---|---|
| RULE-12 | 18 | 16 | -2 |
| RULE-G | 6 | 0 | -6 |
| RULE-I | 2 | 4 | 2 |

_Sanity benchmark; numbers are directional, not a claim of statistical significance._

</details>

_Sanity benchmark; numbers are directional, not a claim of statistical significance. Each model runs the same 10 tasks × 2 generations × 2 conditions = 40 calls per model._
