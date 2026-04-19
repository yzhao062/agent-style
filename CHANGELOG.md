<!-- SPDX-License-Identifier: CC-BY-4.0 -->

# Changelog

All notable changes to *The Elements of Agent Style* are documented here.

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Semantic Versioning: [SemVer 2.0.0](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Phase 1b validator drop: full bodies for RULE-01 (curse of knowledge) and RULE-05 (dying metaphors) in `RULES.md`. Each includes metadata (source, agent-instruction evidence, severity, scope, enforcement tier), directive, 4-5 BAD/GOOD example pairs with technical content from ML / API / LLM-alignment domains, and rationale-for-AI-agent explaining the LLM-specific failure mode. The two rules exercise both phrasing styles: RULE-01 carries a negative directive about a judgment-call anti-pattern (Tier-3/4 enforcement only); RULE-05 carries a negative directive about a pattern-matchable anti-pattern (Tier-1 deny via phrase list). Remaining 10 rules follow the same format in the next drop.

---

[Unreleased]: https://github.com/yzhao062/elements-of-agent-style/compare/main...HEAD
