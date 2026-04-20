# SPDX-License-Identifier: MIT
"""RULES.md loader with the PLAN-documented 5-level resolution order.

Resolution order (first match wins; last step is a hard failure):

1. Project-local: `.agent-style/RULES.md` in the caller's cwd (or any parent).
2. Package bundle: `importlib.resources.files("agent_style.data") / "RULES.md"`.
3. `agent-style rules` subcommand output: captures stdout if the CLI is on PATH.
4. Pinned raw URL fallback at the current package version (10s timeout).
5. Hard fail with an actionable error message.

Both Python and Node emit the same canonical `rules_source: "package-bundle"`
value when resolving from their own bundle, so the parity oracle does not see
ecosystem-specific strings.
"""

from __future__ import annotations

import os
import re
import subprocess
import urllib.request
from dataclasses import dataclass, field
from typing import Optional


RAW_URL_TEMPLATE = (
    "https://raw.githubusercontent.com/yzhao062/agent-style/v{version}/RULES.md"
)


class RulesLoadError(RuntimeError):
    """Raised when RULES.md cannot be located via any resolution step."""


@dataclass(frozen=True)
class Rule:
    """Parsed metadata for one rule from RULES.md."""

    id: str                  # e.g. "RULE-01", "RULE-B"
    title: str               # the heading text minus the ID prefix
    severity: str            # "critical" / "high" / "medium" / "low"
    scope: str               # raw scope line
    source: str              # source citation
    directive: str           # the Directive block body
    bad_good_pairs: list[tuple[str, str]] = field(default_factory=list)
    rationale: str = ""


@dataclass(frozen=True)
class LoadedRules:
    """Result of a successful load."""

    text: str                 # the full RULES.md text
    rules: list[Rule]         # parsed rule metadata in file order
    rules_source: str         # "project-local" | "package-bundle" | "subcommand" | "raw-url"
    source_path: Optional[str]  # filesystem path when known, else None


def load_rules(
    project_root: str = ".",
    prefer_project_local: bool = True,
    package_version: Optional[str] = None,
) -> LoadedRules:
    """Load and parse RULES.md via the documented resolution order.

    Raises RulesLoadError with an actionable message if every step fails.
    """
    attempts: list[tuple[str, Optional[str]]] = []

    if prefer_project_local:
        p = _find_project_local(project_root)
        if p is not None:
            text = _read_file(p)
            return LoadedRules(
                text=text,
                rules=parse_rules(text),
                rules_source="project-local",
                source_path=p,
            )
        attempts.append(("project-local", "not found"))

    # Step 2: package bundle
    try:
        from importlib import resources
        bundle_file = resources.files("agent_style.data") / "RULES.md"
        text = bundle_file.read_text(encoding="utf-8")
        # Try to surface a filesystem path for debuggability (works for most layouts)
        try:
            with resources.as_file(bundle_file) as fs_path:
                path_str = str(fs_path)
        except Exception:
            path_str = None
        return LoadedRules(
            text=text,
            rules=parse_rules(text),
            rules_source="package-bundle",
            source_path=path_str,
        )
    except Exception as exc:  # noqa: BLE001
        attempts.append(("package-bundle", str(exc)))

    # Step 3: agent-style rules subcommand
    text = _try_subcommand()
    if text is not None:
        return LoadedRules(
            text=text,
            rules=parse_rules(text),
            rules_source="subcommand",
            source_path=None,
        )
    attempts.append(("subcommand", "agent-style rules not on PATH or failed"))

    # Step 4: pinned raw URL
    if package_version is None:
        try:
            from agent_style import __version__
            package_version = __version__
        except Exception:  # noqa: BLE001
            package_version = None
    if package_version:
        url = RAW_URL_TEMPLATE.format(version=package_version)
        text = _try_url(url, timeout=10.0)
        if text is not None:
            return LoadedRules(
                text=text,
                rules=parse_rules(text),
                rules_source="raw-url",
                source_path=url,
            )
        attempts.append((f"raw-url ({url})", "fetch failed or 404"))

    # Step 5: hard fail
    attempt_summary = "; ".join(f"{step}: {detail}" for step, detail in attempts)
    raise RulesLoadError(
        "RULES.md not found via any resolution step. "
        "Install agent-style via `pip install agent-style` or `npm install -g agent-style`, "
        "or place RULES.md at .agent-style/RULES.md in this project. "
        f"Tried: {attempt_summary}"
    )


def _find_project_local(project_root: str) -> Optional[str]:
    """Walk up from project_root looking for .agent-style/RULES.md."""
    here = os.path.abspath(project_root)
    prev = None
    while here and here != prev:
        candidate = os.path.join(here, ".agent-style", "RULES.md")
        if os.path.isfile(candidate):
            return candidate
        prev = here
        here = os.path.dirname(here)
    return None


def _read_file(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _try_subcommand() -> Optional[str]:
    """Capture `agent-style rules` stdout if the CLI is reachable."""
    try:
        proc = subprocess.run(
            ["agent-style", "rules"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        if proc.returncode == 0 and proc.stdout and "RULE-" in proc.stdout:
            return proc.stdout
    except (FileNotFoundError, subprocess.SubprocessError):
        pass
    return None


def _try_url(url: str, timeout: float) -> Optional[str]:
    """Fetch a URL with a strict timeout; return text on 200, None otherwise."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            if resp.status == 200:
                return resp.read().decode("utf-8")
    except Exception:  # noqa: BLE001
        pass
    return None


# ---------- Rule parsing ---------------------------------------------------


_RULE_HEADING_RE = re.compile(r"^####\s+(RULE-[0-9A-I]+):\s*(.+?)\s*$", re.MULTILINE)
_META_SEVERITY_RE = re.compile(r"^-\s*\*\*severity\*\*:\s*([a-z]+)", re.MULTILINE | re.IGNORECASE)
_META_SCOPE_RE = re.compile(r"^-\s*\*\*scope\*\*:\s*(.+)$", re.MULTILINE | re.IGNORECASE)
_META_SOURCE_RE = re.compile(r"^-\s*\*\*source\*\*:\s*(.+)$", re.MULTILINE | re.IGNORECASE)
_DIRECTIVE_BLOCK_RE = re.compile(
    r"^#####\s+Directive\s*$(.*?)^#####",
    re.MULTILINE | re.DOTALL | re.IGNORECASE,
)
_RATIONALE_BLOCK_RE = re.compile(
    r"^#####\s+Rationale for AI Agent\s*$(.*?)(?=^####\s|\Z)",
    re.MULTILINE | re.DOTALL | re.IGNORECASE,
)
_BAD_GOOD_RE = re.compile(
    r"^-\s*BAD[^:]*:\s*(.+?)(?:\n-\s*GOOD[^:]*:\s*(.+?))?(?=\n-\s*(?:BAD|GOOD)|\n##|\Z)",
    re.DOTALL | re.IGNORECASE,
)


def parse_rules(text: str) -> list[Rule]:
    """Parse RULES.md into a list of Rule records (file order preserved)."""
    headings = list(_RULE_HEADING_RE.finditer(text))
    if not headings:
        return []
    rules: list[Rule] = []
    for idx, match in enumerate(headings):
        start = match.start()
        end = headings[idx + 1].start() if idx + 1 < len(headings) else len(text)
        block = text[start:end]
        rule_id = match.group(1)
        title = match.group(2).strip()
        severity = _first(_META_SEVERITY_RE, block, default="").lower()
        scope = _first(_META_SCOPE_RE, block, default="")
        source = _first(_META_SOURCE_RE, block, default="")
        directive = _first_block(_DIRECTIVE_BLOCK_RE, block, default="").strip()
        rationale = _first_block(_RATIONALE_BLOCK_RE, block, default="").strip()
        rules.append(
            Rule(
                id=rule_id,
                title=title,
                severity=severity,
                scope=scope.strip(),
                source=source.strip(),
                directive=directive,
                bad_good_pairs=[],  # detectors parse what they need; we keep this light
                rationale=rationale,
            )
        )
    return rules


def _first(pattern: re.Pattern[str], block: str, default: str = "") -> str:
    m = pattern.search(block)
    return m.group(1) if m else default


def _first_block(pattern: re.Pattern[str], block: str, default: str = "") -> str:
    m = pattern.search(block)
    return m.group(1) if m else default
