# SPDX-License-Identifier: CC-BY-4.0

# Revision-pass prompt template for style-review

Used when the user confirms "produce a polished draft at FILE.reviewed.md" in the `/style-review FILE` workflow. The skill composes this template with the audit's findings list and the bundled RULES.md, then invokes the host model.

## System prompt

You are revising a Markdown document in light of a list of writing-rule findings. A finding is a departure from a default for you to consider, not an error to drive to zero. Keep a departure that reads well, and judge the draft's overall pattern, such as varied sentence length and few semicolons. Two kinds of finding never count as a departure that reads well: a banned AI-tell word (RULE-06), which you replace, and a RULE-H unsupported claim, which you leave flagged without inventing support. You produce only the revised text, with no commentary. Honor the hard invariants below without exception.

### Hard invariants

1. **No new facts.** Never add metrics, numbers, citations, references, links, code behavior, or claims that are not already in the source. Do not add a connective (however, thus, because, then) that asserts a cause, contrast, or sequence the source does not state. If a claim is flagged as unsupported (RULE-H), leave it flagged. Do not invent support.
2. **Preserve Markdown structure.** Code fences, tables, frontmatter, link syntax, heading levels, list nesting, inline code spans, and footnotes are preserved exactly. Exception: if the finding is the structure itself (e.g., a RULE-A bullet-list flag on a genuine prose paragraph), convert the structure per the rule.
3. **Preserve meaning.** Revisions address only the listed findings. Leave alone the paragraphs the audit did not flag, keep the order of the sections, and condense prose no further than the flagged rule requires.
4. **Preserve length budget.** Revisions may shorten, but should not balloon the prose.

## User prompt (filled by the skill)

```
Source file: FILE
Source content:
---
{FILE_CONTENTS}
---

Findings reported by `agent-style review`:
{VIOLATIONS_LIST}
  # One per line, shape: "RULE-ID [severity] L:C  detail  ──  excerpt"

Applicable rules (directives + BAD/GOOD examples):
{RULES_MD_SUBSET_FOR_VIOLATED_RULES}
  # Pulled from .agent-style/RULES.md; only the rules that fired.

Task: revise the source where a finding in the list marks a real problem,
honoring the hard invariants from the system prompt. Keep a departure that
reads well, and judge the draft's overall pattern.
Return only the revised Markdown; no commentary, no before/after diff, no
rule recap.
```

## Assistant output contract

- Output is pure Markdown.
- Output preserves the source's frontmatter (if any) byte-for-byte.
- Output preserves the source's trailing newline convention.
- If the model judges that no revision is possible without violating the hard invariants, it outputs the source unchanged and a single comment-line header `<!-- style-review: no in-rule revision possible; see audit -->` at the top of the file.

## Post-processing by the skill

1. Write the model's output to `FILE.reviewed.md`.
2. Shell out to `agent-style review --audit-only FILE.reviewed.md` to re-audit.
3. Report before → after scorecard. Flag any finding that persists after revision, and leave the judgment to the user: a departure that reads well may stay, and a RULE-H unsupported claim cannot be fixed without adding facts.
4. Print `diff FILE FILE.reviewed.md` for user review.

## Why the prompt reads RULES.md from disk

The revision prompt embeds only the rules that fired (a subset of RULES.md), not the full 90 KB. This keeps the context compact and focuses the model on the specific directives the audit flagged. The full file remains on disk at `.agent-style/RULES.md` for the semantic-judgment step (a separate call per rule) and any follow-up audit.
