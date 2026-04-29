<!-- SPDX-License-Identifier: MIT -->

# TODO

Known issues and improvements deferred past their original release cycle. Items move out of this file when they are resolved (with a brief commit note), not when they are merely noted.

Short-lived scratch plans (draft PR submissions, one-shot migrations) belong in `PLAN-*.md` files that are ignored by git; long-lived cross-release follow-ups belong here.

---

## Copilot instruction-loading verification (carried from v0.3.0)

**Status**: open. **Scope**: `agent-style enable copilot` / `enable copilot-path` adapters and the `copilot` bench runner in `scripts/bench/run.sh`.

### What is already confirmed (v0.3.0 evidence)

`copilot -p "$prompt" --allow-all-tools` (Copilot CLI programmatic mode) does not load `.github/copilot-instructions.md` or `.github/instructions/*.instructions.md` into the request context. The v0.3.0 bench measured 40 calls on 10 tasks, baseline 61 → treatment 63 (+3% noise), while Codex on the same GPT-5.4 backend on the same tasks measured -45%. Evidence:

- `docs/bench-0.3.0-copilot.md` (post-`--add-dir` fix clean run)
- `docs/bench-0.3.0-copilot-noisy-archive.md` (pre-fix, narration-polluted)
- `docs/bench-0.3.0-drafts/copilot/` (all 40 draft files)

### What is not yet verified

1. **IDE mode (VS Code Copilot Chat and inline completion).** GitHub documents auto-loading of both instruction-file variants for IDE paths; the `enable copilot` / `enable copilot-path` adapters are designed for this path. We have no end-to-end smoke yet.
2. **`copilot` interactive TUI mode** (bare `copilot` without `-p`). Unclear whether instructions load; some CLI users prefer the TUI over IDE.
3. **`copilot chat`, `copilot edit`, any other subcommands** (if they exist in the current release). Behavior unclear.

### Verification plan (owner: maintainer, budget: ~15 min)

#### Smoke A — IDE Chat (highest value)

1. Open VS Code in a scratch repo with Copilot extension authenticated.
2. Copy `agents/copilot-path-instructions.md` to `.github/instructions/writing-style-agent-style.instructions.md`.
3. Create empty `test.md`. With cursor in `test.md`:
4. Open Copilot Chat. Prompt: `Write a 150-word PR description for switching the session cache from in-process LRU to Redis. Include rollout plan and single biggest trade-off. Output only the PR description text, no commentary.`
5. Eyeball for em-dashes, "Additionally"/"Furthermore" openers, "leverage"/"cutting-edge" clichés, sentences over 30 words.
6. Compare by moving the instruction file aside and rerunning the same prompt.

Pass: instructed draft visibly avoids ≥2 AI-tells the baseline shows. Fail: no difference → delay awesome-copilot PR, file upstream issue.

#### Smoke B — Interactive TUI Chat (3 min)

1. Same scratch repo with `.github/copilot-instructions.md` present (`agent-style enable copilot`).
2. Run `copilot` (no flags). Ask the Smoke A prompt.
3. Eyeball as above.

#### Smoke C — Other subcommands (3 min)

1. `copilot --help` to confirm which subcommands exist (`chat`, `edit`, `review`, etc.).
2. For each non-`-p` subcommand, run a one-shot prompt targeting `test.md`.
3. Record which subcommands load instructions.

### Exit criteria

- [ ] Smoke A result recorded here + summarized in `CHANGELOG.md` Notes
- [ ] Smoke B result recorded
- [ ] Smoke C result recorded (minimum: `copilot chat` if it exists)
- [ ] `CHANGELOG.md` + `RELEASING.md` Copilot caveat updated from "CLI `-p` mode" to the specific list of loading vs non-loading entry points
- [ ] `PLAN-awesome-copilot-submission.md` PR description revised accordingly (if Smoke A passes, cite "locally smoke-tested in VS Code"; if fails, defer PR)
- [ ] If at least one non-IDE path also fails, minimal reproducer and issue filed at `github/copilot-cli`

### Decision tree

Smoke A passes → submit awesome-copilot PR with "IDE smoke-tested" claim, document remaining CLI caveats from Smokes B/C.
Smoke A fails → defer PR, file upstream issue with the exact repo layout reproducer.

### References

- GitHub Copilot CLI programmatic reference: https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-programmatic-reference
- GitHub Copilot custom instructions: https://docs.github.com/en/copilot/how-tos/copilot-cli/add-custom-instructions

---

## Hero figure — paper row polish (carried from v0.3.0)

**Status**: open. **Scope**: `docs/hero-source/hero.html` row 3 (Paper related-work section) and the rendered `docs/hero.png`.

### The issue

Row 3 shows Gemini 3 Flash on `paper-04-related-work-agent-benchmarks`, 6 → 4 violations. Prose is stiff in both conditions:

- **Baseline** has a textbook RULE-D cluster ("However... Similarly...") plus a 33-word sentence, which is good as a rule target. But the surrounding hedged prose ("BFCL provides a rigorous assessment of syntactically correct function calls but frequently lacks...") is formulaic beyond what the ruleset specifically flags.
- **Treatment** is three declarative sentences ("AgentBench provides... tau-bench focuses... BFCL specifically targets...") — clean but reads more like a spec list than related-work prose.

The row was picked (over paper-01-abstract) because both drafts name the same three benchmarks (AgentBench, BFCL, tau-bench) thanks to the prompt anchor, so the style delta is isolated from fabricated-citation noise. The paper-01 alternative had baseline invent "GraphContrast" + "0.89 AUC under 30% edge perturbation" and treatment invent "GCAD" + "18% FPR reduction" — different algorithm name and metrics, confounding the style comparison.

### Fix options

#### A — pick a crisper pair from a future bench run

Wait for v0.3.4+ bench on `paper-04` to surface a pair with:

- Same three benchmark names in both drafts (prompt anchor still holds)
- Baseline showing 2-3 clean AI-tells
- Treatment reading as natural related-work prose, not a spec list

Swap the row 3 excerpts and re-render:

```bash
python scripts/render-bench-png.py \
  --src docs/hero-source/hero.html \
  --selector .hero \
  --out docs/hero.png \
  --viewport-height 1800
```

#### B — tighten the `paper-04` prompt

Edit `scripts/bench/tasks.md` task id `paper-04-related-work-agent-benchmarks`:

- Drop the word target from 300-400 to 200-250 (shorter prose is less formulaic)
- Add "flowing paragraph structure, not enumerated list" to push back against the spec-list treatment register
- Keep the three-benchmark anchor and the no-fabricated-citation rule

Rerun the gemini-flash leg:

```bash
bash scripts/bench/run.sh --runner gemini --model flash --generations 2 \
  --keep-scratch --output docs/bench-0.3.4-gemini.md
```

Pick the new pair for the hero row and re-render.

#### C — pick a different task entirely

`grant-01-nsf-specific-aim` (Flash 19 → 7 on v0.3.0, biggest absolute drop). Caveat: the grant prompt invents a fictional CISE proposal, so baseline/treatment may still drift in content details.

`paper-02-methods-contrastive` — same algorithm-naming concern as paper-01 unless both drafts happen to invent the same name.

A new v0.3.4 task specifically designed to keep content invariant under paraphrase (survey-style summary of a canonical topic with explicit content anchors).

### What NOT to do

- **Do not synthesize a baseline/treatment pair by hand.** The whole point of switching off the v0.2.0 synthetic PR example was that real bench drafts are evidence. Any replacement must come from an actual bench run.
- **Do not mix drafts across runners.** Keep the row labeled with a single runner so the reader can trust the attribution.
- **Do not trim the treatment until it loses the three benchmark anchors.** The anchors are why this row is trustworthy.

### Exit criteria

- [ ] Hero row 3 uses a pair with prose that reads natural in both draft and revised form
- [ ] Row's delta label reflects a real per-task delta from a committed scorecard
- [ ] `docs/hero.png` re-rendered and committed alongside the hero.html change
- [ ] "FOLLOW-UP v0.3.4+" HTML comment in `docs/hero-source/hero.html` removed
- [ ] This entry moved out of `TODO.md`

### References

- Source drafts currently shown: `docs/bench-0.3.0-drafts/gemini/paper-04-related-work-agent-benchmarks-{baseline,treatment}/draft-1.md`
- Scorecard: `docs/bench-0.3.0-gemini.md` row `paper-04-related-work-agent-benchmarks`
- Task prompt: `scripts/bench/tasks.md` task id `paper-04-related-work-agent-benchmarks`

---

## PEP 639 license metadata migration (carried from v0.3.4)

**Status**: open. **Scope**: `packages/pypi/pyproject.toml` `[project]` table.

### The issue

`python -m build` on the v0.3.4 sdist/wheel emits a setuptools deprecation warning: `project.license` as a TOML table (`license = { text = "MIT AND CC-BY-4.0" }`) is deprecated. Setuptools follows PEP 639, which requires `license = "<SPDX expression>"` (a string) and adds `license-files = ["LICENSES/*.txt"]` for the file list. The setuptools deprecation hard-deadline is **2027-02-18**.

### Fix sketch

Replace the table form with the SPDX-expression form:

```toml
[project]
license = "MIT AND CC-BY-4.0"
license-files = ["agent_style/data/LICENSES/*.txt"]
```

Path is relative to `packages/pypi/pyproject.toml` (the build root for the PyPI package), not to the repo root. The repo-root `LICENSES/` directory is a sibling reference; the bundled license files used at install time live under the package dir.

Verify the build still includes the LICENSE files in the wheel and sdist; verify PyPI still renders the license metadata correctly.

### Exit criteria

- [ ] `python -m build` emits no `project.license` deprecation warning
- [ ] PyPI project page renders the license correctly after a test publish (or `twine check` passes)
- [ ] `LICENSES/` directory contents present in wheel and sdist
- [ ] This entry moved out of `TODO.md`

### References

- PEP 639: https://peps.python.org/pep-0639/
- setuptools deprecation timeline: 2027-02-18 hard error
- v0.3.4 execution-review Round 1 (Codex Low #1, 2026-04-28)

## How to add a new item

Each entry follows the same shape:

```markdown
## Short title (carried from v0.X.Y)

**Status**: open | in-progress | blocked. **Scope**: affected files or subsystems.

### The issue

One to three paragraphs. Include enough context that a reader picking this up in six months does not have to dig through git log to reconstruct intent.

### Fix options (if more than one)

Labeled A / B / C with their own trade-offs.

### What NOT to do

The footgun list. More important than the fix list for multi-maintainer repos.

### Exit criteria

Concrete checklist. Entry moves out when every box is checked.

### References

Source files, scorecards, related PLAN files, upstream issues.
```

Keep entries terse. A short-term scratch plan (draft PR submission, one-shot migration task) belongs in a gitignored `PLAN-*.md`, not here.
