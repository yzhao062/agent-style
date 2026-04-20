#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
#
# scripts/bench/run.sh  --  sanity benchmark for agent-style.
#
# For each task in scripts/bench/tasks.md, generate two drafts via Claude Code:
#   - baseline: agent-style NOT loaded (empty CLAUDE.md)
#   - treatment: agent-style loaded (agent-style enable claude-code)
# then score each draft with `agent-style review --mechanical-only --audit-only`
# and produce a Markdown scorecard at the target path (default: docs/bench-<VERSION>.md).
#
# Usage:
#   bash scripts/bench/run.sh [--output PATH] [--generations N]
#
# Required environment:
#   ANTHROPIC_API_KEY  (for `claude -p`)
#
# Dependencies:
#   claude CLI (npm install -g @anthropic-ai/claude-code)
#   agent-style CLI (pip install agent-style OR npm install -g agent-style)
#   jq
#
# Cost: ~$0.40-$0.80 per run with default --generations 2 (10 tasks × 2 × 2 = 40 Claude calls).

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
TASKS_FILE="$ROOT/scripts/bench/tasks.md"

OUTPUT=""
GENS=2
while [[ $# -gt 0 ]]; do
  case "$1" in
    --output) OUTPUT="$2"; shift 2 ;;
    --generations) GENS="$2"; shift 2 ;;
    --help|-h)
      sed -n '2,30p' "$0"; exit 0 ;;
    *) echo "error: unknown arg: $1" >&2; exit 2 ;;
  esac
done

if [[ -z "${ANTHROPIC_API_KEY:-}" ]]; then
  echo "error: ANTHROPIC_API_KEY must be set" >&2
  exit 2
fi
if ! command -v claude >/dev/null 2>&1; then
  echo "error: claude CLI not on PATH; install via 'npm install -g @anthropic-ai/claude-code'" >&2
  exit 2
fi
if ! command -v agent-style >/dev/null 2>&1; then
  echo "error: agent-style CLI not on PATH; install via 'pip install agent-style' or 'npm install -g agent-style'" >&2
  exit 2
fi
if ! command -v jq >/dev/null 2>&1; then
  echo "error: jq is required" >&2
  exit 2
fi

AS_VERSION="$(agent-style --version | awk '{print $2}')"
if [[ -z "$OUTPUT" ]]; then
  OUTPUT="$ROOT/docs/bench-${AS_VERSION}.md"
fi
mkdir -p "$(dirname "$OUTPUT")"

SCRATCH="$(mktemp -d -t as-bench-XXXXXX)"
trap 'rm -rf "$SCRATCH"' EXIT

# Parse tasks.md: extract each <task id="..."><prompt>...</prompt></task> block.
# Writes one $SCRATCH/prompt/<id>.txt per task (preserving any embedded newlines)
# and one $SCRATCH/ids.txt with the task ids in source order. Using per-prompt
# files instead of TSV keeps multi-line prompt bodies intact through the runner.
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
if [[ "$TASK_COUNT" -eq 0 ]]; then
  echo "error: no tasks parsed from $TASKS_FILE" >&2
  exit 2
fi
echo "parsed $TASK_COUNT tasks from $TASKS_FILE"

# For each task, run BOTH conditions × $GENS generations and score.
echo "# agent-style bench — v${AS_VERSION}" > "$OUTPUT"
echo "" >> "$OUTPUT"
echo "- Model: Claude Code default (claude -p)" >> "$OUTPUT"
echo "- Generations per condition: ${GENS}" >> "$OUTPUT"
echo "- Date: $(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$OUTPUT"
echo "- agent-style version: ${AS_VERSION}" >> "$OUTPUT"
echo "" >> "$OUTPUT"
echo "## Per-task per-rule delta (mechanical + structural; semantic excluded)" >> "$OUTPUT"
echo "" >> "$OUTPUT"
echo "| Task | Baseline total | Treatment total | Delta | Dominant rule |" >> "$OUTPUT"
echo "|---|---|---|---|---|" >> "$OUTPUT"

GRAND_A=0
GRAND_B=0
PER_RULE_A_FILE="$SCRATCH/per-rule-a.json"
PER_RULE_B_FILE="$SCRATCH/per-rule-b.json"
echo "{}" > "$PER_RULE_A_FILE"
echo "{}" > "$PER_RULE_B_FILE"

while IFS= read -r TASK_ID; do
  [[ -z "$TASK_ID" ]] && continue
  PROMPT_FILE="$SCRATCH/prompt/$TASK_ID.txt"
  if [[ ! -s "$PROMPT_FILE" ]]; then
    echo "warning: empty prompt for $TASK_ID; skipping" >&2
    continue
  fi
  echo "--- task: $TASK_ID ---"
  TASK_A="$SCRATCH/$TASK_ID-baseline"
  TASK_B="$SCRATCH/$TASK_ID-treatment"
  mkdir -p "$TASK_A" "$TASK_B"
  # Baseline: empty CLAUDE.md; Treatment: agent-style enabled.
  ( cd "$TASK_B" && agent-style enable claude-code >/dev/null )

  TASK_A_TOTAL=0
  TASK_B_TOTAL=0
  for gen in $(seq 1 "$GENS"); do
    # Baseline generation (prompt piped from file; preserves multi-line bodies).
    ( cd "$TASK_A" && claude -p < "$PROMPT_FILE" > "draft-${gen}.md" 2>/dev/null ) || true
    if [[ -s "$TASK_A/draft-${gen}.md" ]]; then
      A_JSON="$(agent-style review --mechanical-only --audit-only "$TASK_A/draft-${gen}.md")"
      A_TOTAL="$(echo "$A_JSON" | jq '.total_violations')"
      TASK_A_TOTAL=$((TASK_A_TOTAL + A_TOTAL))
      # Aggregate per-rule counts into PER_RULE_A_FILE
      echo "$A_JSON" | jq --slurpfile acc "$PER_RULE_A_FILE" '
        .rule_results
        | map(select(.status == "violation"))
        | reduce .[] as $r ($acc[0]; .[$r.rule] = (. [$r.rule] // 0) + $r.count)
      ' > "$SCRATCH/acc.json" && mv "$SCRATCH/acc.json" "$PER_RULE_A_FILE"
    fi

    # Treatment generation
    ( cd "$TASK_B" && claude -p < "$PROMPT_FILE" > "draft-${gen}.md" 2>/dev/null ) || true
    if [[ -s "$TASK_B/draft-${gen}.md" ]]; then
      B_JSON="$(agent-style review --mechanical-only --audit-only "$TASK_B/draft-${gen}.md")"
      B_TOTAL="$(echo "$B_JSON" | jq '.total_violations')"
      TASK_B_TOTAL=$((TASK_B_TOTAL + B_TOTAL))
      echo "$B_JSON" | jq --slurpfile acc "$PER_RULE_B_FILE" '
        .rule_results
        | map(select(.status == "violation"))
        | reduce .[] as $r ($acc[0]; .[$r.rule] = (. [$r.rule] // 0) + $r.count)
      ' > "$SCRATCH/acc.json" && mv "$SCRATCH/acc.json" "$PER_RULE_B_FILE"
    fi
  done

  GRAND_A=$((GRAND_A + TASK_A_TOTAL))
  GRAND_B=$((GRAND_B + TASK_B_TOTAL))
  DELTA=$((TASK_B_TOTAL - TASK_A_TOTAL))

  # Find the dominant rule for this task: the rule with the largest (A-B) delta.
  DOMINANT="—"
  if [[ -s "$TASK_A/draft-1.md" && -s "$TASK_B/draft-1.md" ]]; then
    DOMINANT="$(agent-style review --mechanical-only --compare "$TASK_A/draft-1.md" "$TASK_B/draft-1.md" \
      | jq -r '.per_rule_delta | to_entries | map(select(.value.delta != 0)) | sort_by(.value.delta) | .[0].key // "—"')"
  fi

  printf "| %s | %s | %s | %s | %s |\n" "$TASK_ID" "$TASK_A_TOTAL" "$TASK_B_TOTAL" "$DELTA" "$DOMINANT" >> "$OUTPUT"
done < "$SCRATCH/ids.txt"

echo "" >> "$OUTPUT"
echo "## Totals" >> "$OUTPUT"
echo "" >> "$OUTPUT"
echo "| | Baseline | Treatment | Delta |" >> "$OUTPUT"
echo "|---|---|---|---|" >> "$OUTPUT"
printf "| total violations | %s | %s | %s |\n" "$GRAND_A" "$GRAND_B" "$((GRAND_B - GRAND_A))" >> "$OUTPUT"

echo "" >> "$OUTPUT"
echo "## Per-rule aggregate" >> "$OUTPUT"
echo "" >> "$OUTPUT"
echo "| Rule | Baseline | Treatment | Delta |" >> "$OUTPUT"
echo "|---|---|---|---|" >> "$OUTPUT"
# Merge rule ids from both accumulators and print per-rule counts.
jq -s '.[0] as $a | .[1] as $b | ($a * $b | keys_unsorted) | map({rule: ., a: ($a[.] // 0), b: ($b[.] // 0)})' \
  "$PER_RULE_A_FILE" "$PER_RULE_B_FILE" \
  | jq -r '.[] | "| \(.rule) | \(.a) | \(.b) | \((.b - .a)) |"' >> "$OUTPUT"

echo "" >> "$OUTPUT"
echo "_Sanity benchmark; numbers are directional, not a claim of statistical significance. See \`scripts/bench/tasks.md\` and the generated drafts under \`$SCRATCH\` (ephemeral) for the underlying data._" >> "$OUTPUT"

echo "bench complete; scorecard at: $OUTPUT"
