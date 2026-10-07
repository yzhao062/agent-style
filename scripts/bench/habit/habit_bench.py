#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Before-and-after habit bench for agent-style.

Compares two compact rule packs (A = previous release, B = candidate) on the
paper and proposal tasks in tasks/tasks.md. Each draft runs in a fresh
workspace where only the pack differs. A cross-family judge scores each A/B
pair blind.

Subcommands:
  freeze    record task, rubric, pack, and model settings in a new run directory
  generate  write drafts for every writer x task x condition x generation
  judge     score each A/B pair blind with a cross-family judge
  loop      review-loop check: old versus new review lens, two rounds each
  report    aggregate judge output and numeric density into report.json

Every step after freeze checks the recorded hashes and settings, resumes where
it stopped, and exits nonzero if any model call failed.
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import hashlib
import json
import random
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CLAUDE = "claude"
CODEX = "codex"

WRITERS = {
    "sonnet": ("claude", "claude-sonnet-5-5"),
    "opus": ("claude", "claude-opus-5-5"),
    "codex": ("codex", "gpt-6.1-sol"),
}
# Cross-family judging: Codex judges Claude drafts, Claude Opus judges Codex drafts.
JUDGE_FOR = {"claude": ("codex", "gpt-6.1-sol"), "codex": ("claude", "claude-opus-5-5")}
CODEX_EFFORT = "high"
TIMEOUT = 900
TRAP_VALUES = {"correct", "error", "omitted"}
VOTE_VALUES = {"X", "Y", "tie"}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def outdir(a: argparse.Namespace) -> Path:
    # Absolute, so a relative --out cannot resolve twice under a workspace.
    return Path(a.out).resolve()


def load_tasks(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8")
    tasks = []
    for m in re.finditer(r'<task id="([^"]+)">(.*?)</task>', text, re.S):
        body = m.group(2)

        def field(name: str) -> str:
            f = re.search(rf"<{name}>(.*?)</{name}>", body, re.S)
            return f.group(1).strip() if f else ""

        tasks.append({"id": m.group(1), "trap": field("trap"), "key": field("key"),
                      "prompt": field("prompt")})
    return tasks


def run(cmd: list[str], stdin: str, cwd: Path, out_file: Path | None = None) -> str:
    proc = subprocess.run(cmd, input=stdin, cwd=str(cwd), capture_output=True,
                          text=True, timeout=TIMEOUT)
    if out_file is not None and out_file.exists():
        text = out_file.read_text(encoding="utf-8")
    else:
        text = proc.stdout
    if proc.returncode != 0 or not text.strip():
        raise RuntimeError(f"{cmd[0]} exit {proc.returncode}: {proc.stderr[-800:]}")
    return text.strip() + "\n"


def call_model(family: str, model: str, prompt: str, ws: Path) -> str:
    ws = ws.resolve()
    ws.mkdir(parents=True, exist_ok=True)
    if family == "claude":
        return run([CLAUDE, "-p", "--model", model], prompt, ws)
    last = ws / ".last-message.txt"
    if last.exists():
        last.unlink()
    return run([CODEX, "exec", "--skip-git-repo-check", "--ignore-user-config",
                "-c", f"model={model}", "-c", f"model_reasoning_effort={CODEX_EFFORT}",
                "-s", "read-only", "-C", str(ws), "-o", str(last), "-"], prompt, ws, last)


def make_workspace(ws: Path, family: str, pack: Path | None) -> None:
    """Fresh workspace; the pack is the only instruction file that differs."""
    ws.mkdir(parents=True, exist_ok=True)
    if pack is None:
        return
    body = pack.read_text(encoding="utf-8")
    if family == "claude":
        (ws / ".agent-style").mkdir(exist_ok=True)
        (ws / ".agent-style" / "rule-pack.md").write_text(body, encoding="utf-8")
        (ws / "CLAUDE.md").write_text("@.agent-style/rule-pack.md\n", encoding="utf-8")
    else:
        (ws / "AGENTS.md").write_text(body, encoding="utf-8")


def resolve(out: Path, path: str) -> Path:
    """Manifest paths are relative to the run directory, so a committed run
    can be rechecked on another machine; an absolute path is used as is."""
    p = Path(path)
    return p if p.is_absolute() else out / p


def settings() -> dict:
    # JSON round trip so tuples compare equal to the lists a manifest holds.
    return json.loads(json.dumps({"writers": WRITERS, "judges": JUDGE_FOR,
                                  "codex_effort": CODEX_EFFORT}))


def cmd_freeze(a: argparse.Namespace) -> None:
    out = outdir(a)
    if out.exists() and any(out.iterdir()):
        sys.exit("freeze needs a new or empty run directory; a second freeze would relabel existing drafts")
    (out / "packs").mkdir(parents=True, exist_ok=True)
    shutil.copyfile(a.pack_a, out / "packs" / "A.md")
    shutil.copyfile(a.pack_b, out / "packs" / "B.md")
    manifest = {
        "tasks_sha256": sha256(Path(a.tasks)),
        "rubric_sha256": sha256(HERE / "judge-rubric.md"),
        "pack_a": {"path": "packs/A.md", "sha256": sha256(out / "packs" / "A.md")},
        "pack_b": {"path": "packs/B.md", "sha256": sha256(out / "packs" / "B.md")},
        **settings(),
        "generations": a.gens, "seed": a.seed,
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))


def check_frozen(out: Path, tasks: Path) -> dict:
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    for key, path in (("tasks_sha256", tasks), ("rubric_sha256", HERE / "judge-rubric.md")):
        if manifest[key] != sha256(path):
            sys.exit(f"{path} does not match the frozen hash; pass the run's own task file or freeze a new run")
    for cond in ("pack_a", "pack_b"):
        if manifest[cond]["sha256"] != sha256(resolve(out, manifest[cond]["path"])):
            sys.exit(f"{cond} changed after freeze")
    for key, value in settings().items():
        if manifest.get(key) != value:
            sys.exit(f"model setting {key!r} differs from the frozen run; freeze a new run")
    return manifest


def run_pool(jobs: list, work, jobs_n: int, label) -> None:
    """Run every job, report each outcome, and exit nonzero if any failed.
    Successful outputs stay on disk, so a rerun resumes."""
    failed = 0
    with cf.ThreadPoolExecutor(max_workers=jobs_n) as pool:
        futures = {pool.submit(work, j): j for j in jobs}
        for f in cf.as_completed(futures):
            try:
                print("ok", f.result(), flush=True)
            except Exception as exc:
                failed += 1
                print("FAIL", label(futures[f]), exc, flush=True)
    if failed:
        sys.exit(f"{failed} of {len(jobs)} calls failed; rerun the same command to resume")


def cmd_generate(a: argparse.Namespace) -> None:
    out = outdir(a)
    manifest = check_frozen(out, Path(a.tasks))
    tasks = load_tasks(Path(a.tasks))
    packs = {"A": resolve(out, manifest["pack_a"]["path"]), "B": resolve(out, manifest["pack_b"]["path"])}
    jobs = []
    for writer in a.writers:
        family, model = WRITERS[writer]
        for t in tasks:
            for cond in ("A", "B"):
                for g in range(1, manifest["generations"] + 1):
                    name = f"{writer}__{t['id']}__{cond}__g{g}"
                    draft = out / "drafts" / f"{name}.md"
                    if draft.exists():
                        continue
                    jobs.append((family, model, t["prompt"], out / "ws" / name, packs[cond], draft))

    def work(job):
        family, model, prompt, ws, pack, draft = job
        make_workspace(ws, family, pack)
        text = call_model(family, model, prompt, ws)
        draft.parent.mkdir(parents=True, exist_ok=True)
        draft.write_text(text, encoding="utf-8")
        return draft.name

    print(f"{len(jobs)} drafts to generate")
    run_pool(jobs, work, a.jobs, lambda j: j[-1].name)


def judge_prompt(task: dict, x: str, y: str) -> str:
    rubric = (HERE / "judge-rubric.md").read_text(encoding="utf-8")
    return (f"{rubric}\n\n## Task given to the writer\n\n{task['prompt']}\n\n"
            f"## Answer key\n\n{task['key']}\n\n## Text X\n\n{x}\n\n## Text Y\n\n{y}\n")


def parse_json(text: str) -> dict:
    start, end = text.find("{"), text.rfind("}")
    return json.loads(text[start:end + 1])


def validate_judgment(d: dict) -> None:
    """Reject a judgment that would otherwise count as clean by omission."""
    texts = d.get("texts")
    if not isinstance(texts, dict) or set(texts) != {"X", "Y"}:
        raise ValueError("judgment needs texts X and Y")
    for slot, t in texts.items():
        for key in ("unsupported_claims", "missing_material_qualifiers", "reflexive_qualifiers"):
            items = t.get(key)
            if not isinstance(items, list) or not all(isinstance(i, str) for i in items):
                raise ValueError(f"{slot}.{key} must be a list of strings")
        if t.get("trap") not in TRAP_VALUES:
            raise ValueError(f"{slot}.trap must be one of {sorted(TRAP_VALUES)}")
    for q in ("q1", "q2"):
        if d.get(q) not in VOTE_VALUES:
            raise ValueError(f"{q} must be one of {sorted(VOTE_VALUES)}")


def judge_pairs(out: Path, pairs: list[tuple], seed: int, jobs: int, label: str) -> None:
    """pairs: (pair_id, writer_family, task, text_a, text_b) with conditions A and B."""
    rng = random.Random(seed)
    work_items = []
    for pair_id, family, task, ta, tb in pairs:
        result = out / label / f"{pair_id}.json"
        flip = rng.random() < 0.5  # drawn for every pair so reruns keep the same order
        if result.exists():
            continue
        x, y = (tb, ta) if flip else (ta, tb)
        mapping = {"X": "B" if flip else "A", "Y": "A" if flip else "B"}
        work_items.append((pair_id, JUDGE_FOR[family], task, x, y, mapping, result))

    def work(item):
        pair_id, (jfam, jmodel), task, x, y, mapping, result = item
        raw = call_model(jfam, jmodel, judge_prompt(task, x, y), out / "ws" / f"{label}__{pair_id}")
        result.parent.mkdir(parents=True, exist_ok=True)
        (result.with_suffix(".raw.txt")).write_text(raw, encoding="utf-8")
        data = parse_json(raw)
        validate_judgment(data)
        data["mapping"] = mapping
        data["judge"] = jmodel
        result.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        return pair_id

    print(f"{len(work_items)} pairs to judge")
    run_pool(work_items, work, jobs, lambda w: w[0])


def draft_pairs(out: Path, tasks: dict) -> list[tuple]:
    pairs = []
    for draft_a in sorted((out / "drafts").glob("*__A__g*.md")):
        writer, tid, _, g = draft_a.stem.split("__")
        draft_b = draft_a.with_name(f"{writer}__{tid}__B__{g}.md")
        if tid not in tasks or not draft_b.exists():
            continue
        pairs.append((f"{writer}__{tid}__{g}", WRITERS[writer][0], tasks[tid],
                      draft_a.read_text(encoding="utf-8"), draft_b.read_text(encoding="utf-8")))
    return pairs


def cmd_judge(a: argparse.Namespace) -> None:
    out = outdir(a)
    manifest = check_frozen(out, Path(a.tasks))
    tasks = {t["id"]: t for t in load_tasks(Path(a.tasks))}
    judge_pairs(out, draft_pairs(out, tasks), manifest["seed"], a.jobs, "judge")


REVIEW_PROMPT = """You are reviewing a passage from a paper or proposal draft. Apply the review lens below to the passage, using the task data to check claims. Give numbered findings, each with a suggested rewrite. Output only the findings.

## Review lens

{lens}

## Task data the author worked from

{task}

## Passage

{passage}
"""

REVISE_PROMPT = """Below is a passage you drafted, the task data it was written from, and review findings. Revise the passage to address the findings you agree with. Output only the revised passage.

## Task data

{task}

## Passage

{passage}

## Review findings

{review}
"""


def cmd_loop(a: argparse.Namespace) -> None:
    out = outdir(a)
    manifest = check_frozen(out, Path(a.tasks))
    tasks = load_tasks(Path(a.tasks))
    pack_b = resolve(out, manifest["pack_b"]["path"])
    lens_paths = {"old": Path(a.old_lens), "new": Path(a.new_lens)}
    lens_hashes = {k: sha256(p) for k, p in lens_paths.items()}
    record = out / "loop" / "lenses.json"
    if record.exists():
        if json.loads(record.read_text(encoding="utf-8")) != lens_hashes:
            sys.exit("lens files differ from the ones this loop started with; use a new run directory")
    else:
        record.parent.mkdir(parents=True, exist_ok=True)
        record.write_text(json.dumps(lens_hashes, indent=2) + "\n", encoding="utf-8")
    lenses = {k: p.read_text(encoding="utf-8") for k, p in lens_paths.items()}
    rfam, rmodel = WRITERS["codex"]
    wfam, wmodel = WRITERS["sonnet"]

    def arm(job):
        task, lens_name = job
        name = f"{task['id']}__{lens_name}"
        final = out / "loop" / f"{name}__r2.md"
        if final.exists():
            return final.name
        passage = (out / "drafts" / f"sonnet__{task['id']}__A__g1.md").read_text(encoding="utf-8")
        for r in (1, 2):
            review = call_model(rfam, rmodel, REVIEW_PROMPT.format(
                lens=lenses[lens_name], task=task["prompt"], passage=passage),
                out / "ws" / f"loop__{name}__review{r}")
            ws = out / "ws" / f"loop__{name}__revise{r}"
            make_workspace(ws, wfam, pack_b)
            passage = call_model(wfam, wmodel, REVISE_PROMPT.format(
                task=task["prompt"], passage=passage, review=review), ws)
            (out / "loop" / f"{name}__review{r}.md").write_text(review, encoding="utf-8")
            (out / "loop" / f"{name}__r{r}.md").write_text(passage, encoding="utf-8")
        return final.name

    run_pool([(t, ln) for t in tasks for ln in ("old", "new")], arm, a.jobs,
             lambda j: f"{j[0]['id']}__{j[1]}")
    # Old lens plays condition A and new lens plays condition B in the judge.
    pairs = []
    for t in tasks:
        fa = out / "loop" / f"{t['id']}__old__r2.md"
        fb = out / "loop" / f"{t['id']}__new__r2.md"
        pairs.append((t["id"], wfam, t, fa.read_text(encoding="utf-8"), fb.read_text(encoding="utf-8")))
    judge_pairs(out, pairs, manifest["seed"] + 1, a.jobs, "loop-judge")


NUM_RE = re.compile(r"(?<![\w.])[-+]?\d+(?:[.,]\d+)*(?:\s?%|x\b|×)?")
SKIP_RE = re.compile(r"\b(?:Table|Figure|Fig\.|Section|Aim|Thrust|Eq\.|Equation)\s+\d+", re.I)
YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")


def numeric_stats(text: str) -> dict:
    prose = "\n".join(l for l in text.splitlines() if not l.lstrip().startswith(("#", "|")))
    prose = SKIP_RE.sub(" ", prose)
    prose = YEAR_RE.sub(" ", prose)
    sentences = [s for s in re.split(r"(?<=[.!?])\s+", prose.strip()) if len(s.split()) > 2]
    words = len(prose.split())
    nums = len(NUM_RE.findall(prose))
    return {"sentences": len(sentences), "words": words, "numbers": nums}


def summarize_judgments(directory: Path) -> dict:
    agg: dict = {}
    for f in sorted(directory.glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        try:
            validate_judgment(d)
        except ValueError as exc:
            sys.exit(f"{f}: {exc}; delete it and rerun the judge step")
        cell = f.stem.rsplit("__", 1)[0] if f.stem.count("__") >= 2 else f.stem
        c = agg.setdefault(cell, {"A": {}, "B": {}, "q1": {"A": 0, "B": 0, "tie": 0},
                                  "q2": {"A": 0, "B": 0, "tie": 0}, "pairs": 0})
        c["pairs"] += 1
        for slot, cond in d["mapping"].items():
            t = d["texts"][slot]
            s = c[cond]
            s["unsupported"] = s.get("unsupported", 0) + len(t["unsupported_claims"])
            s["missing"] = s.get("missing", 0) + len(t["missing_material_qualifiers"])
            s["trap_error"] = s.get("trap_error", 0) + (t["trap"] == "error")
            s["trap_omitted"] = s.get("trap_omitted", 0) + (t["trap"] == "omitted")
            s["reflexive"] = s.get("reflexive", 0) + len(t["reflexive_qualifiers"])
        for q in ("q1", "q2"):
            v = d[q]
            c[q][d["mapping"][v] if v in ("X", "Y") else "tie"] += 1
    return agg


def cmd_report(a: argparse.Namespace) -> None:
    out = outdir(a)
    manifest = check_frozen(out, Path(a.tasks))
    tasks = {t["id"]: t for t in load_tasks(Path(a.tasks))}
    rows = {}
    drafts = sorted((out / "drafts").glob("*.md"))
    for f in drafts:
        writer, tid, cond, _ = f.stem.split("__")
        st = numeric_stats(f.read_text(encoding="utf-8"))
        r = rows.setdefault((writer, cond), {"sentences": 0, "words": 0, "numbers": 0})
        for k in r:
            r[k] += st[k]
    expected_drafts = len(WRITERS) * len(tasks) * 2 * manifest["generations"]
    expected_pairs = len(WRITERS) * len(tasks) * manifest["generations"]
    judged = len(list((out / "judge").glob("*.json")))
    report = {
        "coverage": {"drafts": [len(drafts), expected_drafts], "pairs": [judged, expected_pairs],
                     "partial": len(drafts) < expected_drafts or judged < expected_pairs},
        "density": {f"{w}/{c}": v for (w, c), v in rows.items()},
        "judge": summarize_judgments(out / "judge"),
    }
    if (out / "loop-judge").exists():
        report["loop"] = summarize_judgments(out / "loop-judge")
    (out / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if report["coverage"]["partial"]:
        print("PARTIAL RUN: coverage is below the frozen design", file=sys.stderr)
    print(json.dumps(report, indent=2))


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("freeze", "generate", "judge", "loop", "report"):
        s = sub.add_parser(name)
        s.add_argument("--out", required=True)
        s.add_argument("--tasks", default=str(HERE / "tasks" / "tasks.md"))
        s.add_argument("--jobs", type=int, default=6)
        if name == "freeze":
            s.add_argument("--pack-a", required=True)
            s.add_argument("--pack-b", required=True)
            s.add_argument("--gens", type=int, default=3)
            s.add_argument("--seed", type=int, default=20261006)
        if name == "generate":
            s.add_argument("--writers", nargs="+", default=list(WRITERS))
        if name == "loop":
            s.add_argument("--old-lens", required=True)
            s.add_argument("--new-lens", required=True)
    a = p.parse_args()
    {"freeze": cmd_freeze, "generate": cmd_generate, "judge": cmd_judge,
     "loop": cmd_loop, "report": cmd_report}[a.cmd](a)


if __name__ == "__main__":
    main()
