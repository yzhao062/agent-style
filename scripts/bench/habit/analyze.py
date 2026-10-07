#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Print density, per-cell judge counts, and pairwise results for a habit bench run.

Usage: python analyze.py OUT [TASK_ID ...]
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import habit_bench as hb  # noqa: E402

out = Path(sys.argv[1])
only = set(sys.argv[2:])  # optional task-id filter

tot = {"A": [0, 0, 0], "B": [0, 0, 0]}
per = {}
for f in sorted((out / "drafts").glob("*.md")):
    writer, tid, cond, _ = f.stem.split("__")
    if only and tid not in only:
        continue
    st = hb.numeric_stats(f.read_text(encoding="utf-8"))
    for c in (cond,):
        tot[c][0] += st["sentences"]; tot[c][1] += st["words"]; tot[c][2] += st["numbers"]
        r = per.setdefault((writer, c), [0, 0, 0])
        r[0] += st["sentences"]; r[1] += st["words"]; r[2] += st["numbers"]
print("DENSITY numbers/sentence (numbers/100 words)")
def ratio(n, d, scale=1.0):
    return f"{scale * n / d:.2f}" if d else "n/a"


for (w, c), (s, wd, n) in sorted(per.items()):
    print(f"  {w:7s}{c}: {ratio(n, s)} ({ratio(n, wd, 100)})  words={wd}")
for c, (s, wd, n) in tot.items():
    print(f"  pooled {c}: {ratio(n, s)} ({ratio(n, wd, 100)})  words={wd}")
a = tot["A"][2] / tot["A"][0] if tot["A"][0] else 0.0
b = tot["B"][2] / tot["B"][0] if tot["B"][0] else 0.0
print(f"  change per sentence: {100 * (b - a) / a:+.0f}%" if a else "  change per sentence: n/a")

cats = ["unsupported", "missing", "trap_error", "trap_omitted", "reflexive"]
pool = {"A": dict.fromkeys(cats, 0), "B": dict.fromkeys(cats, 0)}
q = {"q1": {"A": 0, "B": 0, "tie": 0}, "q2": {"A": 0, "B": 0, "tie": 0}}
regress = []
print(f"\n{'cell':28s} " + " ".join(f"{c[:7]:>10s}" for c in cats) + "   q1 A/B/t  q2 A/B/t")
for cell, d in sorted(hb.summarize_judgments(out / "judge").items()):
    if only and cell.split("__")[1] not in only:
        continue
    row = []
    for c in cats:
        x, y = d["A"].get(c, 0), d["B"].get(c, 0)
        pool["A"][c] += x; pool["B"][c] += y
        bad = c in ("unsupported", "missing", "trap_error") and y > x
        if bad:
            regress.append((cell, c, x, y))
        row.append(f"{x:>4d}->{y:<3d}{'!' if bad else ' '}")
    for qq in q:
        for k in ("A", "B", "tie"):
            q[qq][k] += d[qq][k]
    print(f"{cell:28s} " + " ".join(row) + f"   {d['q1']['A']}/{d['q1']['B']}/{d['q1']['tie']}     {d['q2']['A']}/{d['q2']['B']}/{d['q2']['tie']}")
print("\nPOOLED A->B:", {c: (pool["A"][c], pool["B"][c]) for c in cats})
for qq in q:
    x, y, t = q[qq]["A"], q[qq]["B"], q[qq]["tie"]
    rate = f"{y / (x + y):.0%}" if x + y else "n/a"
    print(f"{qq}: B wins {y}/{x+y} non-tied = {rate}; ties {t}")
print("Cells where B exceeds A in a safety category:", len(regress))
for r in regress:
    print("  ", r)
