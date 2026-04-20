# SPDX-License-Identifier: MIT
"""Registry: loads and validates tools.json, exposes bundled data paths.

The registry is the single source of truth for supported tools and their install modes.
Both Python and Node CLIs load the same tools.json (shipped in each package's bundled data).
"""

from __future__ import annotations

import json
import os
from typing import Any


# Fields required for the existing 5 install modes (schema_version 1).
LEGACY_REQUIRED_FIELDS = {"install_mode", "target_path", "adapter_source", "load_class"}

# Fields required for skill-with-references (schema_version 1, backward compatible).
SKILL_REQUIRED_FIELDS = {
    "install_mode",
    "skill_source",
    "references_source",
    "target_groups",
    "manual_step_message",
}
# Fields forbidden for skill-with-references (they belong to the legacy 5-mode shape).
SKILL_FORBIDDEN_FIELDS = {"target_path", "adapter_source", "load_class"}

LEGACY_MODES = {"import-marker", "append-block", "owned-file", "multi-file-required", "print-only"}
SKILL_MODES = {"skill-with-references"}
VALID_MODES = LEGACY_MODES | SKILL_MODES


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
            mode = spec.get("install_mode")
            if mode is None:
                raise RegistryError(
                    f"tool {name!r} in tools.json is missing 'install_mode'"
                )
            if mode not in VALID_MODES:
                raise RegistryError(
                    f"tool {name!r} has invalid install_mode {mode!r}; "
                    f"expected one of {sorted(VALID_MODES)}"
                )
            if mode in LEGACY_MODES:
                missing = LEGACY_REQUIRED_FIELDS - set(spec.keys())
                if missing:
                    raise RegistryError(
                        f"tool {name!r} uses install_mode {mode!r} and is missing required fields: "
                        f"{sorted(missing)}"
                    )
                forbidden_present = SKILL_REQUIRED_FIELDS & set(spec.keys()) - {"install_mode"}
                if forbidden_present:
                    raise RegistryError(
                        f"tool {name!r} uses install_mode {mode!r} but has skill-mode-only fields: "
                        f"{sorted(forbidden_present)}"
                    )
            elif mode in SKILL_MODES:
                missing = SKILL_REQUIRED_FIELDS - set(spec.keys())
                if missing:
                    raise RegistryError(
                        f"tool {name!r} uses install_mode {mode!r} and is missing required fields: "
                        f"{sorted(missing)}"
                    )
                forbidden_present = SKILL_FORBIDDEN_FIELDS & set(spec.keys())
                if forbidden_present:
                    raise RegistryError(
                        f"tool {name!r} uses install_mode {mode!r} but has legacy-mode-only fields: "
                        f"{sorted(forbidden_present)} (these belong to the 5-mode shape)"
                    )
                # target_groups must be a list of {target_path, surfaces} with strict schema.
                groups = spec["target_groups"]
                if not isinstance(groups, list) or not groups:
                    raise RegistryError(
                        f"tool {name!r}: target_groups must be a non-empty list"
                    )
                # Surface names must resolve to legacy-mode tools (skill-mode tools
                # cannot host other skills by construction).
                known_surface_tools = {
                    tn for tn, ts in self.tools.items()
                    if ts.get("install_mode") in LEGACY_MODES
                }
                seen_normalized: dict[str, int] = {}
                for i, g in enumerate(groups):
                    if not isinstance(g, dict) or "target_path" not in g or "surfaces" not in g:
                        raise RegistryError(
                            f"tool {name!r}: target_groups[{i}] must have 'target_path' and 'surfaces'"
                        )
                    tp = g["target_path"]
                    if not isinstance(tp, str) or not tp:
                        raise RegistryError(
                            f"tool {name!r}: target_groups[{i}].target_path must be a non-empty string"
                        )
                    if os.path.isabs(tp):
                        raise RegistryError(
                            f"tool {name!r}: target_groups[{i}].target_path {tp!r} must be relative, not absolute"
                        )
                    # Windows drive-qualified paths ("C:foo")
                    if len(tp) >= 2 and tp[1] == ":":
                        raise RegistryError(
                            f"tool {name!r}: target_groups[{i}].target_path {tp!r} must not be drive-qualified"
                        )
                    tp_parts = tp.replace("\\", "/").split("/")
                    if any(p == ".." for p in tp_parts):
                        raise RegistryError(
                            f"tool {name!r}: target_groups[{i}].target_path {tp!r} must not contain '..'"
                        )
                    surfaces = g["surfaces"]
                    if not isinstance(surfaces, list) or not surfaces:
                        raise RegistryError(
                            f"tool {name!r}: target_groups[{i}].surfaces must be a non-empty list"
                        )
                    for j, s in enumerate(surfaces):
                        if not isinstance(s, str) or not s:
                            raise RegistryError(
                                f"tool {name!r}: target_groups[{i}].surfaces[{j}] must be a non-empty string"
                            )
                        if s not in known_surface_tools:
                            raise RegistryError(
                                f"tool {name!r}: target_groups[{i}].surfaces[{j}]={s!r} does not match any "
                                f"known non-skill tool; known surfaces are {sorted(known_surface_tools)}"
                            )
                    # Normalize for uniqueness: strip leading `./` and collapse `//`.
                    norm = "/".join(p for p in tp_parts if p not in ("", "."))
                    if norm in seen_normalized:
                        raise RegistryError(
                            f"tool {name!r}: target_groups[{i}].target_path {tp!r} collides with "
                            f"target_groups[{seen_normalized[norm]}] after normalization; "
                            "combine them into a single entry and merge the surfaces lists"
                        )
                    seen_normalized[norm] = i

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
