# SPDX-License-Identifier: MIT
"""Smoke test for the Python agent-style CLI (in-tree, without installing)."""

import os
import subprocess
import sys
import tempfile

ROOT = r"C:\Users\yuezh\PycharmProjects\agent-style"
PYPATH = os.path.join(ROOT, "packages", "pypi")
env = os.environ.copy()
env["PYTHONPATH"] = PYPATH + os.pathsep + env.get("PYTHONPATH", "")

def run(args, **kwargs):
    kwargs.setdefault("env", env)
    kwargs.setdefault("capture_output", True)
    kwargs.setdefault("text", True)
    return subprocess.run([sys.executable, "-m", "agent_style.cli", *args], **kwargs)

def main():
    print("=== --version ===")
    r = run(["--version"])
    print(r.stdout, r.stderr)

    print("=== list-tools ===")
    r = run(["list-tools"])
    print(r.stdout)
    if r.stderr:
        print("stderr:", r.stderr)

    with tempfile.TemporaryDirectory(prefix="agent-style-smoke-") as scratch:
        print(f"=== enable claude-code --dry-run --json (scratch={scratch}) ===")
        r = run(["enable", "claude-code", "--dry-run", "--json"], cwd=scratch)
        print(r.stdout)
        if r.stderr:
            print("stderr:", r.stderr)

        print(f"=== enable agents-md --dry-run --json ===")
        r = run(["enable", "agents-md", "--dry-run", "--json"], cwd=scratch)
        print(r.stdout)
        if r.stderr:
            print("stderr:", r.stderr)

        print(f"=== enable cursor --dry-run --json ===")
        r = run(["enable", "cursor", "--dry-run", "--json"], cwd=scratch)
        print(r.stdout)
        if r.stderr:
            print("stderr:", r.stderr)

        print(f"=== enable aider --dry-run --json (multi-file-required) ===")
        r = run(["enable", "aider", "--dry-run", "--json"], cwd=scratch)
        print(r.stdout)
        if r.stderr:
            print("stderr:", r.stderr)

        print(f"=== enable codex --dry-run --json (print-only) ===")
        r = run(["enable", "codex", "--dry-run", "--json"], cwd=scratch)
        print(r.stdout)
        if r.stderr:
            print("stderr:", r.stderr)

if __name__ == "__main__":
    main()
