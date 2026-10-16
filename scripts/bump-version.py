# SPDX-License-Identifier: MIT
"""Rewrite version strings across tracked files for a release bump.

Usage:
    python scripts/bump-version.py 0.1.0 0.1.1

- Skips the files and directories that narrate past releases (see SKIP below).
- Refuses to run when any of the five version-carrying files has drifted off OLD.
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
# These files narrate past releases by version number, so a blanket rewrite
# would falsify the record. RELEASING.md recounts which release fix-forwarded a
# packaging bug and which registry artifact still carries it; those sentences
# have to keep naming the release it happened in. TODO.md joined them after a
# bump silently rewrote "wait for the next bench" and "a new task for the next
# cycle" into the version being released, which changed what those entries
# asked for.
#
# Skipping is not the same as holding nothing live. CHANGELOG.md is mixed: its
# past entries must stay pinned, while its top-of-file "Version distribution"
# banner names the release being cut and is what RELEASING.md consults to decide
# what may be published. That banner is prose, so no exact-match pattern here
# can maintain it, and the drift check below cannot see it either. MANUAL_CHECKS
# is printed on every run so the ones this script deliberately will not touch
# are named rather than merely omitted.
# (Do not put a literal version in this comment: the script rewrites its own
# source too.)
SKIP = {"CHANGELOG.md", "RELEASING.md", "TODO.md"}

MANUAL_CHECKS = [
    'CHANGELOG.md: the "Version distribution" banner names this release and the'
    " previous shared registry release",
    "CHANGELOG.md: move [Unreleased] to ## [NEW] with the release date",
    "CHANGELOG.md: compare-link block at the bottom resolves [NEW] and points"
    " [Unreleased] at the new tag",
]

# Directories whose contents are dated records rather than live documentation.
# `docs/followups/` files are named for the day they were written and argue about
# a release that was upcoming at the time. A bump rewrote one into claiming that
# the release being prepared, rather than the one before it, had been the first
# to fire the publish workflow, and collapsed a two-sided "hand-publish this one,
# make the next one the OIDC cut" choice into naming the same release twice.
# Bench reports and their harness record the release they measured. One bump
# retitled the habit bench as a run of the release being prepared, shipped on
# the earlier release's date, and pointed its README at a report that does not
# exist. (No literal version here: the script rewrites its own source too.)
SKIP_PREFIXES = ("docs/followups/", "docs/bench", "scripts/bench/")

PATTERNS = [
    (f"v{OLD}", f"v{NEW}"),
    (f'"{OLD}"', f'"{NEW}"'),
    (f"agent-style@{OLD}", f"agent-style@{NEW}"),
    (f"// {OLD}", f"// {NEW}"),
    (f'EXPECTED_VERSION = "{OLD}"', f'EXPECTED_VERSION = "{NEW}"'),
]

# Every file that must carry the release version. Exact-string replacement
# silently skips a value that has already drifted, which is how both tools.json
# mirrors sat at 0.2.0 across two releases. Refuse to run unless all five agree
# with OLD, so drift is reported instead of being carried forward.
VERSION_FILES = {
    "packages/pypi/pyproject.toml": f'version = "{OLD}"',
    "packages/pypi/agent_style/__init__.py": f'__version__ = "{OLD}"',
    "packages/npm/package.json": f'"version": "{OLD}"',
    "packages/pypi/agent_style/data/tools.json": f'"agent_style_version": "{OLD}"',
    "packages/npm/data/tools.json": f'"agent_style_version": "{OLD}"',
}
drift = []
for rel, needle in VERSION_FILES.items():
    path = os.path.join(ROOT, rel)
    try:
        with open(path, encoding="utf-8") as f:
            if needle not in f.read():
                drift.append(rel)
    except FileNotFoundError:
        drift.append(f"{rel} (missing)")
if drift:
    sys.exit(
        f"refusing to bump: these files do not currently carry {OLD}:\n  "
        + "\n  ".join(drift)
        + "\nFix them to the current version first, then re-run."
    )

files = subprocess.check_output(["git", "-C", ROOT, "ls-files"], text=True).splitlines()
changed = 0
for rel in files:
    if not rel.endswith(EXTS) or rel in SKIP or rel.startswith(SKIP_PREFIXES):
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
print(f"\nstill to do by hand ({len(MANUAL_CHECKS)}), none of which this script can rewrite:")
for check in MANUAL_CHECKS:
    print(f"  [ ] {check.replace('[NEW]', f'[{NEW}]')}")
