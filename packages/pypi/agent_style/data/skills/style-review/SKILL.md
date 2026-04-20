# SPDX-License-Identifier: CC-BY-4.0
---
name: style-review
description: Review Markdown prose against agent-style's 21 rules. `/style-review FILE` audits the file and (on user confirm) writes a polished copy at `FILE.reviewed.md`. `/style-review A.md B.md` A/B-compares two drafts and emits a per-rule delta table. Complements the generation-time rules installed via `agent-style enable <tool>`.
---

# style-review

Post-hoc review for prose an AI agent has already written. The generation-time rules shipped via `CLAUDE.md` / `AGENTS.md` tilt the model; this skill is the **opt-in second pass** that catches whatever the first pass missed.

## Invocation

| Shape | Behavior |
| --- | --- |
| `/style-review FILE` | Audit FILE against all 21 rules. Show per-rule scorecard. Ask the user: "produce a polished draft at FILE.reviewed.md?" On yes, write revised file and print diff. |
| `/style-review A.md B.md` | A/B compare. Emit per-rule delta. No polish, no ask. Used for benchmarking. |

Mode is inferred from argument count. No flags.

## Workflow (single file)

1. **Deterministic audit.** Shell out to `agent-style review --audit-only FILE`. Capture the canonical JSON. Mechanical rules (RULE-B, D, G, I, 12, 05, 06) and structural rules (RULE-A, C, E) return concrete violations with line numbers and excerpts.
2. **Semantic audit.** For each rule marked `status: "skipped"` with detector `semantic` (RULE-01, 03, 04, 08, 11, F, H), run a per-rule judgment using the rule's directive plus its BAD/GOOD examples from `.agent-style/RULES.md` as the judge prompt. Parse the host model's response into the same violation schema.
3. **Merge.** Combine deterministic + semantic rule results into the full scorecard.
4. **Report.** Print the scorecard: per rule, count + first 3 violations. If total is zero, report "no violations" and exit.
5. **Ask.** "Produce a polished draft at FILE.reviewed.md?" Wait for the user's yes/no.
6. **Polish (on yes).** Compose a revision prompt using `references/revision-prompt.md` + the violation list + `.agent-style/RULES.md`. Invoke the host model. Write the output to `FILE.reviewed.md`. Never touch `FILE`.
7. **Verify.** Shell out to `agent-style review --audit-only FILE.reviewed.md`. Show before → after scorecard.
8. **Diff.** Print `diff FILE FILE.reviewed.md` so the user can accept or discard hunks.

## Workflow (A/B compare)

1. Shell out to `agent-style review --mechanical-only --compare A.md B.md`.
2. Print the per-rule delta table from the JSON output.
3. Exit.

No ask, no polish, no file writes. This is the benchmark / regression-check shape.

## Polish invariants (hard)

The revision prompt enforces these in its template (see `references/revision-prompt.md`):

- **No new facts.** No metrics, numbers, citations, references, links, code behavior, or claims that are not already in the source. If a claim is flagged as unsupported (RULE-H), leave it flagged — do not invent support.
- **Preserve Markdown structure.** Code fences, tables, frontmatter, link syntax, heading levels, list nesting, and inline code spans are preserved exactly unless the violation IS the structure.
- **Preserve meaning.** Revisions only resolve flagged violations. Do not rewrite paragraphs the audit did not flag.
- **Write-beside only.** Output at `FILE.reviewed.md`. Never in-place.

## References

- [`references/rule-detectors.md`](references/rule-detectors.md): per-rule detection approach (mechanical regex + structural heuristics + semantic judge prompts).
- [`references/revision-prompt.md`](references/revision-prompt.md): the polish-pass template with hard invariants above.

## Self-verification

When asked "is style-review active?", reply on one line using this exact format:

`style-review active: audit 21 rules (deterministic: RULE-B, D, G, I, 12, 05, 06, A, C, E; semantic via host: RULE-01, 03, 04, 08, 11, F, H); workflow at skills/style-review/SKILL.md.`
