#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# Smoke test for skill-with-references safety behaviors across both CLIs.
# Covers: ownership proof, atomicity on partial failure, drift fail-closed,
# path-traversal rejection.
#
# Usage: bash scripts/smoke-skill-safety.sh [py|node]  (default: both)

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MODE="${1:-both}"

# Platform-aware PYTHONPATH: use Windows-native separators on MSYS/Cygwin, POSIX elsewhere.
case "$(uname -s)" in
  MINGW*|CYGWIN*|MSYS*)
    PY_DIR_NATIVE="$(cygpath -w "$ROOT/packages/pypi" 2>/dev/null || echo "$ROOT/packages/pypi")"
    PY_SEP=";"
    ;;
  *)
    PY_DIR_NATIVE="$ROOT/packages/pypi"
    PY_SEP=":"
    ;;
esac
export PYTHONPATH="${PY_DIR_NATIVE}${PY_SEP}${PYTHONPATH:-}"

# Python binary: prefer AGENT_STYLE_PYTHON env override; else Miniforge py312 on
# Windows; else python3 / python on PATH.
if [[ -n "${AGENT_STYLE_PYTHON:-}" ]]; then
  PY_BIN="$AGENT_STYLE_PYTHON"
elif [[ -x "/c/Users/yuezh/miniforge3/envs/py312/python.exe" ]]; then
  PY_BIN="/c/Users/yuezh/miniforge3/envs/py312/python.exe"
elif command -v python3 >/dev/null 2>&1; then
  PY_BIN="$(command -v python3)"
elif command -v python >/dev/null 2>&1; then
  PY_BIN="$(command -v python)"
else
  echo "error: no Python interpreter found (tried \$AGENT_STYLE_PYTHON, Miniforge py312, python3, python)" >&2
  exit 2
fi

PY_CLI="$PY_BIN -m agent_style.cli"
NODE_CLI="node $ROOT/packages/npm/bin/agent-style.js"

pass() { printf "  \e[32mPASS\e[0m %s\n" "$1"; }
fail() { printf "  \e[31mFAIL\e[0m %s\n" "$1"; exit 1; }

run_suite() {
  local label="$1"
  local cli="$2"
  echo "=== $label ==="

  local scratch
  scratch="$(mktemp -d -t as-smoke-XXXXXX)"
  trap 'rm -rf "$scratch"' RETURN

  # Enable claude-code first so style-review has an active surface.
  ( cd "$scratch" && $cli enable claude-code >/dev/null )

  # Scenario 1: pre-existing SKILL.md without manifest -> fail closed.
  mkdir -p "$scratch/.claude/skills/style-review"
  echo "# user's prior skill" > "$scratch/.claude/skills/style-review/SKILL.md"
  set +e
  ( cd "$scratch" && $cli enable style-review 2>/dev/null )
  local rc=$?
  set -e
  if [[ $rc -eq 0 ]]; then
    fail "$label scenario 1: expected failure, got exit 0"
  fi
  pass "$label scenario 1: pre-existing SKILL.md blocked overwrite"

  # Scenario 1b: atomicity — no partial writes should have happened.
  if [[ -d "$scratch/.agent-style/skills/style-review/references" ]]; then
    fail "$label scenario 1b: references/ was partially written"
  fi
  if [[ -f "$scratch/.agent-style/skills/style-review/manifest.json" ]]; then
    fail "$label scenario 1b: manifest was partially written"
  fi
  pass "$label scenario 1b: no partial writes on ownership failure"

  # Scenario 2: remove user file, fresh enable -> success.
  rm -f "$scratch/.claude/skills/style-review/SKILL.md"
  ( cd "$scratch" && $cli enable style-review >/dev/null )
  if [[ ! -f "$scratch/.claude/skills/style-review/SKILL.md" ]]; then
    fail "$label scenario 2: SKILL.md missing after enable"
  fi
  if [[ ! -f "$scratch/.agent-style/skills/style-review/manifest.json" ]]; then
    fail "$label scenario 2: manifest missing after enable"
  fi
  pass "$label scenario 2: fresh enable writes all files + manifest"

  # Scenario 3: edit SKILL.md (drift), disable -> fail closed, manifest kept.
  echo "# user edited this after enable" >> "$scratch/.claude/skills/style-review/SKILL.md"
  set +e
  local out
  out=$( cd "$scratch" && $cli disable style-review 2>&1 )
  rc=$?
  set -e
  if [[ $rc -eq 0 ]]; then
    fail "$label scenario 3: disable should fail closed on drift (got 0)"
  fi
  if [[ ! -f "$scratch/.agent-style/skills/style-review/manifest.json" ]]; then
    fail "$label scenario 3: manifest was removed despite drift"
  fi
  if [[ ! -f "$scratch/.claude/skills/style-review/SKILL.md" ]]; then
    fail "$label scenario 3: SKILL.md was removed despite drift"
  fi
  pass "$label scenario 3: disable fail-closed on drift, manifest preserved"

  # Scenario 4: path traversal via malicious manifest — reject without deleting.
  # Restore SKILL.md to match manifest hash so we get past drift check.
  # Simpler: write a fresh install, then tamper with the manifest to contain ../outside.
  rm -rf "$scratch/.agent-style" "$scratch/.claude"
  ( cd "$scratch" && $cli enable claude-code >/dev/null )
  ( cd "$scratch" && $cli enable style-review >/dev/null )
  local outside="$scratch/../outside-$(basename "$scratch").txt"
  echo "untouchable" > "$outside"
  # Tamper manifest: add ../outside-*.txt entry
  local manifest="$scratch/.agent-style/skills/style-review/manifest.json"
  local manifest_native
  manifest_native="$(cygpath -w "$manifest" 2>/dev/null || echo "$manifest")"
  local outside_name
  outside_name="$(basename "$outside")"
  "$PY_BIN" -c "
import json
p = r'''$manifest_native'''
with open(p, encoding='utf-8') as f:
    doc = json.load(f)
doc['entries'].append({
    'path': '../$outside_name',
    'kind': 'file',
    'sha256': 'deadbeef' * 8,
    'covered_surfaces': ['claude-code'],
})
with open(p, 'w', encoding='utf-8') as f:
    json.dump(doc, f, indent=2)
"
  set +e
  out=$( cd "$scratch" && $cli disable style-review 2>&1 )
  rc=$?
  set -e
  if [[ $rc -eq 0 ]]; then
    fail "$label scenario 4: path traversal should have been rejected (got 0)"
  fi
  if [[ ! -f "$outside" ]]; then
    fail "$label scenario 4: outside file was deleted! path traversal succeeded"
  fi
  pass "$label scenario 4: path traversal rejected; outside file intact"
  rm -f "$outside"

  # Scenario 5: manifest entry missing sha256 -> enable fails before any write,
  # disable fails closed; targets and manifest remain in place.
  # Rebuild a clean install, then strip `sha256` from the SKILL.md entry.
  rm -rf "$scratch/.agent-style" "$scratch/.claude"
  ( cd "$scratch" && $cli enable claude-code >/dev/null )
  ( cd "$scratch" && $cli enable style-review >/dev/null )
  local manifest_5="$scratch/.agent-style/skills/style-review/manifest.json"
  local manifest_5_native
  manifest_5_native="$(cygpath -w "$manifest_5" 2>/dev/null || echo "$manifest_5")"
  "$PY_BIN" -c "
import json
p = r'''$manifest_5_native'''
with open(p, encoding='utf-8') as f:
    doc = json.load(f)
for e in doc['entries']:
    if e.get('path','').endswith('SKILL.md'):
        e.pop('sha256', None)
        break
with open(p, 'w', encoding='utf-8') as f:
    json.dump(doc, f, indent=2)
"
  # 5a: enable must fail (malformed manifest rejected before any write)
  set +e
  out=$( cd "$scratch" && $cli enable style-review 2>&1 )
  rc=$?
  set -e
  if [[ $rc -eq 0 ]]; then
    fail "$label scenario 5a: enable should refuse malformed manifest (got 0)"
  fi
  pass "$label scenario 5a: missing sha256 blocks re-enable"

  # 5b: disable must fail closed (manifest + target file preserved)
  set +e
  out=$( cd "$scratch" && $cli disable style-review 2>&1 )
  rc=$?
  set -e
  if [[ $rc -eq 0 ]]; then
    fail "$label scenario 5b: disable should fail closed on missing sha256 (got 0)"
  fi
  if [[ ! -f "$scratch/.agent-style/skills/style-review/manifest.json" ]]; then
    fail "$label scenario 5b: manifest was removed despite malformed entry"
  fi
  if [[ ! -f "$scratch/.claude/skills/style-review/SKILL.md" ]]; then
    fail "$label scenario 5b: SKILL.md was removed despite malformed entry"
  fi
  pass "$label scenario 5b: missing sha256 blocks disable; manifest + target preserved"

  # Scenario 6: refused enable leaves no .agent-style/ or .claude/ files behind
  # when they did not exist before. Start from a truly clean scratch with only a
  # pre-existing user SKILL.md at the target path.
  local scratch6
  scratch6="$(mktemp -d -t as-smoke6-XXXXXX)"
  mkdir -p "$scratch6/.claude/skills/style-review"
  echo "# user-authored skill; not ours" > "$scratch6/.claude/skills/style-review/SKILL.md"
  # Make claude-code surface active WITHOUT letting agent-style write .agent-style/
  # Create an empty CLAUDE.md to signal the surface is active.
  touch "$scratch6/CLAUDE.md"
  rm -rf "$scratch6/.agent-style"  # guarantee we start with none
  set +e
  out=$( cd "$scratch6" && $cli enable style-review 2>&1 )
  rc=$?
  set -e
  if [[ $rc -eq 0 ]]; then
    fail "$label scenario 6: enable should refuse pre-existing SKILL.md (got 0)"
  fi
  if [[ -d "$scratch6/.agent-style" ]]; then
    fail "$label scenario 6: .agent-style/ was created despite refusal (atomicity broken)"
  fi
  pass "$label scenario 6: refused enable leaves no .agent-style/ footprint"
  rm -rf "$scratch6"

  # Scenario 7: manifest with entries:[] but live targets -> disable fails closed.
  # Rebuild clean install, then overwrite manifest with empty entries.
  rm -rf "$scratch/.agent-style" "$scratch/.claude"
  ( cd "$scratch" && $cli enable claude-code >/dev/null )
  ( cd "$scratch" && $cli enable style-review >/dev/null )
  local manifest_7="$scratch/.agent-style/skills/style-review/manifest.json"
  local manifest_7_native
  manifest_7_native="$(cygpath -w "$manifest_7" 2>/dev/null || echo "$manifest_7")"
  "$PY_BIN" -c "
import json
p = r'''$manifest_7_native'''
with open(p, encoding='utf-8') as f:
    doc = json.load(f)
doc['entries'] = []
with open(p, 'w', encoding='utf-8') as f:
    json.dump(doc, f, indent=2)
"
  set +e
  out=$( cd "$scratch" && $cli disable style-review 2>&1 )
  rc=$?
  set -e
  if [[ $rc -eq 0 ]]; then
    fail "$label scenario 7: disable should fail closed on empty entries + live target (got 0)"
  fi
  if [[ ! -f "$scratch/.agent-style/skills/style-review/manifest.json" ]]; then
    fail "$label scenario 7: manifest was removed despite uncovered live target"
  fi
  if [[ ! -f "$scratch/.claude/skills/style-review/SKILL.md" ]]; then
    fail "$label scenario 7: SKILL.md was removed despite uncovered state"
  fi
  pass "$label scenario 7: empty entries with live target blocks disable"

  # Scenario 8: absent-manifest after a never-installed project -> clean no-op.
  # Verifies the coverage check does not false-trigger on legitimate "not installed" state.
  local scratch8
  scratch8="$(mktemp -d -t as-smoke8-XXXXXX)"
  touch "$scratch8/CLAUDE.md"  # claude-code surface active, but nothing else
  set +e
  out=$( cd "$scratch8" && $cli disable style-review 2>&1 )
  rc=$?
  set -e
  if [[ $rc -ne 0 ]]; then
    fail "$label scenario 8: absent-manifest + no targets should no-op (rc=$rc)"
  fi
  pass "$label scenario 8: absent-manifest + no targets is a clean no-op"
  rm -rf "$scratch8"

  rm -rf "$scratch"
  echo ""
}

[[ "$MODE" == "py" || "$MODE" == "both" ]] && run_suite "python" "$PY_CLI"
[[ "$MODE" == "node" || "$MODE" == "both" ]] && run_suite "node  " "$NODE_CLI"

echo "smoke test passed"
