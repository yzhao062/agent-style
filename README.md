<!-- SPDX-License-Identifier: CC-BY-4.0 -->

# The Elements of Agent Style

**A small, literature-backed writing ruleset formatted for AI coding and writing agents to follow at generation time. Scoped to English technical prose.**

In scope: API documentation, engineering design docs, research papers, grant proposals, README / CHANGELOG, runbooks, commit messages, error messages, technical blog posts.

Out of scope: fiction, poetry, marketing copy, design writing, long-form narrative nonfiction, non-English prose, any context where rhythm or affect matter more than precision.

Named in homage to Strunk & White's *The Elements of Style* (1918/1959), one of the four canonical sources these rules distill from.

## Status

🚧 **Skeleton repo — Phase 1a.** Content is being written in Phase 1b. See the private plan (`agent-config/PLAN-elements-of-agent-style.md`) for the roadmap.

## Canonical sources

Rules distilled from:

1. Strunk, W., Jr., & White, E. B. (1959). *The Elements of Style* (revised from Strunk 1918).
2. Orwell, G. (1946). "Politics and the English Language." *Horizon*, April 1946.
3. Pinker, S. (2014). *The Sense of Style*. Viking.
4. Gopen, G. D., & Swan, J. A. (1990). "The Science of Scientific Writing." *American Scientist*, 78(6), pp. 550-558.

Rule format and phrasing informed by:

5. Zhang, X. et al. (2026). "Do Agent Rules Shape or Distort? Guardrails Beat Guidance in Coding Agents." arXiv:2604.11088.
6. Bohr, J. (2025). "Show and Tell: Prompt Strategies for Style Control in Multi-Turn LLM Code Generation." arXiv:2511.13972.

See [SOURCES.md](SOURCES.md) for details.

## The 12 rules (summary)

See [RULES.md](RULES.md) for the canonical full version with BAD/GOOD examples and enforcement tier per rule.

1. Do not assume the reader shares your tacit knowledge.
2. Do not use passive voice when the agent matters.
3. Do not use abstract or general language when a concrete, specific term exists.
4. Do not include needless words.
5. Do not use dying metaphors or prefabricated phrases.
6. Do not use avoidable jargon where an everyday English word exists.
7. Use affirmative form for affirmative claims ("trivial" instead of "not important").
8. Do not linguistically overstate or understate claims relative to the evidence.
9. Express coordinate ideas in similar form (parallel structure).
10. Keep related words together.
11. Place new or important information in the stress position at the end of the sentence.
12. Break long sentences; vary length (split sentences over 30 words).

**Escape hatch** (Orwell 1946 Rule 6): *"Break any of these rules rather than write something barbarous."* Rules are guides; clarity is the goal.

## Use

### Single-file pull

```bash
curl -sLO https://raw.githubusercontent.com/yzhao062/elements-of-agent-style/main/RULES.md
```

Paste into your agent's instruction file.

### Per-agent adapter

See [`agents/`](agents/) for ready-to-use adapter files scoped to specific agent ecosystems (Claude Code, Codex, GitHub Copilot, Cursor, Aider, Anthropic Skills, Replit, Windsurf, Ollama, Amazon Q, JetBrains AI Assistant, OpenCode, OpenAI Agents SDK, Continue, Tabnine). The [adapter matrix](adapter-matrix.md) lists every shipped file and its target location.

### Complementary tooling

This repo is **read at generation time**, not run as a linter. For Tier-2 linting over committed prose, see [ProseLint](https://github.com/amperser/proselint); rule-to-check mappings are in [`enforcement/proselint-map.md`](enforcement/proselint-map.md).

## Related work

Closest agent-facing peer: [`softaworks/agent-toolkit/writing-clearly-and-concisely`](https://tessl.io/registry/skills/github/softaworks/agent-toolkit/writing-clearly-and-concisely) — agent skill for prose. Different in scope (covers broader writing contexts) and framing (no explicit source citations or cross-agent adapter files).

## License

Dual license with file-level boundaries (see [`NOTICE.md`](NOTICE.md) for attribution snippet):

- **`RULES.md`, `SOURCES.md`, `examples/`, `agents/`**: CC BY 4.0 ([`LICENSES/CC-BY-4.0.txt`](LICENSES/CC-BY-4.0.txt))
- **`enforcement/`, `.github/workflows/`, generator scripts**: MIT ([`LICENSES/MIT.txt`](LICENSES/MIT.txt))

SPDX identifiers at the top of every file.

## Maintenance

Maintained by [Yue Zhao](https://yzhao062.github.io), USC CS faculty. Issues and PRs welcome.
