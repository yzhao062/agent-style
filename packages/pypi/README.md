<!-- SPDX-License-Identifier: MIT -->

# agent-style (PyPI)

CLI for *The Elements of Agent Style*: a literature-backed English technical-prose writing ruleset for AI agents.

Install:

```bash
pip install agent-style
```

Basic use:

```bash
agent-style list-tools                               # show supported tools
agent-style enable claude-code                       # wire up Claude Code
agent-style enable claude-code --dry-run --json      # preview in canonical JSON
agent-style disable claude-code                      # reverse
agent-style rules                                    # print bundled RULES.md
```

The CLI writes to `.agent-style/` in your project and safely adds a marker-wrapped reference to your existing instruction file (CLAUDE.md, AGENTS.md, .github/copilot-instructions.md, etc.). Existing content is preserved; writes are idempotent; `--dry-run` previews without changing any file.

Supported tools and install modes in v0.1.1:

| Tool | Install mode |
| --- | --- |
| claude-code | import-marker (writes `@.agent-style/claude-code.md` to your CLAUDE.md) |
| agents-md | append-block (writes a marker block to your AGENTS.md) |
| copilot | append-block (writes a marker block to `.github/copilot-instructions.md`) |
| copilot-path | owned-file (writes `.github/instructions/agent-style.instructions.md`) |
| cursor | owned-file (writes `.cursor/rules/agent-style.mdc`) |
| anthropic-skill | owned-file (writes `.claude/skills/agent-style/SKILL.md`) |
| codex | print-only (writes `.agent-style/codex-system-prompt.md`; stdout = prompt) |
| aider | multi-file-required (writes `.agent-style/aider-conventions.md`; stderr = `.aider.conf.yml` snippet) |

The full rule set lives in the canonical repository at https://github.com/yzhao062/agent-style. This PyPI package bundles `RULES.md`, `NOTICE.md`, the 8 primary adapters, and the `tools.json` registry; running `agent-style rules` prints the bundled `RULES.md` for quick review.

## License

- Code: MIT (`LICENSES/MIT.txt`).
- Bundled prose (`RULES.md`, `NOTICE.md`, adapters): CC BY 4.0 (`LICENSES/CC-BY-4.0.txt`).

Roadmap (v0.2.0+): `agent-style update` (pull refreshed adapters), `agent-style override <RULE> disable` (per-rule opt-out), `agent-style clean` (single-command uninstall), `.agent-style/config.toml` (project-level config).
