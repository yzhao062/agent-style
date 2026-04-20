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
import re
import shutil
from typing import Any

from agent_style import __version__
from agent_style.markers import find_block, upsert_block, remove_block, MarkerParseError
from agent_style.owned_file import sign, verify, extract_signature, compute_hash, strip_signature, OwnedFileError
from agent_style.registry import Registry


def _safe_resolve(project_root: str, rel_path: str) -> str:
    """Resolve a project-relative path, rejecting traversal outside project_root.

    Raises RuntimeError for any suspicious input: absolute paths, drive-qualified
    paths, empty strings, `..` components, or resolved paths that escape the
    project root.
    """
    if not rel_path or not isinstance(rel_path, str):
        raise RuntimeError(f"invalid path: empty or non-string ({rel_path!r})")
    if os.path.isabs(rel_path):
        raise RuntimeError(f"invalid path: absolute paths not allowed ({rel_path!r})")
    # Windows drive-qualified paths ("C:foo") — isabs() misses these
    if len(rel_path) >= 2 and rel_path[1] == ":":
        raise RuntimeError(f"invalid path: drive-qualified paths not allowed ({rel_path!r})")
    # Reject explicit parent-directory components
    parts = rel_path.replace("\\", "/").split("/")
    if any(p == ".." for p in parts):
        raise RuntimeError(f"invalid path: '..' components not allowed ({rel_path!r})")
    root_abs = os.path.realpath(os.path.abspath(project_root))
    joined = os.path.realpath(os.path.join(root_abs, rel_path))
    # Resolved path must stay under root
    try:
        common = os.path.commonpath([root_abs, joined])
    except ValueError:  # different drives on Windows
        raise RuntimeError(f"invalid path: resolves outside project root ({rel_path!r})")
    if os.path.normcase(common) != os.path.normcase(root_abs):
        raise RuntimeError(f"invalid path: resolves outside project root ({rel_path!r})")
    return joined


def _canonical_hash(content: str | None) -> str | None:
    """Canonical-byte-stream sha256 for manifest entries (owned-file contract).

    Uses `owned_file.compute_hash`, which strips BOM, normalizes CRLF/CR to LF,
    and ensures exactly one trailing newline before hashing. This makes manifest
    hashes stable across Windows Git / Unix git-checkout line-ending conversions.
    """
    if content is None:
        return None
    return compute_hash(content)


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


def _detect_active_surfaces(project_root: str, registry: Registry) -> set[str]:
    """Return the set of tool names (used as surface ids) that appear installed.

    A tool is considered "active" when its target_path exists in the project.
    Used by the skill-with-references install mode to decide which target_groups
    to write to. `skill-with-references` entries are excluded (they do not
    have target_path and would only be activated by prior install anyway).
    """
    active: set[str] = set()
    for tool_name, tool_spec in registry.tools.items():
        if tool_spec.get("install_mode") == "skill-with-references":
            continue
        tp = tool_spec.get("target_path")
        if not tp:
            continue
        if os.path.exists(os.path.join(project_root, tp)):
            active.add(tool_name)
    return active


def _iter_bundled_references(registry: Registry, references_source: str) -> list[str]:
    """List every file under the bundled references directory, relative to it."""
    base = os.path.join(registry.data_dir, references_source)
    if not os.path.isdir(base):
        return []
    out: list[str] = []
    for root, _dirs, files in os.walk(base):
        for name in files:
            full = os.path.join(root, name)
            rel = os.path.relpath(full, base).replace(os.sep, "/")
            out.append(rel)
    return sorted(out)


_SHA256_HEX_RE = re.compile(r"^[0-9a-f]{64}$")


def _load_and_validate_manifest(manifest_abs: str) -> tuple[dict[str, dict] | None, str | None]:
    """Load a manifest.json and validate every entry's shape.

    Returns a (by_path_or_None, error_or_None) tuple:
    - (None, None)            — manifest absent
    - (None, "reason")        — manifest present but malformed JSON or schema
    - ({path: entry}, None)   — manifest is well-formed

    A valid entry requires:
      - non-empty string `path`
      - `kind == "file"`
      - `sha256` matching `^[0-9a-f]{64}$`
    Missing or malformed hashes fail closed rather than proving ownership or
    permitting deletion (see CodexReview Round 2, Finding 1).
    """
    text = _read_or_none(manifest_abs)
    if text is None:
        return None, None
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        return None, f"JSON parse error: {exc}"
    if not isinstance(doc, dict):
        return None, "manifest root is not a JSON object"
    entries = doc.get("entries")
    if not isinstance(entries, list):
        return None, "'entries' is not a list"
    by_path: dict[str, dict] = {}
    for i, entry in enumerate(entries):
        if not isinstance(entry, dict):
            return None, f"entries[{i}] is not a JSON object"
        path = entry.get("path")
        if not isinstance(path, str) or not path:
            return None, f"entries[{i}] missing non-empty string 'path'"
        kind = entry.get("kind")
        if kind != "file":
            return None, f"entries[{i}] ({path!r}) has kind={kind!r}; expected 'file'"
        sha = entry.get("sha256")
        if not isinstance(sha, str) or not _SHA256_HEX_RE.fullmatch(sha):
            return None, f"entries[{i}] ({path!r}) has invalid or missing sha256"
        by_path[path] = entry
    return by_path, None


def _enable_skill_with_references(tool: str, spec: dict, registry: Registry, project_root: str, dry_run: bool) -> dict:
    """Install a skill with supporting references, auto-detecting active surfaces.

    Mode-specific spec fields:
      - skill_source: bundled path to the SKILL.md (string)
      - references_source: bundled path to the references/ directory (string)
      - target_groups: [{target_path, surfaces: [...]}, ...]
      - manual_step_message: string printed for non-skill-capable tools

    Behavior:
      1. Detect which surfaces are active (by looking for existing adapter files
         for other tools).
      2. Filter target_groups to those whose surface list intersects the active
         set.
      3. Write files for each active group (deduplicated by target_path).
      4. Write a manifest.json under .agent-style/skills/<tool>/manifest.json
         listing every path + sha256 (used by disable for safe removal).
      5. For every enabled tool NOT covered by any active group, emit a
         print-only manual-step action with the manual_step_message.
      6. If no surface is active, return enabled=False, manual_step_required=True,
         with actions=[] and a message pointing at the CLI fallback.
    """
    skill_source = spec["skill_source"]
    references_source = spec["references_source"]
    target_groups = spec["target_groups"]
    manual_msg = spec.get("manual_step_message", "")

    active_surfaces = _detect_active_surfaces(project_root, registry)

    # Figure out which target_groups to write, deduplicated by target_path.
    to_write: dict[str, set[str]] = {}  # target_path -> covered_surfaces
    for group in target_groups:
        covered = set(group.get("surfaces", [])) & active_surfaces
        if not covered:
            continue
        path = group["target_path"]
        to_write.setdefault(path, set()).update(covered)

    actions: list[dict[str, Any]] = []
    manifest_entries: list[dict[str, Any]] = []

    # No active surface at all → print-only
    if not to_write:
        msg = (
            "no skill-capable surface detected in this project. "
            "Enable `claude-code` or `anthropic-skill` first, "
            "or run `agent-style review <file>` from the CLI directly."
        )
        return {
            "tool": tool,
            "install_mode": spec["install_mode"],
            "enabled": False,
            "manual_step_required": True,
            "actions": [
                {
                    "order": 0,
                    "op": "print-message",
                    "path": "",
                    "content_sha256_before": None,
                    "content_sha256_after": None,
                    "message": msg,
                }
            ],
        }

    # Load and validate any prior-install manifest BEFORE we touch the filesystem.
    # A malformed manifest (bad JSON or entry missing sha256 etc.) must fail closed
    # rather than granting ownership of user-owned files.
    manifest_path = os.path.join(AGENT_STYLE_DIR, "skills", tool, "manifest.json")
    manifest_abs = _safe_resolve(project_root, manifest_path)
    prior_manifest, manifest_error = _load_and_validate_manifest(manifest_abs)
    if manifest_error:
        raise RuntimeError(
            f"refusing to enable {tool!r}: manifest at {_to_posix(manifest_path)!r} is malformed "
            f"({manifest_error}); move it aside manually, then rerun `agent-style enable style-review`"
        )
    # Validate every skill target path BEFORE touching the filesystem. A malformed
    # tools.json entry must fail closed, not write to `../outside.md`.
    for tp in list(to_write.keys()):
        _safe_resolve(project_root, tp)

    def _prove_ownership(rel_path: str, current: str | None) -> None:
        """Fail-closed if a file exists at rel_path that was not written by us."""
        if current is None:
            return
        if prior_manifest is None:
            raise RuntimeError(
                f"refusing to overwrite existing file at {rel_path!r}: no manifest found at "
                f"{manifest_path!r}; move or rename that file and rerun `agent-style enable style-review`"
            )
        entry = prior_manifest.get(_to_posix(rel_path))
        if entry is None:
            raise RuntimeError(
                f"refusing to overwrite existing file at {rel_path!r}: not listed in manifest "
                f"{manifest_path!r}; it is owned by another source"
            )
        # Post-validation, `sha256` is guaranteed present and well-formed. Defensive
        # recheck: an entry without a matching sha256 must never prove ownership.
        expected = entry.get("sha256")
        if not expected or _canonical_hash(current) != expected:
            raise RuntimeError(
                f"refusing to overwrite {rel_path!r}: content has drifted since the prior install "
                f"(canonical sha256 mismatch); move your edits aside, run `agent-style disable style-review`, "
                "then rerun `agent-style enable style-review`"
            )

    # Atomicity: first pass proves ownership for every target (raises on any
    # conflict BEFORE any write). Only after every target clears do we write.
    # This prevents partial-install state where some references got written
    # before an ownership error aborted mid-pass.
    _pending_writes: list[tuple[str, str, list[str]]] = []  # (rel_path, body, covered)
    for target_path in sorted(to_write.keys()):
        covered = sorted(to_write[target_path])
        abs_target = _safe_resolve(project_root, target_path)
        if abs_target.endswith(".md") or abs_target.endswith(".mdc"):
            body = registry.read_adapter(skill_source)
            before = _read_or_none(abs_target)
            _prove_ownership(target_path, before)
            _pending_writes.append((target_path, body, covered))
        else:
            for rel in _iter_bundled_references(registry, references_source):
                if ".." in rel.split("/") or os.path.isabs(rel):
                    raise RuntimeError(
                        f"invalid bundled reference path {rel!r}; package data is corrupt"
                    )
                src_abs = os.path.join(registry.data_dir, references_source, rel)
                dst_rel = (target_path.rstrip("/") + "/" + rel).replace(os.sep, "/")
                dst_abs = _safe_resolve(project_root, dst_rel)
                with open(src_abs, encoding="utf-8") as fh:
                    body = fh.read()
                before = _read_or_none(dst_abs)
                _prove_ownership(dst_rel, before)
                _pending_writes.append((dst_rel, body, covered))

    # Ownership passed for every target. Only now do we touch the filesystem.
    # Creating `.agent-style/RULES.md` here (not earlier) preserves the promise
    # that a refused enable leaves no partial install footprint.
    actions.extend(_ensure_agent_style_dir(project_root, registry, dry_run))

    # Second pass: actually write everything (or compute dry-run actions).
    for rel_path, body, covered in _pending_writes:
        abs_path = _safe_resolve(project_root, rel_path)
        before = _read_or_none(abs_path)
        before_hash = _canonical_hash(before)
        after_hash = _canonical_hash(body)
        if before_hash != after_hash:
            if not dry_run:
                os.makedirs(os.path.dirname(abs_path) or ".", exist_ok=True)
                with open(abs_path, "w", encoding="utf-8", newline="\n") as fh:
                    fh.write(body)
            actions.append(
                {
                    "order": len(actions),
                    "op": "owned-file-write",
                    "path": _to_posix(rel_path),
                    "content_sha256_before": before_hash,
                    "content_sha256_after": after_hash,
                    "covered_surfaces": covered,
                }
            )
        manifest_entries.append(
            {
                "path": _to_posix(rel_path),
                "kind": "file",
                "sha256": after_hash,
                "covered_surfaces": covered,
            }
        )

    # Write the manifest.
    manifest_doc = {
        "schema_version": 1,
        "tool": tool,
        "generated_by": f"agent-style {__version__}",
        "entries": sorted(manifest_entries, key=lambda e: e["path"]),
    }
    manifest_body = json.dumps(manifest_doc, sort_keys=True, ensure_ascii=False, indent=2) + "\n"
    before = _read_or_none(manifest_abs)
    before_hash = _canonical_hash(before)
    after_hash = _canonical_hash(manifest_body)
    if before_hash != after_hash:
        if not dry_run:
            os.makedirs(os.path.dirname(manifest_abs) or ".", exist_ok=True)
            with open(manifest_abs, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(manifest_body)
        actions.append(
            {
                "order": len(actions),
                "op": "manifest-write",
                "path": _to_posix(manifest_path),
                "content_sha256_before": before_hash,
                "content_sha256_after": after_hash,
            }
        )

    # Emit print-message actions for tools the user has enabled that are not
    # covered by any target_group (so they see the CLI fallback guidance).
    uncovered_surfaces = active_surfaces - {s for surfaces in to_write.values() for s in surfaces}
    if uncovered_surfaces and manual_msg:
        for uncovered_tool in sorted(uncovered_surfaces):
            actions.append(
                {
                    "order": len(actions),
                    "op": "print-message",
                    "path": "",
                    "content_sha256_before": None,
                    "content_sha256_after": None,
                    "message": manual_msg.format(tool=uncovered_tool),
                }
            )

    return {
        "tool": tool,
        "install_mode": spec["install_mode"],
        "enabled": True,
        "manual_step_required": False,
        "actions": actions,
    }


_ENABLE_DISPATCH = {
    "import-marker": _enable_import_marker,
    "append-block": _enable_append_block,
    "owned-file": _enable_owned_file,
    "multi-file-required": _enable_multi_file_required,
    "print-only": _enable_print_only,
    "skill-with-references": _enable_skill_with_references,
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


def _disable_skill_with_references(tool: str, spec: dict, project_root: str, dry_run: bool) -> dict:
    """Disable a skill-with-references install via its manifest, fail-closed on drift.

    Reads .agent-style/skills/<tool>/manifest.json and removes only the files
    listed there whose current canonical sha256 still matches. If any file drifted
    or if the manifest is missing while target files still exist, fail closed:
    keep the manifest, leave files in place, set manual_step_required=True,
    report the list. No blind recursive deletes; every path is validated.
    """
    manifest_path = os.path.join(AGENT_STYLE_DIR, "skills", tool, "manifest.json")
    manifest_abs = _safe_resolve(project_root, manifest_path)
    actions: list[dict[str, Any]] = []
    drifted: list[str] = []
    non_empty_dirs: list[str] = []

    target_groups = spec.get("target_groups", [])
    # Validate every declared target path up-front (schema-level safety).
    for group in target_groups:
        _safe_resolve(project_root, group["target_path"])

    prior_manifest, manifest_error = _load_and_validate_manifest(manifest_abs)
    if manifest_error:
        # Malformed manifest (bad JSON or malformed entry). Fail closed: leave
        # the manifest and every target in place; emit an actionable message.
        return {
            "tool": tool,
            "install_mode": spec["install_mode"],
            "enabled": True,
            "manual_step_required": True,
            "actions": [],
            "drifted": [],
            "non_empty_directories": [],
            "message": (
                f"refusing to disable {tool!r}: manifest at {_to_posix(manifest_path)!r} is malformed "
                f"({manifest_error}); inspect and repair or remove manually"
            ),
        }
    if prior_manifest is None:
        # No manifest. Scan declared targets; if any still exist, fail closed.
        existing_targets: list[str] = []
        for group in target_groups:
            abs_target = _safe_resolve(project_root, group["target_path"])
            if os.path.isfile(abs_target):
                existing_targets.append(group["target_path"])
            elif os.path.isdir(abs_target) and os.listdir(abs_target):
                existing_targets.append(group["target_path"])
        if existing_targets:
            return {
                "tool": tool,
                "install_mode": spec["install_mode"],
                "enabled": True,
                "manual_step_required": True,
                "actions": [],
                "drifted": [],
                "non_empty_directories": [],
                "message": (
                    f"refusing to disable {tool!r}: manifest missing at {_to_posix(manifest_path)!r} "
                    f"but target files still exist: {sorted(existing_targets)}; "
                    "inspect and remove manually, or restore the manifest and rerun"
                ),
            }
        # No manifest and no target files -> not installed.
        return {
            "tool": tool,
            "install_mode": spec["install_mode"],
            "enabled": False,
            "manual_step_required": False,
            "actions": [],
            "drifted": [],
            "non_empty_directories": [],
        }

    # Manifest is present and every entry's schema is already validated.
    # Re-check each path's safety containment (paranoia: entry paths were only
    # schema-validated, not yet reconciled against the current project root).
    entries = list(prior_manifest.values())
    for entry in entries:
        rel_path = entry["path"]
        try:
            _safe_resolve(project_root, rel_path)
        except RuntimeError as exc:
            raise RuntimeError(
                f"refusing to disable {tool!r}: manifest contains an unsafe path "
                f"({rel_path!r}): {exc}"
            )

    # Coverage check: every declared target_group target that currently exists on
    # disk must be covered by at least one manifest entry. An uncovered active
    # target means the manifest doesn't match reality — disable would leave
    # orphan installed files behind while claiming success. Catches `entries: []`
    # and partial/stale manifests alike (CodexReview Round 3, Finding 1).
    manifest_paths = set(prior_manifest.keys())  # canonical POSIX relpaths
    uncovered_targets: list[str] = []
    for group in target_groups:
        tp = group["target_path"]
        abs_target = _safe_resolve(project_root, tp)
        tp_posix = _to_posix(tp)
        if os.path.isfile(abs_target):
            if tp_posix not in manifest_paths:
                uncovered_targets.append(tp)
        elif os.path.isdir(abs_target):
            prefix = tp_posix.rstrip("/") + "/"
            covered_any = any(p.startswith(prefix) for p in manifest_paths)
            if not covered_any and os.listdir(abs_target):
                uncovered_targets.append(tp)
    if uncovered_targets:
        return {
            "tool": tool,
            "install_mode": spec["install_mode"],
            "enabled": True,
            "manual_step_required": True,
            "actions": [],
            "drifted": [],
            "non_empty_directories": [],
            "message": (
                f"refusing to disable {tool!r}: declared target(s) {sorted(uncovered_targets)} "
                f"exist on disk but are not listed in manifest {_to_posix(manifest_path)!r}; "
                "inspect and remove manually, or restore a complete manifest and rerun"
            ),
        }

    # Remove manifest-owned files whose canonical hash matches; record drift.
    removal_actions: list[dict[str, Any]] = []
    for entry in entries:
        rel_path = entry["path"]
        abs_path = _safe_resolve(project_root, rel_path)
        expected_hash = entry["sha256"]  # validated to be 64-hex above
        current = _read_or_none(abs_path)
        if current is None:
            # Already gone; nothing to do.
            removal_actions.append(
                {
                    "order": 0,  # placeholder, rewritten below
                    "op": "owned-file-remove",
                    "path": _to_posix(rel_path),
                    "content_sha256_before": None,
                    "content_sha256_after": None,
                    "noop": True,
                    "_abs": abs_path,
                }
            )
            continue
        if _canonical_hash(current) != expected_hash:
            drifted.append(rel_path)
            continue
        removal_actions.append(
            {
                "order": 0,
                "op": "owned-file-remove",
                "path": _to_posix(rel_path),
                "content_sha256_before": _canonical_hash(current),
                "content_sha256_after": None,
                "_abs": abs_path,
            }
        )

    # If any file drifted, fail closed: do NOT delete anything, keep manifest intact.
    if drifted:
        return {
            "tool": tool,
            "install_mode": spec["install_mode"],
            "enabled": True,
            "manual_step_required": True,
            "actions": [],
            "drifted": sorted(drifted),
            "non_empty_directories": [],
            "message": (
                f"refusing to disable {tool!r}: {len(drifted)} file(s) have been edited since install "
                f"(canonical sha256 mismatch). Manifest and targets are left in place. "
                "Move your edits aside, then rerun `agent-style disable style-review`."
            ),
        }

    # No drift: apply removals.
    for action in removal_actions:
        abs_path = action.pop("_abs")
        if not action.get("noop") and not dry_run:
            os.remove(abs_path)
        action["order"] = len(actions)
        actions.append(action)

    # Remove each directory target from target_groups if empty after file-by-file cleanup.
    # os.walk(topdown=False) captures `dirs`/`files` before child removal, so those
    # lists lag after we delete subdirs. Use os.listdir(root) instead: it reflects
    # actual current state and lets parents become empty once children are rmdir'd.
    for group in target_groups:
        abs_target = _safe_resolve(project_root, group["target_path"])
        if abs_target.endswith(".md") or abs_target.endswith(".mdc") or abs_target.endswith(".json"):
            continue
        if os.path.isdir(abs_target):
            for root, _dirs, _files in os.walk(abs_target, topdown=False):
                # Containment guard: never walk outside project root
                _safe_resolve(project_root, os.path.relpath(root, project_root))
                if not os.listdir(root):
                    if not dry_run:
                        os.rmdir(root)
                    actions.append(
                        {
                            "order": len(actions),
                            "op": "owned-directory-remove",
                            "path": _to_posix(os.path.relpath(root, project_root)),
                            "content_sha256_before": None,
                            "content_sha256_after": None,
                        }
                    )
                else:
                    non_empty_dirs.append(_to_posix(os.path.relpath(root, project_root)))

    # Remove the manifest file last, after all entries processed. Read once more
    # for the canonical hash before deletion; safe because nothing else wrote to it.
    manifest_text = _read_or_none(manifest_abs)
    if not dry_run:
        try:
            os.remove(manifest_abs)
        except FileNotFoundError:
            pass
    actions.append(
        {
            "order": len(actions),
            "op": "manifest-remove",
            "path": _to_posix(manifest_path),
            "content_sha256_before": _canonical_hash(manifest_text),
            "content_sha256_after": None,
        }
    )
    # Attempt to remove the containing skills directory if empty.
    skills_root = os.path.dirname(manifest_abs)
    if os.path.isdir(skills_root):
        try:
            if not os.listdir(skills_root):
                if not dry_run:
                    os.rmdir(skills_root)
                actions.append(
                    {
                        "order": len(actions),
                        "op": "owned-directory-remove",
                        "path": _to_posix(os.path.relpath(skills_root, project_root)),
                        "content_sha256_before": None,
                        "content_sha256_after": None,
                    }
                )
        except OSError:
            pass

    return {
        "tool": tool,
        "install_mode": spec["install_mode"],
        "enabled": False,
        "manual_step_required": False,
        "actions": actions,
        "drifted": [],
        "non_empty_directories": sorted(set(non_empty_dirs)),
    }


_DISABLE_DISPATCH = {
    "import-marker": _disable_marker_based,
    "append-block": _disable_marker_based,
    "owned-file": _disable_owned_file,
    "multi-file-required": _disable_multi_or_print,
    "print-only": _disable_multi_or_print,
    "skill-with-references": _disable_skill_with_references,
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
