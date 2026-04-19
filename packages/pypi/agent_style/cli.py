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
import sys
from typing import Any

from agent_style import __version__
from agent_style.installer import enable, disable, canonical_json
from agent_style.registry import Registry, RegistryError


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
        print(f"{name:18}  {spec['install_mode']:22}  {spec['target_path']}")
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
    }
    return dispatch[args.command](args, registry)


if __name__ == "__main__":
    sys.exit(main())
