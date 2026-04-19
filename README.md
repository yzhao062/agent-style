<!-- SPDX-License-Identifier: CC-BY-4.0 -->

<a id="readme-top"></a>

<div align="center">

# The Elements of Agent Style

**A literature-backed English writing ruleset formatted for AI agents to follow at generation time. Scoped to technical prose.**

[![License](https://img.shields.io/badge/license-CC%20BY%204.0%20%2B%20MIT-blue.svg)](NOTICE.md)
[![CI](https://github.com/yzhao062/agent-style/actions/workflows/validate.yml/badge.svg)](https://github.com/yzhao062/agent-style/actions/workflows/validate.yml)
[![GitHub stars](https://img.shields.io/github/stars/yzhao062/agent-style?style=social&cacheSeconds=300)](https://github.com/yzhao062/agent-style)

[Use](#use) &nbsp;·&nbsp;
[Rules](#the-12-rules) &nbsp;·&nbsp;
[Sources](#canonical-sources) &nbsp;·&nbsp;
[Related](#related)

</div>

> [!NOTE]
> **Skeleton phase.** Phase 1a has shipped: repo skeleton, 18 adapter placeholders across 13 instruction surfaces, dual-license SPDX boundaries, and CI. Phase 1b fills the 12 rule bodies with directive, BAD/GOOD examples, and citations verified page-by-page. Watch for the first tagged release.

## What it is

A small, curated set of English writing rules formatted for AI coding and writing agents to follow **at generation time** — not as a post-hoc linter. Scoped to technical prose: API documentation, engineering design docs, research papers, grant proposals, READMEs, runbooks, commit messages, error messages, technical blog posts.

Out of scope: fiction, poetry, marketing copy, design writing, long-form narrative nonfiction, non-English prose, any context where rhythm or affect matter more than precision.

Named in homage to Strunk & White's *The Elements of Style* (1918/1959), one of the four canonical sources these rules distill from.

## Who it is for

- **AI coding and writing agents** — Claude Code, Codex, GitHub Copilot, Cursor, Aider, Anthropic Skills, Replit Agent, Windsurf, Amazon Q Developer, JetBrains AI Assistant, Ollama, Continue.dev, Tabnine, OpenCode, OpenAI Agents SDK skills, and any `AGENTS.md`-compliant tool. Each agent reads the ruleset as part of its system prompt or project config.
- **Maintainers of those agents' configurations** who want generated prose to follow literature-backed technical-writing conventions rather than reproduce common LLM tell-patterns.

## Use

### Single-file pull

```bash
curl -sLO https://raw.githubusercontent.com/yzhao062/agent-style/main/RULES.md
```

Paste into the instruction file your agent loads.

### Per-agent adapter

Drop the adapter file for your tool into the expected path. The adapters are thin wrappers with surface-appropriate frontmatter or metadata; the rules themselves live in `RULES.md`.

<details>
<summary><b>Common surfaces (full list in <code>adapter-matrix.md</code>)</b></summary>

| Surface | Target path | Auto-loaded |
| --- | --- | --- |
| Claude Code | `CLAUDE.md` at repo root | yes |
| Anthropic Skills | `.claude/skills/agent-style/SKILL.md` | on invocation |
| GitHub Copilot (repo) | `.github/copilot-instructions.md` | yes |
| GitHub Copilot (path) | `.github/instructions/writing.instructions.md` | yes, path-scoped |
| Cursor | `.cursor/rules/writing.mdc` | yes |
| Aider | `CONVENTIONS.md` + `aider --read CONVENTIONS.md` | explicit |
| Amazon Q Developer | `.amazonq/rules/writing.rule.md` | yes |
| JetBrains AI Assistant | `.aiassistant/rules/writing.md` | yes |
| Windsurf (repo / global) | `.windsurf/rules/writing.md` or `global_rules.md` | yes |
| Ollama | `Modelfile` `SYSTEM` section | on model load |
| Replit | `replit.md` or `.agents/skills/<name>/SKILL.md` | yes / on invocation |
| OpenCode | `.opencode/skills/<name>/SKILL.md` | on invocation |
| Continue.dev | `.continue/rules/writing.md` | yes |
| Tabnine | `.tabnine/guidelines/writing.md` | yes |
| AGENTS.md standard (Codex, Jules, Zed, Warp, Gemini CLI, VS Code, and 17+ others) | `AGENTS.md` at repo root | yes |

</details>

### Complementary post-hoc linting

This repo is read at generation time. For a linter that runs over committed prose in CI, see [ProseLint](https://github.com/amperser/proselint) — per-rule check-ID mappings are in [`enforcement/proselint-map.md`](enforcement/proselint-map.md). Vale users can plug ProseLint via its existing style-pack ecosystem.

## The 12 rules

| # | Rule | Primary source |
|---|------|----------------|
| 01 | Do not assume the reader shares your tacit knowledge | Pinker 2014, Ch. 3 |
| 02 | Do not use passive voice when the agent matters | Orwell 1946 Rule 3; S&W §II.14 |
| 03 | Do not use abstract or general language when a concrete, specific term exists | S&W §II.16; Pinker 2014 Ch. 3 |
| 04 | Do not include needless words | S&W §II.17; Orwell 1946 Rule 3 |
| 05 | Do not use dying metaphors or prefabricated phrases | Orwell 1946 Rule 1 |
| 06 | Do not use avoidable jargon where an everyday English word exists | Orwell 1946 Rule 5; Pinker 2014 Ch. 2 |
| 07 | Use affirmative form for affirmative claims | S&W §II.15 |
| 08 | Do not linguistically overstate or understate claims relative to the evidence | Pinker 2014 Ch. 6; Gopen & Swan 1990 |
| 09 | Express coordinate ideas in similar form (parallel structure) | S&W §II.19 |
| 10 | Keep related words together | S&W §II.20; Gopen & Swan 1990 |
| 11 | Place new or important information in the stress position at the end of the sentence | Gopen & Swan 1990 |
| 12 | Break long sentences; vary length (split sentences over 30 words) | S&W §II.18; Pinker 2014 Ch. 4 |

**Escape hatch** (Orwell 1946 Rule 6): *"Break any of these rules sooner than say anything outright barbarous."* Rules are guides to clarity, not ends in themselves.

See [`RULES.md`](RULES.md) for the canonical full version with BAD/GOOD examples, enforcement tier, and rationale per rule.

## Canonical sources

Four writing authorities for prose content, plus two recent empirical papers for rule format and phrasing. Every one of the 12 rules cites its source explicitly; **each citation is verified page-by-page by the maintainer against the original work, not scraped or summarized from search results.** When the final text disagrees with an authority, the disagreement is stated in the rule's rationale.

### Writing authorities (prose content)

1. **Strunk, W., Jr., & White, E. B. (1959).** *The Elements of Style* (revised from Strunk 1918). The Macmillan Company. Especially Part II, "Elementary Principles of Composition" (§§12-22).
2. **Orwell, G. (1946).** "Politics and the English Language." *Horizon*, April 1946. Public domain; freely available online.
3. **Pinker, S. (2014).** *The Sense of Style: The Thinking Person's Guide to Writing in the 21st Century*. Viking. Especially Ch. 2 (classic style), Ch. 3 (curse of knowledge), Ch. 6 (calibrated claims).
4. **Gopen, G. D., & Swan, J. A. (1990).** "The Science of Scientific Writing." *American Scientist*, 78(6), pp. 550-558.

### Agent-instruction evidence (rule format and phrasing)

5. **Zhang, X. et al. (2026).** "Do Agent Rules Shape or Distort? Guardrails Beat Guidance in Coding Agents." arXiv:2604.11088. 25,532 rules across 679 instruction files; motivates negative-constraint phrasing for anti-pattern rules.
6. **Bohr, J. (2025).** "Show and Tell: Prompt Strategies for Style Control in Multi-Turn LLM Code Generation." arXiv:2511.13972. Motivates the directive + BAD/GOOD example format used throughout `RULES.md`.

See [`SOURCES.md`](SOURCES.md) for the full bibliography and recommended reading ranges per source.

## Curation and method

The 12 rules are not a generated digest of the four source works. The maintainer read each source, extracted the rules most applicable to English technical prose, filtered for AI-agent failure modes observed in practice, and phrased each rule using the negative-versus-positive split that Zhang et al. 2026 found empirically effective for coding-agent instructions. Rules that could be supported only by Bucket A but not mapped to a concrete AI-R&D failure mode are excluded. Rules that felt necessary from practice but had no Bucket A source are excluded. The intersection is what this repo ships.

New contributions are welcome on the same standard: a rule must cite a source from Bucket A or B, include BAD/GOOD examples drawn from real technical-prose output, and include a rationale for why the rule matters specifically for AI-agent-generated prose.

## Related

- **[`anywhere-agents`](https://github.com/yzhao062/anywhere-agents)** ([![PyPI](https://img.shields.io/pypi/v/anywhere-agents?color=blue&label=PyPI)](https://pypi.org/project/anywhere-agents/) [![npm](https://img.shields.io/npm/v/anywhere-agents?color=blue&label=npm)](https://www.npmjs.com/package/anywhere-agents)) — broader AI-agent configuration system by the same maintainer: bootstrap scripts, `PreToolUse` guard hook, four shipped skills (`implement-review`, `my-router`, `ci-mockup-figure`, `readme-polish`), and session protocol. `anywhere-agents` will cite this repo as its canonical writing ruleset in a future release, replacing its built-in banned-word list.
- **[`softaworks/agent-toolkit/writing-clearly-and-concisely`](https://tessl.io/registry/skills/github/softaworks/agent-toolkit/writing-clearly-and-concisely)** — closest agent-facing peer. Prose-writing skill covering documentation, commit messages, error messages, UI copy, reports. Differs in scope (broader writing contexts) and format (no explicit per-rule citations or cross-agent adapters).
- **[ProseLint](https://github.com/amperser/proselint)** — Python linter citing an overlapping authority set (Strunk, Orwell, Pinker, Garner, Butterick). Complementary; use as post-hoc CI check against the same rules.
- **[Vale](https://github.com/errata-ai/vale)** — prose-linter framework with pluggable style packs (Microsoft, Google, proselint, alex).
- **[Google Developer Documentation Style Guide](https://developers.google.com/style)** / **[Microsoft Writing Style Guide](https://learn.microsoft.com/en-us/style-guide/welcome/)** — comprehensive human-facing tech-writing style guides; broader scope, not formatted for agent consumption.

## License

Dual license with file-level SPDX boundaries:

| Content | License |
| --- | --- |
| `RULES.md`, `SOURCES.md`, `NOTICE.md`, `examples/`, `agents/`, `adapter-matrix.md` | [CC BY 4.0](LICENSES/CC-BY-4.0.txt) |
| `enforcement/`, `.github/workflows/`, generator scripts | [MIT](LICENSES/MIT.txt) |

Every source file carries an SPDX-License-Identifier header. See [`NOTICE.md`](NOTICE.md) for the attribution snippet consumers should retain on reuse.

## Maintenance

Maintained by [Yue Zhao](https://yzhao062.github.io), USC CS faculty and author of [PyOD](https://github.com/yzhao062/pyod). Issues and pull requests welcome; contributions that add a new rule must cite a source from Bucket A or B. See [`CHANGELOG.md`](CHANGELOG.md) for release history and upcoming work.

<div align="center">

<a href="#readme-top">↑ back to top</a>

</div>
