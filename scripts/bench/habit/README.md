<!-- SPDX-License-Identifier: CC-BY-4.0 -->

# Habit Bench

A before-and-after check of the compact rule pack on two habits of agent-drafted papers and proposals: attaching a caveat to good results, and transcribing tables into prose. It also guards against the opposite failure, a swing to overclaiming.

## Design

- **Conditions.** A is the previous release's `docs/rule-pack-compact.md`; B is the candidate. Every draft runs in a fresh workspace where the pack is the only instruction file that differs. Claude Code reads it through a `CLAUDE.md` import, and Codex reads it as `AGENTS.md`.
- **Tasks.** Eight paper and proposal tasks in `tasks/tasks.md`. The first six are the original set; `t7-heldout` and `t8-heldout` were added after the first and second v0.5.0 runs as held-out checks. Each committed run keeps the exact task file it froze. Prompts give a results table, name the table it will become, and carry no style instruction. Every task holds one trap (a near-tie, a non-significant result, an overhead, or a mostly negative outcome) and an answer key with the correct reading.
- **Writers.** Claude Sonnet and Opus through `claude -p`, and Codex through `codex exec`, three generations per task and condition.
- **Judge.** Cross-family and blind: Codex judges Claude drafts, Claude Opus judges Codex drafts, and the A/B order is randomized. The rubric in `judge-rubric.md` scores each text for unsupported claims, missing material qualifiers, trap errors, and reflexive qualifiers. It also asks two pairwise questions: contribution visibility without unsupported claims, and clarity of the main pattern.
- **Review loop.** `loop` holds the reviser and the pack fixed and varies only the review lens (`lenses/old-lens.md` against `lenses/new-lens.md`) over two review-and-revise rounds per task.

## Run

```bash
python scripts/bench/habit/habit_bench.py freeze   --out OUT --pack-a A.md --pack-b B.md
python scripts/bench/habit/habit_bench.py generate --out OUT
python scripts/bench/habit/habit_bench.py judge    --out OUT
python scripts/bench/habit/habit_bench.py loop     --out OUT --old-lens scripts/bench/habit/lenses/old-lens.md --new-lens scripts/bench/habit/lenses/new-lens.md
python scripts/bench/habit/habit_bench.py report   --out OUT
```

`freeze` copies both packs into `OUT/packs/` and records the task, rubric, and pack hashes; every later step refuses to run if any of them changed. To recheck a committed run, pass its own task file, for example `--tasks docs/bench-habit-v0.5.0-drafts/run1/tasks.md`. Each step resumes where it stopped, so a failed call can be retried by rerunning the step. The run makes model calls billed to the logged-in Claude Code and Codex accounts.

Release criteria and the v0.5.0 results are in [`docs/bench-habit-v0.5.0.md`](../../../docs/bench-habit-v0.5.0.md).
