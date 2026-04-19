<!-- SPDX-License-Identifier: CC-BY-4.0 -->

# Sources

Two buckets: writing authorities for prose content; agent-instruction evidence for rule format and phrasing.

## Bucket A — Writing authorities

1. **Strunk, W., Jr., & White, E. B. (1959).** *The Elements of Style* (revised from Strunk 1918). The Macmillan Company. Especially Part II, "Elementary Principles of Composition" (§§12-22). ~100 pp.
2. **Orwell, G. (1946).** "Politics and the English Language." *Horizon*, April 1946. Six operational rules at the end of the essay, plus the analytical framework for detecting dead metaphors and jargon. ~15 pp. Public domain; freely available online.
3. **Pinker, S. (2014).** *The Sense of Style: The Thinking Person's Guide to Writing in the 21st Century*. Viking. ISBN 978-0670025855. Especially Ch. 2 ("A Window Onto the World" — classic style), Ch. 3 ("The Curse of Knowledge"), and Ch. 6 ("Telling Right from Wrong" — calibrated vs weasel claims). ~300 pp.
4. **Gopen, G. D., & Swan, J. A. (1990).** "The Science of Scientific Writing." *American Scientist*, 78(6), pp. 550-558. Topic position, stress position, old-new progression, verb-subject proximity. ~9 pp.

Combined reading load: one weekend.

## Bucket B — Agent-instruction evidence

Informs the *format and phrasing* of rules for AI-agent consumption at generation time. Empirical evidence, not authoritative style guidance.

5. **Zhang, X., Wang, G., Cui, Y., Qiu, W., Li, Z., Zhu, B., & He, P. (2026).** "Do Agent Rules Shape or Distort? Guardrails Beat Guidance in Coding Agents." arXiv:2604.11088. 679 instruction files (CLAUDE.md, .cursorrules, etc.), 25,532 rules, 5,000+ SWE-bench Verified evaluations. Key finding: negative constraints are the only individually beneficial rule type in coding-agent settings; broad positive directives hurt when given without examples.
6. **Bohr, J. (2025).** "Show and Tell: Prompt Strategies for Style Control in Multi-Turn LLM Code Generation." arXiv:2511.13972. Compares instruction-only, example-only, and combined prompts (N=160 paired programs). Key finding: combined prompts (directive + examples) give the best initial compression plus the strongest expansion discipline in subsequent turns.

## Bucket C — Maintainer field observation

Informs the 9 field-observed rules (RULE-A through RULE-I) in `RULES.md`. Not a cited writing authority. Patterns were logged across the maintainer's research papers, grant proposals, technical documentation, and agent-configuration work from 2022 to 2026; each named rule required the pattern to appear across distinct projects at a frequency high enough to warrant a rule rather than a one-off edit.

Field-observed rules are labeled transparently in `RULES.md` (`source: Maintainer observation ...`) and do not carry the citation weight of the 12 canonical rules. They sit alongside the canonical rules as peer input to the agent because the maintainer's own editing experience has real signal, even though the evidentiary standard differs. The README states this explicitly.

## Design implications drawn from Bucket B

- **Mixed phrasing**: negative for anti-pattern rules and broad prohibitions; positive for constructive placement, structure, or rhythm rules.
- **Always pair with BAD/GOOD examples** — no rule ships as directive-only.
- **Expect context-priming effect**, not just literal-instruction parsing. Keep the total ruleset compact.

## Related tools (not cited as sources)

- **ProseLint** — Python linter that cites many of the same authorities. Complementary (post-hoc check after generation-time compliance). See `enforcement/proselint-map.md`.
- **Google Developer Documentation Style Guide**, **Microsoft Writing Style Guide** — comprehensive human-oriented tech writing style guides; useful reference but broader scope than this project.
