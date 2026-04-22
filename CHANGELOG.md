<!-- SPDX-License-Identifier: CC-BY-4.0 -->

# Changelog

All notable changes to *The Elements of Agent Style* are documented here.

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Semantic Versioning: [SemVer 2.0.0](https://semver.org/spec/v2.0.0.html).

> **Version distribution (as of 2026-04-21).** PyPI and npm currently distribute **0.3.1**. Git tags **v0.3.2** and **v0.3.3** are *docs-only* additions (`docs/rule-pack.md` published as the `anywhere-agents` rule-pack pin target, and README Use option 3 cross-reference). They are intentionally NOT published to PyPI or npm. The package version files (`packages/pypi/pyproject.toml`, `packages/pypi/agent_style/__init__.py`, `packages/npm/package.json`) remain at `0.3.1` to reflect the last-published state. The next PyPI / npm release MUST bump to **v0.3.4 or later** — never reuse `v0.3.2` or `v0.3.3` as a registry publish target, or you would retroactively attach new package content to a git ref users have already pinned against as "docs-only". See `RELEASING.md` for the docs-only tag convention.

## [Unreleased]

*No unreleased changes queued.*

## [0.3.2] — 2026-04-21

### Added

- **`docs/rule-pack.md`: canonical rule-pack source for anywhere-agents composition.** Verbatim mirror of `RULES.md` at the repo root, with a short HTML-comment preamble explaining the dual role. anywhere-agents' rule-pack composer (forthcoming as a separate aa release) fetches this file at a pinned ref via `https://raw.githubusercontent.com/yzhao062/agent-style/{ref}/docs/rule-pack.md` when a consumer opts into rule-pack composition. agent-style's own installer continues to read `RULES.md` unchanged; both paths stay in sync and diverge only if a future change edits one without the other. No changes to rule content, adapter files, CLI behavior, or package contents in this release.

### Notes

- **Docs-only tag.** The v0.3.2 git tag exists as a stable ref that anywhere-agents can pin against (via the `{ref}` slot in its rule-pack manifest). Whether to also bump the package version files (`pyproject.toml`, `packages/pypi/agent_style/__init__.py`, `packages/npm/package.json`) and adapter handshake strings to v0.3.2, and whether to publish to PyPI / npm, is a separate decision at tag time. If the package version strings stay at v0.3.1, the git tag v0.3.2 still works as an anywhere-agents pin target because aa fetches via raw GitHub URL, not via package install.

## [0.3.1] — 2026-04-21

### Fixed

- **Adapter self-verification strings bumped from v0.2.0 to v0.3.1.** The v0.3.0 release bumped the three package version files (`pyproject.toml`, `__init__.py`, `package.json`) but missed the hardcoded `v0.2.0` strings in `agents/*.md`, `agents/*.mdc`, `packages/pypi/agent_style/data/agents/`, `packages/npm/data/agents/`, and the pinned upstream URLs in the same files. `real-agent-smoke` on the v0.3.0 tag caught the handshake mismatch: Claude replied `agent-style v0.2.0 active: 21 rules...` when the probe expected `0.3.0`. This release restores consistency across the 32 files involved. No rule content, adapter logic, or bench infrastructure changes.

- **`README.md` version references**: `AGENT_STYLE_REF=v0.2.0` → `v0.3.1` in the `curl` recipe, the per-surface install table ("v0.2.0 primary set" → "v0.3.1 primary set"), and the self-verification probe example.

- **`adapter-matrix.md`**: "v0.2.0 ships 9 primary adapters" → "v0.3.1 ships 9 primary adapters".

### Process note

The v0.3.0 cut did the version bump by manual `sed` across only the three package version files, skipping `scripts/bump-version.py` (which walks `git ls-files` and catches the adapter handshake strings and pinned upstream URLs). For v0.3.2+, `RELEASING.md` step "Version Bump Across the Three Files" should be read as a minimum — maintainers must also run `python scripts/bump-version.py <OLD> <NEW>` before tagging to avoid a 0.3.0-style handshake drift.

## [0.3.0] — 2026-04-21

The v0.3.0 cycle turns the bench from a narrow, API-billable CI job into a full-family, long-form, zero-cost local tool: **5 runners** (claude, copilot, codex, gemini, openai) covering every major CLI-based coding agent, **academic-prose task coverage** (paper abstract / methods / experiments / related work) where AI-tells actually accumulate, and **subscription-first auth** that brings the per-release cost from ~$2.50 to $0. See the per-change entries below.

### Added

- **Bench runner family doubled: Codex CLI and GitHub Copilot CLI added to `scripts/bench/run.sh`** (now 5 runners total). Every major CLI-based coding agent can be benched against the ruleset without API spend, using the maintainer's own subscriptions (Claude Max, GitHub Copilot Pro, ChatGPT Plus for Codex, Google One AI Pro for Gemini). The new `copilot` runner invokes `copilot -p -s --model "$MODEL" --allow-all-tools` with treatment = `agent-style enable copilot` (writes repo-wide `.github/copilot-instructions.md`; the path-scoped adapter is not used here because `-p` mode has no file context and path-scoped `applyTo` globs only attach when Copilot is working on a matching prose file). The new `codex` runner invokes `codex exec --skip-git-repo-check` with treatment = `agent-style enable agents-md` (Codex CLI reads workspace AGENTS.md). Existing `claude` / `gemini` / `openai` runners unchanged except for the soft-key checks below. The `openai` runner remains the only billable one because the OpenAI Agents SDK has no subscription path; prefer `codex` for the OpenAI family on local runs. Runners are independent by construction (distinct CLIs, distinct subscriptions, distinct per-task workspaces) and are expected to run in parallel on the maintainer workstation via background jobs or the agent host's parallel-tool mechanism, cutting wall-clock from roughly one hour serial to around twenty minutes parallel. `RELEASING.md` documents the parallel invocation pattern and the one-time CLI setup.

- **Bench task set reshaped for academic-prose coverage** (`scripts/bench/tasks.md`). Previous v0.2.0 set (5 PR descriptions + 3 design-doc sections + 2 commit messages, all <200 words) showed ceiling effects on modern frontier models: mechanical AI-tells in short technical prose are already rare for GPT-5.4 and Gemini 2.5 Pro. The v0.3.0 set keeps ten tasks total but shifts composition: four short-form canaries (2 PR descriptions, 1 design-doc section, 1 commit message) confirm the ruleset does not degrade already-clean short-form baselines, and six long-form tasks target the register where AI-tells accumulate (paper abstract, paper methods, paper experiments, paper related-work, product description, NSF-style grant specific aim). Average draft length moves to ~300 words (from ~150). The bench now measures the failure modes the ruleset actually targets (long sentences, transition openers, em-dash overuse, dying-metaphor clichés in review-style prose) rather than saturating on prompts too short to elicit them.

- **`--keep-scratch` flag** in `scripts/bench/run.sh`. When set (or `KEEP_SCRATCH=1` in env), the script does not delete the per-task scratch directory at exit; the path is printed to stderr at start and stdout at end. Each `<task-id>-{baseline,treatment}/draft-<gen>.md` draft persists for eyeball review and for committing alongside the scorecard as evidence. The release workflow in `RELEASING.md` now directs the maintainer to move drafts under `docs/bench-<VERSION>-drafts/<runner>/` and commit them with the scorecard, so every published delta has the exact prose behind it.

- **Kiro (AWS IDE) adapter** via steering file (`install_mode: owned-file`). `agent-style enable kiro` writes `.kiro/steering/agent-style.md` with `inclusion: auto` frontmatter; Kiro loads steering files into every agent interaction, so the 21 rules apply to all prose generation in the workspace. Same 5-point content contract as the other primary adapters (versioned self-verification handshake, compact directives, load statement, full-body pointer, escape hatch). `adapter-matrix.md` bumped to 9 primary adapters plus the `style-review` skill. Contributed by @Alex-jjh ([#2](https://github.com/yzhao062/agent-style/pull/2)).

### Changed

- **Bench moved from GitHub Actions to local-only** (`.github/workflows/bench.yml` removed). Historically the bench ran in CI at ~$0.45 (cheap tier) or ~$2.20–$2.50 (flagship tier) per dispatch against paid APIs; starting v0.3.0 it runs on the maintainer's machine against the subscription-backed CLIs at $0 per dispatch. The bench no longer needs GitHub Actions secrets (other CI workflows such as `real-agent-smoke.yml` and the `adapter-*-smoke.yml` set continue to use model-API secrets for their own lanes). `RELEASING.md` "Bench (Local Only)" section documents the new invocation pattern, the **4-runner subscription matrix** (claude, copilot, codex, gemini) that is the default local release run, and the cadence (major/minor releases only, with major/minor version bumps gated on a fresh local bench). The 5th runner (`openai` via OpenAI Agents SDK) remains in `run.sh` for parity with the v0.2.0 methodology but is optional and billable. The CI-API-cost-exposure table in `RELEASING.md` drops all three `bench.yml` rows; the annual cost forecast drops the `~$5-$7.50` bench line, moving the overall CI spend forecast from `~$5-$15/year` to `~$0.25-$5/year`, roughly a 70% reduction.

- **API-key handling hardened to force subscription auth** in `scripts/bench/run.sh`. Previously the script hard-required `ANTHROPIC_API_KEY` / `GEMINI_API_KEY` / `OPENAI_API_KEY` for the claude, gemini, and openai runners. v0.3.0 both softens AND hardens: the hard check is removed so the CLIs fall back to their own login auth, AND the corresponding env var is explicitly `unset` inside the script process for the subscription runners (claude, codex, gemini) so that a stray env key in the maintainer shell cannot silently bill the run. `copilot` never touched an API key. The `openai` runner is the one intentional billable path and explicitly keeps `OPENAI_API_KEY` available. The unset only affects the script's own process env, not the user's shell.

### Notes

- **Copilot CLI `-p` programmatic mode does not load `.github/copilot-instructions.md` or `.github/instructions/*.instructions.md`.** The v0.3.0 bench run (10 tasks, 2 generations, 40 total calls) on the `copilot` runner produced baseline 61 and treatment 63 violations — effectively zero delta, compared to Codex on identical GPT-5.4 backend showing baseline 51 → treatment 28 (-45%). This is upstream Copilot CLI behavior for the programmatic `-p` path specifically. Repository-wide and path-scoped instruction files are documented by GitHub to load for IDE Chat and inline completion; our end-to-end verification of the IDE and the CLI interactive (TUI) modes is still pending and tracked in `TODO.md` under "Copilot instruction-loading verification". The bench keeps the copilot runner for completeness and transparency; for gpt-5.4 family measurement, cite the `codex` runner result instead. For the shipped `copilot` and `copilot-path` adapters, the scope of proven non-loading is the `-p` programmatic path only, not every Copilot entry point.

- **Gemini Pro 3.1 (`--model pro`) hits quota limits on a 40-call bench run** during a 22-hour rolling window. An attempted v0.3.0 bench with `pro` failed at task 5/10 with `RetryableQuotaError: No capacity available for model gemini-3.1-pro-preview on the server` after burning through the remaining subscription quota. Gemini 3 Flash (`--model flash`) has a substantially higher limit and completes the 40-call bench comfortably. RELEASING's invocation block recommends `flash` as the default Gemini leg; Pro is documented as an optional upgrade for maintainers whose quota headroom allows it. The partial Pro run before it 429'd (4 tasks, delta -12 on completed work) is archived under `docs/bench-0.3.0-gemini-3.1-pro-partial-archive.md`.

- **Copilot `-p` runner bug discovered and fixed via Codex implement-review Round 2.** The initial copilot invocation passed `--add-dir "$ws"`, which triggered Copilot's agent-explore mode: Copilot read `README.md`, narrated "I'm checking the draft file..." and emitted the narration as part of stdout, contaminating the draft with first-person Copilot commentary. Removing `--add-dir` cleaned the output; the clean run then exposed the separate upstream limitation noted above, namely that CLI `-p` still does not load the instruction files. The archived `docs/bench-0.3.0-copilot-noisy-archive.md` shows the pre-fix data (with narration) for audit.

## [0.2.0] — 2026-04-20

### Added

- **`style-review` skill: second-pass review loop** complementing the generation-time ruleset. The existing `enable <tool>` adapters remain soft enforcement (the model sees the rules and is asked to follow them, but can ignore them). The new skill is the opt-in post-hoc pass: the user asks for it explicitly, the skill audits the prose against the same 21 rules, and on confirmation produces a revised draft at `FILE.reviewed.md` without touching the source. Designed around the observation that prompt-loaded rules nudge the model but cannot override training-prior token distributions, and that adding more examples has diminishing returns — the complement is a review loop the user invokes after the first draft is written.

- **`agent-style review <file>` CLI subcommand** in both the pip and npm packages. Deterministic mechanical + structural detection from the plain CLI (works in any pip / npm / curl / clone context). Flags:
  - `--audit-only`: emit canonical JSON with per-rule violation counts and excerpts; no polish, no ask.
  - `--mechanical-only`: strictest deterministic subset; used by `scripts/verify-install.sh --cli-parity` as the byte-identity oracle.
  - `--compare A B`: A/B audit with per-rule delta (used for benchmarking).
  - `--polish`: requires a skill host (Claude Code / Anthropic Skills); errors with an actionable message from the plain CLI.
  - No new runtime dependencies in either ecosystem. Semantic rules (RULE-01, 03, 04, 08, 11, F, H) emit `status: "skipped"` from the plain CLI and are handled by the skill host.

- **Ten deterministic detectors** covering the mechanical + structural subset of the 21-rule matrix:
  - Mechanical: RULE-B (em/en-dash casual use), RULE-D (transition openers `Additionally` / `Furthermore` / `Moreover` / `In addition`), RULE-G (heading title case per RULE-G's own convention), RULE-I (contractions in formal prose), RULE-12 (sentences >30 words), RULE-05 (cliché phrase list from Orwell 1946 + RULES.md BAD examples), RULE-06 (45-word banned AI-tell list + Orwell Rule 5 jargon).
  - Structural: RULE-A (bullet overuse: ≤2 items or all items ≤8 words), RULE-C (≥2 of 3 consecutive sentences share opening token), RULE-E (paragraph closers restating the topic).
  - RULE-02, 07, 09, 10 structural detectors stubbed as skipped in v0.2.0 (deferred to v0.3.0).

- **New `skill-with-references` install mode** in `tools.json`. `agent-style enable style-review` auto-detects which skill-capable surfaces are active in the project (Claude Code, Anthropic Skills, detected via existing `.agent-style/` or `.claude/skills/` files) and writes `SKILL.md` + `references/*` for each, deduplicated by target path. For tools without a skills directory (Codex, Copilot, Aider, Cursor), it prints a manual-step message pointing at the CLI fallback. No-surface case exits with `enabled: false, manual_step_required: true` and a message. Backward-compatible schema extension (`schema_version` stays at 1).

- **Manifest-based safe disable**. `agent-style enable style-review` writes `.agent-style/skills/style-review/manifest.json` listing every path + sha256 it created. `disable` reads the manifest and removes only files whose current hash still matches; user-edited files are skipped and reported as `drifted`; empty directories are cleaned up; non-empty directories are left in place with a report. No blind recursive deletes.

- **Bundled skill definition** at `skills/style-review/` (synced into both `packages/pypi/agent_style/data/skills/style-review/` and `packages/npm/data/skills/style-review/`):
  - `SKILL.md` with invocation contract, workflow, polish invariants, and self-verification probe.
  - `references/rule-detectors.md` — full 21-row detector matrix (bucket, approach, threshold, fixture).
  - `references/revision-prompt.md` — polish-pass template with hard no-new-facts invariants (no metrics / citations / links / code behavior not in source; preserve Markdown structure; preserve meaning; preserve length budget).
  - `references/fixture-prose/` — 5 fixtures (`mech-violations.md`, `struct-violations.md`, `mixed.md`, `messy-real-world.md`, `clean-control.md`) each with `*.expected.json` documenting per-rule violation counts. Fixtures drive the unit-test suite in both ecosystems.

- **Unit tests** (new):
  - Python: `packages/pypi/tests/test_review_fixtures.py` — 9 tests covering every fixture, plus regression guards (clean-control produces zero; fenced `leverages` not flagged; semantic-skipped contract; mechanical-only purity).
  - Node: `packages/npm/test/review.test.js` — same 9 tests using `node --test` (stdlib; zero new deps). Fixtures and expected counts are byte-for-byte identical between Python and Node.

- **Sanity benchmark** (Phase 3 from PLAN):
  - `scripts/bench/tasks.md`: 10 concrete prose tasks (5 PR descriptions, 3 design-doc sections, 2 commit messages).
  - `scripts/bench/run.sh`: bash runner that generates baseline vs treatment drafts via `claude -p`, scores each with `agent-style review --mechanical-only --audit-only`, and emits a Markdown scorecard at `docs/bench-<version>.md`.
  - `.github/workflows/bench.yml`: `workflow_dispatch` CI job that runs the bench against the live Anthropic API, uploads the scorecard as an artifact. Explicitly workflow-dispatch only (no per-push firing) to keep API cost predictable (~$0.40–$0.80 per run).
  - `docs/bench-0.2.0.md`: placeholder committed alongside this release; populated after the first workflow dispatch post-release. Explicitly framed as a sanity signal, not a ship gate.

- **Schema extension** in `tools.json`:
  - New `install_mode` value `skill-with-references` with mode-specific required fields (`skill_source`, `references_source`, `target_groups`, `manual_step_message`) and mode-specific forbidden fields (`target_path`, `adapter_source`, `load_class`). The validator in `registry.py` / `registry.js` rejects mixed-mode entries; existing 5-mode entries continue to validate as before. `schema_version` remains 1 (backward-compatible additions only).

- **`list-tools` output** now handles mode-specific entries by summarizing `target_groups[*].target_path` joined by ` + ` for `skill-with-references`, without depending on the forbidden legacy fields.

- **`scripts/verify-install.sh --cli-parity` extended to 12/12**: adds `review --mechanical-only FILE` and `review --mechanical-only --compare A B` diffs. The parity oracle uses `--mechanical-only` exclusively because structural detectors are also deterministic but heavier; `--mechanical-only` is the tightest subset. Parity harness continues to pass byte-identically across pip and npm on Windows Git Bash and Linux aarch64.

### Changed

- README rewritten to explain the soft-vs-hard-enforcement split explicitly: the generation-time adapters are soft-load (nudge), and `/style-review` is the opt-in second-pass enforcement loop (audit + diff). New "Second-pass review" section with both CLI and skill-host user paths. Per-surface install table gains a `style-review` row.

### Notes

- Phase 4 (benchmark) is shipped as runner + workflow + placeholder scorecard; the populated scorecard publishes post-release via `workflow_dispatch`. Subsequent releases rerun the benchmark to track delta between releases.
- RULE-02, 07, 09, 10 structural detectors and all 7 semantic detectors remain as documented stubs in this release (`status: "skipped"` with actionable notes). Full coverage is a v0.3.0+ concern.

## [0.1.1] — 2026-04-19

### Fixed

- **npm CLI**: `agent-style rules` on Linux and macOS truncated piped output at the 64 KiB kernel pipe-buffer boundary. Root cause: `process.stdout.write()` returned `false` when the buffer filled and `process.exit()` ran before the queued bytes drained, so `agent-style rules | less` or `agent-style rules | wc -c` lost the last ~25 KiB of `RULES.md`. Fix lives in `packages/npm/bin/agent-style.js`: wait for `stdout` and `stderr` to drain via zero-byte writes with drain callbacks before calling `process.exit`, and swallow `EPIPE` from consumers that close the pipe early (for example `agent-style rules | head -3`). Windows (non-POSIX pipe semantics) and the Python CLI are unaffected by the original bug. Regression covered by `scripts/verify-fresh-install.py` on Linux aarch64.

### Changed

- Bundled `RULES.md` content refresh (no structural change; all 21 rule bodies still line up with the published rule IDs):
  - Stale "Phase 1b draft" banner at the top of the canonical rule file removed.
  - Author voice normalized from "the maintainer" to "I / my / me" across field-observed source metadata and the descriptive intro, so the ruleset reads as a personal project. Field-observed source lines now say "My observation of LLM output across dozens of writing projects and code releases, 2022 – 2026" in place of the prior category enumeration.
- README post-release polish (not a packaged artifact but cited here for completeness): `docs/hero.png` hero figure, `docs/sources.png` canonical-sources collage, "What It Is" rewrite into a Scope table plus Two Rule Groups sub-sections, badge row trimmed, two dense sections moved into collapsible `<details>`.

## [0.1.0] — 2026-04-19

### Added

- Phase 1b full draft: bodies for all 12 canonical rules (RULE-01 through RULE-12) plus 9 field-observed rules (RULE-A through RULE-I) in `RULES.md`. Canonical rules are distilled from Strunk & White, Orwell, Pinker, and Gopen & Swan, with citations verified by the maintainer against chapter, section, or essay-rule references. Field-observed rules come from the maintainer's observation of LLM output across research papers, grant proposals, technical documentation, and agent-configuration work 2022 to 2026, covering bullet-point overuse (A), em/en-dash overuse (B), consecutive same-starts (C), transition-word overuse (D), paragraph-closing summaries (E), term consistency (F), title case for headings (G), citation discipline including anti-hallucination (H, critical), and contraction register (I). Each rule block includes metadata (source, agent-instruction evidence citing Zhang et al. 2026 and Bohr 2025 with narrowed claims, severity per the four-level rubric, scope, enforcement tier), directive (negative for anti-pattern rules; positive for constructive-placement rules), 5 or more BAD/GOOD example pairs with at least one non-paper context, and rationale-for-AI-agent framing the LLM-specific failure mode.
- README rewrite: tagline "Make your AI agent write like a tech pro.", added Before/After demo section, separated rules into Canonical (RULE-01..12) and Field-Observed (RULE-A..I) tables, moved Canonical Sources toward the bottom, dropped the Related section, applied title case to all section headings.
- Slug rename: repo `elements-of-agent-style` renamed to `agent-style` (GitHub + PyPI + npm names consistent; title "The Elements of Agent Style" preserved).
- Codex Round 3 validator review complete; findings addressed in-place. High-severity finding: RULE-H GOOD-example citations rewritten against verified references (ColBERT MRR@10 rather than recall@10; Liu et al. TACL rather than NAACL; Dsouza et al. 2024 for GPT-4/Claude-3 lost-in-the-middle replication; SimCLR 76.5% linear-probe claim corrected). Medium: field-observed rules B-I now carry the Round-2-narrowed Zhang/Bohr wording (RULE-G and RULE-I include the positive-directive exception clause). Reopened markdownlint blocker resolved (13 rewrites: table separators, double-backtick wrapping for inline-code examples with nested backticks, H3 insertion between H2 and RULE-A, fence labels on RULE-A BAD code blocks).
- Post-draft content close-out (Codex validator rounds 3 + 4 on the full 21-rule draft): 5 findings addressed — all 21 `#### RULE-` headings title-cased per RULE-G self-application; `page-by-page` claim softened to "chapter, section, or essay rule" in `README.md` and `CHANGELOG.md`; Gopen & Swan reference removed from the RULE-F `source` bullet (retained as a cross-reference in the RULE-F rationale alongside RULE-01); `imperative sentence` → `command-form sentence` in the `RULES.md` block-shape intro; `3-5 per rule` → `5 or more per rule, with at least one non-paper context (API docs, runbooks, proposals, release notes, postmortems, changelogs, issue reports)` to match the actual block shape and the CHANGELOG "5 or more" claim. Bundled `RULES.md` copies under `packages/pypi/agent_style/data/` and `packages/npm/data/` re-synced; `scripts/verify-install.sh --cli-parity` continued to pass 10/10 JSON diffs. Close-out Round 4 returned 0 new findings and approved v0.1.0 release.
- Repo structure: `examples/` folder dropped (redundant with the 5-6 BAD/GOOD pairs already in each rule body); license tables in `README.md` and `NOTICE.md` updated accordingly.
- v1 release preparation (six rounds of Codex plan-review converged on Rev 8; all 36 findings Fixed; Round 6 produced zero High findings, signaling design convergence):
  - **README "Use" section rewrite**: CLI-primary install (`pip install agent-style && agent-style enable <tool>` or `npx --yes agent-style@0.1.0 enable <tool>`) with manual `curl` fallback; `AGENT_STYLE_REF` version pinning; per-surface install recipes; self-verification probe with the versioned handshake; two-step uninstall recipe (POSIX + PowerShell); v0.2.0 roadmap callout.
  - **Phase 2a — 8 primary adapters populated** per the 5-point content contract (versioned self-verification handshake, compact rule directives, surface-specific load statement, pointer or import for canonical full bodies, Orwell Rule 6 escape hatch): `agents/AGENTS.md`, `agents/claude-code.md`, `agents/codex.md`, `agents/cursor-rule.mdc`, `agents/copilot-instructions.md`, `agents/copilot-path-instructions.md`, `agents/aider-conventions.md`, `agents/anthropic-skill/SKILL.md`. Each adapter targets an `install_mode` (`import-marker`, `append-block`, `owned-file`, `multi-file-required`, `print-only`) and is sized for its load class (~1 KB import-capable; ~2 KB single-file and multi-file-required).
  - **10 deferred adapters moved to roadmap**: Amazon Q Developer, JetBrains AI Assistant, Windsurf (repo / global), Ollama, Replit (project / Skills), OpenCode, Continue.dev, Tabnine, OpenAI Agents SDK skills. Placeholder files under `agents/` removed; `adapter-matrix.md` restructured to "Primary Adapters (v0.1.0, Shipped)" + "Planned Adapters (v1.1, Open to Contributions)".
  - **Python + npm CLI packages with feature parity** (5 subcommands `rules` / `path` / `list-tools` / `enable` / `disable`; 5 install modes `import-marker` / `append-block` / `owned-file` / `multi-file-required` / `print-only`; canonical JSON dry-run output with sorted keys, LF line endings, POSIX-relative paths, content-sha256 hashes for parity; owned-file canonical-UTF-8 byte-stream signature for tamper detection; zero runtime dependencies on both ecosystems).
  - **`RELEASING.md`**: release runbook covering prerequisites, pre-release checks (content-depth, markdownlint, whitespace, secrets grep, AGENT_STYLE_REF substitution), three-file version bump, ecosystem-specific rc rehearsal (PyPI `0.1.0rc1`, npm `0.1.0-rc.1`), TestPyPI dry run, bump-back-to-final + `EXPECTED_VERSION` verification, availability recheck, commit-tag-push, public flip, real PyPI + npm publish with availability rechecks, `gh release create`, post-release cleanup commit, and common-gotchas appendix.
  - **`scripts/verify-install.sh`**: three modes confirmed on Windows Git Bash AND Linux aarch64 (Spark `spark-37f2.local`, Python 3.12, Node v18). Default mode asserts 21 `#### RULE-` headings + exactly 21 `##### Directive` + exactly 21 `##### Rationale for AI Agent` + RULE-01 + RULE-A. `--version-only` with optional `EXPECTED_VERSION` asserts the three version files equal exactly that value and grep-guards against rc substrings leaking into shipped content. `--cli-parity` builds and runs both CLIs in a scratch outside the source repo, strips CRLF/LF for portable diff, and asserts byte-identical JSON across 5 install modes × {enable, disable} = 10 diffs.
  - **Cross-platform parity verified**: Windows Git Bash passes all 10 JSON diffs; Linux aarch64 (Spark) passes all 10 JSON diffs; content hashes match across ecosystems (e.g., RULES.md = `0f615fd1…`, `.agent-style/claude-code.md` = `b258391…`, CLAUDE.md marker block = `6717b9ef…`).

---

[Unreleased]: https://github.com/yzhao062/agent-style/compare/v0.3.2...HEAD
[0.3.2]: https://github.com/yzhao062/agent-style/compare/v0.3.1...v0.3.2
[0.3.1]: https://github.com/yzhao062/agent-style/compare/v0.3.0...v0.3.1
[0.3.0]: https://github.com/yzhao062/agent-style/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/yzhao062/agent-style/compare/v0.1.1...v0.2.0
[0.1.1]: https://github.com/yzhao062/agent-style/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/yzhao062/agent-style/releases/tag/v0.1.0
