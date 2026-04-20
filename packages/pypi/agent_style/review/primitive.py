# SPDX-License-Identifier: MIT
"""High-level primitive entry points for audit and compare.

The primitive orchestrates:
  - loader.load_rules: find RULES.md (5-level resolution)
  - detectors_mech: regex / word-list detectors (deterministic)
  - detectors_struct: line/paragraph heuristics (deterministic)
  - detectors_sem: LLM-judge (stubbed; status "skipped" outside a skill host)

Both `audit` and `compare` emit the same per-rule violation schema so the CLI's
canonical-JSON contract is stable across invocations.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional

from agent_style.review.loader import LoadedRules, load_rules


@dataclass
class Violation:
    """One flagged instance of a rule in a file."""

    rule: str           # "RULE-01", "RULE-B", etc.
    line: int           # 1-based line number of the flagged content
    column: int         # 1-based column offset; 0 if line-level only
    excerpt: str        # the matched text, trimmed to ~120 chars
    detail: str         # short human note about why it matched


@dataclass
class RuleResult:
    """Per-rule audit result for one file."""

    rule: str
    severity: str
    detector: str               # "mechanical" | "structural" | "semantic"
    status: str                 # "ok" | "violation" | "skipped" | "error"
    count: int
    violations: list[Violation] = field(default_factory=list)
    note: str = ""              # populated for status "skipped" / "error"


@dataclass
class AuditResult:
    """Full audit of one file."""

    file: str
    rules_source: str
    rules_path: Optional[str]
    total_violations: int
    rule_results: list[RuleResult] = field(default_factory=list)


@dataclass
class CompareResult:
    """A/B comparison of two files."""

    file_a: str
    file_b: str
    rules_source: str
    rules_path: Optional[str]
    per_rule_delta: dict[str, dict[str, int]]   # {rule_id: {"a": n_a, "b": n_b, "delta": n_b - n_a}}
    total_a: int
    total_b: int


def audit(
    file_path: str,
    project_root: str = ".",
    mechanical_only: bool = False,
    audit_only: bool = True,
    skill_host: bool = False,
) -> AuditResult:
    """Run the deterministic (and optionally semantic) audit on one file.

    Outside a skill host (``skill_host=False``), semantic detectors are reported
    as ``status="skipped"``. Polish is never available from the primitive path;
    the CLI handles the --polish flag separately.

    If ``mechanical_only`` is True, structural detectors are also skipped
    (emitted as ``status="skipped"``). This mode is used by ``--cli-parity`` as
    the deterministic oracle.
    """
    rules = load_rules(project_root=project_root)
    text = _read_utf8(file_path)
    rule_results: list[RuleResult] = []
    total = 0

    # Lazy-import detectors to keep load_rules-only callers cheap.
    from agent_style.review import detectors_mech, detectors_struct, detectors_sem

    for rule in rules.rules:
        bucket = _classify(rule.id)
        if "mechanical" in bucket:
            result = detectors_mech.run(rule, text, file_path)
            rule_results.append(result)
            total += result.count
        if "structural" in bucket:
            if mechanical_only:
                rule_results.append(
                    RuleResult(
                        rule=rule.id,
                        severity=rule.severity,
                        detector="structural",
                        status="skipped",
                        count=0,
                        note="structural detectors disabled (--mechanical-only)",
                    )
                )
            else:
                result = detectors_struct.run(rule, text, file_path)
                rule_results.append(result)
                total += result.count
        if "semantic" in bucket:
            if mechanical_only or not skill_host:
                rule_results.append(
                    RuleResult(
                        rule=rule.id,
                        severity=rule.severity,
                        detector="semantic",
                        status="skipped",
                        count=0,
                        note=(
                            "semantic detectors require a skill host "
                            "(Claude Code or Anthropic Skills); "
                            "run /style-review via one of those hosts to include semantic rules"
                        ),
                    )
                )
            else:
                result = detectors_sem.run(rule, text, file_path)
                rule_results.append(result)
                total += result.count

    return AuditResult(
        file=file_path,
        rules_source=rules.rules_source,
        rules_path=rules.source_path,
        total_violations=total,
        rule_results=rule_results,
    )


def compare(
    file_a: str,
    file_b: str,
    project_root: str = ".",
    mechanical_only: bool = True,
    skill_host: bool = False,
) -> CompareResult:
    """Audit two files and compute per-rule violation deltas.

    Compare defaults to ``mechanical_only=True`` because benchmark / --cli-parity
    use cases need deterministic counts. Callers who want the semantic delta can
    set ``mechanical_only=False`` and ``skill_host=True``.
    """
    a = audit(file_a, project_root=project_root, mechanical_only=mechanical_only, skill_host=skill_host)
    b = audit(file_b, project_root=project_root, mechanical_only=mechanical_only, skill_host=skill_host)
    # Aggregate counts by rule ID across ALL buckets (mechanical + structural +
    # semantic). A rule that shows up in two buckets (e.g., RULE-05 has
    # mechanical + semantic) sums to a single per-rule count.
    per_rule: dict[str, dict[str, int]] = {}
    for ra in a.rule_results:
        row = per_rule.setdefault(ra.rule, {"a": 0, "b": 0, "delta": 0})
        row["a"] += ra.count
    for rb in b.rule_results:
        row = per_rule.setdefault(rb.rule, {"a": 0, "b": 0, "delta": 0})
        row["b"] += rb.count
    for row in per_rule.values():
        row["delta"] = row["b"] - row["a"]
    return CompareResult(
        file_a=file_a,
        file_b=file_b,
        rules_source=a.rules_source,
        rules_path=a.rules_path,
        per_rule_delta=per_rule,
        total_a=a.total_violations,
        total_b=b.total_violations,
    )


# ---------- Rule classification ---------------------------------------------
# Per Rev 3 detector matrix in PLAN-style-review.md. Each rule can have
# multiple buckets; both run for an audit and their counts aggregate.

_CLASSIFICATION: dict[str, set[str]] = {
    "RULE-01": {"semantic"},
    "RULE-02": {"structural", "semantic"},
    "RULE-03": {"semantic"},
    "RULE-04": {"semantic"},
    "RULE-05": {"mechanical", "semantic"},
    "RULE-06": {"mechanical", "semantic"},
    "RULE-07": {"structural"},
    "RULE-08": {"semantic"},
    "RULE-09": {"structural"},
    "RULE-10": {"structural"},
    "RULE-11": {"semantic"},
    "RULE-12": {"mechanical"},
    "RULE-A": {"structural"},
    "RULE-B": {"mechanical"},
    "RULE-C": {"structural"},
    "RULE-D": {"mechanical"},
    "RULE-E": {"structural"},
    "RULE-F": {"semantic"},
    "RULE-G": {"mechanical"},
    "RULE-H": {"semantic"},
    "RULE-I": {"mechanical"},
}


def _classify(rule_id: str) -> set[str]:
    return _CLASSIFICATION.get(rule_id, set())


def _read_utf8(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()
