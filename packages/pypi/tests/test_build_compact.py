# SPDX-License-Identifier: MIT
"""Regression tests for ``scripts/build-compact.py``.

The compact render is the text every consumer loads into its always-on context,
so what it keeps and what it drops is a contract. These tests pin three things:

  1. the compact omits the "Severity Rubric" section, which only explains the
     per-rule severity metadata the compact has already dropped,
  2. the compact keeps the "Escape Hatch" section, because it states how every
     other rule is meant to be applied, and
  3. the full reference (``RULES.md``) still carries the rubric.

The script needs ``markdown-it-py``, which the CI floor jobs do not install, so
the module skips when that parser is absent. The ``rule-pack-parity`` job in
``validate.yml`` installs it and covers byte-level parity of the generated files.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

pytest.importorskip("markdown_it")

# tests/ -> pypi/ -> packages/ -> repo root
REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
SCRIPT = REPO_ROOT / "scripts" / "build-compact.py"
RULES = REPO_ROOT / "RULES.md"


def _load_builder():
    spec = importlib.util.spec_from_file_location("build_compact_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def builder():
    if not SCRIPT.is_file() or not RULES.is_file():
        pytest.skip(f"missing (not a source checkout): {SCRIPT}")
    return _load_builder()


def _h2_titles(builder, text: str) -> list:
    return [h["text"] for h in builder.parse_headings(text) if h["level"] == 2]


def test_compact_omits_the_severity_rubric(builder) -> None:
    compact = builder.build_compact(builder.read_source(RULES))
    assert "Severity Rubric" not in _h2_titles(builder, compact)


def test_compact_keeps_the_escape_hatch(builder) -> None:
    compact = builder.build_compact(builder.read_source(RULES))
    assert any(t.startswith("Escape Hatch") for t in _h2_titles(builder, compact))


def test_full_reference_keeps_the_severity_rubric(builder) -> None:
    source = builder.read_source(RULES)
    assert "Severity Rubric" in _h2_titles(builder, source)
