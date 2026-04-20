# SPDX-License-Identifier: MIT
"""Fixture-driven tests for the review primitive.

Each fixture in `data/skills/style-review/references/fixture-prose/` ships with
a `<name>.expected.json` sibling that documents the expected per-rule violation
count produced by the deterministic (mechanical + structural) detectors. This
test loads every fixture, runs the audit, and asserts the counts match exactly.

These tests are the contract for "detector behavior does not regress silently."
If a detector changes, the expected.json must change with it.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from agent_style.review import audit


FIXTURES_DIR = (
    Path(__file__).parent.parent
    / "agent_style"
    / "data"
    / "skills"
    / "style-review"
    / "references"
    / "fixture-prose"
)


def _list_fixtures():
    """Yield (fixture_path, expected_path) pairs for every fixture on disk."""
    if not FIXTURES_DIR.is_dir():
        pytest.skip(f"fixtures directory missing: {FIXTURES_DIR}")
    for md in sorted(FIXTURES_DIR.glob("*.md")):
        expected = md.with_suffix(".expected.json")
        if expected.is_file():
            yield md, expected


@pytest.mark.parametrize(
    "fixture_md,expected_json",
    [pytest.param(md, ex, id=md.name) for md, ex in _list_fixtures()],
)
def test_audit_matches_expected(fixture_md: Path, expected_json: Path) -> None:
    """Audit each fixture; per-rule counts must equal expected.json."""
    expected = json.loads(expected_json.read_text(encoding="utf-8"))
    result = audit(str(fixture_md), mechanical_only=False, skill_host=False)

    # Total
    assert result.total_violations == expected["total_violations"], (
        f"{fixture_md.name}: expected {expected['total_violations']} total "
        f"violations, got {result.total_violations}"
    )

    # Per-rule aggregated counts (sum across all buckets for the same rule id).
    actual_counts: dict[str, int] = {}
    for rr in result.rule_results:
        if rr.count > 0:
            actual_counts[rr.rule] = actual_counts.get(rr.rule, 0) + rr.count
    expected_counts = expected["per_rule_count"]

    assert actual_counts == expected_counts, (
        f"{fixture_md.name}: per-rule count mismatch.\n"
        f"  expected: {sorted(expected_counts.items())}\n"
        f"  actual:   {sorted(actual_counts.items())}"
    )

    # Semantic / deferred-structural rules must all report status "skipped"
    # so the JSON schema is complete for the whole matrix.
    skipped_ids = {rr.rule for rr in result.rule_results if rr.status == "skipped"}
    for rid in expected.get("expected_skipped_rules", []):
        assert rid in skipped_ids, (
            f"{fixture_md.name}: expected rule {rid} to be skipped but it was not"
        )


def test_clean_control_has_zero_violations() -> None:
    """Explicit regression guard: clean-control must stay at zero."""
    fixture = FIXTURES_DIR / "clean-control.md"
    if not fixture.is_file():
        pytest.skip(f"fixture missing: {fixture}")
    result = audit(str(fixture), mechanical_only=False, skill_host=False)
    triggered = [
        (rr.rule, rr.detector, rr.count)
        for rr in result.rule_results
        if rr.status == "violation"
    ]
    assert triggered == [], (
        f"clean-control.md produced unexpected violations: {triggered}"
    )


def test_messy_real_world_fenced_code_not_flagged() -> None:
    """Regression guard: `leverages` inside a fenced code block must NOT fire RULE-06."""
    fixture = FIXTURES_DIR / "messy-real-world.md"
    if not fixture.is_file():
        pytest.skip(f"fixture missing: {fixture}")
    result = audit(str(fixture), mechanical_only=False, skill_host=False)
    for rr in result.rule_results:
        if rr.rule == "RULE-06":
            assert rr.count == 0, (
                f"RULE-06 fired on fenced-code fixture: {[v.excerpt for v in rr.violations]}"
            )


def test_audit_only_mode_excludes_semantic() -> None:
    """audit(..., skill_host=False) must skip every semantic rule."""
    fixture = FIXTURES_DIR / "mixed.md"
    if not fixture.is_file():
        pytest.skip(f"fixture missing: {fixture}")
    result = audit(str(fixture), mechanical_only=False, skill_host=False)
    semantic_violations = [
        rr for rr in result.rule_results
        if rr.detector == "semantic" and rr.status == "violation"
    ]
    assert semantic_violations == [], (
        f"semantic detectors should never produce violations without a skill host: "
        f"{[rr.rule for rr in semantic_violations]}"
    )


def test_mechanical_only_excludes_structural() -> None:
    """mechanical_only=True must skip every structural and semantic rule."""
    fixture = FIXTURES_DIR / "mixed.md"
    if not fixture.is_file():
        pytest.skip(f"fixture missing: {fixture}")
    result = audit(str(fixture), mechanical_only=True, skill_host=False)
    leaks = [
        rr for rr in result.rule_results
        if rr.detector != "mechanical" and rr.status == "violation"
    ]
    assert leaks == [], (
        f"--mechanical-only should be the deterministic parity oracle; "
        f"non-mechanical violations leaked: {[rr.rule for rr in leaks]}"
    )
