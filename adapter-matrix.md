<!-- SPDX-License-Identifier: CC-BY-4.0 -->

# Adapter Matrix

Every shipped adapter file in `agents/`, with its target path, install mode, and load class. v0.3.5 ships 9 primary adapters plus the `style-review` skill; 10 additional tool surfaces are on the v1.1 "Planned adapters" roadmap.

## Primary Adapters (v0.3.5, Shipped)

| Surface | Shipped file | Target path | install_mode | Load class |
| --- | --- | --- | --- | --- |
| AGENTS.md standard | `agents/AGENTS.md` | `<repo>/AGENTS.md` | `append-block` | single-file |
| Claude Code | `agents/claude-code.md` | `<repo>/CLAUDE.md` (`@.agent-style/claude-code.md` import) | `import-marker` | import-capable |
| Anthropic Skills | `agents/anthropic-skill/SKILL.md` | `.claude/skills/agent-style/SKILL.md` | `owned-file` | single-file |
| OpenAI Codex (API) | `agents/codex.md` | `.agent-style/codex-system-prompt.md` (user pastes into API system prompt) | `print-only` | single-file |
| GitHub Copilot (repo-wide) | `agents/copilot-instructions.md` | `.github/copilot-instructions.md` | `append-block` | single-file |
| GitHub Copilot (path-scoped) | `agents/copilot-path-instructions.md` | `.github/instructions/agent-style.instructions.md` | `owned-file` | single-file |
| Cursor | `agents/cursor-rule.mdc` | `.cursor/rules/agent-style.mdc` | `owned-file` | single-file |
| Aider | `agents/aider-conventions.md` | `.agent-style/aider-conventions.md` + `.aider.conf.yml` snippet | `multi-file-required` | multi-file-required |
| Kiro (AWS IDE) | `agents/kiro-steering.md` | `.kiro/steering/agent-style.md` | `owned-file` | single-file |

**Install**: run `agent-style enable <tool>` (creates `.agent-style/RULES.md`, copies the adapter, safe-appends or writes the target file), or follow the manual `curl` recipe in `README.md` for equivalent manual steps. Both paths never overwrite existing user content.

## Ecosystems Covered via the AGENTS.md Adapter

These tools read the repository root `AGENTS.md` (the same file `agents/AGENTS.md` ships) and do not require a separate adapter:

- **AGENTS.md-only consumers**: Codex, Jules, goose, Zed, Warp, VS Code, Devin, UiPath, Junie, Amp, RooCode, Gemini CLI, Kilo Code, Phoenix, Semgrep, Ona, Augment Code, OpenAI Agents SDK runtime.
- **Dual-path consumers** (read AGENTS.md AND have a first-class adapter in the Primary table above): Aider, Cursor, GitHub Copilot, opencode, Windsurf. Users pick whichever path fits the project.

When a new tool announces AGENTS.md support, it is covered automatically.

## Planned Adapters (v1.1, Open to Contributions)

These surfaces are on the roadmap for v1.1. Users of these tools can load the canonical `.agent-style/RULES.md` into their tool's instruction file manually today; a shipped adapter file would offer the same CLI-primary install path as the primary adapters above.

| Surface | Target path (proposed) | Load class (planned) |
| --- | --- | --- |
| Amazon Q Developer | `.amazonq/rules/agent-style.rule.md` | single-file |
| JetBrains AI Assistant | `.aiassistant/rules/agent-style.md` | single-file |
| Windsurf (repo) | `.windsurf/rules/agent-style.md` | single-file |
| Windsurf (global) | `~/.codeium/windsurf/memories/global_rules.md` | single-file |
| Ollama | `Modelfile` `SYSTEM` section | single-file |
| Replit (project) | `replit.md` | single-file |
| Replit Skills | `.agents/skills/agent-style/SKILL.md` | single-file |
| OpenCode | `.opencode/skills/agent-style/SKILL.md` | single-file |
| Continue.dev | `.continue/rules/agent-style.md` | single-file |
| Tabnine | `.tabnine/guidelines/agent-style.md` | single-file |
| OpenAI Agents SDK skill | skill directory within SDK | single-file |

Contributions welcome. A new adapter must meet the 5-point contract (versioned self-verification handshake, compact rule directives, surface-specific load statement, pointer or import for canonical full bodies, escape hatch line) and ship alongside a per-tool `tools.json` entry so the CLI can dispatch `enable`/`disable` for it.
