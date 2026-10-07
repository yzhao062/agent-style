<!-- SPDX-License-Identifier: CC-BY-4.0 -->

# Habit Bench: v0.5.0

In this benchmark, the v0.5.0 compact pack removes reflexive caveats from agent-drafted paper and proposal prose and produces no judged trap error. Under the release wording, B is preferred on both pairwise questions. It misses two criteria set before the run: the strict per-cell safety rule and the numeric-density target. Section 6 lists the confirmed errors behind the safety result. The maintainer shipped the release with these misses as a field trial, and section 8 records that decision.

Harness: [`scripts/bench/habit/`](../scripts/bench/habit/README.md). Evidence, with every draft, every judgment, the condition key, the packs, the task file, and the frozen manifest of each run, is in `docs/bench-habit-v0.5.0-drafts/`.

## 1. Setup

Condition A is the v0.4.2 compact pack, and condition B is the v0.5.0 candidate. Each draft ran in a fresh workspace where the pack was the only instruction file that differed. The writers were Claude Sonnet 5.5 and Claude Opus 5.5 through `claude -p`, and Codex `gpt-6.1-sol` through `codex exec`, with three generations per task and condition.

The six original tasks are an abstract, a contributions paragraph, a results paragraph, an NSF preliminary-results subsection, a conclusion, and a mostly negative result. Every prompt gives a table, names the table it will become, and carries no style instruction. Each task holds one trap: a near-tie, a non-significant result, an overhead, a weak category, or a method that wins on one dataset of four. Two held-out tasks were added later and used for no wording decision: t7 (traffic forecasting) after run 1, and t8 (precipitation downscaling) after run 2.

A cross-family judge scored every A/B pair blind, in random order: Codex judged Claude drafts, and Claude Opus judged Codex drafts. The judge had the task data, an answer key, and the rubric in `judge-rubric.md`. For each text it counted unsupported claims, missing material qualifiers, trap errors, and reflexive qualifiers. It also answered two pairwise questions: which text shows the contribution without unsupported claims (Q1), and which states the main pattern more clearly (Q2).

## 2. Criteria Set Before the Run

| Criterion | Threshold |
| --- | --- |
| Safety | Within each writer, task, and error category, B adds no confirmed failure mode absent from A, and its confirmed error count does not rise. A confirmed B error that changes a task's conclusion blocks the release. |
| Reflexive qualifiers | Fall by at least 30% pooled |
| Numeric tokens per sentence | Fall by at least 25% pooled |
| Q1 and Q2 | B wins each in at least 60% of non-tied pairs |

## 3. Run 1: First Wording

Run 1 covered the six original tasks (108 drafts, 54 pairs). Pooled from A to B, unsupported claims fell from 30 to 20, trap errors from 3 to 0, and reflexive qualifiers from 7 to 1. Numeric tokens per sentence fell 19%. B won Q2 in 64% of non-tied pairs and Q1 in 50%.

Missing material qualifiers doubled, from 10 to 20, mostly in Codex drafts, so the safety criterion failed. Adjudication against the answer keys confirmed two patterns. All three Codex conclusions for the grasping task left out the weakest category (transparent objects at 68%). Elsewhere a writer moved a significance verdict to the table along with its numbers: a non-significant brain-MRI difference became a "small" gain, and within-noise differences went unstated. Writers read the first wording's "collect general limitations in the Limitations section" and "point to the display for intervals and p-values" too broadly.

The release was blocked and the wording changed. RULE-08 now says that a tie, a loss, a difference within noise, or the weakest case is a finding, reported next to the claim it bounds and in any summary. Only general limitations of the study design go to the Limitations section. The first revision of RULE-03 asked writers to say in words when an interval or test changes the reading, and not to call such a difference a gain. Section 5 describes its final form.

## 4. Run 2: Revised Wording, First Version

Run 2 reused the run-1 A drafts for the six original tasks, since the pack and prompts were unchanged. It wrote new B drafts for those tasks, and A and B drafts for t7.

| Measure (pooled, A to B) | All seven tasks | Held-out t7 only |
| --- | --- | --- |
| Unsupported claims | 32 to 21 | 5 to 1 |
| Missing material qualifiers | 14 to 12 | 4 to 2 |
| Trap errors | 3 to 0 | 0 to 0 |
| Reflexive qualifiers | 9 to 0 | 0 to 0 |
| Numeric tokens per sentence | −14% | −1% |
| Q1, B wins of non-tied | 33 of 58 (57%) | 5 of 8 |
| Q2, B wins of non-tied | 30 of 54 (56%) | 4 of 6 |

The doubling of missing qualifiers is gone. Eight writer-task cells show an increase in at least one judged error category, nine cell-category regressions in all. Adjudication found none that changes a task's conclusion. Four confirmed minor error patterns cover five drafts. Twice, a Sonnet results paragraph calls the non-significant brain-MRI difference a "tie". A proposal states a 29% difference as 23%, and a paragraph says a margin "exceeds" seven standard deviations when it equals seven. One Opus proposal adds a speculative reading of a baseline's convergence. Remaining judged errors are strictness that A drafts show in the same form. Judged again in run 2, the identical A drafts moved by up to three counts in a cell.

## 5. Run 3: Release Wording

Review of run 2's wording found that "an interval or test decides whether a difference is real" misstates what a significance test shows. The sentence was rewritten as it now ships. Run 3 tested the release pack on the three tasks where uncertainty decides the reading (t3, t6, t7, reusing their A drafts) and on a second held-out task, t8. Its pack B is byte-identical to the shipped `docs/rule-pack-compact.md`.

| Measure (pooled, A to B) | Four tasks | Held-out t8 only |
| --- | --- | --- |
| Unsupported claims | 6 to 8 | 1 to 3 |
| Missing material qualifiers | 10 to 7 | 1 to 3 |
| Trap errors | 0 to 0 | 0 to 0 |
| Reflexive qualifiers | 3 to 0 | 2 to 0 |
| Numeric tokens per sentence | −13% | −18% |
| Q1, B wins of non-tied | 20 of 32 (62%) | 5 of 8 |
| Q2, B wins of non-tied | 24 of 35 (69%) | 7 of 9 |

The number cut depends on the writer. In numeric tokens per sentence, Codex drafts fall 38% and Opus drafts 9%, while Sonnet drafts stay level. Sonnet's B drafts are shorter overall, but they often keep an interval and p-value next to the verbal verdict.

Three writer-task cells show an increase, four cell-category regressions in all. Adjudication confirmed three minor patterns. Two of three Opus t8 abstracts end by recommending U-Net for studies of extreme rainfall, which extends a single extremes metric into advice; both abstracts report every result correctly. As in run 2, two Sonnet t3 paragraphs call the non-significant brain-MRI difference a "tie". One Sonnet t7 paragraph reverses the direction of the size trend in one phrase. A further judged item faults the phrase "within noise" itself, which the release wording uses as an example; it was not counted as an error.

The review-loop check ran with the run-1 pack as the reviser's pack in both arms and varied only the `/vet` lens over two review-and-revise rounds per task. After two rounds, the new-lens drafts had no judged error of any kind. Old-lens drafts had one trap error, one unsupported claim, and one reflexive qualifier. Q1 favored the new lens in 5 of 6 tasks, and Q2 in all 5 non-tied tasks.

## 6. Criteria Status for the Release Wording

| Criterion | Status |
| --- | --- |
| Safety | Not met under the strict per-cell rule. Run 3 confirmed three minor error patterns across five drafts: an extrapolated recommendation, "tie" for an inconclusive difference, and one reversed phrase. No judged trap error, and no confirmed error misstates a number. |
| Reflexive qualifiers | Met: 3 to 0 in run 3, and 9 to 0 in run 2. |
| Numeric tokens per sentence | Not met: −13% in run 3 and −14% in run 2, against a 25% target. |
| Q1 and Q2 | Met in run 3: 62% and 69%. The run-2 wording reached 57% and 56%. |

Run 1 showed the trade this change has to manage. The wording that cut numbers harder also dropped qualifiers that changed claims, which is the overclaiming swing the change must avoid. Under the release wording, those qualifiers stay, and the cut in numbers is smaller. Shipping therefore required a maintainer decision on the unmet safety and numeric-density criteria.

## 7. Limitations

Three generations per cell make every cell estimate noisy, and the judge moves by up to three counts on identical text. One judge model scores each writer family, so judge and writer effects cannot be separated. The tasks are synthetic and short; a full paper gives a pack more places to act. Run 3 covers four of the eight tasks. Task t2's table reports a 2.35x speedup at 64k while marking vLLM as out of memory there, so that speedup has no runnable baseline. Several t2 judgments flag this, and the t2 counts in runs 1 and 2 carry that defect.

## 8. Release Decision

On 2026-10-06 the maintainer shipped v0.5.0 with both criteria unmet, as a field trial. The release wording now runs in day-to-day paper and proposal drafting. It will be revised if that use shows the overclaiming patterns of section 6, or if caveat tails and transcribed tables persist. A revision goes through this bench again, with the v0.5.0 compact pack as condition A and the same criteria.
