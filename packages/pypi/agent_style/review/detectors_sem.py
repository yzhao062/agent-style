# SPDX-License-Identifier: MIT
"""Semantic-detector stubs.

Semantic rules (RULE-01, 03, 04, 08, 11, F, H) require an LLM judge and are only
available from a skill host (Claude Code, Anthropic Skills). The plain CLI
surfaces them as ``status="skipped"`` with an actionable note, per PLAN Rev 4.

A future implementation will invoke the host model with the rule's directive +
BAD/GOOD examples + target prose, and parse the judge's response into the same
Violation schema that the mechanical and structural detectors emit.
"""

from __future__ import annotations

from agent_style.review.loader import Rule
from agent_style.review.primitive import RuleResult


def run(rule: Rule, text: str, file_path: str) -> RuleResult:
    """Return a skipped result; semantic rules need a skill host."""
    return RuleResult(
        rule=rule.id,
        severity=rule.severity,
        detector="semantic",
        status="skipped",
        count=0,
        note=(
            "semantic detection not available from the plain CLI; "
            "run /style-review via Claude Code or Anthropic Skills "
            "to include this rule in the audit"
        ),
    )
