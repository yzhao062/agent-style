<!-- SPDX-License-Identifier: MIT -->

# Releasing agent-style

This is the exact procedure for cutting a new `agent-style` release. The repo and both packages (PyPI + npm) share **one final version number**, bumped together and tagged on the same commit so that checking out the tag reproduces exactly what is published.

TestPyPI rehearsal happens **before** tag with ecosystem-specific rc versions (PEP 440 for Python, SemVer for npm); the three version files are bumped back to the final shared `X.Y.Z` before `git tag`.

## Prerequisites (One-Time)

| Item | Needed for | Setup |
| --- | --- | --- |
| Python 3.8+ with `build` and `twine` | PyPI publish | `pip install --upgrade build twine` |
| Node.js 14+ with `npm` | npm publish | Install Node; `npm -v` works |
| `git` | everything | — |
| `gh` CLI | GitHub release | `winget install GitHub.cli` or `brew install gh`; `gh auth login` |
| `~/.pypirc` with PyPI + TestPyPI tokens | `twine upload` | Generate at https://pypi.org/manage/account/token/ and https://test.pypi.org/manage/account/token/ |
| `~/.npmrc` with **bypass-2FA** token | `npm publish` | Generate at https://www.npmjs.com/settings/<user>/tokens/new; check "Bypass Two-Factor Authentication". WebAuthn/Windows Hello cannot accept `--otp`, so non-bypass tokens fail on publish. |

## Pre-Release Checks

From a clean `main` with no uncommitted changes:

```bash
# 1. Content-depth invariants: 21 rule headings, 21 Directive, 21 Rationale, RULE-01 + RULE-A present.
bash scripts/verify-install.sh

# 2. Markdown lint clean across all tracked Markdown (CodexReview.md is intentionally excluded).
npx --yes markdownlint-cli2 "**/*.md" "#CodexReview.md"

# 3. Whitespace-clean staged diff (no trailing spaces / mixed tabs).
git diff --cached --check

# 4. Secrets / API-key grep: nothing accidentally staged.
grep -RniE "sk-[a-zA-Z0-9]{20,}|ghp_[a-zA-Z0-9]{20,}|AKIA[0-9A-Z]{16}|Bearer [A-Za-z0-9._-]{20,}" \
  --include="*.md" --include="*.py" --include="*.js" --include="*.json" --include="*.yml" \
  --include="*.yaml" --include="*.sh" --include="*.ps1" --include="*.toml" \
  . || true
# Review hits manually; there should be none outside of documentation examples.

# 5. AGENT_STYLE_REF in README matches the version-to-be-tagged.
grep -nE "AGENT_STYLE_REF=v[0-9]+\.[0-9]+\.[0-9]+" README.md
```

If any check fails, stop and fix before continuing.

## Local Validation

Builds both packages, installs into scratch env outside the source repo, verifies content and JSON parity:

```bash
bash scripts/verify-install.sh               # content-depth
bash scripts/verify-install.sh --cli-parity  # Python vs Node JSON diff across 5 install modes × 2 subcommands
```

`--cli-parity` must print `PASS: CLI parity check (5 tools × 2 subcommands = 10 JSON diffs)`. A diff signals Python/Node divergence; fix before tagging.

## Version Bump Across the Three Files

> **Docs-only git tag convention.** Some releases (for example `v0.3.2`, `v0.3.3`) are intentionally git-only — a stable ref for external pinning (e.g. `anywhere-agents` fetches `docs/rule-pack.md` at a pinned ref) without a PyPI / npm package bump. When publishing the next proper release, **skip over any docs-only tag numbers**. Do NOT publish `X.Y.Z` to PyPI / npm if a git tag `vX.Y.Z` already exists as a docs-only tag — the registry would retroactively advertise new package content under a ref consumers have already pinned as unchanging. Check `git tag --list --sort=-v:refname` and verify each recent tag against the CHANGELOG's "Docs-only tag" notes before choosing the next version. The CHANGELOG's top-of-file "Version distribution" block is the authoritative record of which git tags were published to PyPI / npm and which were git-only.

Only **three files** hold the release version:

1. `packages/pypi/pyproject.toml` -> `project.version`
2. `packages/pypi/agent_style/__init__.py` -> `__version__`
3. `packages/npm/package.json` -> `version`

The three must hold the same final shared version `X.Y.Z` before tag. They may be temporarily ecosystem-specific during rc rehearsal (see next section).

Also: add a `## [X.Y.Z] — YYYY-MM-DD` section to `CHANGELOG.md`, move contents from `[Unreleased]`, and update the compare-link block at the bottom so `[X.Y.Z]` resolves and `[Unreleased]` compares against the new tag.

## TestPyPI Rehearsal (Before Tag)

Rehearsal uses a **pre-release version**, not the final one, because registries are immutable: once `X.Y.Z` is uploaded anywhere, a packaging fix cannot reuse that version string without a bump. Rehearsal versions are ecosystem-specific because PyPI uses PEP 440 (`0.1.0rc1`) and npm uses SemVer (`0.1.0-rc.1`).

```bash
# Bump Python files only to 0.1.0rc1 (npm stays at 0.1.0 locally; or bump to 0.1.0-rc.1 if you want a matching npm local tarball test).
sed -i 's/version = "0\.1\.0"/version = "0.1.0rc1"/' packages/pypi/pyproject.toml
sed -i 's/__version__ = "0\.1\.0"/__version__ = "0.1.0rc1"/' packages/pypi/agent_style/__init__.py
# Optional: local npm tarball check at a SemVer rc
sed -i 's/"version": "0\.1\.0"/"version": "0.1.0-rc.1"/' packages/npm/package.json

# Build and upload Python rc to TestPyPI.
rm -rf packages/pypi/dist
python -m build packages/pypi --outdir packages/pypi/dist
python -m twine check packages/pypi/dist/*
python -m twine upload --repository testpypi packages/pypi/dist/*

# Wait for TestPyPI simple-index propagation.
sleep 60

# Fresh-venv install from TestPyPI; verify.
SCRATCH=$(python -c "import tempfile; print(tempfile.mkdtemp(prefix='as-testpypi-'))")
python -m venv "$SCRATCH/venv"
"$SCRATCH/venv/Scripts/python.exe" -m pip install --quiet \
    --index-url https://test.pypi.org/simple/ \
    --extra-index-url https://pypi.org/simple/ agent-style==0.1.0rc1
"$SCRATCH/venv/Scripts/python.exe" -c "import agent_style; assert agent_style.__version__ == '0.1.0rc1'; print(agent_style.__version__)"
"$SCRATCH/venv/Scripts/agent-style.exe" list-tools | head -5

# Local npm tarball smoke (no publish).
( cd packages/npm && npm pack --dry-run )
NPM_SCRATCH=$(mktemp -d -t as-npm-pack-XXXXXX)
( cd packages/npm && npm pack --pack-destination "$NPM_SCRATCH" )
( cd "$NPM_SCRATCH" && npm install agent-style-*.tgz && ./node_modules/.bin/agent-style --version )
```

On macOS / Linux, replace `Scripts/python.exe` with `bin/python` and `Scripts/agent-style.exe` with `bin/agent-style`.

During rehearsal, cross-file version equality is intentionally suspended; `scripts/verify-install.sh --version-only` should **not** be run (it would fail the equality check). Run it only after step below.

If TestPyPI catches a packaging issue, fix it, bump to `0.1.0rc2` / `0.1.0-rc.2`, and repeat. Do **not** re-upload the same rc version — TestPyPI forbids it.

## Bump Back to Final Version; Final Local Checks

```bash
# Restore all three files to final shared X.Y.Z.
sed -i 's/version = "0\.1\.0rc[0-9]*"/version = "0.1.0"/' packages/pypi/pyproject.toml
sed -i 's/__version__ = "0\.1\.0rc[0-9]*"/__version__ = "0.1.0"/' packages/pypi/agent_style/__init__.py
sed -i 's/"version": "0\.1\.0-rc\.[0-9]*"/"version": "0.1.0"/' packages/npm/package.json

# Rebuild.
rm -rf packages/pypi/dist
python -m build packages/pypi --outdir packages/pypi/dist
python -m twine check packages/pypi/dist/*
( cd packages/npm && npm pack --dry-run )

# Exact-version check (pinned to 0.1.0) and rc-substring leak check.
EXPECTED_VERSION=0.1.0 bash scripts/verify-install.sh --version-only
bash scripts/verify-install.sh
bash scripts/verify-install.sh --cli-parity
```

The final `EXPECTED_VERSION=0.1.0 --version-only` pass must succeed; it also asserts no `rc` substring leaked into bundled content.

## Availability Recheck

```bash
# PyPI
curl -sfI https://pypi.org/pypi/agent-style/json && echo "TAKEN (halt)" || echo "available"
# npm
npm view agent-style version 2>/dev/null && echo "TAKEN (halt)" || echo "available"
```

If either namespace is taken, halt.

## Commit, Tag, Push

```bash
git add packages/ CHANGELOG.md
git commit -m "release: vX.Y.Z -- <short summary>"
git tag -a vX.Y.Z -m "Release X.Y.Z"
git push origin main
git push origin vX.Y.Z
```

## Flip Repo Public (v0.1.0 Only)

```bash
gh repo edit yzhao062/agent-style --visibility public --accept-visibility-change-consequences
# Verify:
curl -sfL "https://raw.githubusercontent.com/yzhao062/agent-style/vX.Y.Z/RULES.md" | head -5
```

## Real PyPI Upload

Availability recheck immediately before upload:

```bash
curl -sfI https://pypi.org/pypi/agent-style/json && echo "TAKEN (halt)" || echo "available"
python -m twine upload packages/pypi/dist/*
# Verify (force fresh install to bypass pip cache and PyPI CDN staleness):
pip install --upgrade --force-reinstall --no-cache-dir agent-style==X.Y.Z
agent-style --version   # should print X.Y.Z
```

## npm Publish

Availability recheck immediately before publish:

```bash
npm view agent-style version 2>/dev/null && echo "TAKEN (halt)" || echo "available"
npm publish packages/npm --access public
# Verify:
npm view agent-style version   # should print X.Y.Z
cd "$(mktemp -d)" && npx --yes agent-style@X.Y.Z --version
```

## GitHub Release

Trigger any `release: published` CI hooks (none in v0.1.0, but wires the pattern for later):

```bash
echo "v*-release-notes.md" >> .git/info/exclude   # one-time, repo-local ignore
gh release create vX.Y.Z --target main --title "vX.Y.Z" --notes-file vX.Y.Z-release-notes.md
```

## Post-Release Cleanup

```bash
# Reset [Unreleased] in CHANGELOG to start the next development cycle.
# Manually edit CHANGELOG.md so the [Unreleased] section shows "_No unreleased changes queued._"
git add CHANGELOG.md
git commit -m "docs: start next development cycle"
git push origin main

# Delete the scratch release-notes file.
rm -f vX.Y.Z-release-notes.md
```

## CI API Cost Exposure (for humans and agents)

Every workflow in `.github/workflows/` that calls a model API has a documented
per-dispatch cost. Before any `gh workflow run` on a workflow that is not free,
**agents MUST confirm with the user** — "the user approved a larger task" is
not blanket approval for paid dispatch. Each workflow click is a separate
billable action.

### Workflow cost table

| Workflow | Trigger(s) | Cost per run | Safeguards |
|---|---|---|---|
| `validate.yml` | push + PR | $0 (no API calls) | — |
| `real-agent-smoke.yml` | `release: published` + manual | ~$0.05 | Sonnet pin on Claude probes; handshake-only |
| `adapter-aider-smoke.yml` | manual | ~$0.10 | Sonnet 4.6 via Aider |
| `adapter-gemini-smoke.yml` | manual | $0 (Flash free tier) | — |
| `adapter-agents-sdk-smoke.yml` | manual | ~$0.01 | GPT-5.4 Nano |

Bench moved out of CI — see the "Bench (Local Only)" section below. No
workflow dispatches bench anymore; the matrix runs on the maintainer's
subscription-backed CLIs at $0 per dispatch.

### Dispatch-approval policy (for agents)

Any `gh workflow run` on a workflow whose per-dispatch cost is **above $0.01**
requires explicit per-dispatch user approval, even inside a broader approved
task. Before dispatching:

1. Name the workflow and the measured or estimated cost for this specific set
   of inputs.
2. State the hypothesis you expect the run to verify.
3. Wait for an explicit `dispatch` / `go` / `yes` from the user.

`validate.yml` and `adapter-gemini-smoke.yml` (free tier) may be dispatched
inside an approved task without per-run confirmation.

### Annual cost forecast

| Category | Typical year |
|---|---|
| `real-agent-smoke` auto-triggered on ~5 releases | ~$0.25 |
| Ad-hoc adapter smokes during debugging | ~$0-$5 |
| **Total** | **~$0.25-$5** |

v0.2.0 dev-cycle (historical, before bench moved local): ~$2.45 on a
now-removed `bench.yml` (one flagship matrix + one Gemini rerun) plus
~$0.10-$0.20 on adapter-smoke validation. From v0.3.0 onward bench runs
locally on subscription-backed CLIs, so future cycles drop the bench line
entirely.

## Bench (Local Only)

Bench runs on the maintainer's machine against locally-installed CLIs
authenticated with subscriptions (Claude Max/Pro, GitHub Copilot Pro,
ChatGPT Plus for Codex, Google One AI Pro for Gemini). **$0 per dispatch**;
no CI workflow and no bench-specific GitHub Actions secrets (the other
CI workflows such as `real-agent-smoke.yml` still use model-API secrets
for their own lanes). This replaces the earlier
`bench.yml` workflow removed in v0.3.0. Per-release mechanical correctness
is still guarded by `real-agent-smoke.yml` (~$0.05 per release, auto-
triggered on `release: published`); local bench adds behavioral data for
the README figure when a major/minor release warrants it.

### Cadence

Run before tagging a major or minor release (v0.3.0, v0.4.0, v1.0.0).
Skip on patch releases (v0.2.1, v0.2.2) unless the patch touches bench
code itself.

### Maintainer machine prerequisites

The bench expects the maintainer's workstation to hold all four
subscription CLIs logged in. Setup is one-time per machine:

| CLI | Install | Login |
|---|---|---|
| `claude` (Claude Code CLI) | `curl -fsSL https://claude.ai/install.sh \| sh` (macOS/Linux) or `irm https://claude.ai/install.ps1 \| iex` (Windows) | `claude login` via browser flow |
| `copilot` (GitHub Copilot CLI) | `winget install GitHub.Copilot` (Windows) or see [docs.github.com/copilot/how-tos/copilot-cli](https://docs.github.com/copilot/how-tos/copilot-cli) | `copilot auth login` via browser flow; GitHub Education gives eligible faculty/students Copilot Pro for free |
| `codex` (Codex CLI) | `npm install -g @openai/codex` | `codex login` via browser flow; bundled with ChatGPT Plus/Pro |
| `gemini` (Gemini CLI) | `npm install -g @google/gemini-cli` | `gemini` interactive first time for Google OAuth; bundled with Google One AI Pro |

Skip this table if the workstation is already set up (one-time per
machine). Once logged in, every subsequent bench run is $0.

### Parallel execution is the expected runtime

Runners are independent by design (different CLIs, different
subscriptions, different workspaces). Claude Code should dispatch all
four runners **in parallel**, then wait on the aggregate step. Wall-clock
drops from ~60 min serial to ~20 min parallel (bottleneck: slowest
runner, typically Claude Opus). No subscription conflicts because each
runner consumes its own account's quota.

For agents driving the bench:

- Launch `claude`, `copilot`, `codex`, `gemini` runners concurrently via
  background jobs (`&` + `wait`) or the agent host's parallel-tool
  mechanism.
- The `aggregate.py` step must run **after** all four scorecards are on
  disk. Do not parallelize aggregate with the runner launches.
- On subscription rate-limit throttle (Claude Max enforces a ~5h rolling
  window), fail-closed on that single runner and rerun it later; the
  other three complete independently.

### Runners supported (5 total: 4 subscription-backed + 1 billable)

The default local release bench uses the **4-runner subscription matrix**
(claude, copilot, codex, gemini). The `openai` runner is supported in
`run.sh` for historical parity with the v0.2.0 bench methodology, but
it talks to the API directly and burns money; prefer `codex` for the
OpenAI family on local runs.

| Runner | CLI | Treatment adapter | Auth | Cost |
|---|---|---|---|---|
| claude | `claude` (Claude Code CLI) | `agent-style enable claude-code` | Claude Code subscription via `claude` login | $0 |
| copilot | `copilot` (GitHub Copilot CLI) | `agent-style enable copilot` (repo-wide; `-p` mode has no file context, so path-scoped is skipped) | Copilot Pro via `copilot auth login` | $0 |
| codex | `codex` (Codex CLI) | `agent-style enable agents-md` | ChatGPT Plus/Pro via `codex login` | $0 |
| gemini | `gemini` (Gemini CLI) | `agent-style enable agents-md` + `.gemini/settings.json` | Google AI Studio / Gemini Advanced login | $0 |
| openai (optional) | OpenAI Agents SDK (Python) | `agent-style enable codex` | `OPENAI_API_KEY` | ~$0.17 at gpt-5.4 flagship; billable |

### Copilot runner caveat (important)

The `copilot` runner is kept for completeness, but the data it produces
is narrow and specific. Empirically, GitHub Copilot CLI `-p` programmatic
mode does not load `.github/copilot-instructions.md` or
`.github/instructions/*.instructions.md` into the request context: the
v0.3.0 bench shows baseline 61 → treatment 63 (+3% noise) on identical
tasks where Codex on the same GPT-5.4 backend shows -45%. For GPT-5.4
family measurement in a release scorecard, cite the `codex` runner
result, not the `copilot` runner.

The scope of the confirmed non-loading behavior is the `-p` programmatic
path only. IDE Chat and inline completion are documented by GitHub to
auto-load the instruction files, and the CLI interactive (TUI) mode is
not yet tested. The shipped `agent-style enable copilot` (repo-wide)
and `enable copilot-path` (path-scoped for `.md`/`.tex`/`.rst`/`.txt`)
adapters target those loading paths, but we have not smoke-tested
them end to end; a full verification matrix is pending and tracked in
`TODO.md` at the repository root under "Copilot instruction-loading
verification". Until that verification
completes, do not overclaim in downstream
docs (for example, an awesome-copilot PR description) that "IDE users
are unaffected" — the accurate claim is "CLI `-p` mode is confirmed not
to load; IDE and interactive CLI paths are documented by GitHub but not
yet end-to-end smoke tested by us."

### Gemini model selection (Pro quota warning)

`--model pro` (Gemini 3.1 Pro) typically fails mid-run with
`RetryableQuotaError: No capacity available for model
gemini-3.1-pro-preview on the server` on a 40-call bench run
(`--generations 2` × 10 tasks × 2 conditions). A 22-hour rolling quota
window is enforced at the subscription level (Google One AI Pro) and
agent-style's bench burns the remaining quota well before the 40th
call. `--model flash` (Gemini 3 Flash) has a substantially higher limit
and completes the 40-call matrix comfortably; it is the default and
recommended Gemini leg for a v0.3.0+ release bench. A pro run can be
spliced in after the quota window resets if flagship data is required,
but plan for a 24-hour cooldown between attempts.

### Invocation

```bash
# Full 4-runner local matrix, publication-quality (--generations 2).
# Adds --keep-scratch so drafts survive for eyeballs and evidence.
mkdir -p /tmp/as-bench-drafts
for runner_model in \
    'claude:claude-opus-4-7' \
    'copilot:gpt-5.4' \
    'codex:gpt-5.4' \
    'gemini:gemini-2.5-pro'; do
  runner="${runner_model%%:*}"
  model="${runner_model##*:}"
  bash scripts/bench/run.sh \
    --runner "$runner" \
    --model "$model" \
    --generations 2 \
    --keep-scratch \
    --output "docs/bench-<VERSION>-${runner}.md" &
done
wait

# Aggregate 4-leg matrix into docs/bench-<VERSION>.md
python scripts/bench/aggregate.py \
  --version <VERSION> \
  --output docs/bench-<VERSION>.md \
  docs/bench-<VERSION>-claude.md \
  docs/bench-<VERSION>-copilot.md \
  docs/bench-<VERSION>-codex.md \
  docs/bench-<VERSION>-gemini.md
```

`--generations 2` matches the published v0.2.0 methodology (10 tasks × 2 conditions × 2 generations = 40 calls per runner). `--generations 1` is a half-rate smoke for quick iteration on bench code changes.

### After the local run completes

1. **Collect scorecards**. Four `docs/bench-<VERSION>-{claude,copilot,codex,gemini}.md` files plus the aggregated `docs/bench-<VERSION>.md`.
2. **Preserve drafts**. Each runner's `--keep-scratch` path is printed on completion (e.g., `/tmp/as-bench-keep-XXXXXX/`). Move them under `docs/bench-<VERSION>-drafts/<runner>/` and commit, so every published number has the exact prose behind it.
3. **Review per-model results honestly.** Archive uninformative legs under `docs/bench-<VERSION>-<runner>-archive.md` with a short note rather than dropping them from the tree. The v0.2.0 pattern: Claude Opus baseline was AI-tell-heavy and dropped -47%; GPT-5.4 baseline was already clean and moved -23%; Gemini baseline was already clean and moved +13% (noise). Copilot (added in v0.3.0) patterns with the GPT-5.4 side.
4. **Commit the aggregated scorecard** to `docs/bench-<VERSION>.md`. If regenerating the README bench figure, re-render `docs/bench.png` from `docs/hero-source/bench.html` at 3x DPI and commit.
5. **Update README caption** to reflect which models are headlined.

### When a bench run fails mid-run

- **Single-runner rerun**: just rerun that one. Runners are independent; no aggregation dependency.
- **Partial matrix aggregation**: `scripts/bench/aggregate.py` accepts any subset of per-runner scorecards as positional args — splice stale + fresh without redoing the whole matrix.
- **Subscription rate limits**: Claude Max enforces a ~5h rolling window (~80 Opus calls). One runner at `--generations 2` = 40 calls, well under the cap; two back-to-back runs may queue briefly. Serialize if you hit throttling.

## Common Gotchas

- **PyPI CDN cache**: after `twine upload`, a fresh `pip install --upgrade` may still report the previous version for 1-2 minutes. Always use `--force-reinstall --no-cache-dir` with an explicit `==X.Y.Z` for verification.
- **npm without bypass-2FA**: if the token does not have bypass-2FA enabled and you use Windows Hello, `npm publish` fails with a 403 and cannot be completed via `--otp=` (WebAuthn does not produce a 6-digit code). Regenerate the token with bypass-2FA enabled.
- **Version drift across the three files**: bumping one and forgetting another. Guard: `EXPECTED_VERSION=X.Y.Z scripts/verify-install.sh --version-only` before tag.
- **Tag-before-publish**: always tag before `twine upload` and `npm publish`. If publishing fails, adjusting a local tag is easy; retracting a published package is not (registries are immutable).
- **Rc substring leaking into final**: after bump-back from rc to final, `scripts/verify-install.sh --version-only` with `EXPECTED_VERSION` greps bundled content for stray `rc` strings. Always run this step before tag.
- **Cross-ecosystem rc versions**: PyPI `0.1.0rc1` and npm `0.1.0-rc.1` are not literal equal strings; the three-file equality check is intentionally skipped during rehearsal.

## Reference

- PyPI packaging: https://packaging.python.org/
- PEP 440 (Python version specifiers): https://peps.python.org/pep-0440/
- SemVer (npm versions): https://semver.org/
- npm publish docs: https://docs.npmjs.com/cli/v10/commands/npm-publish
- Keep a Changelog: https://keepachangelog.com/en/1.1.0/
