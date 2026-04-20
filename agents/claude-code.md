<!-- SPDX-License-Identifier: CC-BY-4.0 -->
<!-- Adapter: Claude Code (CLAUDE.md) -->
<!-- Target path: <repo root>/CLAUDE.md, or referenced via @.agent-style/claude-code.md -->
<!-- Load class: import-capable; install_mode: import-marker -->

# agent-style v0.2.0 — Claude Code adapter

agent-style is a literature-backed English technical-prose writing ruleset for AI agents. This adapter is import-capable: Claude Code resolves `@.agent-style/RULES.md` at launch and loads the 21 full rule bodies into the active context. This file carries only the handshake, load statement, rule-name index, and escape hatch; the full rule text is expected to be imported.

## Self-Verification Handshake

When asked "is agent-style active?" or "what writing rules apply here?", answer: `agent-style v0.2.0 active: 21 rules (RULE-01..12 canonical + RULE-A..I field-observed); full bodies at .agent-style/RULES.md.`

## Load Statement

Full rule bodies are imported from `.agent-style/RULES.md` via the Claude Code `@path` directive. If that file is missing (the user ran the manual curl without the import line, or has not run `agent-style enable claude-code`), only the rule-name index below has reached context; the full directive text, BAD/GOOD examples, and rationale have not.

## The 21 Rules (Names; Full Bodies via Import)

Canonical (Strunk & White 1959, Orwell 1946, Pinker 2014, Gopen & Swan 1990):

- RULE-01: Curse of knowledge.
- RULE-02: Passive voice.
- RULE-03: Abstract vs concrete language.
- RULE-04: Needless words.
- RULE-05: Dying metaphors.
- RULE-06: Avoidable jargon.
- RULE-07: Affirmative form.
- RULE-08: Claim calibration.
- RULE-09: Parallel structure.
- RULE-10: Related words together.
- RULE-11: Stress position.
- RULE-12: Long sentences, varied length.

Field-observed (maintainer observation of LLM output, 2022-2026):

- RULE-A: Bullet-point overuse.
- RULE-B: Em and en dashes as casual punctuation.
- RULE-C: Consecutive same-starts.
- RULE-D: Transition-word overuse.
- RULE-E: Paragraph-closing summary sentences.
- RULE-F: Inconsistent terms / abbreviation redefinition.
- RULE-G: Sentence-case section headings.
- **RULE-H: Handwavy claims and fabricated citations (critical).**
- RULE-I: Contractions in formal technical prose.

## Escape Hatch

*"Break any of these rules sooner than say anything outright barbarous."* — George Orwell, "Politics and the English Language" (1946), Rule 6. Rules are guides to clarity, not ends in themselves.

## Full Rule Bodies (Canonical)

- Imported: `@.agent-style/RULES.md`
- Pinned upstream: https://raw.githubusercontent.com/yzhao062/agent-style/v0.2.0/RULES.md
