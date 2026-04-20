# SPDX-License-Identifier: MIT
"""agent_style.review: deterministic review primitive for the style-review skill.

This module implements the deterministic half of the style-review workflow:
mechanical and structural detection against agent-style's own rules.

Semantic detection (RULE-01, RULE-03, RULE-04, RULE-08, RULE-11, RULE-F, RULE-H)
requires an LLM judge and is only available from a skill host (Claude Code,
Anthropic Skills) that provides the model. The plain CLI surfaces these as
`status: "skipped"` rather than attempting them.

Public entry points:

    from agent_style.review import audit, compare

    result = audit("DESIGN.md", mechanical_only=False)
    delta = compare("baseline.md", "treatment.md", mechanical_only=True)

The CLI subcommand (`agent-style review`) and the scoring wrapper
(`as/scripts/score.py`) both call these entry points.
"""

from __future__ import annotations

from agent_style.review.loader import load_rules, RulesLoadError
from agent_style.review.primitive import audit, compare, AuditResult, CompareResult

__all__ = [
    "audit",
    "compare",
    "load_rules",
    "RulesLoadError",
    "AuditResult",
    "CompareResult",
]
