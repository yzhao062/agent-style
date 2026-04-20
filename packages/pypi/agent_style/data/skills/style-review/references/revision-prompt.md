# SPDX-License-Identifier: CC-BY-4.0

# Revision-pass prompt template for style-review

Used when the user confirms "produce a polished draft at FILE.reviewed.md" in the `/style-review FILE` workflow. The skill composes this template with the audit's violation list and the bundled RULES.md, then invokes the host model.

## System prompt

You are revising a Markdown document to resolve a specific list of writing-rule violations. You produce only the revised text; you make no commentary. You honor the hard invariants below without exception.

### Hard invariants

1. **No new facts.** Do not add metrics, numbers, citations, references, links, code behavior, or claims that are not already in the source. If a claim is flagged as unsupported (RULE-H), leave it flagged — do not invent support.
2. **Preserve Markdown structure.** Code fences, tables, frontmatter, link syntax, heading levels, list nesting, inline code spans, and footnotes are preserved exactly. Exception: if the violation is the structure itself (e.g., a RULE-A bullet-list flag on a genuine prose paragraph), convert the structure per the rule.
3. **Preserve meaning.** Revisions resolve only the listed violations. Do not rewrite paragraphs the audit did not flag. Do not reorder sections. Do not condense prose beyond what the flagged rule requires.
4. **Preserve length budget.** Revisions may shorten, but should not balloon the prose.

## User prompt (filled by the skill)

```
Source file: FILE
Source content:
---
{FILE_CONTENTS}
---

Violations reported by `agent-style review`:
{VIOLATIONS_LIST}
  # One per line, shape: "RULE-ID [severity] L:C  detail  ──  excerpt"

Applicable rules (directives + BAD/GOOD examples):
{RULES_MD_SUBSET_FOR_VIOLATED_RULES}
  # Pulled from .agent-style/RULES.md; only the rules that fired.

Task: revise the source to resolve every violation in the list, honoring the
hard invariants from the system prompt. Return only the revised Markdown; no
commentary, no before/after diff, no rule recap.
```

## Assistant output contract

- Output is pure Markdown.
- Output preserves the source's frontmatter (if any) byte-for-byte.
- Output preserves the source's trailing newline convention.
- If the model judges that no revision is possible without violating the hard invariants, it outputs the source unchanged and a single comment-line header `<!-- style-review: no in-rule revision possible; see audit -->` at the top of the file.

## Post-processing by the skill

1. Write the model's output to `FILE.reviewed.md`.
2. Shell out to `agent-style review --audit-only FILE.reviewed.md` to re-audit.
3. Report before → after scorecard. Flag any violation that persists after revision (rare; usually RULE-H unsupported claims that cannot be fixed without adding facts).
4. Print `diff FILE FILE.reviewed.md` for user review.

## Why the prompt reads RULES.md from disk

The revision prompt embeds only the rules that fired (a subset of RULES.md), not the full 90 KB. This keeps the context compact and focuses the model on the specific directives the audit flagged. The full file remains on disk at `.agent-style/RULES.md` for the semantic-judgment step (a separate call per rule) and any follow-up audit.
