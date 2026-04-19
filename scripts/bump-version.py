# SPDX-License-Identifier: MIT
"""Rewrite version strings across tracked files for a release bump.

Usage:
    python scripts/bump-version.py 0.1.0 0.1.1

- Skips CHANGELOG.md (historical version references stay pinned).
- Walks tracked files ending in .md / .py / .js / .mdc / .json / .toml.
- Applies a small set of exact-match replacements: `vX.Y.Z`, `"X.Y.Z"`,
  `agent-style@X.Y.Z`, `// X.Y.Z`, and `EXPECTED_VERSION = "X.Y.Z"`.
"""

import os
import subprocess
import sys

if len(sys.argv) != 3:
    sys.exit("usage: bump-version.py <old> <new>")

OLD, NEW = sys.argv[1], sys.argv[2]
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXTS = (".md", ".py", ".js", ".mdc", ".json", ".toml")
SKIP = {"CHANGELOG.md"}

PATTERNS = [
    (f"v{OLD}", f"v{NEW}"),
    (f'"{OLD}"', f'"{NEW}"'),
    (f"agent-style@{OLD}", f"agent-style@{NEW}"),
    (f"// {OLD}", f"// {NEW}"),
    (f'EXPECTED_VERSION = "{OLD}"', f'EXPECTED_VERSION = "{NEW}"'),
]

files = subprocess.check_output(["git", "-C", ROOT, "ls-files"], text=True).splitlines()
changed = 0
for rel in files:
    if not rel.endswith(EXTS) or rel in SKIP:
        continue
    path = os.path.join(ROOT, rel)
    try:
        with open(path, "rb") as f:
            data = f.read()
    except FileNotFoundError:
        continue
    new_data = data
    for old, new in PATTERNS:
        new_data = new_data.replace(old.encode("utf-8"), new.encode("utf-8"))
    if new_data != data:
        with open(path, "wb") as f:
            f.write(new_data)
        changed += 1
        print(f"  updated: {rel}")
print(f"total: {changed} files")
