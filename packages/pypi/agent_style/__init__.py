# SPDX-License-Identifier: MIT
"""agent-style: literature-backed English technical-prose writing ruleset for AI agents.

Programmatic entry points:

    from agent_style import __version__, rules, path, list_tools, enable, disable

See `agent-style --help` for the CLI.
"""

__version__ = "0.3.5"


def rules() -> str:
    """Return the bundled RULES.md content as a string."""
    from agent_style.registry import Registry
    return Registry().read_bundled_rules()


def path() -> str:
    """Return the absolute path of the bundled data directory."""
    from agent_style.registry import Registry
    return Registry().data_dir


def list_tools() -> list:
    """Return a list of (tool_name, install_mode, target_path) tuples."""
    from agent_style.registry import Registry
    r = Registry()
    return [
        (name, spec["install_mode"], spec["target_path"])
        for name, spec in r.tools.items()
    ]


def enable(tool: str, project_root: str = ".", dry_run: bool = False) -> dict:
    """Enable agent-style for the given tool in the given project root.

    Returns a canonical JSON-shaped dict with fields: tool, install_mode, enabled,
    manual_step_required, actions.
    """
    from agent_style.installer import enable as _enable
    from agent_style.registry import Registry
    return _enable(tool, Registry(), project_root=project_root, dry_run=dry_run)


def disable(tool: str, project_root: str = ".", dry_run: bool = False) -> dict:
    """Disable agent-style for the given tool in the given project root."""
    from agent_style.installer import disable as _disable
    from agent_style.registry import Registry
    return _disable(tool, Registry(), project_root=project_root, dry_run=dry_run)
