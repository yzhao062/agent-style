# SPDX-License-Identifier: MIT
"""Tests for the hook-only RULE-A detector that flags prose in a LaTeX table cell.

``_rule_a`` reads LaTeX only: tabular, tabular*, tabularx, tabulary, longtable
and tblr. A table outside an appendix or a supplement is flagged, once, when a
cell holds more than 15 words or two sentences. A table cell holds a number, a
label, or a short phrase; anything that needs a sentence belongs in the text.
Markdown tables in agent documents carry long cells by design, so a ``.md`` file
is never read.

The detector is registered for hooks and is not part of ``agent-style review``:
the audit classifies RULE-A as structural (bullet overuse), and these tests pin
that the audit output does not move.

Every text here is synthetic: invented words and made-up numbers.
"""

from __future__ import annotations

import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from agent_style.review import audit, detectors_mech, primitive
from agent_style.review.detectors_mech import _rule_03, _rule_a


def words(n: int) -> str:
    return " ".join(["alpha"] * n)


def table(rows, spec="ll", env="tabular", head=None):
    begin = head if head is not None else "\\begin{" + env + "}{" + spec + "}"
    return begin + "\n" + "\\\\\n".join(rows) + "\\\\\n\\end{" + env + "}\n"


ENVS = [
    ("tabular", "\\begin{tabular}{ll}"),
    ("tabular*", "\\begin{tabular*}{\\textwidth}{ll}"),
    ("tabularx", "\\begin{tabularx}{\\textwidth}{lX}"),
    ("tabulary", "\\begin{tabulary}{\\textwidth}{LL}"),
    ("longtable", "\\begin{longtable}{p{3cm}p{6cm}}"),
    ("tblr", "\\begin{tblr}{colspec={ll}, hlines}"),
]


# ---------- what flags -------------------------------------------------------------


@pytest.mark.parametrize("env,head", ENVS, ids=[e for e, _h in ENVS])
def test_a_cell_over_fifteen_words_flags_in_every_table_environment(env, head):
    text = table(["Name & Note", "A & " + words(16)], env=env, head=head)
    found = _rule_a(text, "main.tex")
    assert len(found) == 1, (env, [v.detail for v in found])
    assert found[0].rule == "RULE-A" and found[0].line == 3
    assert "a table cell of 16 words" in found[0].detail


@pytest.mark.parametrize("env,head", ENVS, ids=[e for e, _h in ENVS])
def test_fifteen_words_and_the_layout_arguments_stay_quiet(env, head):
    # The width and the column specification open the table; they are no words.
    text = table([words(15) + " & x", "A & B"], env=env, head=head)
    assert _rule_a(text, "main.tex") == [], env


def test_the_first_cell_is_read_after_the_arguments():
    text = "\\begin{tabular}[t]{@{}p{3cm}p{6cm}@{}}\n" + words(16) + " & x\\\\\n\\end{tabular}\n"
    found = _rule_a(text, "main.tex")
    assert len(found) == 1 and found[0].line == 2 and found[0].column == 1


def test_two_sentences_in_a_short_cell_flag():
    text = table(["Metric & Note", "A & Lower is better. Averaged over five seeds."])
    found = _rule_a(text, "main.tex")
    assert len(found) == 1 and "a table cell of 2 sentences" in found[0].detail


@pytest.mark.parametrize(
    "cell",
    [
        "Lower is better.",
        "Lower is better",
        "Lower is better, averaged over five seeds.",
        "Lee and Kim ran Prof. Park and Dr. Chen over five seeds",
        "Lee and Kim ran J. Smith and K. Lee over five seeds",
        "Gain over the baseline, e.g. Five seeds, i.e. Averaged over runs",
        "See Fig. Three for the setup and Tab. Four for the other splits",
        "Compared vs. Baseline models on the full test set",
        "Study of 3.5 points. 4.2 points. 1.1 points",
        "Yes. No.",
        "Mean (std.) over five seeds",
    ],
)
def test_one_sentence_is_not_two(cell):
    assert _rule_a(table(["Metric & Note", "A & " + cell]), "main.tex") == [], cell


def test_each_table_is_one_finding_at_the_first_offending_cell():
    text = table(["Name & Note", "A & short", "B & " + words(20), "C & " + words(30)])
    found = _rule_a(text, "main.tex")
    assert len(found) == 1 and found[0].line == 4
    assert "20 words" in found[0].detail


def test_two_tables_are_two_findings_on_their_own_lines():
    text = (
        table(["A & " + words(16)]) + "\nText between the tables.\n\n"
        + table(["A & short"]) + table(["A & " + words(17)])
    )
    found = _rule_a(text, "main.tex")
    assert [v.line for v in found] == [2, 11]


def test_the_finding_sits_on_the_offending_cell_line_of_a_multi_line_table():
    text = (
        "\\begin{table}\n\\begin{tabular}{lll}\n\\toprule\nA & B & C\\\\\n\\midrule\n"
        "x & y & z\\\\\n"
        "x & " + words(16) + " & z\\\\\n"
        "\\bottomrule\n\\end{tabular}\n\\end{table}\n"
    )
    found = _rule_a(text, "main.tex")
    assert len(found) == 1 and found[0].line == 7 and found[0].column == 5


def test_a_rule_command_before_a_cell_does_not_move_the_finding():
    text = (
        "\\begin{tabular}{ll}\n\\toprule\nA & B\\\\\n\\midrule\n"
        + words(16) + " & x\\\\\n\\cmidrule(lr){1-2}\n"
        + "y & z\\\\\n\\bottomrule\n\\end{tabular}\n"
    )
    found = _rule_a(text, "main.tex")
    assert len(found) == 1 and found[0].line == 5
    after_rule = "\\begin{tabular}{ll}\nA & B\\\\\n\\midrule\n" + "x & " + words(16) + "\\\\\n\\end{tabular}\n"
    assert _rule_a(after_rule, "main.tex")[0].line == 4
    rule_line = "\\begin{tabular}{ll}\nA & B\\\\\n\\midrule\n" + words(16) + " & x\\\\\n\\end{tabular}\n"
    assert _rule_a(rule_line, "main.tex")[0].line == 4


def test_a_cell_that_spans_lines_is_one_cell():
    text = "\\begin{tabular}{ll}\nA & " + words(8) + "\n" + words(8) + "\\\\\n\\end{tabular}\n"
    found = _rule_a(text, "main.tex")
    assert len(found) == 1 and found[0].line == 2 and "16 words" in found[0].detail


# ---------- what counts as a word ---------------------------------------------------


def test_numbers_single_letters_math_citations_and_references_are_no_words():
    cell = (
        words(15) + " 12 3.45 6\\% a b c $x_i + y_j$ \\citep{lee2020,kim2021} "
        "\\ref{tab:x} \\cref{sec:y} \\label{z} 99.5 x y"
    )
    assert _rule_a(table(["A & " + cell]), "main.tex") == []
    assert len(_rule_a(table(["A & " + cell + " beta"]), "main.tex")) == 1


def test_a_command_is_dropped_and_its_text_is_kept():
    bold = "\\textbf{" + words(8) + "} \\emph{" + words(8) + "}"
    found = _rule_a(table(["A & " + bold]), "main.tex")
    assert len(found) == 1 and "16 words" in found[0].detail


def test_layout_commands_add_no_words():
    cell = "\\cellcolor{lightgray} \\textcolor{red}{" + words(15) + "} \\parbox[t]{5cm}{} \\hspace{2cm} \\rule{1cm}{1pt}"
    assert _rule_a(table(["A & " + cell]), "main.tex") == []


@pytest.mark.parametrize(
    "cell",
    [
        "\\multicolumn{2}{c}{" + words(15) + "}",
        "\\multirow{2}{*}{" + words(15) + "}",
        "\\multicolumn{2}{|c|}{" + words(15) + "}",
        "\\cmidrule(lr){2-3} " + words(15),
        "\\midrule " + words(15),
        "\\cline{1-2} " + words(15),
        "\\addlinespace[2pt] " + words(15),
    ],
)
def test_span_and_rule_commands_keep_the_text_and_add_no_words(cell):
    assert _rule_a(table(["A & B", cell + " & x"]), "main.tex") == [], cell


def test_a_long_cell_inside_multicolumn_flags():
    found = _rule_a(table(["A & B", "\\multicolumn{2}{c}{" + words(16) + "}"]), "main.tex")
    assert len(found) == 1 and "16 words" in found[0].detail


def test_a_separator_inside_braces_does_not_split_a_cell():
    # `\\` inside \makecell is a line break in the cell, not a row end.
    cell = "\\makecell{" + words(8) + "\\\\" + words(8) + "}"
    found = _rule_a(table(["A & " + cell]), "main.tex")
    assert len(found) == 1 and "16 words" in found[0].detail
    split = words(8) + "\\\\" + words(8)
    assert _rule_a(table(["A & " + split]), "main.tex") == []


def test_an_escaped_ampersand_does_not_split_a_cell():
    cell = " \\& ".join(["alpha"] * 8)
    assert len(_rule_a(table(["A & " + cell + " \\& " + words(8)]), "main.tex")) == 1


# ---------- nested tables, captions, comments, code -----------------------------------


def test_a_short_nested_table_is_not_prose_in_the_outer_cell():
    inner = "\\begin{tabular}{@{}l@{}}" + words(9) + "\\\\" + words(9) + "\\end{tabular}"
    assert _rule_a(table(["A & " + inner + " & x"]), "main.tex") == []


def test_a_nested_table_is_its_own_finding_and_its_words_do_not_leak():
    inner = "\\begin{tabular}{@{}l@{}}" + words(20) + "\\end{tabular}"
    text = table(["A & " + words(10) + " " + inner])
    found = _rule_a(text, "main.tex")
    assert len(found) == 1 and "20 words" in found[0].detail
    both = table(["A & " + words(20) + " " + inner])
    assert len(_rule_a(both, "main.tex")) == 2


def test_tables_nested_deeper_than_the_limit_stay_inside_their_parent():
    text = ""
    for _ in range(8):
        text += "\\begin{tabular}{l}\n" + words(2) + " &\n"
    text += words(20)
    for _ in range(8):
        text += "\n\\end{tabular}"
    found = _rule_a(text + "\n", "main.tex")
    assert isinstance(found, list) and len(found) <= detectors_mech._RA_MAX_DEPTH


def test_a_caption_in_a_longtable_is_not_a_cell():
    text = (
        "\\begin{longtable}{ll}\n\\caption{" + words(40) + "}\\\\\nA & B\\\\\n\\end{longtable}\n"
    )
    assert _rule_a(text, "main.tex") == []
    with_cell = text.replace("A & B", "A & " + words(16))
    found = _rule_a(with_cell, "main.tex")
    assert len(found) == 1 and found[0].line == 3


def test_a_table_environment_wrapper_is_not_a_table():
    text = "\\begin{table}\n\\caption{" + words(40) + "}\n" + words(40) + "\n\\end{table}\n"
    assert _rule_a(text, "main.tex") == []


@pytest.mark.parametrize(
    "wrap",
    [
        "% {}",
        "\\begin{verbatim}\n{}\n\\end{verbatim}",
        "\\begin{lstlisting}\n{}\n\\end{lstlisting}",
        "\\begin{comment}\n{}\n\\end{comment}",
    ],
)
def test_a_table_in_a_comment_or_code_is_not_read(wrap):
    inner = table(["A & " + words(20)])
    text = wrap.replace("{}", inner.strip()) if wrap.startswith("\\") else "".join("% " + l + "\n" for l in inner.splitlines())
    assert _rule_a("\\begin{document}\n" + text + "\n", "main.tex") == [], wrap


def test_a_commented_cell_is_not_read():
    text = "\\begin{tabular}{ll}\nA & B\\\\\n% C & " + words(30) + "\\\\\nD & E\\\\\n\\end{tabular}\n"
    assert _rule_a(text, "main.tex") == []
    tail = "\\begin{tabular}{ll}\nA & B % " + words(30) + "\\\\\n\\end{tabular}\n"
    assert _rule_a(tail, "main.tex") == []


# ---------- exemptions and formats -----------------------------------------------------


@pytest.mark.parametrize(
    "name",
    ["appendix.tex", "02-Appendix.tex", "supp.tex", "supplement.tex", "supplementary-tables.tex",
     "A_appendices.tex", "C:\\x\\appendix.tex", "/tmp/x/sections/supp_b.tex"],
)
def test_appendix_and_supplement_file_names_are_exempt(name):
    assert _rule_a(table(["A & " + words(20)]), name) == [], name


@pytest.mark.parametrize("name", ["support.tex", "tables.tex", "main.tex", "application.tex", "results.tex", ""])
def test_other_file_names_are_read(name):
    assert len(_rule_a(table(["A & " + words(20)]), name)) == 1, name


def test_a_table_after_the_appendix_command_is_exempt():
    text = (
        table(["A & " + words(20)]) + "\\appendix\n\\section{Details}\n" + table(["A & " + words(20)])
    )
    found = _rule_a(text, "main.tex")
    assert [v.line for v in found] == [2]


def test_a_table_in_the_appendices_environment_is_exempt():
    text = (
        table(["A & " + words(20)])
        + "\\begin{appendices}\n" + table(["A & " + words(20)]) + "\\end{appendices}\n"
        + table(["A & " + words(20)])
    )
    assert [v.line for v in _rule_a(text, "main.tex")] == [2, 10]
    unclosed = table(["A & " + words(20)]) + "\\begin{appendices}\n" + table(["A & " + words(20)])
    assert [v.line for v in _rule_a(unclosed, "main.tex")] == [2]


@pytest.mark.parametrize("name", ["notes.md", "README.markdown", "NOTES.MD", "notes.txt", "notes.rst"])
def test_markdown_plain_text_and_rst_files_are_never_read(name):
    assert _rule_a(table(["A & " + words(20)]), name) == [], name
    markdown = (
        "| Name | Note |\n| --- | --- |\n| A | " + words(40) + " |\n| B | Lower is better. Averaged over seeds. |\n"
    )
    assert _rule_a(markdown, name) == [], name


def test_unnamed_text_is_read_only_when_it_is_latex():
    assert len(_rule_a(table(["A & " + words(20)]), "")) == 1
    assert _rule_a(table(["A & " + words(20)])) != []
    markdown = "| Name | Note |\n| --- | --- |\n| A | " + words(40) + " |\n"
    assert _rule_a(markdown, "") == []
    assert _rule_a("A & " + words(40) + "\\\\", "") == []


def test_an_edit_sized_fragment_is_read_alone():
    # The guard hands an Edit's new fragment to the detector, not the file.
    fragment = table(["A & " + words(16)])
    assert len(_rule_a(fragment, "main.tex")) == 1
    assert len(_rule_a(fragment, "")) == 1
    # Rows alone have no table to belong to, so nothing is read.
    assert _rule_a("A & " + words(16) + "\\\\\n", "main.tex") == []


def test_findings_are_ordered_by_position():
    text = table(["A & " + words(16)]) + "\n" + table(["B & " + words(17)])
    lines = [v.line for v in _rule_a(text, "main.tex")]
    assert lines == sorted(lines) and len(lines) == 2


def test_the_message_says_what_a_cell_holds():
    found = _rule_a(table(["A & " + words(16)]), "main.tex")[0]
    assert found.detail == (
        "a table cell of 16 words; a table cell holds a number, a label, or a short phrase, "
        "so move content that needs a sentence into the text"
    )
    two = _rule_a(table(["A & Lower is better. Averaged over five seeds."]), "main.tex")[0]
    assert two.detail.startswith("a table cell of 2 sentences; a table cell holds a number")


def test_positions_survive_crlf():
    text = "\\begin{tabular}{ll}\r\nA & B\\\\\r\nx & " + words(16) + "\\\\\r\n\\end{tabular}\r\n"
    found = _rule_a(text, "main.tex")
    assert len(found) == 1 and found[0].line == 3


# ---------- registration: hook-only ---------------------------------------------------


def test_registered_for_hooks_with_the_file_path():
    assert detectors_mech._DISPATCH["RULE-A"] is _rule_a
    assert "RULE-A" in detectors_mech._FILE_PATH_RULES
    rule = SimpleNamespace(id="RULE-A", severity="low")
    text = table(["A & " + words(16)])
    assert detectors_mech.run(rule, text, "main.tex").count == 1
    assert detectors_mech.run(rule, text, "appendix.tex").count == 0
    assert detectors_mech.run(rule, text, "notes.md").count == 0


def test_default_file_path_is_empty_string():
    text = table(["A & " + words(16)])
    assert _rule_a(text) == _rule_a(text, "")


def test_the_audit_never_runs_the_hook_only_detectors(tmp_path):
    # `agent-style review` classifies RULE-A as structural and RULE-03 as semantic;
    # the benchmark pins its mechanical scope on that.
    assert primitive._CLASSIFICATION["RULE-A"] == {"structural"}
    assert primitive._CLASSIFICATION["RULE-03"] == {"semantic"}
    source = tmp_path / "paper.tex"
    source.write_text(
        "\\section{Results}\n"
        "Raising the cache changes the hit rate by 3.7, 41.6 and 45.3 points. "
        "Prefetching lowers the miss rate by 8.9 and 5.2 points. A second layout gives 0.57 and 0.43.\n"
        + table(["A & " + words(40), "B & Lower is better. Averaged over five seeds."])
        + "\\begin{figure}\n\\caption{Hit rate was 41.6, 45.3 and 47.1 on three traces.}\n\\end{figure}\n",
        encoding="utf-8",
    )
    for only in (True, False):
        result = audit(str(source), mechanical_only=only)
        mech = {r.rule for r in result.rule_results if r.detector == "mechanical"}
        assert "RULE-A" not in mech and "RULE-03" not in mech, mech
        for r in result.rule_results:
            if r.rule in ("RULE-A", "RULE-03"):
                assert r.detector != "mechanical"
                assert all(v.rule == r.rule for v in r.violations)
                assert not any("table cell" in v.detail or "caption" in v.detail for v in r.violations)


# ---------- cross-rule: tblr and tabulary cells under RULE-03 ----------------------------

# A numeric table cell is a table cell. RULE-03 reads prose, so every table
# environment RULE-A reads is a display for RULE-03 too; the numbers in tblr and
# tabulary cells feed none of checks A, B and D, while a long prose cell still
# belongs to RULE-A.

CROSS = [
    ("tblr", "\\begin{tblr}{cccc}"),
    ("tabulary", "\\begin{tabulary}{\\textwidth}{CCCC}"),
]
NUMERIC_ROWS = [
    "0.81234 & 0.82345 & 0.83456 & 0.84567",
    "0.71234 & 0.72345 & 0.73456 & 0.74567",
    "0.62 [0.51, 0.83] & 41.6\\% & 45.3\\% & 47.1\\%",
    "0.41 & 0.52 & 0.63 & 0.74",
    "0.85 & 0.96 & 0.17 & 0.28",
]


@pytest.mark.parametrize("env,head", CROSS, ids=[e for e, _h in CROSS])
@pytest.mark.parametrize("path", ["main.tex", "04-results.tex", "00-abstract.tex", "01-introduction.tex", ""])
def test_numeric_cells_in_a_table_fragment_stay_quiet_under_rule_03(env, head, path):
    fragment = table(NUMERIC_ROWS, env=env, head=head)
    assert _rule_03(fragment, path) == [], (env, path)
    assert _rule_a(fragment, path) == [], (env, path)


@pytest.mark.parametrize("env,head", CROSS, ids=[e for e, _h in CROSS])
def test_numeric_cells_stay_quiet_in_a_float_and_among_prose(env, head):
    fragment = table(NUMERIC_ROWS, env=env, head=head)
    floated = "\\begin{table}\n\\caption{Scores by split.}\n" + fragment + "\\end{table}\n"
    assert _rule_03(floated, "main.tex") == []
    among = "\\section{Results}\nThe scores are in the table.\n\n" + fragment + "\nNothing else moved.\n"
    assert _rule_03(among, "main.tex") == []
    assert _rule_03("\\begin{abstract}\n" + fragment + "\\end{abstract}\n", "main.tex") == []


@pytest.mark.parametrize("env,head", CROSS, ids=[e for e, _h in CROSS])
def test_long_prose_cells_still_trigger_rule_a_and_not_rule_03(env, head):
    rows = ["Name & Note & x & y", "A & " + words(20) + " & 0.81234 & 0.82345"] + NUMERIC_ROWS
    text = table(rows, env=env, head=head)
    found = _rule_a(text, "main.tex")
    assert len(found) == 1 and found[0].line == 3, [v.detail for v in found]
    assert "a table cell of 20 words" in found[0].detail
    assert _rule_03(text, "main.tex") == []
    two_sentences = table(["A & Lower is better. Averaged over five seeds. & 0.81234 & 0.82345"], env=env, head=head)
    assert len(_rule_a(two_sentences, "main.tex")) == 1
    assert _rule_03(two_sentences, "main.tex") == []


def test_the_table_environments_rule_a_reads_are_displays_for_rule_03():
    # One list of environments: a table RULE-A reads must not feed RULE-03's prose checks.
    for env, head in ENVS:
        fragment = table(NUMERIC_ROWS, env=env, head=head)
        assert _rule_03(fragment, "main.tex") == [], env


# ---------- robustness -----------------------------------------------------------------

ODD_INPUTS = [
    "",
    " ",
    "\n",
    "\\begin{tabular}",
    "\\begin{tabular}{",
    "\\begin{tabular}{ll}",
    "\\begin{tabular}{ll} A & B",
    "\\end{tabular}",
    "\\end{tabular}\\begin{tabular}",
    "\\begin{tabular}{ll}\\end{tblr}",
    "\\begin{tblr}{ll}\\begin{tabular}{l}\\end{tblr}\\end{tabular}",
    "\\begin{tabular}[",
    "\\begin{tabular}[t",
    "\\begin{tabular*}{\\textwidth}",
    "\\begin{tabularx}{",
    "\\begin{tabular}{ll}\\end{tabular}",
    "\\begin{tabular}{ll}{}{}{}\\end{tabular}",
    "\\begin{tabular}{ll}}}}} & {{{{\\end{tabular}",
    "\\begin{tabular}{ll}\\\\ & \\\\ & \\\\\\end{tabular}",
    "\\begin{tabular}{ll}\\multicolumn{2}{c}{\\end{tabular}",
    "\\begin{tabular}{ll}\\multirow{2}{*}{" + words(30) + "\\end{tabular}",
    "\\begin{tabular}{ll}\\cmidrule(lr){ \\end{tabular}",
    "\\begin{tabular}{ll}$ $ $ & \\( \\end{tabular}",
    "\\begin{tabular}{ll}" + words(30) + "\\end{tabular}\\appendix",
    "\\begin{tabular}{ll}\\caption{" + words(30) + "\\end{tabular}",
    "\\begin{tabular}{ll}" + "\\\\[" * 50 + "\\end{tabular}",
    "\\begin{tabular}{ll}" + "x. Y. " * 200 + "\\end{tabular}",
    "\\begin{tabular}{ll}" + "." * 500 + words(10) + "\\end{tabular}",
    "\x00\x01 \\begin{tabular}{ll}\x00 A \x00 & \x00 " + words(30) + "\\end{tabular}",
    "".join(chr(i) for i in range(0, 0x300)),
    "{" * 2000 + "}" * 2000,
    "\\begin{tabular}{ll}" + "{" * 2000 + words(30) + "}" * 2000 + "\\end{tabular}",
]


@pytest.mark.parametrize("text", ODD_INPUTS, ids=[f"odd-{i}" for i in range(len(ODD_INPUTS))])
@pytest.mark.parametrize("path", ["", "main.tex", "appendix.tex", "notes.md"])
def test_never_raises(text, path):
    # The scan itself, not the public wrapper, so a bug cannot hide behind the
    # wrapper's catch-all.
    assert isinstance(detectors_mech._rule_a_scan(text, path), list)
    assert isinstance(_rule_a(text, path), list)


def test_never_raises_on_odd_argument_types():
    assert _rule_a(None) == []  # type: ignore[arg-type]
    assert _rule_a(42) == []  # type: ignore[arg-type]
    assert _rule_a(table(["A & " + words(16)]), None) is not None  # type: ignore[arg-type]
    assert len(_rule_a(table(["A & " + words(16)]), Path("main.tex"))) == 1  # type: ignore[arg-type]


def test_a_broken_scan_is_swallowed_not_raised(monkeypatch):
    def boom(*_args, **_kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(detectors_mech, "_ra_tables", boom)
    assert _rule_a(table(["A & " + words(16)]), "main.tex") == []


# Built inside a list with short ids: pytest copies a test id into the
# PYTEST_CURRENT_TEST environment variable, and Windows caps one variable at
# 32,767 characters, so a raw 200 KB parameter breaks setup there.
HOSTILE_INPUTS = [
    "\\begin{tabular}{l}" * 50_000,
    "\\begin{tabular}{l}" * 30_000 + "\\end{tabular}" * 30_000,
    "\\begin{tabular}{l} a & b \\\\ " * 20_000 + "\\end{tabular}",
    "\\begin{tabular}{l}" + "a & " * 100_000 + "\\end{tabular}",
    "\\begin{tabular}{l}" + "x. " * 60_000 + "\\end{tabular}",
    "\\begin{tabular}{l}" + "." * 200_000 + " a b c d e f \\end{tabular}",
    "\\begin{tabular}[" * 50_000 + "\\end{tabular}",
    "\\begin{tabular}" + "{" * 100_000 + "\\end{tabular}",
    "\\begin{tabular}{l}" + "\\multicolumn{2}{c}{" * 20_000 + "\\end{tabular}",
    "\\begin{tabular}{l}" + "\\cmidrule(lr){2-3} " * 20_000 + "\\end{tabular}",
    "\\begin{tabular}{l}" + "\\\\[" * 60_000 + "\\end{tabular}",
    "\\begin{tabular}{l}" + "\\a[" * 60_000 + words(20) + "\\end{tabular}",
    "\\begin{tabular}{l}" + "$" * 200_000 + words(20) + "\\end{tabular}",
    "\\begin{tabular}{l}" + "\\href{" * 30_000 + words(20) + "\\end{tabular}",
    "\\begin{tabular}{l}" + "\\caption{x}" * 30_000 + "\\end{tabular}",
    "\\begin{tabular}{l}" + " " * 200_000 + "\\end{tabular}",
    "\\begin{tabular}{l}" + "\\\\" * 100_000 + "\\end{tabular}",
    "\\begin{tabular}{l}" + "&" * 200_000 + "\\end{tabular}",
    "\\begin{tabular}{l}" + "x " * 100_000 + "\\end{tabular}",
    "\\begin{tabular}{l}" + "\\textbf{" * 30_000 + "}" * 30_000 + "\\end{tabular}",
    ("\\begin{tabular}{l}\\begin{tabular}{l}" + words(3) + "\\end{tabular}\\end{tabular}") * 10_000,
    ("\\begin{tabular}{l}" + words(20) + "\\end{tabular}") * 10_000,
    "\\begin{tblr}\\begin{tabular}" * 40_000 + "\\end{tabular}\\end{tblr}" * 5_000,
    "\\end{tabular}" * 50_000,
    "\\begin{verbatim}\\begin{tabular}" * 20_000,
    "\\appendix \\begin{tabular}{l}" * 20_000,
    "\\caption{" * 50_000 + "\\begin{tabular}{l}" + words(20) + "\\end{tabular}",
]


@pytest.mark.parametrize("text", HOSTILE_INPUTS, ids=[f"hostile-{i}" for i in range(len(HOSTILE_INPUTS))])
def test_hostile_inputs_are_fast(text):
    for path in ("main.tex", ""):
        start = time.perf_counter()
        _rule_a(text, path)
        assert time.perf_counter() - start < 3.0, path


def test_two_hundred_kilobytes_of_tables_is_fast():
    block = (
        "\\begin{table}\n\\begin{tabular}{p{3cm}p{6cm}}\n\\toprule\nName & Note\\\\\n\\midrule\n"
        "A & short\\\\\nB & " + words(20) + " \\citep{lee2020}\\\\\n\\bottomrule\n\\end{tabular}\n\\end{table}\n\n"
    )
    text = block * (200_000 // len(block) + 1)
    assert len(text) >= 200_000
    start = time.perf_counter()
    found = _rule_a(text, "main.tex")
    assert time.perf_counter() - start < 3.0
    assert len(found) > 100
