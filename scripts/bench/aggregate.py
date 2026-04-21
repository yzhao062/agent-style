# SPDX-License-Identifier: MIT
"""Combine per-runner bench scorecards into a multi-model matrix scorecard.

Usage:
    python aggregate.py \
        --version 0.2.0 \
        --output docs/bench-0.2.0.md \
        docs/bench-0.2.0-claude.md \
        docs/bench-0.2.0-gemini.md \
        docs/bench-0.2.0-openai.md

Each input is the output of `scripts/bench/run.sh --runner X`. The aggregate
emits, in order:

  1. Front-matter (version, task count, generations, date, model list).
  2. `## Totals across models` — one row per input with baseline / treatment /
     Δ / Δ% columns.
  3. `## Per-rule Δ across models` — wide table, one row per rule seen in any
     input, one column per model showing the treatment-minus-baseline delta.
  4. `<details>` collapsible containing each input's original scorecard body
     verbatim (minus its H1), so per-task per-rule detail is preserved.
  5. A closing caveat paragraph about directional-not-statsig framing.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


RE_TOTALS = re.compile(r"\| total violations \| (\d+) \| (\d+) \| (-?\d+) \|")
RE_RULE_ROW = re.compile(r"\| (RULE-\S+) \| (\d+) \| (\d+) \| (-?\d+) \|")
RE_RUNNER_LABEL = re.compile(r"^- Runner: (.+)$", re.MULTILINE)


class ScorecardParseError(ValueError):
    """Raised when a per-runner scorecard is missing the structural rows the
    aggregate needs. Surfaces the input filename so CI logs point at the
    actual broken file, not the downstream combine step."""


def parse_scorecard(path: Path) -> dict:
    """Extract the bits the aggregate needs from a per-runner scorecard.

    A malformed or truncated scorecard must abort the aggregate run — silent
    zero-substitution lets a matrix leg failure look like "model X showed 0
    violations," which is the opposite of the signal we want.
    """
    text = path.read_text(encoding="utf-8")

    runner_match = RE_RUNNER_LABEL.search(text)
    runner = runner_match.group(1).strip() if runner_match else path.stem

    m = RE_TOTALS.search(text)
    if not m:
        raise ScorecardParseError(
            f"{path}: missing `| total violations | A | B | D |` row; "
            "scorecard is malformed or truncated"
        )
    totals = {
        "baseline": int(m.group(1)),
        "treatment": int(m.group(2)),
        "delta": int(m.group(3)),
    }

    # Per-rule rows live under the `## Per-rule aggregate` section only.
    per_rule: dict[str, dict[str, int]] = {}
    in_section = False
    saw_section_header = False
    for line in text.splitlines():
        if line.startswith("## Per-rule aggregate"):
            in_section = True
            saw_section_header = True
            continue
        if in_section:
            if line.startswith("## "):
                break
            m = RE_RULE_ROW.match(line)
            if m:
                per_rule[m.group(1)] = {
                    "baseline": int(m.group(2)),
                    "treatment": int(m.group(3)),
                    "delta": int(m.group(4)),
                }

    if not saw_section_header:
        raise ScorecardParseError(
            f"{path}: missing `## Per-rule aggregate` section header"
        )
    # Totals > 0 but no per-rule rows parsed -> something dropped the breakdown
    # table. Fail rather than emit an empty cross-model row for this model.
    if (totals["baseline"] + totals["treatment"]) > 0 and not per_rule:
        raise ScorecardParseError(
            f"{path}: totals are non-zero ({totals}) but no per-rule rows "
            "parsed; per-rule breakdown table is missing or malformed"
        )

    return {"runner": runner, "totals": totals, "per_rule": per_rule, "text": text}


def format_delta(value: int) -> str:
    if value == 0:
        return "0"
    return f"{value:+d}"


def strip_h1(text: str) -> str:
    """Remove the leading `# ...` line (and its trailing blank) from an input card."""
    return re.sub(r"\A# [^\n]*\n\n?", "", text, count=1)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--version", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--date", default=None, help="Override ISO-8601 date (default: today UTC)")
    p.add_argument("inputs", nargs="+")
    args = p.parse_args()

    if not args.inputs:
        sys.stderr.write("error: at least one input scorecard required\n")
        return 2

    cards = [parse_scorecard(Path(f)) for f in args.inputs]

    from datetime import datetime, timezone
    date_str = args.date or datetime.now(timezone.utc).strftime("%Y-%m-%d")

    lines: list[str] = []
    lines.append(f"# agent-style bench — v{args.version} (multi-model matrix)")
    lines.append("")
    lines.append(f"- Task set: 10 fixed prose tasks (see `scripts/bench/tasks.md`)")
    lines.append(f"- Generations per condition: 2")
    lines.append(f"- Models compared: {len(cards)}")
    lines.append(f"- Date: {date_str}")
    lines.append("")

    # 1. Totals across models
    lines.append("## Totals across models")
    lines.append("")
    lines.append("| Model | Baseline | Treatment | Δ | Δ% |")
    lines.append("|---|---|---|---|---|")
    for c in cards:
        t = c["totals"]
        b, tr, d = t["baseline"], t["treatment"], t["delta"]
        pct = f"{100 * d / b:+.0f}%" if b else "n/a"
        lines.append(f"| {c['runner']} | {b} | {tr} | {format_delta(d)} | {pct} |")
    lines.append("")

    # 2. Per-rule Δ across models
    all_rules = sorted({r for c in cards for r in c["per_rule"].keys()})
    if all_rules:
        lines.append("## Per-rule Δ across models (treatment − baseline)")
        lines.append("")
        header = "| Rule | " + " | ".join(c["runner"] for c in cards) + " |"
        sep = "|---|" + "---|" * len(cards)
        lines.append(header)
        lines.append(sep)
        for rule in all_rules:
            row = [rule]
            for c in cards:
                d = c["per_rule"].get(rule, {}).get("delta", 0)
                row.append(format_delta(d))
            lines.append("| " + " | ".join(row) + " |")
        lines.append("")

    # 3. Per-model detail collapsible
    lines.append("<details>")
    lines.append("<summary><b>Per-model detail (full per-task scorecards)</b></summary>")
    lines.append("")
    for c in cards:
        lines.append(f"### {c['runner']}")
        lines.append("")
        lines.append(strip_h1(c["text"]).rstrip())
        lines.append("")
    lines.append("</details>")
    lines.append("")

    lines.append(
        "_Sanity benchmark; numbers are directional, not a claim of statistical "
        "significance. Each model runs the same 10 tasks × 2 generations × 2 "
        "conditions = 40 calls per model._"
    )
    lines.append("")

    Path(args.output).write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
