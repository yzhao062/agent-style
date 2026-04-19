<!-- SPDX-License-Identifier: CC-BY-4.0 -->

# Changelog

All notable changes to *The Elements of Agent Style* are documented here.

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Semantic Versioning: [SemVer 2.0.0](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Phase 1b full draft: bodies for all 12 canonical rules (RULE-01 through RULE-12) plus 9 field-observed rules (RULE-A through RULE-I) in `RULES.md`. Canonical rules are distilled from Strunk & White, Orwell, Pinker, and Gopen & Swan, with citations verified page-by-page. Field-observed rules come from the maintainer's observation of LLM output across research papers, grant proposals, technical documentation, and agent-configuration work 2022 to 2026, covering bullet-point overuse (A), em/en-dash overuse (B), consecutive same-starts (C), transition-word overuse (D), paragraph-closing summaries (E), term consistency (F), title case for headings (G), citation discipline including anti-hallucination (H, critical), and contraction register (I). Each rule block includes metadata (source, agent-instruction evidence citing Zhang et al. 2026 and Bohr 2025 with narrowed claims, severity per the four-level rubric, scope, enforcement tier), directive (negative for anti-pattern rules; positive for constructive-placement rules), 5 or more BAD/GOOD example pairs with at least one non-paper context, and rationale-for-AI-agent framing the LLM-specific failure mode.
- README rewrite: tagline "Make your AI agent write like a tech pro.", added Before/After demo section, separated rules into Canonical (RULE-01..12) and Field-Observed (RULE-A..I) tables, moved Canonical Sources toward the bottom, dropped the Related section, applied title case to all section headings.
- Slug rename: repo `elements-of-agent-style` renamed to `agent-style` (GitHub + PyPI + npm names consistent; title "The Elements of Agent Style" preserved).
- Codex Round 3 validator review complete; findings addressed in-place. High-severity finding: RULE-H GOOD-example citations rewritten against verified references (ColBERT MRR@10 rather than recall@10; Liu et al. TACL rather than NAACL; Dsouza et al. 2024 for GPT-4/Claude-3 lost-in-the-middle replication; SimCLR 76.5% linear-probe claim corrected). Medium: field-observed rules B-I now carry the Round-2-narrowed Zhang/Bohr wording (RULE-G and RULE-I include the positive-directive exception clause). Reopened markdownlint blocker resolved (13 rewrites: table separators, double-backtick wrapping for inline-code examples with nested backticks, H3 insertion between H2 and RULE-A, fence labels on RULE-A BAD code blocks).
- Repo structure: `examples/` folder dropped (redundant with the 5-6 BAD/GOOD pairs already in each rule body); license tables in `README.md` and `NOTICE.md` updated accordingly.

---

[Unreleased]: https://github.com/yzhao062/agent-style/compare/main...HEAD
