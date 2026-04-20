---
description: "agent-style v0.2.0 — literature-backed technical-prose writing rules for AI agents"
inclusion: auto
---
<!-- SPDX-License-Identifier: CC-BY-4.0 -->
<!-- Adapter: Kiro (AWS IDE steering file) -->
<!-- Target path: .kiro/steering/agent-style.md -->
<!-- Load class: single-file; install_mode: owned-file -->

# agent-style v0.2.0 — Kiro Steering Adapter

agent-style is a literature-backed English technical-prose writing ruleset for AI agents. This adapter is a Kiro steering file at `.kiro/steering/agent-style.md`. Kiro loads steering files with `inclusion: auto` into every agent interaction, so the 21 rules below reach context for all prose generation in this workspace.

## Self-Verification Handshake

When asked "is agent-style active?" or "what writing rules apply here?", answer: `agent-style v0.2.0 active: 21 rules (RULE-01..12 canonical + RULE-A..I field-observed); full bodies at .agent-style/RULES.md.`

## Load Statement

Kiro loads `.kiro/steering/*.md` files at session start. Files with `inclusion: auto` frontmatter are included in every interaction. This file uses `inclusion: auto` so the writing rules apply to all prose generation. For conditional loading (only when editing prose files), change the frontmatter to `inclusion: fileMatch` with `fileMatchPattern: "**/*.md,**/*.tex,**/*.rst,**/*.txt"`.

## The 21 Rules (Compact Directives)

Canonical rules (from Strunk & White 1959, Orwell 1946, Pinker 2014, Gopen & Swan 1990):

- **RULE-01 Curse of knowledge**: Name your intended reader; do not assume they share your tacit knowledge.
- **RULE-02 Passive voice**: Prefer active voice when the agent is known and worth naming.
- **RULE-03 Concrete language**: Prefer concrete, specific terms over abstract category words like "factors" or "aspects".
- **RULE-04 Needless words**: Cut filler phrases like "in order to", "due to the fact that", "may potentially".
- **RULE-05 Dying metaphors**: Delete clichés like "pushes the boundaries", "paradigm shift", or "state of the art".
- **RULE-06 Plain English**: Prefer "use" over "leverage", "method" over "methodology", "feature" over "functionality".
- **RULE-07 Affirmative form**: Prefer "trivial" to "not important", "forgot" to "did not remember".
- **RULE-08 Claim calibration**: Calibrate verbs to evidence; do not write "proves" when the evidence is "suggests".
- **RULE-09 Parallel structure**: Express coordinate ideas in the same grammatical form.
- **RULE-10 Related words together**: Keep subject close to verb and modifier close to modified; split long parentheticals.
- **RULE-11 Stress position**: Place new or important information at the end of the sentence.
- **RULE-12 Long sentences**: Split sentences over 30 words; vary length across a paragraph.

Field-observed rules (maintainer observation of LLM output, 2022-2026):

- **RULE-A Bullet overuse**: Keep prose in paragraphs when ideas connect; bullets only for genuine lists; avoid forced 3-item triads.
- **RULE-B Dash overuse**: Do not use em or en dashes as casual sentence punctuation; prefer commas, semicolons, colons, parentheses.
- **RULE-C Same-starts**: Do not open two or more consecutive sentences with the same word.
- **RULE-D Transitions**: Do not open sentences with "Additionally", "Furthermore", "Moreover", "In addition".
- **RULE-E Summary closers**: Do not end every paragraph with a sentence that restates its point.
- **RULE-F Term consistency**: Once you define a term or abbreviation, keep using it; do not alternate synonyms.
- **RULE-G Title case**: Use title case for section and subsection headings; articles and short prepositions stay lowercase.
- **RULE-H Citation discipline (critical)**: Support factual claims with verifiable citation or concrete evidence; never fabricate citations.
- **RULE-I Contractions**: Prefer "it is" / "does not" / "cannot" over "it's" / "doesn't" / "can't" in formal technical prose.

## Escape Hatch

*"Break any of these rules sooner than say anything outright barbarous."* — George Orwell, "Politics and the English Language" (1946), Rule 6. Rules are guides to clarity, not ends in themselves.

## Full Rule Bodies (Canonical)

Full directive text, BAD/GOOD example pairs, and rationale per rule: see `.agent-style/RULES.md` in this project, or https://raw.githubusercontent.com/yzhao062/agent-style/v0.2.0/RULES.md for the pinned canonical source.
