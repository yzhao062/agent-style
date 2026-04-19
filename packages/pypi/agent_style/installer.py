# SPDX-License-Identifier: MIT
"""5-mode install dispatcher for agent-style.

enable/disable dispatch by the `install_mode` field in tools.json:

- `import-marker`: marker block with an import line in an existing user instruction file
- `append-block`: marker block with compact adapter body in an existing Markdown file
- `owned-file`: agent-style-owned file; hash-signed; fail closed on tamper
- `multi-file-required`: owned adapter + printed config snippet; manual step required
- `print-only`: owned adapter + printed content to stdout; manual step required

All modes support dry-run and return a canonical-JSON-shaped result dict.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from typing import Any

from agent_style import __version__
from agent_style.markers import find_block, upsert_block, remove_block, MarkerParseError
from agent_style.owned_file import sign, verify, extract_signature, compute_hash, strip_signature, OwnedFileError
from agent_style.registry import Registry


AGENT_STYLE_DIR = ".agent-style"
RULES_FILENAME = "RULES.md"


def _to_posix(path: str) -> str:
    """Return a POSIX-relative path string for canonical JSON output."""
    return path.replace(os.sep, "/")


def _read_or_none(path: str) -> str | None:
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _content_hash(content: str | None) -> str | None:
    if content is None:
        return None
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _ensure_agent_style_dir(project_root: str, registry: Registry, dry_run: bool) -> list[dict[str, Any]]:
    """Create `.agent-style/RULES.md` and the per-tool adapter copy; return actions."""
    actions: list[dict[str, Any]] = []
    agent_dir = os.path.join(project_root, AGENT_STYLE_DIR)
    rules_target = os.path.join(agent_dir, RULES_FILENAME)
    bundled_rules = registry.read_bundled_rules()
    before = _read_or_none(rules_target)
    if before != bundled_rules:
        if not dry_run:
            os.makedirs(agent_dir, exist_ok=True)
            with open(rules_target, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(bundled_rules)
        actions.append(
            {
                "order": len(actions),
                "op": "create" if before is None else "owned-file-write",
                "path": _to_posix(os.path.relpath(rules_target, project_root)),
                "content_sha256_before": _content_hash(before),
                "content_sha256_after": _content_hash(bundled_rules),
            }
        )
    return actions


def _copy_bundled_adapter(
    project_root: str, registry: Registry, adapter_source: str, dest_rel: str, dry_run: bool
) -> dict[str, Any]:
    """Copy a bundled adapter file under .agent-style/; return the action."""
    agent_dir = os.path.join(project_root, AGENT_STYLE_DIR)
    dest = os.path.join(agent_dir, dest_rel)
    adapter_body = registry.read_adapter(adapter_source)
    before = _read_or_none(dest)
    if before == adapter_body:
        return {
            "order": 0,
            "op": "owned-file-write",
            "path": _to_posix(os.path.relpath(dest, project_root)),
            "content_sha256_before": _content_hash(before),
            "content_sha256_after": _content_hash(adapter_body),
            "noop": True,
        }
    if not dry_run:
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(adapter_body)
    return {
        "order": 0,
        "op": "owned-file-write",
        "path": _to_posix(os.path.relpath(dest, project_root)),
        "content_sha256_before": _content_hash(before),
        "content_sha256_after": _content_hash(adapter_body),
    }


def _enable_import_marker(tool: str, spec: dict, registry: Registry, project_root: str, dry_run: bool) -> dict:
    actions = _ensure_agent_style_dir(project_root, registry, dry_run)
    # Copy the adapter file under .agent-style/<name>.md for the @import target.
    adapter_filename = os.path.basename(spec["adapter_source"])
    adapter_action = _copy_bundled_adapter(project_root, registry, spec["adapter_source"], adapter_filename, dry_run)
    if not adapter_action.get("noop"):
        adapter_action["order"] = len(actions)
        actions.append(adapter_action)
    # Upsert the marker block in the target instruction file.
    target = os.path.join(project_root, spec["target_path"])
    before_text = _read_or_none(target) or ""
    import_line = spec["import_line"]
    new_text, op = upsert_block(before_text, __version__, import_line)
    before_hash = _content_hash(before_text) if before_text else None
    after_hash = _content_hash(new_text)
    if before_hash != after_hash:
        if not dry_run:
            os.makedirs(os.path.dirname(target) or ".", exist_ok=True)
            with open(target, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(new_text)
        actions.append(
            {
                "order": len(actions),
                "op": op,  # "create" or "update-marker"
                "path": _to_posix(os.path.relpath(target, project_root)),
                "content_sha256_before": before_hash,
                "content_sha256_after": after_hash,
            }
        )
    return {
        "tool": tool,
        "install_mode": spec["install_mode"],
        "enabled": True,
        "manual_step_required": False,
        "actions": actions,
    }


def _enable_append_block(tool: str, spec: dict, registry: Registry, project_root: str, dry_run: bool) -> dict:
    actions = _ensure_agent_style_dir(project_root, registry, dry_run)
    target = os.path.join(project_root, spec["target_path"])
    before_text = _read_or_none(target) or ""
    body = registry.read_adapter(spec["adapter_source"])
    new_text, op = upsert_block(before_text, __version__, body)
    before_hash = _content_hash(before_text) if before_text else None
    after_hash = _content_hash(new_text)
    if before_hash != after_hash:
        if not dry_run:
            os.makedirs(os.path.dirname(target) or ".", exist_ok=True)
            with open(target, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(new_text)
        actions.append(
            {
                "order": len(actions),
                "op": op,
                "path": _to_posix(os.path.relpath(target, project_root)),
                "content_sha256_before": before_hash,
                "content_sha256_after": after_hash,
            }
        )
    return {
        "tool": tool,
        "install_mode": spec["install_mode"],
        "enabled": True,
        "manual_step_required": False,
        "actions": actions,
    }


def _enable_owned_file(tool: str, spec: dict, registry: Registry, project_root: str, dry_run: bool) -> dict:
    actions = _ensure_agent_style_dir(project_root, registry, dry_run)
    target = os.path.join(project_root, spec["target_path"])
    before_text = _read_or_none(target)
    body = registry.read_adapter(spec["adapter_source"])
    signed = sign(body, __version__)
    # If the target already exists, it must be agent-style-owned AND hash-valid.
    if before_text is not None:
        if extract_signature(before_text) is None:
            raise RuntimeError(
                f"refusing to overwrite non-agent-style file at {target!r}; "
                "move or rename that file and rerun `agent-style enable`"
            )
        try:
            verify(before_text)
        except OwnedFileError as exc:
            raise RuntimeError(
                f"agent-style owned file at {target!r} has been edited since it was written: {exc}; "
                "move your edits into a separate file, then rerun"
            )
    before_hash = _content_hash(before_text) if before_text else None
    after_hash = _content_hash(signed)
    if before_hash != after_hash:
        if not dry_run:
            os.makedirs(os.path.dirname(target) or ".", exist_ok=True)
            with open(target, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(signed)
        actions.append(
            {
                "order": len(actions),
                "op": "owned-file-write",
                "path": _to_posix(os.path.relpath(target, project_root)),
                "content_sha256_before": before_hash,
                "content_sha256_after": after_hash,
            }
        )
    return {
        "tool": tool,
        "install_mode": spec["install_mode"],
        "enabled": True,
        "manual_step_required": False,
        "actions": actions,
    }


def _enable_multi_file_required(tool: str, spec: dict, registry: Registry, project_root: str, dry_run: bool) -> dict:
    """Write the compact adapter under .agent-style/; emit a snippet action for the second file."""
    actions = _ensure_agent_style_dir(project_root, registry, dry_run)
    # Target is `.agent-style/<adapter-name>`.
    target = os.path.join(project_root, spec["target_path"])
    body = registry.read_adapter(spec["adapter_source"])
    before_text = _read_or_none(target)
    before_hash = _content_hash(before_text)
    after_hash = _content_hash(body)
    if before_hash != after_hash:
        if not dry_run:
            os.makedirs(os.path.dirname(target) or ".", exist_ok=True)
            with open(target, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(body)
        actions.append(
            {
                "order": len(actions),
                "op": "owned-file-write",
                "path": _to_posix(os.path.relpath(target, project_root)),
                "content_sha256_before": before_hash,
                "content_sha256_after": after_hash,
            }
        )
    snippet = spec.get("second_file_snippet", "")
    actions.append(
        {
            "order": len(actions),
            "op": "print-snippet",
            "path": _to_posix(os.path.relpath(target, project_root)),
            "content_sha256_before": None,
            "content_sha256_after": _content_hash(snippet),
            "snippet": snippet,
        }
    )
    return {
        "tool": tool,
        "install_mode": spec["install_mode"],
        "enabled": False,
        "manual_step_required": True,
        "actions": actions,
    }


def _enable_print_only(tool: str, spec: dict, registry: Registry, project_root: str, dry_run: bool) -> dict:
    """Write the adapter under .agent-style/; emit a print-prompt action for stdout."""
    actions = _ensure_agent_style_dir(project_root, registry, dry_run)
    target = os.path.join(project_root, spec["target_path"])
    body = registry.read_adapter(spec["adapter_source"])
    before_text = _read_or_none(target)
    before_hash = _content_hash(before_text)
    after_hash = _content_hash(body)
    if before_hash != after_hash:
        if not dry_run:
            os.makedirs(os.path.dirname(target) or ".", exist_ok=True)
            with open(target, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(body)
        actions.append(
            {
                "order": len(actions),
                "op": "owned-file-write",
                "path": _to_posix(os.path.relpath(target, project_root)),
                "content_sha256_before": before_hash,
                "content_sha256_after": after_hash,
            }
        )
    actions.append(
        {
            "order": len(actions),
            "op": "print-prompt",
            "path": _to_posix(os.path.relpath(target, project_root)),
            "content_sha256_before": None,
            "content_sha256_after": _content_hash(body),
        }
    )
    return {
        "tool": tool,
        "install_mode": spec["install_mode"],
        "enabled": False,
        "manual_step_required": True,
        "actions": actions,
    }


_ENABLE_DISPATCH = {
    "import-marker": _enable_import_marker,
    "append-block": _enable_append_block,
    "owned-file": _enable_owned_file,
    "multi-file-required": _enable_multi_file_required,
    "print-only": _enable_print_only,
}


def enable(tool: str, registry: Registry, project_root: str = ".", dry_run: bool = False) -> dict:
    spec = registry.get(tool)
    fn = _ENABLE_DISPATCH[spec["install_mode"]]
    return fn(tool, spec, registry, project_root, dry_run)


def _disable_marker_based(tool: str, spec: dict, project_root: str, dry_run: bool) -> dict:
    actions = []
    target = os.path.join(project_root, spec["target_path"])
    before_text = _read_or_none(target)
    if before_text is None:
        return {
            "tool": tool,
            "install_mode": spec["install_mode"],
            "enabled": False,
            "manual_step_required": False,
            "actions": [],
        }
    try:
        new_text, op = remove_block(before_text)
    except MarkerParseError as exc:
        raise RuntimeError(
            f"refusing to modify {target!r}: agent-style marker region is tampered or ambiguous: {exc}; "
            "inspect the file and repair manually"
        )
    if op == "noop":
        return {
            "tool": tool,
            "install_mode": spec["install_mode"],
            "enabled": False,
            "manual_step_required": False,
            "actions": [],
        }
    if not dry_run:
        with open(target, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(new_text)
    actions.append(
        {
            "order": 0,
            "op": "remove-marker",
            "path": _to_posix(os.path.relpath(target, project_root)),
            "content_sha256_before": _content_hash(before_text),
            "content_sha256_after": _content_hash(new_text),
        }
    )
    return {
        "tool": tool,
        "install_mode": spec["install_mode"],
        "enabled": False,
        "manual_step_required": False,
        "actions": actions,
    }


def _disable_owned_file(tool: str, spec: dict, project_root: str, dry_run: bool) -> dict:
    actions = []
    target = os.path.join(project_root, spec["target_path"])
    before_text = _read_or_none(target)
    if before_text is None:
        return {
            "tool": tool,
            "install_mode": spec["install_mode"],
            "enabled": False,
            "manual_step_required": False,
            "actions": [],
        }
    if extract_signature(before_text) is None:
        raise RuntimeError(
            f"refusing to delete {target!r}: not agent-style-owned (no signature found); "
            "inspect the file and remove manually if intended"
        )
    try:
        verify(before_text)
    except OwnedFileError as exc:
        raise RuntimeError(
            f"refusing to delete {target!r}: {exc}; "
            "inspect the file and repair manually"
        )
    if not dry_run:
        os.remove(target)
    actions.append(
        {
            "order": 0,
            "op": "owned-file-remove",
            "path": _to_posix(os.path.relpath(target, project_root)),
            "content_sha256_before": _content_hash(before_text),
            "content_sha256_after": None,
        }
    )
    return {
        "tool": tool,
        "install_mode": spec["install_mode"],
        "enabled": False,
        "manual_step_required": False,
        "actions": actions,
    }


def _disable_multi_or_print(tool: str, spec: dict, project_root: str, dry_run: bool) -> dict:
    """For multi-file-required and print-only, `disable` removes the .agent-style/<file>; snippet/prompt do not need undoing."""
    actions = []
    target = os.path.join(project_root, spec["target_path"])
    before_text = _read_or_none(target)
    if before_text is not None:
        if not dry_run:
            os.remove(target)
        actions.append(
            {
                "order": 0,
                "op": "owned-file-remove",
                "path": _to_posix(os.path.relpath(target, project_root)),
                "content_sha256_before": _content_hash(before_text),
                "content_sha256_after": None,
            }
        )
    return {
        "tool": tool,
        "install_mode": spec["install_mode"],
        "enabled": False,
        "manual_step_required": False,
        "actions": actions,
    }


_DISABLE_DISPATCH = {
    "import-marker": _disable_marker_based,
    "append-block": _disable_marker_based,
    "owned-file": _disable_owned_file,
    "multi-file-required": _disable_multi_or_print,
    "print-only": _disable_multi_or_print,
}


def disable(tool: str, registry: Registry, project_root: str = ".", dry_run: bool = False) -> dict:
    spec = registry.get(tool)
    fn = _DISABLE_DISPATCH[spec["install_mode"]]
    return fn(tool, spec, project_root, dry_run)


def canonical_json(result: dict) -> str:
    """Return a canonical JSON rendering of an enable/disable result.

    Canonical form:
    - Sorted object keys.
    - LF line endings (Python's json module already uses LF).
    - POSIX-style relative paths (produced by the install functions).
    - `actions` array sorted by (path, op, order) tuple.
    """
    actions = list(result.get("actions", []))
    actions.sort(key=lambda a: (a.get("path", ""), a.get("op", ""), a.get("order", 0)))
    normalized = {**result, "actions": actions}
    return json.dumps(normalized, sort_keys=True, ensure_ascii=False, indent=2)
