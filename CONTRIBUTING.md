<!-- SPDX-License-Identifier: CC-BY-4.0 -->

# Contributing to agent-style

Thank you for contributing. This guide covers the two most common contribution types: **adding or modifying rules** and **opening pull requests**.

---

## How to Add a Rule

### 1. Propose the rule with evidence

Before writing code, open a GitHub Discussion describing:

- The failure mode in AI-generated prose (with before/after examples)
- Whether it is a chronic AI-tell (field-observed) or a violation of a classical writing principle (canonical)
- The proposed directive (one sentence, negative for anti-patterns, positive for constructive rules)
- The proposed scope (file types and document kinds where the rule applies)

Rule proposals with at least 5 real before/after examples (from bench drafts or production output) are prioritized.

### 2. Name the rule

Follow the naming conventions below. Get the next ID from the current RULES.md:

- **Canonical rules** — `RULE-01` through `RULE-12` + full name. These cite classical writing authorities (Strunk & White, Orwell, Pinker, Gopen & Swan). Do not reuse a canonical ID.
- **Field-observed rules** — `RULE-A` through `RULE-I` + full name. These capture LLM-specific failure modes observed in AI output. The letter sequence is reserved for field-observed rules that are confirmed in production bench data. Do not use letters outside this range.

**Rule full names** use Title Case and follow the pattern: *"Do Not [anti-pattern]"* or *"Do [positive behavior]."* Keep names under 70 characters.

### 3. Add the rule to RULES.md

Each rule entry in RULES.md must include:

```markdown
#### RULE-XX: Full Name

- **source**: Author Year, Chapter or Section or Essay Rule
- **agent-instruction evidence**: Citation that supports negative phrasing + example pairing (Zhang et al. 2026, Bohr 2025)
- **severity**: critical | high | medium | low
- **scope**: file extensions and document kinds
- **enforcement**: Tier-1 through Tier-4 (see Enforcement below)

##### Directive

One command-form sentence. Negative for anti-patterns ("Do not..."), positive for constructive rules.

##### BAD → GOOD

At least 5 examples covering at least 3 document types (e.g., API docs, runbooks, research papers, release notes, postmortems, proposals, issue reports). Each BAD → GOOD pair must show the same content rewritten per the rule.

##### Rationale for AI Agent

One paragraph explaining why the rule specifically matters for LLM-generated prose, not just human writing.
```

**Severity rubric:**

| Level | Meaning |
| --- | --- |
| critical | Reader cannot understand or trust the prose if violated |
| high | Recurring AI-tell or clarity failure that breaks skim-reading |
| medium | Local readability cost, felt but not trust-breaking |
| low | Polish; flagged for consistency rather than comprehension |

**Enforcement tiers:**

| Tier | Mechanism | When used |
| --- | --- | --- |
| 1 | Tier-1 deny (regex or simple pattern match) | High-precision anti-patterns only |
| 2 | Tier-2 external linter (LanguageTool PASSIVE_VOICE, etc.) | Rules with validated external tooling |
| 3 | Tier-3 agent self-check (judgment rule) | Rules requiring contextual judgment |
| 4 | Tier-4 Codex review as primary gate | Rules needing LLM-level evaluation |

### 4. Add test fixtures

Fixture-driven tests live in `packages/pypi/agent_style/data/skills/style-review/references/fixture-prose/`.

Create a `<name>.md` fixture and a `<name>.expected.json` sibling:

```json
{
  "total_violations": 3,
  "per_rule_count": {
    "RULE-01": 1,
    "RULE-06": 2
  },
  "expected_skipped_rules": ["RULE-H"]
}
```

Run the fixture tests before committing:

```bash
cd packages/pypi
python -m pytest tests/test_review_fixtures.py -v
```

### 5. Regenerate rule-pack artifacts

After modifying RULES.md, regenerate the derived artifacts:

```bash
python scripts/build-compact.py
```

Then commit the changed files:

```
docs/rule-pack.md
docs/rule-pack-compact.md
packages/pypi/agent_style/data/RULES.md
packages/pypi/agent_style/data/rule-pack-compact.md
packages/npm/data/RULES.md
packages/npm/data/rule-pack-compact.md
```

The `validate.yml` CI workflow will fail if these are out of date.

---

## Rule Naming Conventions

### ID format

| Group | Pattern | Example |
| --- | --- | --- |
| Canonical | `RULE-NN` (two digits) | `RULE-01`, `RULE-12` |
| Field-observed | `RULE-X` (single letter) | `RULE-A`, `RULE-H` |

### Full name format

- Title Case, imperative mood
- Anti-pattern rules: *"Do Not [behavior]"*
- Positive rules: *"Do [behavior]"*
- Maximum 70 characters
- No articles ("a", "an", "the") unless part of a fixed phrase

### Examples

```
RULE-01: Do Not Assume the Reader Shares Your Tacit Knowledge
RULE-06: Do Not Use Avoidable Jargon Where an Everyday English Word Exists
RULE-H:  Cite Sources for Quantitative Claims and Specific Assertions
```

### What goes in which group

**Canonical (RULE-01..12):** Violations of classical writing authority. Each must cite a source by chapter, section, or essay rule. Citations must be verified against the original work.

**Field-observed (RULE-A..I):** Patterns observed in AI output across writing projects. These do not require a classical source citation but require evidence from real AI-generated prose (bench drafts, production output).

---

## Testing Requirements

### Fixture-driven tests (required for every rule change)

Location: `packages/pypi/tests/test_review_fixtures.py`

These tests load every `.md` fixture in `fixture-prose/`, run the audit, and assert per-rule violation counts match the sibling `.expected.json`. If a rule's behavior changes intentionally, the corresponding `.expected.json` must be updated in the same commit.

Run locally:

```bash
cd packages/pypi
python -m pytest tests/test_review_fixtures.py -v
```

### Skill safety smoke tests

The skill safety suite (`scripts/smoke-skill-safety.sh`) validates:

- Ownership proof and atomicity on partial failure
- Drift fail-closed behavior
- Path-traversal rejection

Run locally:

```bash
bash scripts/smoke-skill-safety.sh        # both Python and Node CLIs
bash scripts/smoke-skill-safety.sh py     # Python only
bash scripts/smoke-skill-safety.sh node   # Node only
```

### Markdown linting and link checks

CI runs these on every push. Run locally before opening a PR:

```bash
# markdownlint-cli2 (Node, requires npm)
npx markdownlint-cli2 "**/*.md"

# markdown link check (Node)
npx markdown-link-check --config .github/mlc-config.json README.md
```

### Rule-pack parity check

The `validate.yml` workflow verifies that `RULES.md` and the generated rule-pack artifacts are in sync. Run locally:

```bash
python scripts/build-compact.py
git diff --exit-code -- \
  docs/rule-pack.md \
  docs/rule-pack-compact.md \
  packages/pypi/agent_style/data/RULES.md \
  packages/pypi/agent_style/data/rule-pack-compact.md \
  packages/npm/data/RULES.md \
  packages/npm/data/rule-pack-compact.md
```

---

## Pull Request Checklist

Before opening a PR, confirm:

- [ ] **Rule change:** RULES.md entry is complete (source, severity, scope, enforcement tier, directive, 5+ BAD→GOOD examples, rationale for AI agent)
- [ ] **Fixture:** New or updated fixture with matching `.expected.json`; `test_review_fixtures.py` passes
- [ ] **Artifacts:** `scripts/build-compact.py` run; all changed generated files committed
- [ ] **Skill safety:** `scripts/smoke-skill-safety.sh` passes (both py and node)
- [ ] **Lint:** `markdownlint-cli2 "**/*.md"` passes with no new errors
- [ ] **Links:** Markdown link check passes on modified files
- [ ] **CHANGELOG.md:** Entry added under `## Unreleased` with rule name, brief description, and PR number
- [ ] **Scope:** Changes are within scope (technical prose: API docs, design docs, research papers, proposals, READMEs, runbooks, commit messages, error messages, release notes, postmortems, issue reports)

### Out of scope

Do not submit rules for:

- Fiction, poetry, marketing copy
- Long-form narrative non-fiction
- Non-English prose
- Any context where rhythm or affect matters more than precision

---

## CI Validation

All PRs run the `validate.yml` workflow, which includes:

1. **Markdown lint** — `markdownlint-cli2` across all `.md` files
2. **Link check** — `markdown-link-check` for all hyperlinks
3. **Rule-pack parity** — `build-compact.py` regeneration check

A green CI run is required before merging. If linting errors appear, fix them before requesting review.