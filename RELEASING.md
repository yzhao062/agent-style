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
