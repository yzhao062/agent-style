# SPDX-License-Identifier: MIT
"""agent-style CLI entry point.

Subcommands:
    rules            Print bundled RULES.md to stdout
    path             Print bundled data directory
    list-tools       Print supported tools
    enable <tool>    Install agent-style for a given tool (safe, idempotent)
    disable <tool>   Remove agent-style from a given tool's instruction file

Global:
    --version        Print version and exit
    --help           Print help
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from agent_style import __version__
from agent_style.installer import enable, disable, canonical_json
from agent_style.registry import Registry, RegistryError
from agent_style.review import (
    audit as review_audit,
    compare as review_compare,
    RulesLoadError,
)
from agent_style.review.polish import PolishNotAvailableError, check_host_and_raise


def _print_json_result(result: dict[str, Any]) -> None:
    sys.stdout.write(canonical_json(result))
    sys.stdout.write("\n")


def _print_human_result(result: dict[str, Any], subcommand: str) -> None:
    tool = result.get("tool", "?")
    mode = result.get("install_mode", "?")
    manual = result.get("manual_step_required", False)
    actions = result.get("actions", [])
    if manual:
        # FIRST LINE must be "manual step required:" per Rev 8 acceptance criterion.
        sys.stdout.write(f"manual step required: {tool} ({mode}) prepared, but needs a user action\n")
    else:
        sys.stdout.write(f"agent-style {subcommand} {tool} ({mode}): ")
        sys.stdout.write("ok\n" if actions else "no changes\n")
    for action in actions:
        op = action.get("op", "?")
        path = action.get("path", "?")
        if op == "print-prompt":
            # For print-only tools, the prompt body goes to stdout (clean).
            # The human-step message is already above; the prompt content is whatever
            # the adapter contains. The CLI loads it via print-prompt here.
            # (Installer already wrote the file; we just echo the bundled body.)
            sys.stderr.write(f"  action: {op} {path} (prompt body printed to stdout below)\n")
        elif op == "print-snippet":
            # For multi-file-required, the snippet goes to stderr so stdout stays clean.
            snippet = action.get("snippet", "")
            sys.stderr.write(f"  action: {op} {path}\n")
            sys.stderr.write("  add this to your config:\n")
            for line in snippet.splitlines():
                sys.stderr.write(f"    {line}\n")
        else:
            sys.stderr.write(f"  action: {op} {path}\n")


def _cmd_rules(args: argparse.Namespace, registry: Registry) -> int:
    sys.stdout.write(registry.read_bundled_rules())
    return 0


def _cmd_path(args: argparse.Namespace, registry: Registry) -> int:
    print(registry.data_dir)
    return 0


def _cmd_list_tools(args: argparse.Namespace, registry: Registry) -> int:
    for name, spec in registry.tools.items():
        mode = spec["install_mode"]
        if mode == "skill-with-references":
            # Summarize target_groups[*].target_path joined by " + ".
            paths = " + ".join(g["target_path"] for g in spec.get("target_groups", []))
            print(f"{name:18}  {mode:22}  {paths}")
        else:
            print(f"{name:18}  {mode:22}  {spec['target_path']}")
    return 0


def _cmd_enable(args: argparse.Namespace, registry: Registry) -> int:
    try:
        result = enable(args.tool, registry, project_root=".", dry_run=args.dry_run)
    except (RegistryError, RuntimeError) as exc:
        sys.stderr.write(f"error: {exc}\n")
        return 2
    if args.json:
        _print_json_result(result)
    else:
        _print_human_result(result, "enable")
        if result.get("install_mode") == "print-only":
            # Clean stdout with prompt body (for users who redirect `> prompt.md`).
            target = result["actions"][0].get("path") if result["actions"] else None
            if target:
                body = registry.read_adapter(registry.get(args.tool)["adapter_source"])
                sys.stdout.write(body)
    return 0


def _cmd_review(args: argparse.Namespace, registry: Registry) -> int:
    """Review one or two Markdown files against agent-style's rules."""
    # Polish path short-circuits outside a skill host.
    if args.polish:
        try:
            check_host_and_raise()
        except PolishNotAvailableError as exc:
            sys.stderr.write(f"error: {exc}\n")
            return 2

    files = list(args.files or [])
    if args.compare is not None:
        # --compare A B: two-file delta. Ignore positional `files` if --compare given.
        a, b = args.compare
        try:
            result = review_compare(
                a, b,
                mechanical_only=args.mechanical_only,
                skill_host=False,
            )
        except (RulesLoadError, FileNotFoundError) as exc:
            sys.stderr.write(f"error: {exc}\n")
            return 2
        payload = _compare_to_dict(result)
        _print_review_json(payload)
        return 0

    if not files:
        sys.stderr.write("error: review requires a FILE argument (or --compare A B)\n")
        return 2
    if len(files) > 1:
        sys.stderr.write(
            f"error: review takes 1 file argument; got {len(files)}. "
            "For A/B compare, use --compare A B.\n"
        )
        return 2

    file_path = files[0]
    try:
        result = review_audit(
            file_path,
            mechanical_only=args.mechanical_only,
            audit_only=args.audit_only,
            skill_host=False,
        )
    except (RulesLoadError, FileNotFoundError) as exc:
        sys.stderr.write(f"error: {exc}\n")
        return 2

    payload = _audit_to_dict(result)
    if args.json or args.audit_only or args.mechanical_only:
        # All machine-readable paths emit canonical JSON.
        _print_review_json(payload)
    else:
        _print_audit_human(payload)
    return 0


def _audit_to_dict(result) -> dict[str, Any]:
    """Serialize AuditResult to a canonical-JSON-compatible dict.

    rules_path is intentionally excluded: it carries the absolute filesystem
    path of the resolved RULES.md, which differs between pip and npm installs
    and would break --cli-parity byte identity. rules_source is included (both
    ecosystems emit "package-bundle" when loading from their own bundle).
    """
    return {
        "command": "review",
        "file": _as_posix(result.file),
        "rules_source": result.rules_source,
        "total_violations": result.total_violations,
        "rule_results": [
            {
                "rule": rr.rule,
                "severity": rr.severity,
                "detector": rr.detector,
                "status": rr.status,
                "count": rr.count,
                "note": rr.note,
                "violations": [
                    {
                        "line": v.line,
                        "column": v.column,
                        "excerpt": v.excerpt,
                        "detail": v.detail,
                    }
                    for v in rr.violations
                ],
            }
            for rr in result.rule_results
        ],
    }


def _compare_to_dict(result) -> dict[str, Any]:
    """Serialize CompareResult to a canonical-JSON-compatible dict.

    rules_path is intentionally excluded (see _audit_to_dict for rationale).
    """
    return {
        "command": "review-compare",
        "file_a": _as_posix(result.file_a),
        "file_b": _as_posix(result.file_b),
        "rules_source": result.rules_source,
        "total_a": result.total_a,
        "total_b": result.total_b,
        "per_rule_delta": {
            rule_id: {"a": v["a"], "b": v["b"], "delta": v["delta"]}
            for rule_id, v in result.per_rule_delta.items()
        },
    }


def _print_review_json(payload: dict[str, Any]) -> None:
    """Print review JSON without the enable/disable-style `actions` injection."""
    sys.stdout.write(json.dumps(payload, sort_keys=True, ensure_ascii=False, indent=2))
    sys.stdout.write("\n")


def _as_posix(path: str) -> str:
    """POSIX-relative path for canonical JSON (matches existing contract)."""
    if path is None:
        return None
    # Strip leading ./ and normalize separators.
    p = str(path).replace("\\", "/")
    if p.startswith("./"):
        p = p[2:]
    return p


def _print_audit_human(payload: dict[str, Any]) -> None:
    """Human-readable audit output to stdout."""
    f = payload["file"]
    total = payload["total_violations"]
    sys.stdout.write(f"agent-style review {f}: {total} violation(s)\n")
    for rr in payload["rule_results"]:
        if rr["status"] == "violation":
            sys.stdout.write(
                f"  {rr['rule']} [{rr['severity']}, {rr['detector']}]: {rr['count']}\n"
            )
            for v in rr["violations"][:5]:
                sys.stdout.write(f"    L{v['line']}:C{v['column']}  {v['detail']}\n")
    skipped = [rr for rr in payload["rule_results"] if rr["status"] == "skipped"]
    if skipped:
        sys.stdout.write(f"  ({len(skipped)} rule(s) skipped; run via a skill host for semantic coverage)\n")


def _cmd_disable(args: argparse.Namespace, registry: Registry) -> int:
    try:
        result = disable(args.tool, registry, project_root=".", dry_run=args.dry_run)
    except (RegistryError, RuntimeError) as exc:
        sys.stderr.write(f"error: {exc}\n")
        return 2
    if args.json:
        _print_json_result(result)
    else:
        _print_human_result(result, "disable")
        # Surface the fail-closed message (drifted files or missing manifest with targets).
        msg = result.get("message")
        if msg:
            sys.stderr.write(f"error: {msg}\n")
    # If the installer refused to disable (fail-closed on drift or missing-manifest-with-targets),
    # `enabled: True` remains in the result. Propagate that as a non-zero exit so shell callers
    # and CI pipelines see the partial state.
    if result.get("enabled") is True:
        return 2
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agent-style",
        description=(
            "agent-style: install and manage The Elements of Agent Style writing "
            "ruleset for AI agents (Claude Code, GitHub Copilot, Cursor, AGENTS.md-aware "
            "tools, Aider, Anthropic Skills, Codex API, and more)."
        ),
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"agent-style {__version__}",
    )
    sub = parser.add_subparsers(dest="command", required=True, metavar="<command>")

    sub.add_parser("rules", help="Print bundled RULES.md to stdout.")
    sub.add_parser("path", help="Print bundled data directory path.")
    sub.add_parser("list-tools", help="List supported tools and their install modes.")

    for subcmd in ("enable", "disable"):
        p = sub.add_parser(
            subcmd,
            help=(
                "Enable agent-style for a given tool (safe-append to your existing file)."
                if subcmd == "enable"
                else "Remove agent-style for a given tool from your instruction file."
            ),
        )
        p.add_argument("tool", help="Tool name (see `agent-style list-tools`).")
        p.add_argument(
            "--dry-run",
            action="store_true",
            help="Print planned actions without writing any file.",
        )
        p.add_argument(
            "--json",
            action="store_true",
            help="Emit canonical JSON output (sorted keys, LF, POSIX paths).",
        )

    # review subcommand
    rp = sub.add_parser(
        "review",
        help=(
            "Review one or two Markdown files against agent-style's rules. "
            "Deterministic (mechanical + structural) from the plain CLI; "
            "semantic rules need a skill host (Claude Code or Anthropic Skills)."
        ),
    )
    rp.add_argument(
        "files",
        nargs="*",
        help="File(s) to review. One file = audit; use --compare for two-file delta.",
    )
    rp.add_argument(
        "--audit-only",
        action="store_true",
        help="Deterministic audit; semantic rules reported as 'skipped'. Emits JSON.",
    )
    rp.add_argument(
        "--mechanical-only",
        action="store_true",
        help=(
            "Strictest deterministic subset: mechanical detectors only. "
            "Used by `verify-install.sh --cli-parity` as the byte-identity oracle."
        ),
    )
    rp.add_argument(
        "--compare",
        nargs=2,
        metavar=("A", "B"),
        help="A/B compare: audit two files, report per-rule delta. No polish, no ask.",
    )
    rp.add_argument(
        "--polish",
        action="store_true",
        help=(
            "Produce a revised draft alongside the original. "
            "Requires a skill host (Claude Code or Anthropic Skills); errors from the plain CLI."
        ),
    )
    rp.add_argument(
        "--json",
        action="store_true",
        help="Emit canonical JSON output (implied by --audit-only and --mechanical-only).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        registry = Registry()
    except RegistryError as exc:
        sys.stderr.write(f"registry error: {exc}\n")
        return 2
    dispatch = {
        "rules": _cmd_rules,
        "path": _cmd_path,
        "list-tools": _cmd_list_tools,
        "enable": _cmd_enable,
        "disable": _cmd_disable,
        "review": _cmd_review,
    }
    return dispatch[args.command](args, registry)


if __name__ == "__main__":
    sys.exit(main())
