<!-- SPDX-License-Identifier: CC-BY-4.0 -->

# Agent-Style Usage Guide

This guide covers three topics not fully addressed in the README: running `agent-style` in CI, adding custom rules, and interpreting the violation output from `agent-style review`.

---

## Table of Contents

- [CI Integration](#ci-integration)
- [Adding Custom Rules](#adding-custom-rules)
- [Interpreting Violation Output](#interpreting-violation-output)

---

## CI Integration

`agent-style` runs in CI via two paths: the **review audit** (post-hoc, catches violations after generation) and **ProseLint** (post-hoc linter, catches a subset of mechanical violations on committed prose).

Both run as standard shell commands; any CI platform works.

### 1. Review Audit in CI

The `agent-style review --audit-only` command emits machine-readable JSON and exits non-zero when violations are found. Use this to gate PRs or fail builds.

```yaml
# .github/workflows/style-check.yml
name: agent-style review

on:
  pull_request:
    paths:
      - "**.md"          # only prose files
      - ".agent-style/"  # or if agent-style config changes

jobs:
  review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install agent-style
        run: pip install agent-style

      - name: Run agent-style review
        id: review
        run: |
          # Review all markdown files, fail on any violation
          # --audit-only: JSON output, no polish
          # Exit code 3 means violations found; treat as failure
          agent-style review . --audit-only --output-format=json || {
            exit_code=$?
            if [ $exit_code -eq 3 ]; then
              echo "agent-style violations found — see output above"
              exit 1
            fi
            # Re-throw unexpected errors
            exit $exit_code
          }
```

**Tip:** Add `--output-format=json` and parse the `summary.total` field if you want to threshold violations (e.g., fail only when `critical` > 0).

### 2. ProseLint in CI (Mechanical Subset)

For a faster, language-tool-based linter that catches filler phrases, clichés, jargon, and passive voice, run ProseLint in CI using the mapping in [`enforcement/proselint-map.md`](../enforcement/proselint-map.md).

```yaml
# .github/workflows/proselint.yml
name: ProseLint

on: [push, pull_request]

jobs:
  proselint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install ProseLint
        run: pip install proselint

      - name: Run ProseLint on markdown files
        run: |
          # Run on all markdown, stop on first error
          find . -name "*.md" -not -path "./.agent-style/*" | xargs proselint
```

**What ProseLint catches vs. what it misses:**

| Caught by ProseLint | Not caught (needs `style-review` skill) |
| --- | --- |
| RULE-04 filler phrases | RULE-01 curse-of-knowledge (semantic) |
| RULE-05 clichés/dying metaphors | RULE-03 vague/abstract language (semantic) |
| RULE-06 jargon | RULE-08 uncalibrated claims (semantic) |
| RULE-02 passive voice (via `misc.passive_voice`) | RULE-H unsupported claims (semantic) |
| RULE-12 long sentences | RULE-01 / RULE-03 context-dependent violations |

ProseLint is a fast subset gate; `agent-style review` with a skill host catches the full 21-rule set.

### 3. Pre-Commit Hook (Local CI)

For local pre-commit enforcement (before files are ever committed):

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: agent-style-review
        name: agent-style review
        entry: agent-style review --audit-only
        language: system
        files: \.md$
        pass_filenames: true
```

Install with: `pip install pre-commit && pre-commit install`

---

## Adding Custom Rules

Agent-style has two rule tracks: **canonical** (sourced from writing authorities) and **field-observed** (RULE-A through RULE-I, logged from LLM output). You can add your own field-observed rules following the same format.

### Adding a Field-Observed Rule (RULE-X)

**Step 1: Define the rule in `RULES.md`**

Add a new section following the existing RULE-A through RULE-I format. The required fields are:

```markdown
#### RULE-X: <Short Title>

- **source**: field-observed (your name or team, year range)
- **agent-instruction evidence**: <cite any relevant papers or internal studies>
- **severity**: critical | high | medium | low
- **scope**: `.md`, `.tex`, `.rst`, `.txt`, and prose sections of source files.
- **enforcement**: Tier-1 deny | Tier-2 | Tier-3 agent self-check | Tier-4 Codex review

##### Directive

<One to three sentences in command form — negative for anti-patterns,
positive for constructive rules. Use "Do not..." for violations,
"Do ..." for constructive rules.>

##### BAD → GOOD

<At least 5 BAD → GOOD examples. Include at least one non-paper context
(API docs, runbooks, proposals, release notes, postmortems, changelogs,
or issue reports). Each example should be a real pattern you have seen
in your LLM output.>

##### Rationale for AI Agent

<2-4 sentences explaining why this rule specifically matters for
LLM-generated prose. What training-signal or failure-mode does it address?>
```

**Step 2: Add the mechanical detector (if applicable)**

If the rule has a mechanical, regex-detectable pattern, add it to the appropriate detector in `packages/pypi/agent_style/review/primitive.py` or as a deny-phrase entry in `enforcement/deny-phrases.txt`.

For rules that need semantic judgment (like RULE-01, RULE-03), add the rule ID to the `semantic` list in the skill's `SKILL.md` workflow, so the style-review skill routes it to the host model.

**Step 3: Update the rule count in adapters**

Regenerate the compact adapter files to include the new rule:

```bash
python scripts/build-compact.py
```

**Step 4: Test the new rule**

```bash
# Mechanical-only test
agent-style review path/to/test-file.md --audit-only

# Full skill test (if semantic)
# Run inside Claude Code with style-review enabled:
/style-review path/to/test-file.md
```

### Disabling a Rule in a Project

To disable a specific rule locally without removing it from the shared ruleset:

There is no per-rule disable flag yet (planned for v1.1 per the roadmap). As a workaround:

1. **Soft enforcement:** Edit `.agent-style/RULES.md` and comment out or remove the rule's section before enabling.
2. **Skill:** You cannot currently override a rule for the skill; the skill always audits all 21 rules.

---

## Interpreting Violation Output

### JSON Output Format (`--audit-only`)

```bash
agent-style review path/to/file.md --audit-only
```

```json
{
  "file": "path/to/file.md",
  "summary": {
    "total": 6,
    "critical": 1,
    "high": 2,
    "medium": 3,
    "low": 0,
    "rules_triggered": ["RULE-01", "RULE-B", "RULE-H", "RULE-12"]
  },
  "violations": [
    {
      "rule": "RULE-H",
      "severity": "critical",
      "line": 14,
      "excerpt": "This approach is widely adopted in the industry.",
      "message": "Support factual claims with citation or concrete evidence; do not be handwavy.",
      "fix_required": "Add a citation or concrete evidence for the claim."
    },
    {
      "rule": "RULE-B",
      "severity": "high",
      "line": 22,
      "excerpt": "The service — which had been running for 3 weeks — crashed.",
      "message": "Do not use em or en dashes as casual sentence punctuation.",
      "fix_required": "Replace the em-dash sentence break with a period or semicolon."
    }
  ]
}
```

### Severity Levels

| Severity | Meaning | What to do |
| --- | --- | --- |
| **critical** | Reader cannot trust or understand the prose | Fix before merge |
| **high** | Visible AI-tell or recurring clarity failure | Fix before merge |
| **medium** | Local readability cost | Address in next polish pass |
| **low** | Polish / consistency | Nice to fix, not blocking |

**RULE-H (citation discipline)** and **RULE-01 (curse of knowledge)** are the two most likely to be critical in research and technical documentation contexts.

### Deterministic vs. Semantic Rules

When you run `agent-style review` from the CLI (no skill host), some rules return `status: "skipped"` because they need semantic judgment:

```json
{
  "rule": "RULE-01",
  "status": "skipped",
  "detector": "semantic",
  "reason": "Requires host model for context-aware judgment"
}
```

The style-review skill (`/style-review FILE` inside Claude Code) fills in these semantic rules by routing them to the host model. If you need the full 21-rule audit without a skill host, the mechanical subset (RULE-B, D, G, I, 12, 05, 06, A, C, E) is fully covered.

### Exit Codes

| Exit code | Meaning |
| --- | --- |
| 0 | No violations found |
| 1 | Internal error (file not found, parse error, etc.) |
| 2 | Usage error (bad flag, missing argument) |
| 3 | Violations found — see JSON output |

### Reading the Per-Rule Count

The scorecard emitted by `agent-style review FILE` shows counts per rule:

```
RULE-01 (curse of knowledge)     ██████████░░░░░░  10
RULE-B (em-dash punctuation)     ████░░░░░░░░░░░░   4
RULE-H (citation discipline)      ██░░░░░░░░░░░░░░   2
RULE-12 (long sentences)          ██░░░░░░░░░░░░░░   2
```

A high count on RULE-B or RULE-D almost always reflects a model that overuses dashes or transition openers by default. RULE-01 is typically the largest count in longer documents because every unexplained acronym or assumed prerequisite adds a tick.

### Comparing Two Drafts

```bash
agent-style review --compare baseline.md revised.md
```

This emits a per-rule delta table showing which rules improved, which got worse, and which are new:

```
Rule             | Baseline | Revised | Δ
-----------------|----------|---------|---
RULE-01          |    8     |    3    | -5
RULE-B           |    4     |    0    | -4
RULE-H           |    2     |    2    |  0
RULE-12          |    3     |    5    | +2   ← sentence splitting over-corrected
```

A `+N` delta on RULE-12 means the revision split sentences but may have over-split. Review those cases manually.
