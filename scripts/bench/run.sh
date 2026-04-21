#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
#
# scripts/bench/run.sh  --  sanity benchmark for agent-style (per-runner).
#
# Runs 10 fixed prose tasks × 2 generations × 2 conditions (baseline /
# treatment) against a specified runner and model. Scores each draft with
# `agent-style review --mechanical-only --audit-only`. Produces a Markdown
# scorecard at docs/bench-<VERSION>-<RUNNER>.md. Use
# `scripts/bench/aggregate.py` to combine multiple runners into a matrix.
#
# Usage:
#   bash scripts/bench/run.sh --runner <claude|gemini|openai> --model <id> \
#                             [--output PATH] [--generations N]
#
# Runners:
#   claude  — Claude Code CLI. Treatment: `agent-style enable claude-code`.
#             --model: opus / sonnet / full-id (e.g. claude-opus-4-7).
#             env: ANTHROPIC_API_KEY
#   gemini  — Gemini CLI with AGENTS.md as context. Treatment:
#             `agent-style enable agents-md` + `.gemini/settings.json` with
#             `context.fileName = ["AGENTS.md","GEMINI.md"]`.
#             --model: e.g. gemini-2.5-pro, gemini-2.5-flash.
#             env: GEMINI_API_KEY
#   openai  — OpenAI Agents SDK. Treatment loads
#             `.agent-style/codex-system-prompt.md` into Agent(instructions=).
#             --model: e.g. gpt-5.4, gpt-5.4-mini, gpt-5.4-nano.
#             env: OPENAI_API_KEY
#
# Cost estimates (40 calls = 10 tasks × 2 gens × 2 conditions):
#   claude --model claude-opus-4-7:   ~$1.20
#   claude --model claude-sonnet-4-6: ~$0.40
#   gemini --model gemini-2.5-pro:    ~$0.10 (free tier may cover)
#   openai --model gpt-5.4:           ~$0.17

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
TASKS_FILE="$ROOT/scripts/bench/tasks.md"

RUNNER=""
MODEL=""
OUTPUT=""
GENS=2
while [[ $# -gt 0 ]]; do
  case "$1" in
    --runner) RUNNER="$2"; shift 2 ;;
    --model) MODEL="$2"; shift 2 ;;
    --output) OUTPUT="$2"; shift 2 ;;
    --generations) GENS="$2"; shift 2 ;;
    --help|-h) sed -n '2,38p' "$0"; exit 0 ;;
    *) echo "error: unknown arg: $1" >&2; exit 2 ;;
  esac
done

case "${RUNNER:-}" in
  claude|gemini|openai) ;;
  "") echo "error: --runner required (claude|gemini|openai)" >&2; exit 2 ;;
  *) echo "error: unknown runner '$RUNNER' (expected claude|gemini|openai)" >&2; exit 2 ;;
esac
[[ -n "$MODEL" ]] || { echo "error: --model required" >&2; exit 2; }

# Hard cap on --generations. The workflow_dispatch cost estimate (~$1.47 at
# GENS=2, per-model flagships) assumes 2 generations. Anything higher
# multiplies cost proportionally; a typo like "20" would 10x the bill. If a
# larger run is ever warranted, bump this cap intentionally and update the
# cost estimate in the workflow comment in the same commit.
case "$GENS" in
  1|2) ;;
  *) echo "error: --generations must be 1 or 2 (got: $GENS); higher values multiply cost and are not budget-approved" >&2; exit 2 ;;
esac

# Shared dependencies.
command -v agent-style >/dev/null 2>&1 || { echo "error: agent-style CLI not on PATH" >&2; exit 2; }
command -v jq >/dev/null 2>&1 || { echo "error: jq is required" >&2; exit 2; }

# Per-runner env + CLI presence checks.
case "$RUNNER" in
  claude)
    [[ -n "${ANTHROPIC_API_KEY:-}" ]] || { echo "error: ANTHROPIC_API_KEY must be set for --runner claude" >&2; exit 2; }
    command -v claude >/dev/null 2>&1 || { echo "error: claude CLI not on PATH (npm install -g @anthropic-ai/claude-code)" >&2; exit 2; }
    RUNNER_LABEL="Claude Code CLI ($MODEL)"
    ;;
  gemini)
    [[ -n "${GEMINI_API_KEY:-}" ]] || { echo "error: GEMINI_API_KEY must be set for --runner gemini" >&2; exit 2; }
    command -v gemini >/dev/null 2>&1 || { echo "error: gemini CLI not on PATH (npm install -g @google/gemini-cli)" >&2; exit 2; }
    RUNNER_LABEL="Gemini CLI ($MODEL)"
    ;;
  openai)
    [[ -n "${OPENAI_API_KEY:-}" ]] || { echo "error: OPENAI_API_KEY must be set for --runner openai" >&2; exit 2; }
    PYTHON_BIN="${PYTHON_BIN:-}"
    if [[ -z "$PYTHON_BIN" ]]; then
      if command -v python3 >/dev/null 2>&1; then PYTHON_BIN="$(command -v python3)"
      elif command -v python >/dev/null 2>&1; then PYTHON_BIN="$(command -v python)"
      else echo "error: no python interpreter for --runner openai" >&2; exit 2; fi
    fi
    "$PYTHON_BIN" -c "import agents" 2>/dev/null || { echo "error: openai-agents not importable (pip install openai-agents)" >&2; exit 2; }
    RUNNER_LABEL="OpenAI Agents SDK ($MODEL)"
    ;;
esac

AS_VERSION="$(agent-style --version | awk '{print $2}')"
if [[ -z "$OUTPUT" ]]; then
  OUTPUT="$ROOT/docs/bench-${AS_VERSION}-${RUNNER}.md"
fi
mkdir -p "$(dirname "$OUTPUT")"

SCRATCH="$(mktemp -d -t as-bench-XXXXXX)"
trap 'rm -rf "$SCRATCH"' EXIT

# Parse tasks.md: one $SCRATCH/prompt/<id>.txt per task; $SCRATCH/ids.txt in order.
mkdir -p "$SCRATCH/prompt"
: > "$SCRATCH/ids.txt"
awk -v SCRATCH="$SCRATCH" '
  /<task id=/ {
    match($0, /id="[^"]+"/); id = substr($0, RSTART + 4, RLENGTH - 5);
    in_task = 1; in_prompt = 0; buf = ""; next
  }
  in_task && /<prompt>/ { in_prompt = 1; next }
  in_prompt && /<\/prompt>/ {
    in_prompt = 0
    outfile = SCRATCH "/prompt/" id ".txt"
    printf "%s", buf > outfile
    close(outfile)
    print id >> SCRATCH "/ids.txt"
    next
  }
  in_prompt { buf = buf (buf ? "\n" : "") $0; next }
  in_task && /<\/task>/ { in_task = 0; id = "" }
' "$TASKS_FILE"

TASK_COUNT="$(wc -l < "$SCRATCH/ids.txt" | tr -d ' ')"
[[ "$TASK_COUNT" -gt 0 ]] || { echo "error: no tasks parsed from $TASKS_FILE" >&2; exit 2; }
echo "parsed $TASK_COUNT tasks"
echo "runner: $RUNNER_LABEL"

# Set up a per-task, per-condition workspace. Treatment installs the adapter
# the runner reads; baseline leaves the workspace empty.
setup_workspace() {
  local ws="$1" cond="$2"
  case "$RUNNER" in
    claude)
      if [[ "$cond" == "treatment" ]]; then
        ( cd "$ws" && agent-style enable claude-code >/dev/null )
      fi
      ;;
    gemini)
      if [[ "$cond" == "treatment" ]]; then
        ( cd "$ws" && agent-style enable agents-md >/dev/null )
        mkdir -p "$ws/.gemini"
        # Gemini CLI defaults to GEMINI.md for context; override to prefer the
        # AGENTS.md the adapter writes. Keep GEMINI.md as a fallback.
        printf '%s\n' '{"context":{"fileName":["AGENTS.md","GEMINI.md"]}}' > "$ws/.gemini/settings.json"
      fi
      ;;
    openai)
      if [[ "$cond" == "treatment" ]]; then
        ( cd "$ws" && agent-style enable codex >/dev/null 2>&1 )
      fi
      ;;
  esac
}

# Minimum bytes a valid draft must contain. 20 chars catches empty responses,
# API-error HTML pages written to stdout, single-word outputs, etc. Short
# prompts (commit messages) still easily exceed this floor.
MIN_DRAFT_BYTES=20

# Generate a single draft. Writes $ws/draft-$gen.md and $ws/draft-$gen.err.
# Fails CLOSED: any non-zero runner exit, missing draft, or sub-MIN_DRAFT_BYTES
# draft aborts the whole bench with full context (task id, condition, gen,
# runner, model, stderr tail). This prevents silent zero-violation scorecards
# from partial failures — a paid matrix run that looks green but measured
# nothing is worse than a failed run you can diagnose.
generate_draft() {
  local ws="$1" cond="$2" gen="$3" prompt_file="$4"
  local out="$ws/draft-${gen}.md"
  local err="$ws/draft-${gen}.err"
  local rc=0
  # CRITICAL: every runner MUST redirect stdin (either to the prompt file or
  # /dev/null). The outer task-id loop reads from $SCRATCH/ids.txt via
  # `while IFS= read -r TASK_ID; do ... done < ids.txt`, so stdin inside the
  # loop is the remaining ids stream. Runners that read stdin by default
  # (gemini CLI is one) will drain the loop after iteration 1, silently
  # producing a scorecard with only task 1 recorded. Always close stdin.
  case "$RUNNER" in
    claude)
      ( cd "$ws" && claude -p --model "$MODEL" < "$prompt_file" > "$out" 2> "$err" ) || rc=$?
      ;;
    gemini)
      local prompt
      prompt="$(cat "$prompt_file")"
      ( cd "$ws" && gemini --prompt "$prompt" --model "$MODEL" < /dev/null > "$out" 2> "$err" ) || rc=$?
      ;;
    openai)
      local -a extra_args=()
      if [[ "$cond" == "treatment" ]]; then
        extra_args=(--instructions-file "$ws/.agent-style/codex-system-prompt.md")
      fi
      "$PYTHON_BIN" "$ROOT/scripts/bench/runners/run_openai.py" \
        --model "$MODEL" \
        --prompt-file "$prompt_file" \
        "${extra_args[@]}" \
        < /dev/null > "$out" 2> "$err" || rc=$?
      ;;
  esac
  if [[ $rc -ne 0 ]]; then
    echo "::error::runner $RUNNER (model $MODEL) exited $rc on $(basename "$ws")/gen-$gen ($cond)" >&2
    echo "--- stderr tail ---" >&2
    tail -n 20 "$err" >&2 || true
    exit 1
  fi
  local bytes
  bytes="$(wc -c < "$out" 2>/dev/null || echo 0)"
  if [[ "$bytes" -lt "$MIN_DRAFT_BYTES" ]]; then
    echo "::error::draft too short ($bytes < $MIN_DRAFT_BYTES bytes) for $(basename "$ws")/gen-$gen ($cond, $RUNNER $MODEL)" >&2
    echo "--- stderr tail ---" >&2
    tail -n 20 "$err" >&2 || true
    echo "--- draft contents ---" >&2
    cat "$out" >&2 || true
    exit 1
  fi
}

# Scorecard header.
{
  echo "# agent-style bench — v${AS_VERSION} (runner: $RUNNER_LABEL)"
  echo ""
  echo "- Runner: $RUNNER_LABEL"
  echo "- Generations per condition: ${GENS}"
  echo "- Date: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "- agent-style version: ${AS_VERSION}"
  echo ""
  echo "## Per-task per-rule delta (mechanical + structural; semantic excluded)"
  echo ""
  echo "| Task | Baseline total | Treatment total | Delta | Dominant rule |"
  echo "|---|---|---|---|---|"
} > "$OUTPUT"

GRAND_A=0
GRAND_B=0
TASKS_PROCESSED=0
PER_RULE_A_FILE="$SCRATCH/per-rule-a.json"
PER_RULE_B_FILE="$SCRATCH/per-rule-b.json"
echo "{}" > "$PER_RULE_A_FILE"
echo "{}" > "$PER_RULE_B_FILE"

while IFS= read -r TASK_ID; do
  [[ -z "$TASK_ID" ]] && continue
  PROMPT_FILE="$SCRATCH/prompt/$TASK_ID.txt"
  [[ -s "$PROMPT_FILE" ]] || { echo "warning: empty prompt for $TASK_ID; skipping" >&2; continue; }
  echo "--- task: $TASK_ID ---"
  TASK_A="$SCRATCH/$TASK_ID-baseline"
  TASK_B="$SCRATCH/$TASK_ID-treatment"
  mkdir -p "$TASK_A" "$TASK_B"
  setup_workspace "$TASK_A" baseline
  setup_workspace "$TASK_B" treatment

  TASK_A_TOTAL=0
  TASK_B_TOTAL=0
  for gen in $(seq 1 "$GENS"); do
    # generate_draft fails closed on any runner error or short draft, so drafts
    # here are guaranteed to be non-empty and past the min-bytes gate.
    generate_draft "$TASK_A" baseline "$gen" "$PROMPT_FILE"
    A_JSON="$(agent-style review --mechanical-only --audit-only "$TASK_A/draft-${gen}.md")"
    if ! A_TOTAL="$(jq -er '.total_violations | numbers' <<<"$A_JSON")"; then
      echo "::error::scorer JSON lacks numeric .total_violations for $TASK_ID baseline gen-$gen" >&2
      echo "$A_JSON" >&2
      exit 1
    fi
    TASK_A_TOTAL=$((TASK_A_TOTAL + A_TOTAL))
    echo "$A_JSON" | jq --slurpfile acc "$PER_RULE_A_FILE" '
      .rule_results
      | map(select(.status == "violation"))
      | reduce .[] as $r ($acc[0]; .[$r.rule] = (. [$r.rule] // 0) + $r.count)
    ' > "$SCRATCH/acc.json" && mv "$SCRATCH/acc.json" "$PER_RULE_A_FILE"

    generate_draft "$TASK_B" treatment "$gen" "$PROMPT_FILE"
    B_JSON="$(agent-style review --mechanical-only --audit-only "$TASK_B/draft-${gen}.md")"
    if ! B_TOTAL="$(jq -er '.total_violations | numbers' <<<"$B_JSON")"; then
      echo "::error::scorer JSON lacks numeric .total_violations for $TASK_ID treatment gen-$gen" >&2
      echo "$B_JSON" >&2
      exit 1
    fi
    TASK_B_TOTAL=$((TASK_B_TOTAL + B_TOTAL))
    echo "$B_JSON" | jq --slurpfile acc "$PER_RULE_B_FILE" '
      .rule_results
      | map(select(.status == "violation"))
      | reduce .[] as $r ($acc[0]; .[$r.rule] = (. [$r.rule] // 0) + $r.count)
    ' > "$SCRATCH/acc.json" && mv "$SCRATCH/acc.json" "$PER_RULE_B_FILE"
  done

  GRAND_A=$((GRAND_A + TASK_A_TOTAL))
  GRAND_B=$((GRAND_B + TASK_B_TOTAL))
  DELTA=$((TASK_B_TOTAL - TASK_A_TOTAL))

  # Gen-1 drafts are guaranteed non-empty by generate_draft's fail-closed contract.
  DOMINANT="$(agent-style review --mechanical-only --compare "$TASK_A/draft-1.md" "$TASK_B/draft-1.md" \
    | jq -r '.per_rule_delta | to_entries | map(select(.value.delta != 0)) | sort_by(.value.delta) | .[0].key // "—"')"

  printf "| %s | %s | %s | %s | %s |\n" "$TASK_ID" "$TASK_A_TOTAL" "$TASK_B_TOTAL" "$DELTA" "$DOMINANT" >> "$OUTPUT"
  TASKS_PROCESSED=$((TASKS_PROCESSED + 1))
done < "$SCRATCH/ids.txt"

# Defensive check: the loop must have visited every parsed task. A runner
# that drains the parent's stdin (e.g., gemini without `< /dev/null`) would
# short-circuit the `while read` loop after iteration 1 without tripping
# any error handler, producing a scorecard with only 1 task. Fail closed
# so such a bug can never silently land as "success" with partial data.
if [[ "$TASKS_PROCESSED" -ne "$TASK_COUNT" ]]; then
  echo "::error::bench loop processed $TASKS_PROCESSED of $TASK_COUNT tasks; the runner may be draining stdin — check generate_draft's stdin handling" >&2
  exit 1
fi

{
  echo ""
  echo "## Totals"
  echo ""
  echo "| | Baseline | Treatment | Delta |"
  echo "|---|---|---|---|"
  printf "| total violations | %s | %s | %s |\n" "$GRAND_A" "$GRAND_B" "$((GRAND_B - GRAND_A))"
  echo ""
  echo "## Per-rule aggregate"
  echo ""
  echo "| Rule | Baseline | Treatment | Delta |"
  echo "|---|---|---|---|"
} >> "$OUTPUT"

jq -s '.[0] as $a | .[1] as $b | ($a * $b | keys_unsorted) | map({rule: ., a: ($a[.] // 0), b: ($b[.] // 0)})' \
  "$PER_RULE_A_FILE" "$PER_RULE_B_FILE" \
  | jq -r '.[] | "| \(.rule) | \(.a) | \(.b) | \((.b - .a)) |"' >> "$OUTPUT"

{
  echo ""
  echo "_Sanity benchmark; numbers are directional, not a claim of statistical significance._"
} >> "$OUTPUT"

echo "bench complete; scorecard at: $OUTPUT"
