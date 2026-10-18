#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Measure how human-written papers read, and what each detector says about them.

Run it before a detector is added or changed, on a corpus of papers people wrote,
to see how often the detector would have spoken. A detector that reports on most
human papers is measuring a habit people share, and its threshold needs to move
before it ships.

For each document (``.tex``, ``.md`` or ``.txt``) it reports the words, the
prose sentences, the sentence-length median and 90th percentile, the share of
sentences over 30 words, the rates per 1,000 words of ", so" clause joins,
semicolons, sentence-initial relation words (contrast, cause, sequence) and
scope-negation sentences, and the number and per-1,000-word rate of findings from
every detector in ``agent_style.review.detectors_mech``: the CLI rules and the
hook-only ones. For the hook-only RULE-12 profile it also reports whether the share
check was evaluated (a complete LaTeX document with enough sentences) and how many
sentences pass each length in ``TAIL_WORDS``, which is the basis of the extreme-sentence
threshold. Output is Markdown, JSON, or both.

The package is imported from this repository (``packages/pypi``), never from
site-packages, so the measurement describes the working tree. Prose is segmented
by the detectors' own pipeline (``_pf_document``), so a metric here counts the
sentences a detector would see. The corpus is never committed; ``README.md``
explains how to assemble one.

Usage:
    python scripts/human-baseline/measure.py CORPUS_DIR [CORPUS_DIR ...] \\
        [--manifest scripts/human-baseline/manifest.tsv] [--md out.md] [--json out.json]
"""

from __future__ import annotations

import argparse
import importlib
import json
import re
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PACKAGE_ROOT = HERE.parent.parent / "packages" / "pypi"
EXTENSIONS = (".tex", ".md", ".txt")
LONG_SENTENCE_WORDS = 30
# Sentence lengths whose tail is counted: how many sentences pass each, pooled by group.
TAIL_WORDS = (50, 60, 65, 70, 75, 80, 100)

# Sentence-initial relation words by what they relate. A word followed by a hyphen
# is a compound ("first-order"), not a relation word.
RELATION_WORDS = {
    "contrast": (
        "however", "but", "yet", "instead", "in contrast", "by contrast", "conversely",
        "nevertheless", "nonetheless", "on the other hand", "rather", "still",
    ),
    "cause": (
        "thus", "therefore", "hence", "consequently", "accordingly", "as a result",
        "for this reason", "because", "as such",
    ),
    "sequence": (
        "first", "second", "secondly", "third", "next", "then", "finally", "lastly",
        "subsequently", "afterward", "afterwards", "meanwhile", "later", "previously",
        "initially",
    ),
}
_RELATION_RES = {
    kind: re.compile(
        r"^[\W_]*(?:" + "|".join(r"\s+".join(map(re.escape, w.split())) for w in words) + r")\b(?!-)",
        re.IGNORECASE,
    )
    for kind, words in RELATION_WORDS.items()
}
_ENTITY_RE = re.compile(r"&#?\w{1,8};")


# ---------- package import ---------------------------------------------------


def _under(path, root: Path) -> bool:
    try:
        Path(path).resolve().relative_to(root.resolve())
        return True
    except (ValueError, OSError, TypeError):
        return False


def import_detectors():
    """Return (detectors_mech, primitive) from ``packages/pypi`` of this repository.

    A copy of ``agent_style`` already imported from elsewhere (site-packages, an
    editable install of another checkout) is dropped first, so the measurement is
    always of the working tree.
    """
    loaded = sys.modules.get("agent_style")
    if loaded is not None and not _under(getattr(loaded, "__file__", None) or "", PACKAGE_ROOT):
        for name in [n for n in sys.modules if n == "agent_style" or n.startswith("agent_style.")]:
            del sys.modules[name]
    root = str(PACKAGE_ROOT)
    if root in sys.path:
        sys.path.remove(root)
    sys.path.insert(0, root)
    mech = importlib.import_module("agent_style.review.detectors_mech")
    primitive = importlib.import_module("agent_style.review.primitive")
    if not _under(mech.__file__, PACKAGE_ROOT):
        raise RuntimeError(f"agent_style loaded from {mech.__file__}, not from {PACKAGE_ROOT}")
    return mech, primitive


def detector_table(mech, primitive) -> list:
    """(label, function, takes_path, kind) for each detector in detectors_mech.

    ``kind`` is "cli" for a rule the audit runs mechanically and "hook" for a rule
    only a hook reaches. The registered detectors come from ``_DISPATCH``; the
    hook-only ones that are not registered are looked up by name, so an older
    checkout without them still runs.
    """
    rows = []
    for rule_id, fn in mech._DISPATCH.items():
        kind = "cli" if "mechanical" in primitive._CLASSIFICATION.get(rule_id, set()) else "hook"
        rows.append((rule_id, fn, rule_id in mech._FILE_PATH_RULES, kind))
    for label, attr in (("RULE-12 profile", "_rule_12_profile"), ("RULE-08 repeats", "_rule_08_repeats")):
        fn = getattr(mech, attr, None)
        if callable(fn):
            rows.append((label, fn, True, "hook"))
    return rows


# ---------- metrics ------------------------------------------------------------


def percentile(values, q: float) -> float:
    """The ``q``-th percentile (0 to 100) by linear interpolation; 0.0 for no values."""
    if not values:
        return 0.0
    ordered = sorted(values)
    pos = (len(ordered) - 1) * q / 100.0
    lo = int(pos)
    hi = min(lo + 1, len(ordered) - 1)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (pos - lo)


def per_1k(count: int, words: int):
    return None if words <= 0 else count * 1000.0 / words


def relation_counts(plain_sentences) -> dict:
    """Sentences that open with a relation word, by kind, and in total."""
    counts = {kind: 0 for kind in RELATION_WORDS}
    for plain in plain_sentences:
        for kind, pattern in _RELATION_RES.items():
            if pattern.search(plain):
                counts[kind] += 1
                break
    counts["total"] = sum(counts.values())
    return counts


def semicolon_count(plain_sentences) -> int:
    return sum(_ENTITY_RE.sub(" ", plain).count(";") for plain in plain_sentences)


def scope_negation_count(mech, plain_sentences) -> int:
    """Sentences that state a scope or a limitation (the RULE-08 cues)."""
    return sum(1 for plain in plain_sentences if any(p.search(plain) for p in mech._R08_CUE_RES))


def extreme_count(mech, doc, lengths) -> int:
    """Sentences over the extreme length. The profile reports them as one finding per document."""
    limit = getattr(mech, "_R12_EXTREME_WORDS", None)
    if limit is None:
        return 0
    return sum(1 for n in lengths if n > limit)


def share_evaluated(mech, doc) -> bool:
    """True when the profile's share check runs on ``doc``: a complete LaTeX document of enough sentences."""
    whole = getattr(mech, "_pf_whole_document", None)
    if whole is None:
        return False
    return bool(whole(doc)) and len(doc.sentences) >= mech._R12_SHARE_MIN_SENTENCES


def tail_counts(lengths) -> dict:
    """Sentences over each length in ``TAIL_WORDS``."""
    return {str(n): sum(1 for length in lengths if length > n) for n in TAIL_WORDS}


def measure_text(mech, table, text: str, file_path: str) -> dict:
    """Metrics and detector findings for one document."""
    doc = mech._pf_document(text, file_path)
    lengths = [s[2] for s in doc.sentences]
    plains = [s[3] for s in doc.sentences]
    words = sum(lengths)
    relation = relation_counts(plains)
    over = sum(1 for n in lengths if n > LONG_SENTENCE_WORDS)
    so = len(mech._r12_so_joins(doc))
    metrics = {
        "words": words,
        "sentences": len(lengths),
        "sentence_median": statistics.median(lengths) if lengths else 0,
        "sentence_p90": percentile(lengths, 90),
        "over30_pct": (100.0 * over / len(lengths)) if lengths else None,
        "so_per_1k": per_1k(so, words),
        "semicolons_per_1k": per_1k(semicolon_count(plains), words),
        "contrast_per_1k": per_1k(relation["contrast"], words),
        "cause_per_1k": per_1k(relation["cause"], words),
        "sequence_per_1k": per_1k(relation["sequence"], words),
        "relation_per_1k": per_1k(relation["total"], words),
        "scope_negation_per_1k": per_1k(scope_negation_count(mech, plains), words),
    }
    profile = getattr(mech, "_r12_profile_findings", None)
    kinds = [k for k, _offset, _detail in profile(doc)] if profile else []
    document_level = {
        "extreme_sentences": extreme_count(mech, doc, lengths),
        "share_high": kinds.count("share-high"),
        "share_low": kinds.count("share-low"),
        "so_joins": kinds.count("so"),
        "share_evaluated": share_evaluated(mech, doc),
    }
    findings = {}
    for label, fn, takes_path, kind in table:
        try:
            found = fn(text, file_path) if takes_path else fn(text)
            findings[label] = {"count": len(found), "per_1k": per_1k(len(found), words), "kind": kind}
        except Exception as exc:  # a broken detector is a result, not a crash
            findings[label] = {"count": None, "per_1k": None, "kind": kind, "error": repr(exc)}
    return {
        "metrics": metrics, "document_level": document_level, "detectors": findings,
        "tail": tail_counts(lengths),
    }


# ---------- corpus ---------------------------------------------------------------


def load_manifest(path) -> dict:
    """Map an arXiv ID to its manifest row. Lines starting with ``#`` are comments."""
    rows = {}
    header = None
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        cells = line.split("\t")
        if header is None:
            header = cells
            continue
        row = dict(zip(header, cells))
        if row.get("id"):
            rows[row["id"]] = row
    return rows


def collect(paths) -> list:
    """Sorted list of .tex, .md and .txt files under the given files and directories."""
    found = []
    for item in paths:
        p = Path(item)
        if p.is_dir():
            found.extend(sorted(f for f in p.rglob("*") if f.is_file() and f.suffix.lower() in EXTENSIONS))
        elif p.is_file():
            found.append(p)
    return found


def group_of(path: Path, manifest: dict) -> str:
    row = manifest.get(path.stem)
    if row and row.get("group"):
        return row["group"]
    return path.parent.name or "-"


def measure_paths(paths, manifest=None) -> dict:
    manifest = manifest or {}
    mech, primitive = import_detectors()
    table = detector_table(mech, primitive)
    documents = []
    for path in collect(paths):
        text = path.read_text(encoding="utf-8", errors="replace")
        result = measure_text(mech, table, text, str(path))
        result.update({"document": path.stem, "path": str(path), "group": group_of(path, manifest)})
        documents.append(result)
    version = getattr(sys.modules["agent_style"], "__version__", "unknown")
    return {
        "agent_style_version": version,
        "package_root": str(PACKAGE_ROOT),
        "detectors": [{"label": t[0], "kind": t[3]} for t in table],
        "documents": documents,
        "groups": summarize(documents),
        "tail": summarize_tail(documents),
    }


def summarize(documents) -> dict:
    """Per group: the number of documents and the min, median and max of each metric."""
    keys = [k for k in documents[0]["metrics"]] if documents else []
    out = {}
    for group in dict.fromkeys(d["group"] for d in documents):
        members = [d for d in documents if d["group"] == group]
        row = {"documents": len(members)}
        for key in keys:
            vals = [d["metrics"][key] for d in members if d["metrics"][key] is not None]
            row[key] = (
                {"min": min(vals), "median": statistics.median(vals), "max": max(vals)} if vals else None
            )
        out[group] = row
    return out


def summarize_tail(documents) -> dict:
    """Per group and length: the pooled sentences over it and the words per such sentence."""
    out = {}
    names = list(dict.fromkeys(d["group"] for d in documents))
    for group in names + (["pooled"] if len(names) > 1 else []):
        members = [d for d in documents if group == "pooled" or d["group"] == group]
        words = sum(d["metrics"]["words"] for d in members)
        row = {"words": words, "documents_with_hit": {}, "hits": {}, "words_per_hit": {}}
        for n in TAIL_WORDS:
            key = str(n)
            hits = sum(d["tail"][key] for d in members)
            row["hits"][key] = hits
            row["documents_with_hit"][key] = sum(1 for d in members if d["tail"][key] > 0)
            row["words_per_hit"][key] = (words / hits) if hits else None
        out[group] = row
    return out


# ---------- report -----------------------------------------------------------------


def _fmt(value, digits: int = 2) -> str:
    if value is None:
        return "-"
    if digits == 0:
        return str(int(round(value)))
    return f"{value:.{digits}f}"


METRIC_COLUMNS = (
    ("words", "words", 0),
    ("sentences", "sentences", 0),
    ("sentence_median", "median", 1),
    ("sentence_p90", "p90", 1),
    ("over30_pct", "over 30 (%)", 1),
    ("so_per_1k", ", so /1k", 2),
    ("semicolons_per_1k", "; /1k", 2),
    ("contrast_per_1k", "contrast /1k", 2),
    ("cause_per_1k", "cause /1k", 2),
    ("sequence_per_1k", "sequence /1k", 2),
    ("relation_per_1k", "relation /1k", 2),
    ("scope_negation_per_1k", "scope neg. /1k", 2),
)


def render_markdown(report: dict) -> str:
    docs = report["documents"]
    lines = [
        "# Human-Baseline Measurement",
        "",
        f"agent-style {report['agent_style_version']}, {len(docs)} documents. "
        "Rates are per 1,000 prose words. Prose is segmented by the detectors' own pipeline.",
        "",
        "## Prose Metrics",
        "",
        "| group | document | " + " | ".join(c[1] for c in METRIC_COLUMNS) + " |",
        "|---|---|" + "---|" * len(METRIC_COLUMNS),
    ]
    for d in docs:
        cells = [_fmt(d["metrics"][key], digits) for key, _name, digits in METRIC_COLUMNS]
        lines.append(f"| {d['group']} | {d['document']} | " + " | ".join(cells) + " |")
    labels = [x["label"] for x in report["detectors"]]
    lines += [
        "",
        "## Detector Findings",
        "",
        "Each cell is the finding count, with the rate per 1,000 words in parentheses. "
        "CLI rules: " + ", ".join(x["label"] for x in report["detectors"] if x["kind"] == "cli")
        + ". Hook-only: " + ", ".join(x["label"] for x in report["detectors"] if x["kind"] == "hook") + ".",
        "",
        "| group | document | " + " | ".join(labels) + " |",
        "|---|---|" + "---|" * len(labels),
    ]
    for d in docs:
        cells = []
        for label in labels:
            cell = d["detectors"].get(label, {})
            if cell.get("count") is None:
                cells.append("error")
            else:
                cells.append(f"{cell['count']} ({_fmt(cell['per_1k'])})")
        lines.append(f"| {d['group']} | {d['document']} | " + " | ".join(cells) + " |")
    lines += [
        "",
        "## Document-Level Reports",
        "",
        "What the two new hook-only detectors would report for a whole document: sentences over the "
        "extreme length (one finding for the document; the count is of sentences), a share of long "
        "sentences above or below the human range, ', so' clause joins past the threshold, and "
        "caveats repeated three times. 'share checked' is yes when the share check ran: a complete "
        "LaTeX document with enough sentences. A document that is not checked cannot report a share.",
        "",
        "| group | document | extreme sentences | share checked | share high | share low | , so joins | repeated caveats |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for d in docs:
        dl = d.get("document_level", {})
        repeats = d["detectors"].get("RULE-08 repeats", {}).get("count")
        checked = {True: "yes", False: "no"}.get(dl.get("share_evaluated"), "-")
        lines.append(
            f"| {d['group']} | {d['document']} | {dl.get('extreme_sentences', '-')} | {checked} | "
            f"{dl.get('share_high', '-')} | {dl.get('share_low', '-')} | {dl.get('so_joins', '-')} | "
            f"{'-' if repeats is None else repeats} |"
        )
    lines += [
        "",
        "## Long-Sentence Tail",
        "",
        "Sentences over each length, pooled over the documents of a group. 'words per hit' is the "
        "group's words divided by its hits. The extreme-sentence threshold sits in the far tail, at "
        "a length where the pooled corpus gives one hit per several thousand words.",
        "",
        "| group | words | over (words) | hits | documents with a hit | words per hit |",
        "|---|---|---|---|---|---|",
    ]
    for group, row in report.get("tail", {}).items():
        for key in row["hits"]:
            per = row["words_per_hit"][key]
            lines.append(
                f"| {group} | {row['words']} | {key} | {row['hits'][key]} | {row['documents_with_hit'][key]} | "
                f"{'-' if per is None else format(per, ',.0f')} |"
            )
    lines += [
        "",
        "## Group Summary",
        "",
        "Minimum, median and maximum of each metric over the documents of a group.",
        "",
        "| group | documents | metric | min | median | max |",
        "|---|---|---|---|---|---|",
    ]
    for group, row in report["groups"].items():
        for key, name, digits in METRIC_COLUMNS:
            stat = row.get(key)
            if stat:
                lines.append(
                    f"| {group} | {row['documents']} | {name} | {_fmt(stat['min'], digits)} | "
                    f"{_fmt(stat['median'], digits)} | {_fmt(stat['max'], digits)} |"
                )
    lines += [
        "",
        "## Documents with a Detector Finding",
        "",
        "| group | detector | documents with a finding | of |",
        "|---|---|---|---|",
    ]
    for group in report["groups"]:
        members = [d for d in docs if d["group"] == group]
        for label in labels:
            hit = sum(1 for d in members if (d["detectors"].get(label, {}).get("count") or 0) > 0)
            lines.append(f"| {group} | {label} | {hit} | {len(members)} |")
    lines.append("")
    return "\n".join(lines)


# ---------- command line --------------------------------------------------------------


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("paths", nargs="+", help="files or directories of .tex, .md and .txt")
    parser.add_argument("--manifest", help="manifest.tsv; maps a file name stem to its group")
    parser.add_argument("--md", help="write the Markdown report here (stdout when neither --md nor --json)")
    parser.add_argument("--json", help="write the JSON report here")
    args = parser.parse_args(argv)
    manifest = load_manifest(args.manifest) if args.manifest else {}
    report = measure_paths(args.paths, manifest)
    if not report["documents"]:
        print("no .tex, .md or .txt files found", file=sys.stderr)
        return 1
    markdown = render_markdown(report)
    if args.md:
        Path(args.md).write_text(markdown, encoding="utf-8")
    if args.json:
        Path(args.json).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if not args.md and not args.json:
        sys.stdout.write(markdown)
    return 0


if __name__ == "__main__":
    sys.exit(main())
