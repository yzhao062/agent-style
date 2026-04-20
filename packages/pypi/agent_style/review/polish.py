# SPDX-License-Identifier: MIT
"""Polish stub: the revision pass requires a skill host.

The CLI's --polish flag handler calls ``check_host_and_raise`` before doing any
work. Outside a Claude Code / Anthropic Skills context, we error early with an
actionable message rather than attempting an API-key-backed call.

The full polish implementation lives in the skill (`as/skills/style-review/`)
which composes the revision prompt from ``references/revision-prompt.md`` and
calls the host model. This module exists so the Python API and JSON output
contract remain consistent.
"""

from __future__ import annotations


class PolishNotAvailableError(RuntimeError):
    """Raised when --polish is requested outside a skill host."""


def check_host_and_raise() -> None:
    """Unconditionally raise. Polish from the plain CLI is not supported."""
    raise PolishNotAvailableError(
        "polish is only available inside a skill host (Claude Code or Anthropic Skills); "
        "run /style-review from one of those hosts. "
        "For a deterministic audit without polish, use "
        "`agent-style review --audit-only <file>`."
    )
