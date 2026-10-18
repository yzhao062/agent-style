# SPDX-License-Identifier: MIT
"""Tests for ``scripts/human-baseline/measure.py``, the human-baseline harness.

The harness measures prose habits and detector findings on a corpus of papers.
These tests pin its metric functions on synthetic text, the shipped manifest, the
import of the package from this repository, and the report and JSON output. No
corpus is committed and none is needed: every text here is invented.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

# tests/ -> pypi/ -> packages/ -> repo root
REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
HARNESS_DIR = REPO_ROOT / "scripts" / "human-baseline"
MEASURE = HARNESS_DIR / "measure.py"

WORDS = ("gadget", "river", "lantern", "orchard", "ribbon", "harbor", "meadow", "copper")


def _load():
    if not MEASURE.is_file():
        pytest.skip(f"missing (not a source checkout): {MEASURE}")
    spec = importlib.util.spec_from_file_location("human_baseline_measure", MEASURE)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def hb():
    return _load()


@pytest.fixture(scope="module")
def tools(hb):
    mech, primitive = hb.import_detectors()
    return mech, hb.detector_table(mech, primitive)


def sentence(n: int, seed: int = 0, lead: str = "The") -> str:
    return lead + " " + " ".join(WORDS[(seed + i) % len(WORDS)] for i in range(n - 1)) + "."


def doc(sentences, per_paragraph: int = 8) -> str:
    """A LaTeX section file: a fragment, with no ``\\begin{document}``."""
    chunks = [" ".join(sentences[i:i + per_paragraph]) for i in range(0, len(sentences), per_paragraph)]
    return "\\section{Results}\n" + "\n\n".join(chunks) + "\n"


def whole_doc(sentences, per_paragraph: int = 8) -> str:
    """A whole LaTeX document, which the profile's share check can read."""
    return "\\documentclass{article}\n\\begin{document}\n" + doc(sentences, per_paragraph) + "\\end{document}\n"


# ---------- the package comes from this repository ---------------------------------------


def test_the_detectors_are_imported_from_the_working_tree(hb):
    mech, primitive = hb.import_detectors()
    package_root = (REPO_ROOT / "packages" / "pypi").resolve()
    assert hb.PACKAGE_ROOT.resolve() == package_root
    assert str(package_root) in str(Path(mech.__file__).resolve())
    assert str(package_root) in str(Path(primitive.__file__).resolve())


def test_a_copy_imported_from_elsewhere_is_replaced(hb, tmp_path):
    # An agent_style loaded from another location is dropped and re-imported from the repo.
    stub = tmp_path / "agent_style"
    stub.mkdir()
    (stub / "__init__.py").write_text("__version__ = '0.0.0-stub'\n", encoding="utf-8")
    saved = {k: v for k, v in sys.modules.items() if k == "agent_style" or k.startswith("agent_style.")}
    try:
        for name in saved:
            del sys.modules[name]
        sys.path.insert(0, str(tmp_path))
        import agent_style as imported_stub  # the stub, from tmp_path

        assert imported_stub.__version__ == "0.0.0-stub"
        mech, _primitive = hb.import_detectors()
        assert str(REPO_ROOT / "packages" / "pypi") in str(Path(mech.__file__).resolve())
    finally:
        if str(tmp_path) in sys.path:
            sys.path.remove(str(tmp_path))
        for name in [k for k in sys.modules if k == "agent_style" or k.startswith("agent_style.")]:
            del sys.modules[name]
        sys.modules.update(saved)


def test_the_table_covers_every_detector_in_the_module(hb, tools):
    mech, table = tools
    labels = [row[0] for row in table]
    for rule_id in mech._DISPATCH:
        assert rule_id in labels
    assert "RULE-12 profile" in labels and "RULE-08 repeats" in labels
    kinds = {row[0]: row[3] for row in table}
    assert kinds["RULE-12"] == "cli" and kinds["RULE-B"] == "cli"
    assert kinds["RULE-03"] == "hook" and kinds["RULE-A"] == "hook"
    assert kinds["RULE-12 profile"] == "hook" and kinds["RULE-08 repeats"] == "hook"
    paths = {row[0]: row[2] for row in table}
    assert paths["RULE-03"] and paths["RULE-A"] and paths["RULE-12 profile"] and not paths["RULE-12"]


# ---------- small metric functions -----------------------------------------------------------


def test_percentile_interpolates_and_handles_edges(hb):
    assert hb.percentile([], 90) == 0.0
    assert hb.percentile([7], 90) == 7
    assert hb.percentile([1, 2, 3, 4, 5], 50) == 3
    assert hb.percentile([1, 2, 3, 4, 5], 90) == pytest.approx(4.6)
    assert hb.percentile([10, 0], 100) == 10
    assert hb.percentile(list(range(1, 11)), 90) == pytest.approx(9.1)


def test_per_1k_guards_zero_words(hb):
    assert hb.per_1k(3, 0) is None
    assert hb.per_1k(3, 1500) == pytest.approx(2.0)


@pytest.mark.parametrize("sentence_text,kind", [
    ("However, the river rose.", "contrast"),
    ("Instead the gadget moved.", "contrast"),
    ("In contrast, the harbor stayed calm.", "contrast"),
    ("On the other hand, the orchard grew.", "contrast"),
    ("Thus the lantern lit.", "cause"),
    ("As a result, the ribbon held.", "cause"),
    ("Because the meadow flooded, we waited.", "cause"),
    ("First, the copper cooled.", "sequence"),
    ("Finally the gadget stopped.", "sequence"),
    ("Then the river fell.", "sequence"),
])
def test_relation_words_are_counted_by_kind(hb, sentence_text, kind):
    counts = hb.relation_counts([sentence_text])
    assert counts[kind] == 1 and counts["total"] == 1


def test_relation_words_need_a_word_boundary_and_no_hyphen(hb):
    for text in ("First-order methods moved the river.", "Thusly the gadget moved.", "Butter melts in the harbor.",
                 "Secondary lanterns lit the meadow.", "The river rose however slowly."):
        assert hb.relation_counts([text])["total"] == 0, text
    assert hb.relation_counts(['"However," said the gadget.', "(First) the river rose."])["total"] == 2


def test_semicolons_ignore_entities(hb):
    assert hb.semicolon_count(["The gadget moved; the river rose; the lantern lit."]) == 2
    assert hb.semicolon_count(["Fish &amp; chips and a &nbsp; space."]) == 0


def test_scope_negation_counts_cue_sentences(hb, tools):
    mech, _table = tools
    sentences = [
        "The survey does not establish that pruning works.",
        "We leave the harbor study to future work.",
        "The river rose.",
    ]
    assert hb.scope_negation_count(mech, sentences) == 2


# ---------- one document --------------------------------------------------------------------------


def test_measure_text_on_a_synthetic_paper(hb, tools):
    mech, table = tools
    # 30 sentences of 10 words and 10 of 40 words: 40 sentences, 25% over 30 words.
    body = [sentence(10, seed=i) for i in range(30)] + [sentence(40, seed=i) for i in range(10)]
    text = whole_doc(body)
    result = hb.measure_text(mech, table, text, "paper.tex")
    m = result["metrics"]
    assert m["words"] == 30 * 10 + 10 * 40
    assert m["sentences"] == 40
    assert m["over30_pct"] == pytest.approx(25.0)
    assert m["sentence_median"] == 10
    assert m["sentence_p90"] == pytest.approx(hb.percentile([10] * 30 + [40] * 10, 90))
    assert m["so_per_1k"] == 0 and m["semicolons_per_1k"] == 0 and m["relation_per_1k"] == 0
    assert set(result["detectors"]) == {row[0] for row in table}
    assert all(cell["count"] is not None for cell in result["detectors"].values())
    assert result["detectors"]["RULE-12"]["count"] == 10  # the CLI rule, per sentence over 30
    assert result["detectors"]["RULE-12"]["per_1k"] == pytest.approx(10 * 1000.0 / m["words"])
    assert result["document_level"] == {
        "extreme_sentences": 0, "share_high": 0, "share_low": 0, "so_joins": 0, "share_evaluated": True,
    }
    assert result["tail"]["50"] == 0 and result["tail"]["60"] == 0


def test_rates_count_so_semicolons_relations_and_scope_negations(hb, tools):
    mech, table = tools
    sentences = [
        "The gadget moved the river, so the lantern rose over the orchard.",
        "However, the ribbon held; the copper cooled.",
        "Thus the meadow dried and the harbor emptied slowly today.",
        "First, the lantern lit the orchard path and the river bank.",
        "The survey does not establish that pruning raises the fruit yield.",
    ] + [sentence(10, seed=i) for i in range(5)]
    text = doc(sentences, per_paragraph=3)
    m = hb.measure_text(mech, table, text, "paper.tex")["metrics"]
    words = m["words"]
    assert m["so_per_1k"] == pytest.approx(1000.0 / words)
    assert m["semicolons_per_1k"] == pytest.approx(1000.0 / words)
    assert m["contrast_per_1k"] == pytest.approx(1000.0 / words)
    assert m["cause_per_1k"] == pytest.approx(1000.0 / words)
    assert m["sequence_per_1k"] == pytest.approx(1000.0 / words)
    assert m["relation_per_1k"] == pytest.approx(3000.0 / words)
    assert m["scope_negation_per_1k"] == pytest.approx(1000.0 / words)


def test_an_empty_document_has_no_rates(hb, tools):
    mech, table = tools
    result = hb.measure_text(mech, table, "", "empty.tex")
    m = result["metrics"]
    assert m["words"] == 0 and m["sentences"] == 0
    assert m["over30_pct"] is None and m["so_per_1k"] is None and m["relation_per_1k"] is None
    assert result["detectors"]["RULE-12 profile"]["per_1k"] is None


def test_a_broken_detector_is_recorded_not_raised(hb, tools):
    mech, _table = tools

    def broken(text, path):
        raise RuntimeError("boom")

    result = hb.measure_text(mech, [("RULE-X", broken, True, "hook")], doc([sentence(10)]), "paper.tex")
    assert result["detectors"]["RULE-X"]["count"] is None
    assert "boom" in result["detectors"]["RULE-X"]["error"]


def test_document_level_counts_split_the_profile_checks(hb, tools):
    mech, table = tools
    so = ["The gadget moved the river, so the lantern rose over the orchard today."] * 12
    # About 1,090 words in 73 sentences, one of them 90 words long. The share of long sentences is low.
    text = whole_doc(so + [sentence(14, seed=i) for i in range(60)] + [sentence(90)])
    dl = hb.measure_text(mech, table, text, "paper.tex")["document_level"]
    assert dl == {"extreme_sentences": 1, "share_high": 0, "share_low": 1, "so_joins": 1, "share_evaluated": True}


def test_extreme_sentences_are_counted_apart_from_the_one_finding(hb, tools):
    mech, table = tools
    text = whole_doc([sentence(14, seed=i) for i in range(45)] + [sentence(85), sentence(90), sentence(100)])
    result = hb.measure_text(mech, table, text, "paper.tex")
    # The profile reports one finding for the document; the harness counts the sentences behind it.
    assert result["document_level"]["extreme_sentences"] == 3
    assert hb.extreme_count(mech, mech._pf_document(text, "paper.tex"), [14, 80, 90, 100, 81, 61]) == 3


def test_the_share_check_is_marked_evaluated_only_for_a_complete_latex_document(hb, tools):
    mech, table = tools
    body = [sentence(14, seed=i) for i in range(45)]

    def evaluated(text, name):
        return hb.measure_text(mech, table, text, name)["document_level"]["share_evaluated"]

    assert evaluated(whole_doc(body), "p.tex") is True
    # A section file or a fragment is not read, however long it runs.
    assert evaluated(doc(body), "p.tex") is False
    # A whole document under 40 sentences is not read either.
    assert evaluated(whole_doc(body[:30]), "p.tex") is False
    # Slides are not a paper.
    slides = "\\documentclass{beamer}\n\\begin{document}\n" + doc(body) + "\\end{document}\n"
    assert evaluated(slides, "talk.tex") is False
    # A main file that pulls its sections in holds no complete prose; an \input in a table does not count.
    main = "\\documentclass{article}\n\\begin{document}\n" + doc(body) + "\\input{methods}\n\\end{document}\n"
    assert evaluated(main, "main.tex") is False
    table_input = whole_doc(body).replace("\\end{document}", "\\begin{table}\\input{t}\\end{table}\n\\end{document}")
    assert evaluated(table_input, "p.tex") is True
    # An opening \begin{document} with no \end{document} is an edit, not a paper.
    assert evaluated(whole_doc(body).replace("\\end{document}\n", ""), "p.tex") is False
    # Markdown and text are never checked, with or without an abstract or an introduction.
    md = "# Abstract\n\n" + " ".join(sentence(14, seed=i) for i in range(160)) + "\n"
    for name in ("draft.md", "notes.md", "intro.md", "abstract.txt"):
        assert evaluated(md, name) is False, name
    assert evaluated("# Notes\n\n" + md.split("\n\n", 1)[1], "notes.md") is False


def test_markdown_footnote_bodies_are_left_out_of_the_measured_prose(hb, tools):
    mech, table = tools
    host = "The harbor moved quietly across the meadow today.[^a]"
    note = "[^a]: " + " ".join(["gadget"] * 84) + ".\n\n    " + " ".join(["river"] * 60) + ".\n"
    text = host + "\n\n" + note + "\nThe lantern rose over the orchard today.\n"
    result = hb.measure_text(mech, table, text, "notes.md")
    assert result["metrics"]["sentences"] == 2 and result["metrics"]["words"] == 8 + 7
    assert result["document_level"]["extreme_sentences"] == 0 and result["tail"]["50"] == 0
    assert result["detectors"]["RULE-12 profile"]["count"] == 0


def test_the_tail_counts_sentences_over_each_length(hb):
    counts = hb.tail_counts([10, 50, 51, 61, 66, 71, 76, 81, 101])
    assert counts == {"50": 7, "60": 6, "65": 5, "70": 4, "75": 3, "80": 2, "100": 1}
    assert tuple(counts) == tuple(str(n) for n in hb.TAIL_WORDS)
    assert hb.tail_counts([]) == {str(n): 0 for n in hb.TAIL_WORDS}


def test_the_tail_summary_pools_words_and_hits_per_group(hb, tools):
    mech, table = tools
    docs = []
    for group, body in (("human", [sentence(14)] * 30 + [sentence(70)]), ("human", [sentence(14)] * 30), ("era", [sentence(14)] * 10 + [sentence(90), sentence(65)])):
        result = hb.measure_text(mech, table, doc(body), "p.tex")
        result.update({"group": group, "document": "d"})
        docs.append(result)
    tail = hb.summarize_tail(docs)
    assert set(tail) == {"human", "era", "pooled"}
    human = tail["human"]
    assert human["hits"]["60"] == 1 and human["documents_with_hit"]["60"] == 1 and human["hits"]["70"] == 0
    assert human["words_per_hit"]["60"] == human["words"] and human["words_per_hit"]["70"] is None
    assert tail["era"]["hits"]["60"] == 2 and tail["era"]["hits"]["80"] == 1
    assert tail["pooled"]["hits"]["60"] == 3 and tail["pooled"]["words"] == human["words"] + tail["era"]["words"]
    assert hb.summarize_tail(docs[:1]).keys() == {"human"}  # one group: no pooled row


# ---------- corpus plumbing -------------------------------------------------------------------------


def test_load_manifest_skips_comments_and_blank_lines(hb, tmp_path):
    manifest = tmp_path / "m.tsv"
    manifest.write_text(
        "# SPDX-License-Identifier: CC-BY-4.0\n\nid\tgroup\ttitle\n1111.00001\thuman\tA paper\n2222.00002\tera\tAnother\n",
        encoding="utf-8",
    )
    rows = hb.load_manifest(manifest)
    assert sorted(rows) == ["1111.00001", "2222.00002"]
    assert rows["2222.00002"]["group"] == "era" and rows["1111.00001"]["title"] == "A paper"


def test_group_comes_from_the_manifest_then_the_directory(hb, tmp_path):
    (tmp_path / "human").mkdir()
    path = tmp_path / "human" / "1111.00001.tex"
    path.write_text("x", encoding="utf-8")
    assert hb.group_of(path, {"1111.00001": {"group": "era"}}) == "era"
    assert hb.group_of(path, {}) == "human"


def test_collect_walks_directories_and_filters_extensions(hb, tmp_path):
    (tmp_path / "sub").mkdir()
    for name in ("b.tex", "a.md", "c.txt", "d.pdf", "sub/e.tex", "sub/f.png"):
        (tmp_path / name).write_text("x", encoding="utf-8")
    found = [p.relative_to(tmp_path).as_posix() for p in hb.collect([tmp_path])]
    assert found == ["a.md", "b.tex", "c.txt", "sub/e.tex"]
    single = hb.collect([tmp_path / "b.tex", tmp_path / "missing.tex"])
    assert [p.name for p in single] == ["b.tex"]


def make_corpus(tmp_path):
    human = tmp_path / "human"
    era = tmp_path / "era"
    human.mkdir(parents=True, exist_ok=True)
    era.mkdir(parents=True, exist_ok=True)
    (human / "1111.00001.tex").write_text(doc([sentence(10, seed=i) for i in range(30)] + [sentence(40)] * 10), encoding="utf-8")
    (human / "1111.00002.tex").write_text(doc([sentence(12, seed=i) for i in range(45)]), encoding="utf-8")
    (era / "2222.00001.md").write_text("# Notes\n\n" + sentence(14) + " " + sentence(80) + "\n", encoding="utf-8")
    return tmp_path


def test_measure_paths_and_summary(hb, tmp_path):
    corpus = make_corpus(tmp_path)
    report = hb.measure_paths([corpus])
    assert [d["document"] for d in report["documents"]] == ["2222.00001", "1111.00001", "1111.00002"]
    assert set(report["groups"]) == {"human", "era"}
    assert report["groups"]["human"]["documents"] == 2 and report["groups"]["era"]["documents"] == 1
    stat = report["groups"]["human"]["over30_pct"]
    assert stat["min"] <= stat["median"] <= stat["max"]
    assert report["agent_style_version"] and Path(report["package_root"]).parts[-2:] == ("packages", "pypi")
    json.dumps(report)  # serializable as it stands


def test_markdown_report_has_every_section_and_row(hb, tmp_path):
    report = hb.measure_paths([make_corpus(tmp_path)])
    md = hb.render_markdown(report)
    for heading in ("# Human-Baseline Measurement", "## Prose Metrics", "## Detector Findings",
                    "## Document-Level Reports", "## Long-Sentence Tail", "## Group Summary",
                    "## Documents with a Detector Finding"):
        assert heading in md
    assert "| share checked |" in md and "| pooled |" in md
    for doc_id in ("1111.00001", "1111.00002", "2222.00001"):
        assert md.count("| " + doc_id + " |") >= 3
    assert "RULE-12 profile" in md and "RULE-08 repeats" in md
    assert "violation" not in md.lower()


def test_main_writes_markdown_and_json(hb, tmp_path):
    corpus = make_corpus(tmp_path / "corpus")
    out_md, out_json = tmp_path / "out.md", tmp_path / "out.json"
    assert hb.main([str(corpus), "--md", str(out_md), "--json", str(out_json)]) == 0
    assert out_md.read_text(encoding="utf-8").startswith("# Human-Baseline Measurement")
    data = json.loads(out_json.read_text(encoding="utf-8"))
    assert len(data["documents"]) == 3 and "detectors" in data["documents"][0]


def test_main_prints_markdown_without_output_flags(hb, tmp_path, capsys):
    corpus = make_corpus(tmp_path / "corpus")
    assert hb.main([str(corpus)]) == 0
    assert capsys.readouterr().out.startswith("# Human-Baseline Measurement")


def test_main_reports_an_empty_corpus(hb, tmp_path, capsys):
    (tmp_path / "empty").mkdir()
    assert hb.main([str(tmp_path / "empty")]) == 1
    assert "no .tex" in capsys.readouterr().err


def test_main_uses_the_manifest_groups(hb, tmp_path):
    corpus = make_corpus(tmp_path / "corpus")
    manifest = tmp_path / "m.tsv"
    manifest.write_text("id\tgroup\n1111.00001\tpilot\n", encoding="utf-8")
    out = tmp_path / "out.json"
    assert hb.main([str(corpus), "--manifest", str(manifest), "--json", str(out)]) == 0
    groups = {d["document"]: d["group"] for d in json.loads(out.read_text(encoding="utf-8"))["documents"]}
    assert groups["1111.00001"] == "pilot" and groups["1111.00002"] == "human" and groups["2222.00001"] == "era"


# ---------- what is committed -------------------------------------------------------------------------


def test_the_shipped_manifest_lists_public_arxiv_ids(hb):
    rows = hb.load_manifest(HARNESS_DIR / "manifest.tsv")
    assert len(rows) == 18
    assert {r["group"] for r in rows.values()} == {"human", "era"}
    assert sum(1 for r in rows.values() if r["group"] == "human") == 12
    for arxiv_id, row in rows.items():
        assert re.fullmatch(r"\d{4}\.\d{4,5}", arxiv_id), arxiv_id
        assert row["title"] and row["first_author"] and re.fullmatch(r"\d{4}", row["year"])
    human_years = [int(r["year"]) for r in rows.values() if r["group"] == "human"]
    era_years = [int(r["year"]) for r in rows.values() if r["group"] == "era"]
    assert max(human_years) < 2023 and min(era_years) >= 2023


def test_no_corpus_is_committed_beside_the_harness():
    allowed = {"measure.py", "README.md", "manifest.tsv"}
    names = {p.name for p in HARNESS_DIR.iterdir() if p.name != "__pycache__"}
    assert names <= allowed, names - allowed
    assert not list(HARNESS_DIR.rglob("*.tex")) and not list(HARNESS_DIR.rglob("*.pdf"))
