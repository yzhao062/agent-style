# agent-style bench — v0.3.0 (multi-model matrix)

- Task set: 10 fixed prose tasks (see `scripts/bench/tasks.md`)
- Generations per condition: 2
- Models compared: 4
- Date: 2026-04-21
- **Version note**: the individual scorecards below record `agent-style version: 0.2.0` because this bench was run against the installed v0.2.0 PyPI/npm package (the last cut release). The `v0.3.0` prefix on these files names the release cycle and the reshaped task set (long-form paper / product / grant prose replacing the v0.2.0 short-PR-heavy set). The 21-rule payload itself is unchanged between 0.2.0 and 0.3.0; only bench infrastructure and task composition changed. When v0.3.0 cuts, rerunning this bench is optional — the current numbers remain valid measurements of the payload the release will ship.

## Totals across models

| Model | Baseline | Treatment | Δ | Δ% |
|---|---|---|---|---|
| Claude Code CLI (claude-opus-4-7) | 105 | 58 | -47 | -45% |
| Codex CLI (gpt-5.4) | 51 | 28 | -23 | -45% |
| GitHub Copilot CLI (gpt-5.4) | 61 | 63 | +2 | +3% |
| Gemini CLI (flash) | 79 | 14 | -65 | -82% |

## Per-rule Δ across models (treatment − baseline)

| Rule | Claude Code CLI (claude-opus-4-7) | Codex CLI (gpt-5.4) | GitHub Copilot CLI (gpt-5.4) | Gemini CLI (flash) |
|---|---|---|---|---|
| RULE-05 | 0 | 0 | 0 | -2 |
| RULE-06 | 0 | 0 | 0 | -13 |
| RULE-12 | -17 | -23 | +2 | -34 |
| RULE-B | -27 | 0 | 0 | -8 |
| RULE-G | +1 | 0 | -1 | -2 |
| RULE-I | -4 | 0 | +1 | -6 |

<details>
<summary><b>Per-model detail (full per-task scorecards)</b></summary>

### Claude Code CLI (claude-opus-4-7)

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

### Codex CLI (gpt-5.4)

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

### GitHub Copilot CLI (gpt-5.4)

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

### Gemini CLI (flash)

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

</details>

_Sanity benchmark; numbers are directional, not a claim of statistical significance. Each model runs the same 10 tasks × 2 generations × 2 conditions = 40 calls per model._
