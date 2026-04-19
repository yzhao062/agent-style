# SPDX-License-Identifier: MIT
"""Registry: loads and validates tools.json, exposes bundled data paths.

The registry is the single source of truth for supported tools and their install modes.
Both Python and Node CLIs load the same tools.json (shipped in each package's bundled data).
"""

from __future__ import annotations

import json
import os
from typing import Any


REQUIRED_FIELDS = {"install_mode", "target_path", "adapter_source", "load_class"}
VALID_MODES = {"import-marker", "append-block", "owned-file", "multi-file-required", "print-only"}


class RegistryError(Exception):
    """Raised when tools.json is malformed or inconsistent."""


class Registry:
    """Loads bundled tools.json and provides lookup helpers."""

    def __init__(self) -> None:
        self.data_dir = self._find_data_dir()
        self.tools_json_path = os.path.join(self.data_dir, "tools.json")
        self.rules_md_path = os.path.join(self.data_dir, "RULES.md")
        self._raw = self._load_tools_json()
        self.schema_version = int(self._raw.get("schema_version", 0))
        self.agent_style_version = str(self._raw.get("agent_style_version", ""))
        self.tools: dict[str, dict[str, Any]] = self._raw.get("tools", {})
        self._validate()

    def _find_data_dir(self) -> str:
        """Locate the bundled data directory next to this module."""
        here = os.path.dirname(os.path.abspath(__file__))
        candidate = os.path.join(here, "data")
        if not os.path.isdir(candidate):
            raise RegistryError(
                f"bundled data directory not found at {candidate}; "
                "is the package installed correctly?"
            )
        return candidate

    def _load_tools_json(self) -> dict[str, Any]:
        with open(self.tools_json_path, encoding="utf-8") as fh:
            return json.load(fh)

    def _validate(self) -> None:
        if self.schema_version != 1:
            raise RegistryError(
                f"tools.json schema_version {self.schema_version} not supported; "
                "expected 1"
            )
        for name, spec in self.tools.items():
            missing = REQUIRED_FIELDS - set(spec.keys())
            if missing:
                raise RegistryError(
                    f"tool {name!r} in tools.json is missing required fields: {sorted(missing)}"
                )
            mode = spec["install_mode"]
            if mode not in VALID_MODES:
                raise RegistryError(
                    f"tool {name!r} has invalid install_mode {mode!r}; "
                    f"expected one of {sorted(VALID_MODES)}"
                )

    def get(self, tool: str) -> dict[str, Any]:
        """Return the spec for a tool, or raise RegistryError if unknown."""
        if tool not in self.tools:
            raise RegistryError(
                f"unknown tool {tool!r}; run `agent-style list-tools` to see supported tools"
            )
        return self.tools[tool]

    def read_bundled_rules(self) -> str:
        """Return the bundled RULES.md content as a string."""
        with open(self.rules_md_path, encoding="utf-8") as fh:
            return fh.read()

    def read_adapter(self, adapter_source: str) -> str:
        """Return the adapter file content as a string, given its relative data path."""
        p = os.path.join(self.data_dir, adapter_source)
        with open(p, encoding="utf-8") as fh:
            return fh.read()
