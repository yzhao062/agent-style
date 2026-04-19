<!-- SPDX-License-Identifier: CC-BY-4.0 -->

# Adapter Matrix

Every shipped adapter file in `agents/`, with its target path, auto-load behavior, and token-budget risk.

🚧 Phase 1a skeleton — adapter files are placeholders; Phase 2a populates them.

## Adapter files this repo ships

| Surface | Shipped file | Target path | Scope | Auto-loaded? | Token risk |
|---|---|---|---|---|---|
| AGENTS.md standard | `agents/AGENTS.md` | `<repo>/AGENTS.md` | repo | ✓ by AGENTS.md-compliant tools (see list below) | medium |
| Claude Code | `agents/claude-code.md` | `<repo>/CLAUDE.md` | repo | ✓ | medium |
| Anthropic Skills | `agents/anthropic-skill/SKILL.md` | `.claude/skills/elements-of-agent-style/SKILL.md` | per-skill | on invocation (progressive disclosure) | low |
| OpenAI Codex (API) | `agents/codex.md` | developer-supplied system prompt | session | manual | low-medium |
| OpenAI Agents SDK skill | `agents/openai-agents-sdk-skill.md` | skill directory within SDK | per-skill | on invocation | low |
| GitHub Copilot (repo-level) | `agents/copilot-instructions.md` | `.github/copilot-instructions.md` | repo | ✓ | low |
| GitHub Copilot (path-scoped) | `agents/copilot-path-instructions.md` | `.github/instructions/writing.instructions.md` | path | ✓ | low |
| Cursor | `agents/cursor-rule.mdc` | `.cursor/rules/writing.mdc` | repo | ✓ | low |
| Aider | `agents/aider-conventions.md` | `<repo>/CONVENTIONS.md` + `aider --read` or `.aider.conf.yml` | session | manual | low |
| Replit Skills | `agents/replit-skill/SKILL.md` | `.agents/skills/elements-of-agent-style/SKILL.md` | per-skill | on invocation | low |
| Replit | `agents/replit-md.md` | `<repo>/replit.md` | project | ✓ | medium |
| Windsurf (repo) | `agents/windsurf-rule.md` | `.windsurf/rules/writing.md` | repo | ✓ | low |
| Windsurf (global) | `agents/windsurf-rule.md` (same file) | `~/.codeium/windsurf/memories/global_rules.md` | global | ✓ | medium |
| Ollama | `agents/ollama-modelfile.md` | `Modelfile` `SYSTEM` section | per-model | ✓ on model load | medium-high |
| Amazon Q Developer | `agents/amazon-q-rule.md` | `.amazonq/rules/writing.rule.md` | repo | ✓ | low |
| JetBrains AI Assistant | `agents/jetbrains-ai-rule.md` | `.aiassistant/rules/writing.md` | repo | ✓ | low |
| OpenCode | `agents/opencode-skill/SKILL.md` | `.opencode/skills/elements-of-agent-style/SKILL.md` (also `.claude/skills`, `.agents/skills`) | per-skill | on invocation | low |
| Continue.dev | `agents/continue-rule.md` | `.continue/rules/writing.md` | repo | ✓ | low |
| Tabnine | `agents/tabnine-guideline.md` | `.tabnine/guidelines/writing.md` | repo | ✓ | low |

## Ecosystems covered via the shipped AGENTS.md adapter

These tools read the repo's root `AGENTS.md` (the same file `agents/AGENTS.md` ships) and do not require a separate adapter. List verified against `agents.md/` at plan Revision 4:

- **AGENTS.md-only consumers** (the root file is the only adapter needed): Codex, Jules, goose, opencode, Zed, Warp, VS Code, Devin, UiPath, Junie, Amp, RooCode, Gemini CLI, Kilo Code, Phoenix, Semgrep, Ona, Augment Code, OpenAI Agents SDK runtime.
- **Dual-path consumers** (read AGENTS.md AND have a first-class adapter file above): Aider, Cursor, GitHub Copilot, opencode, Windsurf. Use whichever path the user prefers.

When a new tool announces AGENTS.md support, it is covered automatically.

## Phase 2a scope

Populate each `agents/*.md` and `agents/*/SKILL.md` placeholder with the surface-appropriate compact ruleset or frontmatter metadata plus an include directive for `RULES.md` (or the compact inline body, for surfaces that do not support file inclusion). Verify each surface's loading behavior against current vendor docs.
