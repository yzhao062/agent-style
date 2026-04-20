<!-- SPDX-License-Identifier: MIT -->

# agent-style (npm)

CLI for *The Elements of Agent Style*: a literature-backed English technical-prose writing ruleset for AI agents.

Install:

```bash
npm install -g agent-style
# or run without installing:
npx --yes agent-style@0.2.0 <subcommand>
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

Programmatic use from Node:

```js
const agentStyle = require('agent-style');
console.log(agentStyle.version);                       // 0.2.0
console.log(agentStyle.listTools());
agentStyle.enable('claude-code', { dryRun: true });
```

Supported tools and install modes in v0.2.0:

| Tool | Install mode |
| --- | --- |
| claude-code | import-marker |
| agents-md | append-block |
| copilot | append-block |
| copilot-path | owned-file |
| cursor | owned-file |
| anthropic-skill | owned-file |
| codex | print-only |
| aider | multi-file-required |
| kiro | owned-file |

Canonical repository: https://github.com/yzhao062/agent-style

## License

- Code: MIT (`LICENSES/MIT.txt`).
- Bundled prose (`RULES.md`, `NOTICE.md`, adapters): CC BY 4.0 (`LICENSES/CC-BY-4.0.txt`).

Roadmap (v0.2.0+): `agent-style update`, `agent-style override`, `agent-style clean`, and project-level config.
