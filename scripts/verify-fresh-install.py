# SPDX-License-Identifier: MIT
"""End-to-end fresh-install verification of agent-style v0.2.0 from real PyPI + npm.

Creates a scratch directory, makes fresh venv / npm install, exercises the
CLI surface (`--version`, `list-tools`, `rules`, `enable --dry-run --json`,
`enable`), and checks the written files are correct. Works on Windows and
POSIX; the only required binaries on PATH are `python`/`python3` and `npm`.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile

EXPECTED_VERSION = "0.3.5"
EXPECTED_TOOL_COUNT = 10  # v0.3.0 added Kiro to the 9 existing (8 primary + style-review skill)

SCRATCH = tempfile.mkdtemp(prefix="as-final-")
print(f"scratch: {SCRATCH}")
print(f"platform: {sys.platform}")


def sh(cmd, cwd=None):
    return subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)


def section(name):
    print()
    print("=" * 50)
    print(name)
    print("=" * 50)


def check(label, ok, detail=""):
    mark = "PASS" if ok else "FAIL"
    print(f"  [{mark}] {label}" + (f"  ({detail})" if detail else ""))
    return ok


all_ok = True


def exercise(label, cli_path):
    global all_ok

    r = sh([cli_path, "--version"])
    all_ok &= check(f"{label} --version", r.returncode == 0 and EXPECTED_VERSION in r.stdout, r.stdout.strip())

    r = sh([cli_path, "list-tools"])
    tools = [ln.split()[0] for ln in r.stdout.splitlines() if ln.strip()]
    all_ok &= check(f"{label} list-tools count", len(tools) == EXPECTED_TOOL_COUNT, f"{len(tools)} tools")

    r = sh([cli_path, "rules"])
    all_ok &= check(f"{label} rules output", r.returncode == 0 and r.stdout.startswith("<!-- SPDX-License-Identifier"), f"{len(r.stdout)} bytes")

    ws = tempfile.mkdtemp(prefix=f"as-ws-{label}-", dir=SCRATCH)
    r = sh([cli_path, "enable", "claude-code", "--dry-run", "--json"], cwd=ws)
    try:
        data = json.loads(r.stdout)
        ok = (data.get("tool") == "claude-code"
              and data.get("install_mode") == "import-marker"
              and isinstance(data.get("actions"), list)
              and len(data["actions"]) >= 3)
        all_ok &= check(f"{label} enable --dry-run --json", ok, f"{len(data.get('actions', []))} actions, tool={data.get('tool')}, mode={data.get('install_mode')}, keys={sorted(data.keys())[:6]}")
    except Exception as e:
        all_ok &= check(f"{label} enable --dry-run --json parses", False, f"{e}")

    r = sh([cli_path, "enable", "claude-code"], cwd=ws)
    ok = r.returncode == 0
    workspace_files = sorted(os.listdir(ws))
    all_ok &= check(f"{label} enable (real)", ok, f"rc={r.returncode}")
    all_ok &= check(f"{label} CLAUDE.md written", "CLAUDE.md" in workspace_files)
    all_ok &= check(f"{label} .agent-style/ dir written", ".agent-style" in workspace_files)

    claude = os.path.join(ws, "CLAUDE.md")
    if os.path.exists(claude):
        with open(claude, encoding="utf-8") as f:
            c = f.read()
        all_ok &= check(f"{label} CLAUDE.md has BEGIN marker", "BEGIN agent-style" in c, f"{len(c)} bytes")
        all_ok &= check(f"{label} CLAUDE.md has import", "@.agent-style/claude-code.md" in c)

    ast_dir = os.path.join(ws, ".agent-style")
    if os.path.isdir(ast_dir):
        contents = sorted(os.listdir(ast_dir))
        all_ok &= check(f"{label} .agent-style/RULES.md", "RULES.md" in contents)
        all_ok &= check(f"{label} .agent-style/claude-code.md", "claude-code.md" in contents)


# --- Python CLI via real PyPI ---
section(f"Python CLI via real PyPI (pip install agent-style=={EXPECTED_VERSION})")
py_venv = os.path.join(SCRATCH, "py-venv")
subprocess.run([sys.executable, "-m", "venv", py_venv], check=True)

if sys.platform == "win32":
    py_pip = os.path.join(py_venv, "Scripts", "python.exe")
    py_as = os.path.join(py_venv, "Scripts", "agent-style.exe")
else:
    py_pip = os.path.join(py_venv, "bin", "python")
    py_as = os.path.join(py_venv, "bin", "agent-style")

r = sh([py_pip, "-m", "pip", "install", "-q", "--no-cache-dir", "--force-reinstall", f"agent-style=={EXPECTED_VERSION}"])
all_ok &= check("pip install from PyPI", r.returncode == 0, r.stderr[-120:] if r.stderr else "")
exercise("Python", py_as)


# --- Node CLI via real npm ---
section(f"Node CLI via real npm (npm install agent-style@{EXPECTED_VERSION})")
npm_dir = os.path.join(SCRATCH, "npm-install")
os.makedirs(npm_dir)
NPM_BIN = shutil.which("npm") or ("npm.cmd" if sys.platform == "win32" else "npm")
r = sh([NPM_BIN, "install", "--prefix", npm_dir, "--silent", f"agent-style@{EXPECTED_VERSION}"])
all_ok &= check("npm install from registry", r.returncode == 0, r.stderr[-120:] if r.stderr else "")

if sys.platform == "win32":
    node_as = os.path.join(npm_dir, "node_modules", ".bin", "agent-style.cmd")
    if not os.path.exists(node_as):
        node_as = os.path.join(npm_dir, "node_modules", ".bin", "agent-style")
else:
    node_as = os.path.join(npm_dir, "node_modules", ".bin", "agent-style")

exercise("Node  ", node_as)


# --- Cleanup + summary ---
shutil.rmtree(SCRATCH, ignore_errors=True)
print()
print("=" * 50)
if all_ok:
    print("ALL CHECKS PASSED")
    sys.exit(0)
else:
    print("SOME CHECKS FAILED")
    sys.exit(1)
