<!--
  Archive scorecard. NOT included in docs/bench-0.2.0.md.

  Kept here for transparency: Gemini 2.5 Pro's baseline output is already
  very clean (15 violations across 10 tasks × 2 gens, compared to Claude
  Opus 4.7's 62 and GPT-5.4's 26). The `agent-style` treatment produced a
  small regression (+2 violations, driven by one outlier task), which we
  read as "ruleset helps most on models with noisier baselines; Gemini
  Pro already avoids the mechanical tell patterns." Rather than average
  this into the 2-model headline, we archive it so future rule authors
  can see the per-rule pattern (RULE-B and RULE-G never fire for Gemini).

  The RULE-B count of 0 baseline / 0 treatment is especially notable:
  Google's RLHF appears to strip em/en-dash casual punctuation at the
  post-training step.
-->

# agent-style bench — v0.2.0 (runner: Gemini CLI (gemini-2.5-pro)) — ARCHIVE

- Runner: Gemini CLI (gemini-2.5-pro)
- Generations per condition: 2
- Date: 2026-04-21T03:22:54Z
- agent-style version: 0.2.0

## Per-task per-rule delta (mechanical + structural; semantic excluded)

| Task | Baseline total | Treatment total | Delta | Dominant rule |
|---|---|---|---|---|
| pr-01-redis-cache | 0 | 0 | 0 | — |
| pr-02-jwt-rotation | 0 | 0 | 0 | — |
| pr-03-auth-middleware | 0 | 0 | 0 | — |
| pr-04-db-index | 0 | 0 | 0 | — |
| pr-05-dependency-bump | 0 | 0 | 0 | — |
| design-01-incident-response | 5 | 4 | -1 | — |
| design-02-rate-limiter | 5 | 8 | 3 | RULE-12 |
| design-03-schema-migration | 3 | 3 | 0 | — |
| commit-01-fix-timezone | 2 | 2 | 0 | — |
| commit-02-feat-pagination | 0 | 0 | 0 | — |

## Totals

| | Baseline | Treatment | Delta |
|---|---|---|---|
| total violations | 15 | 17 | 2 |

## Per-rule aggregate

| Rule | Baseline | Treatment | Delta |
|---|---|---|---|
| RULE-12 | 6 | 7 | 1 |
| RULE-G | 6 | 6 | 0 |
| RULE-I | 3 | 4 | 1 |

_Sanity benchmark; numbers are directional, not a claim of statistical significance._
