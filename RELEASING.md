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
| `bench.yml` (cheap default) | manual | ~$0.45 | `confirm="run"` + Sonnet 4.6 / Gemini Flash / GPT-5.4 Nano defaults |
| `bench.yml` (flagship inputs) | manual | **~$2.20-$2.50** | requires explicit `claude_model=claude-opus-4-7` override |
| `bench.yml` (single runner) | manual | $0-$2.00 | `runners=<one>` skips aggregation |
| `adapter-aider-smoke.yml` | manual | ~$0.10 | Sonnet 4.6 via Aider |
| `adapter-gemini-smoke.yml` | manual | $0 (Flash free tier) | — |
| `adapter-agents-sdk-smoke.yml` | manual | ~$0.01 | GPT-5.4 Nano |

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
| `bench` on 2-3 major/minor releases (flagship tier) | ~$5-$7.50 |
| Ad-hoc adapter smokes during debugging | ~$0-$5 |
| **Total** | **~$5-$15** |

v0.2.0 dev-cycle reality check: ~$2.45 on bench work (one flagship matrix at
$2.35 + one Gemini-only rerun at $0.10) plus ~$0.10-$0.20 on adapter-smoke
validation. Total v0.2.0 CI spend: ~$2.55-$2.65.

## Bench (Major/Minor Releases Only)

The 3-model matrix bench (`.github/workflows/bench.yml`) is **opt-in** and **expensive**. Dispatch only on major / minor releases (v0.3.0, v0.4.0, v1.0.0). **Do not** dispatch on patch releases (v0.2.1, v0.2.2). Per-release mechanical correctness is already covered by `real-agent-smoke.yml` (~$0.04 per release, auto-triggered on `release: published`); `bench.yml` exists to produce publication-quality behavioral data for the README figure and deserves human judgment each time.

### Cost (measured on 2026-04-21 billing, 40 calls per model per matrix leg)

| Dispatch mode | What you get | Approx cost |
|---|---|---|
| `runners=all`, default cheap-tier inputs | Sonnet 4.6 / Gemini Flash / GPT-5.4 Nano matrix — regression check | ~$0.45 |
| `runners=all`, flagship override inputs | Opus 4.7 / Gemini Pro / GPT-5.4 matrix — **publication-quality data** | **~$2.20–$2.50** |
| `runners=<one>`, any model | Single-leg rerun — for cheap targeted validation after a fix | $0–$2.00 |

### Cadence

```bash
# One dispatch per major/minor release, flagship-tier inputs.
# Expects: ANTHROPIC_API_KEY, GEMINI_API_KEY, OPENAI_API_KEY as repo secrets.
gh workflow run bench.yml \
  --repo yzhao062/agent-style --ref main \
  -f confirm=run \
  -f runners=all \
  -f install_from=branch \
  -f claude_model=claude-opus-4-7 \
  -f gemini_model=gemini-2.5-pro \
  -f openai_model=gpt-5.4
```

### After the dispatch completes

1. **Download artifacts** (per-runner scorecards + aggregated combined scorecard) from the workflow run.
2. **Review per-model results honestly.** Not every model will show a strong reduction — publish what you actually observed. The v0.2.0 run showed Claude Opus at −47%, GPT-5.4 at −23%, and Gemini Pro at +13% (noise on a clean baseline). Archive uninformative legs under `docs/bench-<VERSION>-<runner>-archive.md` with a short note rather than dropping them from the tree.
4. **Commit the combined scorecard** to `docs/bench-<VERSION>.md`. If you are regenerating the README bench figure, re-render `docs/bench.png` from `docs/hero-source/bench.html` at 3x DPI and commit.
5. **Update README caption** to reflect which models are headlined.

### When a bench dispatch fails mid-run

- **Gemini-only rerun after a fix**: use `-f runners=gemini` — ~$0 on free Flash tier, ~$0.10 on Pro. Aggregation is skipped in single-runner mode.
- **Splicing stale + fresh data**: `scripts/bench/aggregate.py` accepts N arbitrary `bench-<version>-<runner>.md` files as positional args. Download the still-valid artifacts from the prior run, the fresh ones from the rerun, and run aggregate locally — no need to redispatch a full matrix just to regenerate a combined scorecard.

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
