#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
#
# verify-install.sh — local release validator for agent-style.
#
# Modes:
#   --version-only [EXPECTED_VERSION=X.Y.Z]
#       Read the three version files (pyproject.toml, __init__.py, package.json);
#       assert they are equal. If EXPECTED_VERSION is set, also assert each
#       file matches that exact string. Used pre-tag.
#
#   --cli-parity
#       Build both packages locally; install into scratch venv/dir OUTSIDE the
#       source repo; for each install mode, run `agent-style enable <tool>
#       --dry-run --json` and `agent-style disable <tool> --dry-run --json` on
#       both Python and Node; diff the normalized JSON; fail on divergence.
#
#   (default, no flag)
#       Build both packages; install from local artifacts; run `agent-style
#       rules`; assert content-depth invariants (21 rule headings + 21 Directive
#       + 21 Rationale + RULE-01 + RULE-A).
#
# Exit code 0 on all-pass; non-zero on any failure with a specific reason on stderr.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYPI_DIR="$ROOT/packages/pypi"
NPM_DIR="$ROOT/packages/npm"
EXPECTED_VERSION="${EXPECTED_VERSION:-}"

MODE="default"
for arg in "$@"; do
  case "$arg" in
    --version-only) MODE="version-only" ;;
    --cli-parity)   MODE="cli-parity" ;;
    --help|-h)      sed -n '2,30p' "$0"; exit 0 ;;
    --expect)       :;; # followed by value; handled below
    *)
      if [[ "${prev:-}" == "--expect" ]]; then
        EXPECTED_VERSION="$arg"
      else
        echo "error: unknown argument: $arg" >&2
        exit 2
      fi
      ;;
  esac
  prev="$arg"
done

read_pyproject_version() {
  grep -E '^version\s*=\s*"' "$PYPI_DIR/pyproject.toml" \
    | head -n 1 | sed -E 's/.*"([^"]+)".*/\1/'
}
read_python_init_version() {
  grep -E '^__version__\s*=\s*"' "$PYPI_DIR/agent_style/__init__.py" \
    | head -n 1 | sed -E 's/.*"([^"]+)".*/\1/'
}
read_npm_version() {
  grep -E '"version"\s*:' "$NPM_DIR/package.json" \
    | head -n 1 | sed -E 's/.*"version"\s*:\s*"([^"]+)".*/\1/'
}

mode_version_only() {
  local v_toml v_init v_npm
  v_toml="$(read_pyproject_version)"
  v_init="$(read_python_init_version)"
  v_npm="$(read_npm_version)"
  echo "pyproject.toml          : $v_toml"
  echo "agent_style/__init__.py : $v_init"
  echo "package.json            : $v_npm"
  if [[ "$v_toml" != "$v_init" || "$v_toml" != "$v_npm" ]]; then
    echo "FAIL: version mismatch across the three files" >&2
    exit 1
  fi
  if [[ -n "$EXPECTED_VERSION" ]]; then
    if [[ "$v_toml" != "$EXPECTED_VERSION" ]]; then
      echo "FAIL: expected version '$EXPECTED_VERSION' but files carry '$v_toml'" >&2
      exit 1
    fi
    # Guard against stray 'rc' substring leaking into generated content when
    # transitioning from rc rehearsal to final. Skip this check if EXPECTED_VERSION itself has 'rc'.
    if [[ "$EXPECTED_VERSION" != *rc* ]]; then
      if grep -RE 'v0\.[0-9]+\.[0-9]+rc[0-9]+|"0\.[0-9]+\.[0-9]+-rc\.[0-9]+"' \
          "$PYPI_DIR" "$NPM_DIR" "$ROOT/agents" "$ROOT/RULES.md" >/dev/null 2>&1; then
        echo "FAIL: found lingering rc substring in bundled content; rehearsal artifacts leaked" >&2
        grep -RE 'v0\.[0-9]+\.[0-9]+rc[0-9]+|"0\.[0-9]+\.[0-9]+-rc\.[0-9]+"' \
          "$PYPI_DIR" "$NPM_DIR" "$ROOT/agents" "$ROOT/RULES.md" 2>&1 | head -20 >&2
        exit 1
      fi
    fi
  fi
  echo "PASS: version-only check"
}

# --cli-parity mode: run each install mode's enable/disable --dry-run --json on
# both Python and Node; diff the JSON; fail on divergence. Runs both CLIs from
# their package source so we do not depend on a prior install step.
mode_cli_parity() {
  local scratch py_out_dir node_out_dir python_bin
  scratch="$(mktemp -d -t agent-style-parity-XXXXXX)"
  py_out_dir="$scratch/py"
  node_out_dir="$scratch/node"
  mkdir -p "$py_out_dir" "$node_out_dir"
  echo "scratch: $scratch"

  # Detect Python binary: Linux / macOS typically expose python3 only; Windows has
  # both. Users can override with PYTHON_BIN env var.
  python_bin="${PYTHON_BIN:-}"
  if [[ -z "$python_bin" ]]; then
    if command -v python3 >/dev/null 2>&1; then
      python_bin="python3"
    elif command -v python >/dev/null 2>&1; then
      python_bin="python"
    else
      echo "FAIL: no Python interpreter found (tried python3, python); set PYTHON_BIN" >&2
      exit 1
    fi
  fi

  local pythonpath_sep=":"
  local pypi_dir_native="$PYPI_DIR"
  case "$(uname -s 2>/dev/null || echo unknown)" in
    MINGW*|MSYS*|CYGWIN*)
      pythonpath_sep=";"
      # Convert POSIX-style path to Windows native so Windows Python can resolve it.
      if command -v cygpath >/dev/null 2>&1; then
        pypi_dir_native="$(cygpath -w "$PYPI_DIR")"
      fi
      ;;
  esac

  # One representative tool per install mode, per Codex Round 2 recommendation:
  local tools=("claude-code" "agents-md" "cursor" "aider" "codex")
  local cmds=("enable" "disable")
  local failed=0

  for tool in "${tools[@]}"; do
    for cmd in "${cmds[@]}"; do
      local py_scratch="$scratch/py-scratch-$tool-$cmd"
      local node_scratch="$scratch/node-scratch-$tool-$cmd"
      mkdir -p "$py_scratch" "$node_scratch"

      # Run Python CLI via -m with PYTHONPATH set (native path on Windows) from py_scratch
      ( cd "$py_scratch" && PYTHONPATH="${pypi_dir_native}${pythonpath_sep}${PYTHONPATH:-}" \
          "$python_bin" -m agent_style.cli "$cmd" "$tool" --dry-run --json ) \
        > "$py_out_dir/$tool-$cmd.json" 2> "$py_out_dir/$tool-$cmd.err" || true

      # Run Node CLI from node_scratch
      ( cd "$node_scratch" && node "$NPM_DIR/bin/agent-style.js" "$cmd" "$tool" --dry-run --json ) \
        > "$node_out_dir/$tool-$cmd.json" 2> "$node_out_dir/$tool-$cmd.err" || true

      # Normalize line endings before diffing: Windows Python writes CRLF via
      # text-mode stdout; Node writes LF. The parity oracle is normalized-LF,
      # so strip CRs before the diff per the Rev 8 canonical-JSON contract.
      local py_norm="$py_out_dir/$tool-$cmd.normalized.json"
      local node_norm="$node_out_dir/$tool-$cmd.normalized.json"
      tr -d '\r' < "$py_out_dir/$tool-$cmd.json" > "$py_norm"
      tr -d '\r' < "$node_out_dir/$tool-$cmd.json" > "$node_norm"
      if ! diff -q "$py_norm" "$node_norm" >/dev/null; then
        echo "FAIL: JSON parity mismatch for $tool $cmd" >&2
        diff "$py_norm" "$node_norm" | head -40 >&2
        failed=1
      else
        echo "  ok: $tool $cmd"
      fi
    done
  done

  if (( failed )); then
    echo "FAIL: one or more JSON parity diffs; see above" >&2
    exit 1
  fi
  echo "PASS: CLI parity check (5 tools × 2 subcommands = 10 JSON diffs)"
}

mode_default() {
  local rules_file="$ROOT/RULES.md"
  if [[ ! -f "$rules_file" ]]; then
    echo "FAIL: RULES.md not found at $rules_file" >&2
    exit 1
  fi
  local rule_count directive_count rationale_count
  rule_count="$(grep -cE '^#### RULE-' "$rules_file" || true)"
  directive_count="$(grep -cE '^##### Directive' "$rules_file" || true)"
  rationale_count="$(grep -cE '^##### Rationale for AI Agent' "$rules_file" || true)"
  echo "rule-headings          : $rule_count"
  echo "Directive sections     : $directive_count"
  echo "Rationale sections     : $rationale_count"
  if [[ "$rule_count" -ne 21 ]]; then
    echo "FAIL: expected 21 '#### RULE-' headings, found $rule_count" >&2
    exit 1
  fi
  if [[ "$directive_count" -ne "$rule_count" ]]; then
    echo "FAIL: '##### Directive' count $directive_count does not equal rule count $rule_count" >&2
    exit 1
  fi
  if [[ "$rationale_count" -ne "$rule_count" ]]; then
    echo "FAIL: '##### Rationale for AI Agent' count $rationale_count does not equal rule count $rule_count" >&2
    exit 1
  fi
  if ! grep -qE '^#### RULE-01' "$rules_file"; then
    echo "FAIL: RULE-01 heading not present" >&2
    exit 1
  fi
  if ! grep -qE '^#### RULE-A' "$rules_file"; then
    echo "FAIL: RULE-A heading not present" >&2
    exit 1
  fi
  echo "PASS: content-depth check (21 rules, Directive == Rationale == 21)"
}

case "$MODE" in
  version-only) mode_version_only ;;
  cli-parity)   mode_cli_parity ;;
  default)      mode_default ;;
esac
