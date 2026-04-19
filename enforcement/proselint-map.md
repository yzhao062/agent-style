<!-- SPDX-License-Identifier: MIT -->

# ProseLint rule map

Mapping between the 12 rules in `RULES.md` and the corresponding check IDs in [ProseLint](https://github.com/amperser/proselint). Use ProseLint as a Tier-2 post-hoc linter in CI to catch what the generation-time ruleset missed.

🚧 Phase 2b placeholder — draft table below; verify each ProseLint ID during Phase 2b by running `proselint --list-checks` or inspecting the ProseLint source.

| RULE | Recommended ProseLint checks |
|---|---|
| 01 curse of knowledge | (no direct ProseLint equivalent; Tier-4 Codex review) |
| 02 active voice | `leonard.exclamation.30ppm` (proxy), `misc.passive_voice` (if available) |
| 03 concrete/specific | (no direct equivalent; partial: `misc.waxed` for hollow phrases) |
| 04 omit needless words | `airlinese.misc`, `terms.denizen_labels`, `misc.phrasal_adjectives` |
| 05 dying metaphors | `misc.phrasal_adjectives`, `airlinese.misc`, `cliches.hell`, `cliches.misc` |
| 06 plain English / jargon | `airlinese.misc`, `cursing.filth`, `jargon.misc` |
| 07 affirmative form | `lexical_illusions.misc` (proxy) |
| 08 claim calibration | (no direct equivalent; Tier-4 Codex review primary) |
| 09 parallel structure | (no direct equivalent; partial: structural lints via Vale) |
| 10 keep related words close | (no direct equivalent; dependency parse needed) |
| 11 stress position | (no direct equivalent) |
| 12 long sentences / vary length | `misc.sentence_length` (custom), Vale `Microsoft.SentenceLength` |

## Usage

Install:

```bash
pip install proselint
```

Run on staged prose files:

```bash
proselint RULES.md examples/*.md
```

Configure via `.proselintrc.json` to enable the checks from this map and suppress the rest.
