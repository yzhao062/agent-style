# SPDX-License-Identifier: MIT
"""Tests for the 0.7.0 RULE-03 checks on LaTeX: body-prose stacks, captions, excess precision.

Check B reads figures stacked in an abstract or an introduction (tests/test_rule03_figures.py).
In a LaTeX file it now also reads the body prose between them, with the run
criterion only: three consecutive sentences that carry two precise figures each.
Check C flags a caption that carries three precise figures or runs over 100 words.
Check D flags a paragraph that holds four numbers written to four or more decimal
places. All three read LaTeX only and skip an appendix or a supplement, which is
where the detail removed from the text belongs.

Every text here is synthetic: invented sentences about caches, networks, batteries and
crop yields, with made-up numbers. Nothing is copied or paraphrased from a real
document, and the corpora the limits were measured on are not committed.
"""

from __future__ import annotations

import time

import pytest

from agent_style.review import detectors_mech
from agent_style.review.detectors_mech import _rule_03


def body_runs(violations):
    return [v for v in violations if "consecutive sentences in the body text" in v.detail]


def body_crowds(violations):
    return [v for v in violations if v.detail.startswith("one sentence in the body text")]


def front_hits(violations):
    return [v for v in violations if "in the abstract" in v.detail or "in the introduction" in v.detail]


def caption_hits(violations):
    return [v for v in violations if v.detail.startswith("a caption")]


def precision_hits(violations):
    return [v for v in violations if "decimal places" in v.detail]


def interval_hits(violations):
    return [v for v in violations if "numeric interval" in v.detail]


# Three consecutive sentences with 5, 3 and 3 precise figures: a stack.
STACK = (
    "Raising the cache from 2\\% to 100\\% of memory changes the hit rate by 3.7 points, "
    "from 41.6 to 45.3 on the shared trace. "
    "Prefetching lowers the miss rate by 8.9 points at full load and by 5.2 points "
    "at idle load, against 73.4 for the baseline policy. "
    "A second layout gives 0.57 and 0.43 with a 6\\% floor."
)

# One sentence with six figures, and two with one each.
CROWD = (
    "The gap is 0.15, 0.26, 0.48, 0.59, 0.67, and 0.82 across the six sensors. "
    "Operators should expect little change. Nothing else moved."
)


# ---------- check B in body prose ---------------------------------------------


@pytest.mark.parametrize("name", ["main.tex", "04-results.tex", "sections/related-work.tex", "C:\\x\\paper.tex", "x.TEX"])
def test_a_stack_in_latex_body_prose_flags(name):
    text = "\\section{Results}\n" + STACK + "\n"
    found = body_runs(_rule_03(text, name))
    assert len(found) == 1, (name, [v.detail for v in _rule_03(text, name)])
    assert found[0].line == 2 and found[0].column == 1
    assert "3 consecutive sentences in the body text carry 11 precise figures" in found[0].detail


def test_a_stack_in_unnamed_text_with_latex_markup_flags():
    text = "\\section{Results}\n" + STACK + "\n"
    assert len(body_runs(_rule_03(text, ""))) == 1
    assert len(body_runs(_rule_03(text))) == 1


@pytest.mark.parametrize("name", ["notes.md", "README.markdown", "results.txt", "results.rst", "NOTES.MD"])
def test_a_stack_in_other_formats_is_not_read_as_body_prose(name):
    text = "\\section{Results}\n" + STACK + "\n"
    assert _rule_03(text, name) == [], name
    assert _rule_03("## Results\n\n" + STACK + "\n", name) == [], name


def test_unnamed_text_without_latex_markup_is_not_body_prose():
    assert _rule_03(STACK) == []
    assert _rule_03(STACK, "") == []


def test_a_sparse_body_is_quiet():
    text = (
        "\\section{Results}\n"
        "Prefetching lowers the miss rate by 8.9 points at full load. "
        "Changing the block size or the associativity moves them by under one point. "
        "Operators that raise either should expect little change. "
        "Production kernels already enable the prefetch path.\n"
    )
    assert _rule_03(text, "main.tex") == []


def test_two_stacked_sentences_in_the_body_are_below_the_run_threshold():
    text = (
        "\\section{Results}\n"
        "Prefetching lowers misses by 8.9 points and 5.2 points. "
        "Tuning moves them by 0.6 and 0.8 points. "
        "Operators should expect little change.\n"
    )
    assert _rule_03(text, "main.tex") == []


def test_a_run_needs_adjacent_sentences_in_the_body():
    text = (
        "\\section{Results}\n"
        "Prefetching lowers misses by 8.9 points and 5.2 points. "
        "Tuning moves them by 0.6 and 0.8 points. "
        "Operators should expect little change. "
        "The block size moves them by 0.3 and 0.2 points. "
        "A second layout agrees at 0.5 and 0.4 points.\n"
    )
    assert _rule_03(text, "main.tex") == []


def test_a_crowded_sentence_in_the_body_is_not_flagged():
    # Six figures in one sentence fired on human body prose in the measurement
    # (7 sentences of 169 files), so the crowded criterion stays in the abstract
    # and the introduction.
    assert _rule_03("\\section{Results}\n" + CROWD + "\n", "main.tex") == []
    assert detectors_mech._R03_BODY_CROWDED is None
    abstract = "\\begin{abstract}\n" + CROWD + "\n\\end{abstract}\n"
    assert len(front_hits(_rule_03(abstract, "main.tex"))) == 1
    intro = "\\section{Introduction}\n" + CROWD + "\n"
    found = _rule_03(intro, "main.tex")
    assert len(front_hits(found)) == 1 and body_crowds(found) == []


def test_the_body_crowded_limit_applies_when_it_is_set(monkeypatch):
    monkeypatch.setattr(detectors_mech, "_R03_BODY_CROWDED", 5)
    found = body_crowds(_rule_03("\\section{Results}\n" + CROWD + "\n", "main.tex"))
    assert len(found) == 1 and "6 precise figures" in found[0].detail
    assert found[0].detail.startswith("one sentence in the body text carries")


def test_abstract_and_introduction_messages_are_unchanged():
    abstract = "\\begin{abstract}\n" + STACK + "\n\\end{abstract}\n"
    one = front_hits(_rule_03(abstract, "main.tex"))[0].detail
    assert one == (
        "3 consecutive sentences in the abstract carry 11 precise figures; "
        "keep the few magnitudes behind the main findings and move the rest to a table"
    )
    intro = "\\section{Introduction}\n" + STACK + "\n"
    two = front_hits(_rule_03(intro, "main.tex"))[0].detail
    assert two.startswith("3 consecutive sentences in the introduction carry 11 precise figures")
    assert "body" not in one and "body" not in two
    body = body_runs(_rule_03("\\section{Results}\n" + STACK, "main.tex"))[0].detail
    assert "abstract" not in body and "introduction" not in body
    assert body.endswith("move the rest to a table or an appendix")


def test_an_abstract_stack_is_one_finding_not_also_a_body_finding():
    text = "\\begin{abstract}\n" + STACK + "\n\\end{abstract}\n\\section{Method}\nWe run it.\n"
    found = _rule_03(text, "main.tex")
    assert len(front_hits(found)) == 1 and body_runs(found) == []
    named = _rule_03(STACK, "00-abstract.tex")
    assert len(front_hits(named)) == 1 and body_runs(named) == []
    named_intro = _rule_03(STACK, "01-introduction.tex")
    assert len(front_hits(named_intro)) == 1 and body_runs(named_intro) == []


def test_a_stack_before_and_after_an_introduction_is_body_prose():
    text = (
        "\\section{Related Work}\n" + STACK + "\n"
        "\\section{Introduction}\nWe study caches.\n"
        "\\section{Results}\n" + STACK + "\n"
    )
    found = body_runs(_rule_03(text, "main.tex"))
    assert [v.line for v in found] == [2, 6]


def test_the_body_stack_in_an_edit_sized_fragment_flags():
    # The guard hands an Edit's new fragment to the detector alone.
    assert len(body_runs(_rule_03(STACK, "main.tex"))) == 1
    assert len(body_runs(_rule_03("\\emph{Sizes.} " + STACK, ""))) == 1
    assert body_runs(_rule_03(STACK, "main.md")) == []


# Exemptions: tables and other displays, code, comments, the appendix, the preamble.


@pytest.mark.parametrize(
    "env",
    [
        "table", "figure", "tabular", "tabulary", "tblr", "equation", "align", "verbatim", "lstlisting",
        "algorithm", "comment",
    ],
)
def test_a_stack_inside_a_display_or_code_environment_is_skipped(env):
    text = "\\section{Results}\n\\begin{" + env + "}\n" + STACK + "\n\\end{" + env + "}\n"
    assert _rule_03(text, "main.tex") == [], env


def test_a_stack_in_a_comment_is_skipped():
    commented = "".join("% " + line + "\n" for line in STACK.split(". "))
    assert _rule_03("\\section{Results}\n" + commented, "main.tex") == []


def test_a_display_between_sentences_does_not_hide_the_stack_around_it():
    text = (
        "\\section{Results}\n"
        "Raising the cache from 2\\% to 100\\% changes the hit rate by 3.7 points and 4.1 points. "
        "Prefetching lowers misses by 8.9 points and 5.2 points.\n"
        "\\begin{equation}\nx = 0.51 + 0.62 + 0.73\n\\end{equation}\n"
        "A second layout gives 0.57 and 0.43 at idle load.\n"
    )
    assert len(body_runs(_rule_03(text, "main.tex"))) == 1


@pytest.mark.parametrize(
    "name",
    ["appendix.tex", "02-Appendix.tex", "supp.tex", "supplement.tex", "supplementary-results.tex", "A_appendices.tex"],
)
def test_appendix_and_supplement_file_names_skip_body_prose(name):
    assert _rule_03("\\section{Details}\n" + STACK + "\n", name) == [], name


def test_text_after_the_appendix_command_is_skipped():
    text = (
        "\\section{Results}\n" + STACK + "\n"
        "\\appendix\n\\section{Details}\n" + STACK + "\n"
    )
    assert [v.line for v in body_runs(_rule_03(text, "main.tex"))] == [2]
    assert _rule_03("\\appendix\n" + STACK + "\n", "main.tex") == []


def test_the_appendices_environment_is_skipped():
    text = (
        "\\section{Results}\n" + STACK + "\n"
        "\\begin{appendices}\n" + STACK + "\n\\end{appendices}\n"
        "\\section{Discussion}\n" + STACK + "\n"
    )
    assert [v.line for v in body_runs(_rule_03(text, "main.tex"))] == [2, 7]
    unclosed = "\\section{Results}\n" + STACK + "\n\\begin{appendices}\n" + STACK + "\n"
    assert [v.line for v in body_runs(_rule_03(unclosed, "main.tex"))] == [2]


def test_the_preamble_and_the_text_after_the_document_are_not_body_prose():
    preamble = "\\documentclass{article}\n" + STACK + "\n\\begin{document}\nWe study caches.\n\\end{document}\n"
    assert _rule_03(preamble, "main.tex") == []
    after = "\\begin{document}\n\\section{Results}\nWe study caches.\n\\end{document}\n" + STACK + "\n"
    assert _rule_03(after, "main.tex") == []
    inside = "\\begin{document}\n\\section{Results}\n" + STACK + "\n\\end{document}\n"
    assert [v.line for v in body_runs(_rule_03(inside, "main.tex"))] == [3]


def test_a_body_stack_is_independent_of_the_appendix_exemption_of_check_a():
    # An interval in the appendix is skipped by check A; check A still reads the
    # body, and a body stack does not hide an interval beside it.
    text = "\\section{Results}\nGain is 0.62 [0.51, 0.83] here. " + STACK + "\n"
    found = _rule_03(text, "main.tex")
    assert len(interval_hits(found)) == 1 and len(body_runs(found)) == 1


def test_body_findings_are_ordered_by_position_with_the_other_checks():
    text = (
        "\\section{Results}\nGain is 0.62 [0.51, 0.83] here.\n\n" + STACK + "\n\n"
        "\\begin{figure}\n\\caption{Hit rate was 41.6, 45.3 and 47.1 on three traces.}\n\\end{figure}\n"
    )
    found = _rule_03(text, "main.tex")
    assert [v.line for v in found] == sorted(v.line for v in found) and len(found) == 3


# ---------- check C: captions ---------------------------------------------------


def fig(caption: str) -> str:
    return "\\begin{figure}\n\\centering\n\\includegraphics{a.pdf}\n" + caption + "\n\\end{figure}\n"


THREE = "Hit rate was 41.6, 45.3 and 47.1 on three traces."


@pytest.mark.parametrize(
    "caption",
    [
        "\\caption{" + THREE + "}",
        "\\caption[Hit rate]{" + THREE + "}",
        "\\caption*{" + THREE + "}",
        "\\captionof{figure}{" + THREE + "}",
        "\\captionof*{table}{" + THREE + "}",
        "\\caption {" + THREE + "}",
        "\\caption\n{" + THREE + "}",
        "\\caption{\\textbf{Hit rate.} " + THREE + " \\label{fig:hit}}",
        "\\caption{Hit rate was 41.6\\%, 45.3\\% and 47\\% on three traces.}",
        "\\caption{Hit rate was $0.416$, $0.453$ and $0.471$ on three traces.}",
    ],
)
def test_a_caption_with_three_precise_figures_flags(caption):
    found = caption_hits(_rule_03(fig(caption), "main.tex"))
    assert len(found) == 1, [v.detail for v in _rule_03(fig(caption), "main.tex")]
    assert found[0].line == 4 if caption.startswith("\\caption") else found[0].line >= 4
    assert "precise figures" in found[0].detail


@pytest.mark.parametrize(
    "caption",
    [
        "\\caption{Hit rate was 41.6 and 45.3 on two traces.}",
        "\\caption{Hit rate on 3 traces of 1200 requests and 45 clients.}",
        "\\caption{Hit rate by trace.}",
        "\\caption{Hit rate was 41.6 and 45.3 on Trace~2 (Section 3.2, Table 4, Figure 5.1).}",
        "\\caption{Hit rate on the traces of \\citet{lee2020.123}, run at 0.9\\textwidth.}",
        "\\caption{Hit rate was 41.6 and 45.3 (95\\% CI).}",
        "\\caption{Hit rate was 41.6 and 45.3, with 95\\% bootstrap intervals.}",
        "\\caption{Hit rate was 41.6 and 45.3 (CI 95\\%).}",
        "\\caption{Hit rate was 41.6 and 45.3 on v0.9.0 of the tool, run 2026-10-16.}",
    ],
)
def test_a_caption_below_the_limits_stays_quiet(caption):
    assert caption_hits(_rule_03(fig(caption), "main.tex")) == [], caption


def test_a_confidence_level_is_metadata_and_not_a_figure_in_a_caption():
    # Two results and a 95% level: two figures, not three.
    assert caption_hits(_rule_03(fig("\\caption{Gain was 4.1 and 5.2 with a 95\\% confidence interval.}"), "main.tex")) == []
    # The same words with a third result flag.
    flagged = fig("\\caption{Gain was 4.1, 5.2 and 6.3 with a 95\\% confidence interval.}")
    assert len(caption_hits(_rule_03(flagged, "main.tex"))) == 1


def test_a_caption_over_one_hundred_words_flags():
    def words(n):
        return " ".join(f"word{chr(97 + i % 26)}" for i in range(n))

    quiet = _rule_03(fig("\\caption{" + words(100) + "}"), "main.tex")
    assert caption_hits(quiet) == []
    found = caption_hits(_rule_03(fig("\\caption{" + words(101) + "}"), "main.tex"))
    assert len(found) == 1 and "101 words" in found[0].detail


def test_caption_words_skip_citations_references_math_and_numbers():
    base = " ".join(f"token{chr(97 + i % 26)}" for i in range(100))
    padding = " \\citep{a,b} \\ref{fig:x} $x_i + y_j$ 12 3 45 \\label{fig:y} 6.5 "
    assert caption_hits(_rule_03(fig("\\caption{" + base + padding + "}"), "main.tex")) == []
    # A command is dropped and the text in its argument is kept.
    bold = "\\textbf{" + " ".join(f"token{chr(97 + i % 26)}" for i in range(101)) + "}"
    assert len(caption_hits(_rule_03(fig("\\caption{" + bold + "}"), "main.tex"))) == 1


def test_a_caption_is_one_finding_even_when_it_breaks_both_limits():
    caption = "\\caption{" + THREE + " " + " ".join(f"word{chr(97 + i % 26)}" for i in range(120)) + "}"
    assert len(caption_hits(_rule_03(fig(caption), "main.tex"))) == 1


def test_each_caption_is_checked_on_its_own_line():
    text = (
        fig("\\caption{" + THREE + "}")
        + "\nText between the figures.\n\n"
        + fig("\\caption{A short caption.}")
        + fig("\\caption{" + THREE + "}")
    )
    assert [v.line for v in caption_hits(_rule_03(text, "main.tex"))] == [4, 17]


def test_a_multi_line_caption_is_reported_at_the_command_line():
    caption = "\\caption{Hit rate\nwas 41.6,\n45.3 and 47.1\non three traces.}"
    found = caption_hits(_rule_03(fig(caption), "main.tex"))
    assert len(found) == 1 and found[0].line == 4 and found[0].column == 1


def test_a_caption_fragment_is_checked_alone():
    # An Edit that rewrites one caption hands the detector that line only.
    assert len(caption_hits(_rule_03("\\caption{" + THREE + "}\n", "main.tex"))) == 1
    assert len(caption_hits(_rule_03("\\emph{Hit rate.} \\caption{" + THREE + "}\n", ""))) == 1
    # A bare caption with no file name has no LaTeX marker the detector knows.
    assert caption_hits(_rule_03("\\caption{" + THREE + "}\n", "")) == []


def test_a_caption_flags_outside_abstract_and_introduction_and_inside_them():
    text = "\\section{Introduction}\n" + fig("\\caption{" + THREE + "}")
    assert len(caption_hits(_rule_03(text, "main.tex"))) == 1
    assert len(caption_hits(_rule_03(fig("\\caption{" + THREE + "}"), "04-results.tex"))) == 1


def test_a_caption_in_an_appendix_or_a_supplement_is_skipped():
    caption = fig("\\caption{" + THREE + "}")
    for name in ("appendix.tex", "supp.tex", "supplement-figures.tex", "02-Appendices.tex"):
        assert caption_hits(_rule_03(caption, name)) == [], name
    after = "\\section{Results}\n" + caption + "\\appendix\n\\section{Details}\n" + caption
    assert [v.line for v in caption_hits(_rule_03(after, "main.tex"))] == [5]
    environment = caption + "\\begin{appendices}\n" + caption + "\\end{appendices}\n"
    assert [v.line for v in caption_hits(_rule_03(environment, "main.tex"))] == [4]


def test_a_caption_in_a_markdown_or_plain_text_file_is_not_read():
    text = fig("\\caption{" + THREE + "}")
    for name in ("notes.md", "notes.markdown", "notes.txt", "notes.rst"):
        assert _rule_03(text, name) == [], name
    # Plain Markdown prose with no LaTeX marker is not read either.
    assert _rule_03("Caption: " + THREE, "") == []


@pytest.mark.parametrize(
    "text",
    [
        "% \\caption{" + THREE + "}\n",
        "\\begin{verbatim}\n\\caption{" + THREE + "}\n\\end{verbatim}\n",
        "\\begin{lstlisting}\n\\caption{" + THREE + "}\n\\end{lstlisting}\n",
        "\\begin{comment}\n\\caption{" + THREE + "}\n\\end{comment}\n",
        "\\verb|\\caption{" + THREE + "}|\n",
        "\\captionsetup{font=small, skip=0.5em, width=0.95\\textwidth, labelsep=0.1em}\n",
        "\\caption{" + THREE + "\n",
        "\\caption\n\n",
        "\\caption[" + THREE + "\n",
        "\\captionof{figure}[" + THREE + "]\n",
        "\\caption}" + THREE + "{\n",
        "\\mycaption{" + THREE + "}\n",
    ],
)
def test_text_that_is_no_caption_is_not_read_as_one(text):
    assert caption_hits(_rule_03("\\begin{document}\n" + text, "main.tex")) == [], text


def test_a_caption_does_not_feed_checks_a_and_b():
    # A caption outside any figure or table environment is still display material.
    stacked = "\\captionof{table}{" + STACK + "}\n"
    found = _rule_03("\\section{Results}\n" + stacked, "main.tex")
    assert body_runs(found) == [] and front_hits(found) == []
    interval = "\\section{Results}\n\\captionof{figure}{Gain is 0.4 (95\\% CI 0.2 to 0.6) at idle load.}\n"
    assert interval_hits(_rule_03(interval, "main.tex")) == []
    inside = fig("\\caption{Gain is 0.4 [0.2, 0.6] at idle load.}")
    assert interval_hits(_rule_03("\\section{Results}\n" + inside, "main.tex")) == []
    # In an abstract region too.
    abstract = "\\begin{abstract}\n\\captionof{table}{" + STACK + "}\n\\end{abstract}\n"
    assert front_hits(_rule_03(abstract, "main.tex")) == []


def test_a_figures_only_file_still_reaches_the_caption_check():
    # No prose at all: every line is a display, yet the caption is read.
    text = "\\begin{figure}\n\\caption{" + THREE + "}\n\\end{figure}\n"
    assert len(caption_hits(_rule_03(text, "figs.tex"))) == 1


def test_caption_message_names_the_pattern_and_where_the_rest_goes():
    figures = caption_hits(_rule_03(fig("\\caption{" + THREE + "}"), "main.tex"))[0].detail
    assert figures == (
        "a caption carries 3 precise figures. A caption names the display, its pattern, and "
        "what the marks mean. Keep decoding values such as error-bar definitions; move "
        "repeated results, setup narration, and caveats to the text or an appendix"
    )
    long = caption_hits(_rule_03(fig("\\caption{" + " ".join(["word"] * 101) + "}"), "main.tex"))[0].detail
    assert long.startswith("a caption runs 101 words. A caption names the display, its pattern")


# Legend and decoding metadata. The numbers that name a line, a threshold or a symbol
# are keys to the display, so the figure count skips them; a result written beside
# them still counts.

LEGENDS = [
    "\\caption{Coverage by model. Lines mark the 25\\%, 50\\% and 75\\% quantiles.}",
    "\\caption{Coverage by model. Significance thresholds are 0.05, 0.01 and 0.001.}",
    "\\caption{Coverage by model. Stars mark significance at 0.05, 0.01, and 0.001.}",
    "\\caption{Stars: * $p<0.05$, ** $p<0.01$, *** $p<0.001$.}",
    "\\caption{Stars: * p < 0.05, ** p < 0.01, *** p < 0.001.}",
    "\\caption{Dashed lines at 0.25, 0.50 and 0.75.}",
    "\\caption{Shaded bands span the 5th and 95th percentiles; quantiles 0.05, 0.50 and 0.95.}",
    "\\caption{Curves for quantile levels 0.1, 0.5 and 0.9.}",
    "\\caption{Significant at $\\alpha = 0.05$, 0.01 and 0.001.}",
    "\\caption{Cells shaded at 0.05, 0.01 and 0.001 significance levels.}",
    "\\caption{Dotted line: random baseline at 0.5; dashed lines at 0.25 and 0.75.}",
    "\\caption{Markers denote the 0.1, 0.5 and 0.9 settings.}",
    "\\caption{Bands show the 10--90\\% and 25--75\\% percentile ranges, with p-values below 0.05 and 0.01.}",
    "\\caption{Solid, dashed, and dotted lines correspond to dropout rates of 0.1, 0.2, and 0.5, respectively.}",
    "\\caption{Shaded bands show the $68\\%$, $95\\%$, and $99.7\\%$ confidence intervals.}",
    "\\caption{Shaded bands show the 68\\%, 95\\%, and 99.7\\% confidence intervals.}",
    "\\caption{Ellipses give confidence levels of 68\\%, 95\\%, and 99.7\\%.}",
    "\\caption{Stars mark p-value thresholds of 0.05, 0.01, and 0.001.}",
    "\\caption{Stars: $p \\le 0.05$, 0.01, and 0.001.}",
    # A level list beside one result: every level is a key, so one figure remains.
    "\\caption{Mean latency is 12.4 ms. Shaded bands show the 68\\%, 95\\%, and 99.7\\% confidence intervals.}",
    "\\caption{Mean latency is 12.4 ms; bands give the 50\\%, 90\\%, and 95\\% CIs.}",
    "\\caption{Accuracy reaches 0.84. Shaded bands show the 68\\%, 95\\%, and 99.7\\% confidence intervals.}",
    "\\caption{Accuracy reaches 0.84 and 0.86. Bands show the 68\\%, 95\\%, and 99.7\\% confidence intervals.}",
    "\\caption{Shaded bands show the 50\\%, 68\\%, 95\\%, and 99.7\\% confidence intervals.}",
    # Wrapped and indented in the source, as captions often are.
    "\\caption{Shaded bands show the 50\\%,\n    68\\%,\n    95\\%,\n    99.7\\% confidence intervals.}",
    "\\caption{Accuracy reaches 0.84 and 0.86.\n    Shaded bands show the 68\\%,\n    95\\%, and 99.7\\% confidence intervals.}",
]


@pytest.mark.parametrize("caption", LEGENDS)
def test_legend_numbers_are_keys_and_not_results_in_a_caption(caption):
    assert caption_hits(_rule_03(fig(caption), "main.tex")) == [], caption


@pytest.mark.parametrize(
    "caption",
    [
        "\\caption{Hit rate was $0.416$, $0.453$ and $0.471$ on three traces.}",
        "\\caption{LRU reaches 41.2 ms (95\\% CI 39.8 to 42.7), LFU 38.9 ms, and prefetching 27.4 ms.}",
        "\\caption{Hit rate was 0.416, 0.453 and 0.471 at the 25th and 75th percentiles.}",
        "\\caption{Hit rate was 41.6, 45.3 and 47.1 (p < 0.05).}",
        "\\caption{A decision threshold of 0.5 gives 41.6, 45.3 and 47.1.}",
        "\\caption{LRU 41.6, LFU 45.3 and ARC 47.1; dashed lines mark the 25\\% and 75\\% quantiles.}",
        "\\caption{Lines show hit rates of 0.416, 0.453 and 0.471 on three traces.}",
        "\\caption{Markers show 41.6, 45.3 and 47.1.}",
        "\\caption{Stars mark p < 0.05. Hit rate was 41.6, 45.3 and 47.1.}",
        # A reported p-value is a result; only an inequality or a threshold word makes it a key.
        "\\caption{The three tests returned p-values of 0.041, 0.023, and 0.012.}",
        "\\caption{The three tests gave p = 0.041, 0.023, and 0.012.}",
        # A style mapped to values needs "respectively" to read as a legend.
        "\\caption{Lines represent accuracies of 0.812, 0.834, and 0.851.}",
        "\\caption{Confidence in the three runs was 0.812, 0.834, and 0.851.}",
        # A confidence level is a percentage; interval endpoints are results.
        "\\caption{Latency was 41.2 ms, with a confidence interval of 39.8 to 42.7.}",
        "\\caption{Accuracy was 81.2\\%, with a confidence interval of 79.4\\% to 83.0\\%.}",
        "\\caption{Accuracy reaches 0.84,\n    0.86, and 0.88.\n    Shaded bands show the 68\\%,\n    95\\%, and 99.7\\% confidence intervals.}",
        "\\caption{Accuracy reaches 0.84, 0.86, and 0.88. Bands show the 68\\% and 95\\% confidence intervals.}",
    ],
)
def test_results_beside_a_legend_phrase_still_flag(caption):
    found = caption_hits(_rule_03(fig(caption), "main.tex"))
    assert len(found) == 1 and "precise figures" in found[0].detail, (caption, [v.detail for v in found])


def test_a_legend_hides_only_its_own_numbers():
    legend = " Lines mark the 25\\%, 50\\% and 75\\% quantiles."
    two = fig("\\caption{Hit rate was 41.6 and 45.3 on two traces." + legend + "}")
    assert caption_hits(_rule_03(two, "main.tex")) == []
    three = fig("\\caption{" + THREE + legend + "}")
    found = caption_hits(_rule_03(three, "main.tex"))
    assert len(found) == 1 and "3 precise figures" in found[0].detail


def test_a_legend_does_not_lift_the_word_limit():
    words = " ".join(f"word{chr(97 + i % 26)}" for i in range(101))
    caption = "\\caption{" + words + " Lines mark the 25\\%, 50\\% and 75\\% quantiles.}"
    found = caption_hits(_rule_03(fig(caption), "main.tex"))
    assert len(found) == 1 and "words" in found[0].detail


def test_the_legend_rule_is_for_captions_only():
    # Three sentences of three figures each are a stack in an abstract, quantile list or not.
    sentence = "Lines mark the 25\\%, 50\\% and 75\\% quantiles. "
    abstract = "\\begin{abstract}\n" + sentence * 3 + "\n\\end{abstract}\n"
    assert len(front_hits(_rule_03(abstract, "main.tex"))) == 1


def test_a_legend_in_a_caption_fragment_is_read_alone():
    assert caption_hits(_rule_03("\\caption{Lines mark the 25\\%, 50\\% and 75\\% quantiles.}\n", "main.tex")) == []
    assert len(caption_hits(_rule_03("\\caption{" + THREE + "}\n", "main.tex"))) == 1


# ---------- check D: excess precision --------------------------------------------

FOUR = "We obtain 0.81234, 0.82345, 0.83456 and 0.84567 on the four splits."


def test_four_long_numbers_in_a_paragraph_flag_once_at_the_first():
    text = "\\section{Results}\n" + FOUR + "\n"
    found = precision_hits(_rule_03(text, "main.tex"))
    assert len(found) == 1
    assert found[0].line == 2 and found[0].column == FOUR.index("0.81234") + 1
    assert "4 numbers written to 4 or more decimal places in one paragraph" in found[0].detail


@pytest.mark.parametrize(
    "name", ["main.tex", "04-results.tex", "00-abstract.tex", "01-introduction.tex", "x.TEX"]
)
def test_excess_precision_is_read_everywhere_outside_the_appendix(name):
    assert len(precision_hits(_rule_03(FOUR, name))) == 1, name


def test_excess_precision_is_read_in_an_abstract_and_an_introduction():
    abstract = "\\begin{abstract}\n" + FOUR + "\n\\end{abstract}\n"
    assert len(precision_hits(_rule_03(abstract, "main.tex"))) == 1
    intro = "\\section{Introduction}\n" + FOUR + "\n"
    assert len(precision_hits(_rule_03(intro, "main.tex"))) == 1


@pytest.mark.parametrize("name", ["notes.md", "README.markdown", "notes.txt", "notes.rst", "NOTES.MD"])
def test_excess_precision_is_latex_only(name):
    assert _rule_03("\\section{Results}\n" + FOUR + "\n", name) == [], name
    assert _rule_03(FOUR, name) == [], name


def test_unnamed_text_is_read_only_when_it_is_latex():
    assert len(precision_hits(_rule_03("\\section{Results}\n" + FOUR + "\n", ""))) == 1
    assert _rule_03(FOUR, "") == []


@pytest.mark.parametrize(
    "text",
    [
        "We obtain 0.81234, 0.82345 and 0.83456 on three splits.",                      # three numbers
        "We obtain 0.812, 0.823, 0.834, 0.845 and 0.856 on the five splits.",           # three places
        "We obtain 0.81, 0.82, 0.83, 0.84 and 0.85 on the five splits.",
        "We obtain 0.81234, 0.82345 and 0.83456 on three splits.\n\nOn a fourth, 0.84567.",  # two paragraphs
        "\\begin{itemize}\n\\item A: 0.81234.\n\\item B: 0.82345.\n\\item C: 0.83456.\n\\item D: 0.84567.\n\\end{itemize}",
        "We obtain 81234, 82345, 83456 and 84567 requests on the four splits.",         # integers
        "We obtain 1.2.3.4567, 1.2.3.4568, 1.2.3.4569 and 1.2.3.4570 as versions.",
        "Releases v0.12345, v0.12346, v0.12347 and v0.12348 shipped.",
        "See arXiv:2310.12345, arXiv:2310.12346, arXiv:2310.12347 and arXiv:2310.12348.",
        "See https://example.org/0.12345 https://example.org/0.12346 https://example.org/0.12347 https://example.org/0.12348.",
        "Cited as \\citep{lee2020.12345} \\citep{lee2020.12346} \\citep{lee2020.12347} \\citep{lee2020.12348}.",
        "Widths of 0.12345\\textwidth, 0.12346\\textwidth, 0.12347\\textwidth and 0.12348\\textwidth.",
        "Version 3.12345 of Python, Section 3.12346, Table 4.12347 and Figure 5.12348.",
    ],
)
def test_text_below_the_limit_or_not_a_result_stays_quiet(text):
    assert precision_hits(_rule_03("\\section{Results}\n" + text + "\n", "main.tex")) == [], text


@pytest.mark.parametrize(
    "env", ["table", "tabular", "tabulary", "tblr", "figure", "equation", "align", "verbatim", "lstlisting", "comment"]
)
def test_long_numbers_inside_a_display_or_code_environment_are_skipped(env):
    text = "\\section{Results}\n\\begin{" + env + "}\n" + FOUR + "\n\\end{" + env + "}\n"
    assert precision_hits(_rule_03(text, "main.tex")) == [], env


def test_long_numbers_in_a_comment_are_skipped():
    commented = "".join("% " + piece + "\n" for piece in FOUR.split(", "))
    assert precision_hits(_rule_03("\\section{Results}\n" + commented, "main.tex")) == []


def test_long_numbers_in_an_appendix_or_supplement_are_skipped():
    for name in ("appendix.tex", "supp.tex", "supplement.tex", "supplementary-tables.tex"):
        assert precision_hits(_rule_03(FOUR, name)) == [], name
    text = "\\section{Results}\n" + FOUR + "\n\n\\appendix\n\\section{Details}\n" + FOUR + "\n"
    assert [v.line for v in precision_hits(_rule_03(text, "main.tex"))] == [2]
    environment = FOUR + "\n\n\\begin{appendices}\n" + FOUR + "\n\\end{appendices}\n\n" + FOUR + "\n"
    assert [v.line for v in precision_hits(_rule_03(environment, "main.tex"))] == [1, 7]


def test_the_preamble_is_not_read_for_excess_precision():
    text = "\\documentclass{article}\n" + FOUR + "\n\\begin{document}\nHello.\n\\end{document}\n"
    assert precision_hits(_rule_03(text, "main.tex")) == []


def test_two_paragraphs_each_with_four_long_numbers_flag_twice():
    text = "\\section{Results}\n" + FOUR + "\n\n" + FOUR.replace("0.8", "0.7") + "\n"
    assert [v.line for v in precision_hits(_rule_03(text, "main.tex"))] == [2, 4]


@pytest.mark.parametrize(
    "first,rest",
    [
        ("-0.81234", "0.82345, 0.83456 and 0.84567"),
        ("+0.81234", "0.82345, 0.83456 and 0.84567"),
        ("\u22120.81234", "0.82345, 0.83456 and 0.84567"),
        ("$-0.81234$", "0.82345, 0.83456 and 0.84567"),
        ("$-$0.81234", "0.82345, 0.83456 and 0.84567"),
        ("$+0.81234$", "0.82345, 0.83456 and 0.84567"),
    ],
)
def test_a_leading_sign_belongs_to_the_number(first, rest):
    # Four numbers whichever way the sign is written, reported at the sign.
    sentence = "The shifts are " + first + ", " + rest + " on the splits."
    found = precision_hits(_rule_03("\\section{Results}\n" + sentence + "\n", "main.tex"))
    assert len(found) == 1, sentence
    assert found[0].column == sentence.index(first) + 1, (sentence, found[0].column)


def test_signed_numbers_and_unsigned_numbers_count_alike():
    signed = "Shifts of -0.1234, +0.2345, \u22120.3456 and $-0.4567$ appeared."
    assert len(precision_hits(_rule_03(signed, "main.tex"))) == 1
    short = "Shifts of -0.1234, +0.2345 and \u22120.3456 appeared."
    assert precision_hits(_rule_03(short, "main.tex")) == []


def test_a_hyphen_inside_a_name_is_not_a_sign_and_the_number_still_counts():
    text = "Layers layer-0.1234 and layer-0.2345 beat run-0.3456 and run-0.4567 on the splits."
    found = precision_hits(_rule_03(text, "main.tex"))
    assert len(found) == 1 and found[0].column == text.index("0.1234") + 1


def test_a_number_at_the_end_of_a_sentence_counts():
    text = "Scores were 0.1234, 0.2345, 0.3456 and 0.4567. Nothing else moved."
    assert len(precision_hits(_rule_03(text, "main.tex"))) == 1


def test_thousands_separators_do_not_hide_a_long_decimal():
    text = "Costs were 1,234.5678, 2,345.6789, 3,456.7890 and 4,567.8901 dollars."
    assert len(precision_hits(_rule_03(text, "main.tex"))) == 1


def test_a_confidence_level_is_not_a_long_number():
    text = "Gains were 0.1234, 0.2345 and 0.3456 (95.0000\\% CI) on the splits."
    assert precision_hits(_rule_03(text, "main.tex")) == []


@pytest.mark.parametrize(
    "number,digits",
    [
        ("0.0143", 3), ("-0.0143", 3), ("$-0.0143$", 3), ("\u22120.0143", 3), ("0.00143", 3), ("0.81234", 5),
        ("0.0001", 1), ("0.00025", 2), ("0.0010", 2), ("0.1000", 4), ("1.0000", 5), (".0000", 0), ("0.0000", 0),
        ("1,234.5678", 8), ("12.3456", 6),
    ],
)
def test_significant_digits_skip_the_leading_zeros(number, digits):
    assert detectors_mech._r03_significant(number) == digits, number


@pytest.mark.parametrize(
    "text",
    [
        "We search learning rates 0.0001, 0.0002, 0.0005 and 0.0008.",
        "We search rates 0.00025, 0.00035, 0.00045 and 0.00055 on the splits.",
        "We search steps 0.0010, 0.0020, 0.0030 and 0.0040 on the splits.",
        "We search rates $0.0001$, $0.0002$, $0.0005$ and $0.0008$ on the splits.",
        "We search rates -0.0001, -0.0002, -0.0005 and -0.0008 on the splits.",
        "We search rates 0.0001, 0.0002, 0.0005, 0.0008, 0.0009 and 0.00012 on the splits.",
        "Shifts of 0.0143, 0.0256 and 0.0371 came with steps 0.0001, 0.0002 and 0.0003.",
    ],
)
def test_leading_fractional_zeros_are_scale_and_not_precision(text):
    # A learning rate of 0.0001 has one significant digit, so a paragraph of them reports no
    # excess precision; the paragraph stays quiet in a results section as well as a method one.
    assert precision_hits(_rule_03("\\section{Results}\n" + text + "\n", "main.tex")) == [], text


@pytest.mark.parametrize(
    "text",
    [
        "We obtain -0.0143, 0.0256, -0.0371 and 0.0482 on the four splits.",
        "We obtain 0.00143, 0.00256, 0.00371 and 0.00482 on the four splits.",
        "We obtain 0.1000, 0.2000, 0.3000 and 0.4000 on the four splits.",
        "We obtain $-0.0143$, $0.0256$, $-0.0371$ and $0.0482$ on the four splits.",
    ],
)
def test_four_places_and_three_significant_digits_count(text):
    found = precision_hits(_rule_03("\\section{Results}\n" + text + "\n", "main.tex"))
    assert len(found) == 1 and "4 numbers written to 4 or more decimal places" in found[0].detail, text


def test_small_numbers_do_not_count_toward_the_four():
    qualifying = "Shifts of 0.0143, 0.0256, 0.0371 and 0.0482 came with steps 0.0001, 0.0002 and 0.0003.\n"
    found = precision_hits(_rule_03("\\section{Results}\n" + qualifying, "main.tex"))
    assert len(found) == 1 and "4 numbers" in found[0].detail
    three = "Shifts of 0.0143, 0.0256 and 0.0371 came with steps 0.0001, 0.0002, 0.0003 and 0.0004.\n"
    assert precision_hits(_rule_03("\\section{Results}\n" + three, "main.tex")) == []


def test_the_significant_digit_limit_follows_the_constant(monkeypatch):
    text = "We search learning rates 0.0001, 0.0002, 0.0005 and 0.0008.\n"
    assert precision_hits(_rule_03("\\section{Results}\n" + text, "main.tex")) == []
    monkeypatch.setattr(detectors_mech, "_R03_DECIMAL_SIGNIFICANT", 1)
    assert len(precision_hits(_rule_03("\\section{Results}\n" + text, "main.tex"))) == 1


def test_a_thousands_group_belongs_to_the_number_and_to_its_significant_digits():
    text = "Costs were 1,000.0001, 2,000.0002, 3,000.0003 and 4,000.0004 dollars."
    found = precision_hits(_rule_03(text, "main.tex"))
    assert len(found) == 1 and found[0].column == text.index("1,000.0001") + 1


def test_excess_precision_in_an_edit_sized_fragment():
    assert len(precision_hits(_rule_03(FOUR, "main.tex"))) == 1
    assert len(precision_hits(_rule_03("\\emph{Splits.} " + FOUR, ""))) == 1


def test_excess_precision_limits_follow_the_constants(monkeypatch):
    text = "We obtain 0.812, 0.823, 0.834 and 0.845 on the four splits.\n"
    assert precision_hits(_rule_03(text, "main.tex")) == []
    monkeypatch.setattr(detectors_mech, "_R03_DECIMAL_PLACES", 3)
    assert len(precision_hits(_rule_03(text, "main.tex"))) == 1
    monkeypatch.setattr(detectors_mech, "_R03_DECIMAL_COUNT", 5)
    assert precision_hits(_rule_03(text, "main.tex")) == []


def test_sentence_unit_counts_per_sentence(monkeypatch):
    monkeypatch.setattr(detectors_mech, "_R03_DECIMAL_UNIT", "sentence")
    monkeypatch.setattr(detectors_mech, "_R03_DECIMAL_COUNT", 2)
    text = (
        "We obtain 0.81234 and 0.82345 on two splits. A third gives 0.83456. "
        "A fourth gives 0.84567.\n"
    )
    found = precision_hits(_rule_03(text, "main.tex"))
    assert len(found) == 1 and "2 numbers" in found[0].detail and "in one sentence" in found[0].detail
    assert found[0].column == text.index("0.81234") + 1


def test_a_run_in_heading_ends_a_paragraph():
    # \paragraph{} runs its body on in the same source line; each heading still
    # starts a new paragraph, so two short ones do not add up to four numbers.
    two = (
        "\\section{Results}\n\\paragraph{Accuracy.} Scores are 0.8123 and 0.8234.\n"
        "\\paragraph{Calibration.} Errors are 0.0143 and 0.0256.\n"
    )
    assert precision_hits(_rule_03(two, "main.tex")) == []
    one = "\\section{Results}\n\\paragraph{Accuracy.} " + FOUR + "\n"
    assert len(precision_hits(_rule_03(one, "main.tex"))) == 1
    joined = "\\section{Results}\nScores are 0.8123 and 0.8234.\nErrors are 0.0143 and 0.0256.\n"
    assert len(precision_hits(_rule_03(joined, "main.tex"))) == 1


def test_the_excess_precision_message_says_what_to_report():
    found = precision_hits(_rule_03(FOUR, "main.tex"))[0].detail
    assert found == (
        "4 numbers written to 4 or more decimal places in one paragraph. Report the precision "
        "the measurement supports, usually two or three significant digits, and keep the full "
        "values in a table or an appendix"
    )


# ---------- method and setup sections: exact settings are not findings -------------------------

# The exact settings of a method (optimizer constants, dropout, splits) are what a
# reader needs to repeat the work. A heading that names a method or a setup exempts the
# body run of check B and check D up to the next heading of the same or a higher level.
# Check A (intervals), check C (captions), the abstract and the introduction are read as
# before.

SETTINGS = (
    "Adam uses beta values 0.9 and 0.999. Dropout is 0.1 and label smoothing is 0.2. "
    "Training and validation use fractions 0.8 and 0.2."
)


def test_exact_settings_in_a_methods_section_are_not_a_body_run():
    assert _rule_03("\\section{Methods}\n" + SETTINGS + "\n", "main.tex") == []
    assert len(body_runs(_rule_03("\\section{Results}\n" + SETTINGS + "\n", "main.tex"))) == 1


@pytest.mark.parametrize(
    "title",
    [
        "Method", "Methods", "Methodology", "Our Approach", "Proposed Method", "Setup", "Experimental Setup",
        "Experimental Settings", "Implementation", "Implementation Details", "Hyperparameters", "Hyper-parameters",
        "Training Details", "Configuration", "Datasets", "Datasets and Metrics", "Set-up", "METHODS",
        "1. Method", "2.1 Experimental Setup", "Evaluation Setup", "Evaluation Protocol",
    ],
)
def test_a_section_that_names_a_method_or_a_setup_is_exempt(title):
    for command in ("section", "section*", "subsection", "subsubsection", "section[Short]"):
        text = "\\" + command + "{" + title + "}\n" + SETTINGS + "\n" + FOUR + "\n"
        assert _rule_03(text, "main.tex") == [], (command, title)


@pytest.mark.parametrize(
    "title",
    [
        "Results", "Experiments", "Evaluation", "Analysis", "Discussion", "Related Work", "Ablation Study", "Conclusion",
        "Setup and Results", "Methods and Results", "Methodology and Analysis", "Settings and Findings",
        "Main Results", "Introduction to Caches",
    ],
)
def test_other_sections_are_read(title):
    text = "\\section{" + title + "}\n" + SETTINGS + "\n"
    assert len(body_runs(_rule_03(text, "main.tex"))) == 1, title



def test_check_d_skips_a_setup_section_and_reads_the_rest():
    text = (
        "\\section{Experimental Setup}\n" + FOUR + "\n\n"
        "\\section{Results}\n" + FOUR + "\n"
    )
    assert [v.line for v in precision_hits(_rule_03(text, "main.tex"))] == [5]


def test_a_setup_section_ends_at_the_next_section():
    text = (
        "\\section{Methods}\n" + STACK + "\n"
        "\\section{Results}\n" + STACK + "\n"
        "\\section{Implementation Details}\n" + STACK + "\n"
        "\\chapter{Discussion}\n" + STACK + "\n"
    )
    assert [v.line for v in body_runs(_rule_03(text, "main.tex"))] == [4, 8]


def test_a_subsection_exempts_until_the_next_subsection_or_section():
    quiet = "Nothing else moved.\n"
    text = (
        "\\section{Experiments}\n" + STACK + "\n" + quiet +
        "\\subsection{Implementation details}\n" + STACK + "\n"
        "\\subsubsection{Optimizer}\n" + STACK + "\n"
        "\\subsection{Main results}\n" + STACK + "\n" + quiet +
        "\\section{Discussion}\n" + STACK + "\n"
    )
    assert [v.line for v in body_runs(_rule_03(text, "main.tex"))] == [2, 9, 12]


def test_a_deeper_heading_stays_inside_the_setup_section():
    text = (
        "\\subsection{Setup}\n" + STACK + "\n"
        "\\subsubsection{Results of a pilot}\n" + STACK + "\n"
        "\\paragraph{Results}\n" + STACK + "\n"
        "\\subsection{Results}\n" + STACK + "\n"
    )
    assert [v.line for v in body_runs(_rule_03(text, "main.tex"))] == [8]


def test_a_paragraph_header_opens_a_setup_span_to_the_next_paragraph_header_or_section():
    text = (
        "\\section{Experiments}\n"
        "\\paragraph{Implementation details.} " + SETTINGS + "\n"
        "\\subparagraph{Optimizer} " + STACK + "\n"
        "\\paragraph{Results.} " + STACK + "\n"
        "\\paragraph{Implementation details} " + STACK + "\n"
        "\\subsection{Analysis}\n" + STACK + "\n"
    )
    assert [v.line for v in body_runs(_rule_03(text, "main.tex"))] == [4, 7]


def test_a_commented_out_heading_opens_no_setup_span():
    text = "% \\section{Methods}\n\\section{Results}\n" + STACK + "\n"
    assert len(body_runs(_rule_03(text, "main.tex"))) == 1
    verbatim = "\\begin{verbatim}\n\\section{Methods}\n\\end{verbatim}\n\\section{Results}\n" + STACK + "\n"
    assert len(body_runs(_rule_03(verbatim, "main.tex"))) == 1


def test_a_setup_section_without_a_later_heading_runs_to_the_end():
    text = "\\section{Results}\n" + STACK + "\n\n\\section{Methods}\n" + STACK + "\n\n" + STACK + "\n"
    assert [v.line for v in body_runs(_rule_03(text, "main.tex"))] == [2]


def test_a_setup_section_leaves_the_other_checks_alone():
    interval = "\\section{Methods}\nGain is 0.62 [0.51, 0.83] here.\n"
    assert len(interval_hits(_rule_03(interval, "main.tex"))) == 1
    caption = "\\section{Methods}\n" + fig("\\caption{" + THREE + "}")
    assert len(caption_hits(_rule_03(caption, "main.tex"))) == 1
    abstract = "\\begin{abstract}\n" + STACK + "\n\\end{abstract}\n\\section{Methods}\n" + SETTINGS + "\n"
    assert len(front_hits(_rule_03(abstract, "main.tex"))) == 1
    intro = "\\section{Introduction}\n\\subsection{Setup}\n" + STACK + "\n"
    assert len(front_hits(_rule_03(intro, "main.tex"))) == 1
    named = _rule_03("\\subsection{Setup}\n" + STACK + "\n", "01-introduction.tex")
    assert len(front_hits(named)) == 1


def test_a_sentence_does_not_straddle_the_edge_of_a_setup_section():
    # The setup text has no full stop before the next heading. The first sentence of the
    # results is still its own sentence, so three results sentences make a run.
    text = (
        "\\section{Methods}\nDropout is 0.1 and label smoothing is 0.2\n"
        "\\section{Results}\nThe gap is 0.41 and 0.52. The next is 0.63 and 0.74. The last is 0.85 and 0.96.\n"
    )
    found = body_runs(_rule_03(text, "main.tex"))
    assert len(found) == 1 and found[0].line == 4


def test_a_fragment_with_no_heading_is_read_as_body_prose():
    # The detector reads the text it is handed; it does not guess the section around an Edit.
    assert len(body_runs(_rule_03(SETTINGS, "main.tex"))) == 1


def test_a_title_the_detector_cannot_read_leaves_the_section_in_scope():
    # A heading with a nested command or a non-ASCII spelling is not matched as a setup title.
    for title in ("M\u00e9thode", "\\textsc{Method}", "Method~\\label{sec:m}"):
        found = body_runs(_rule_03("\\section{" + title + "}\n" + SETTINGS + "\n", "main.tex"))
        assert len(found) == 1, title


# ---------- positions, robustness, performance -------------------------------------


def test_positions_survive_comments_and_crlf():
    text = (
        "% a comment line\r\n\\section{Results}\r\n" + FOUR + "\r\n\r\n"
        "\\begin{figure}\r\n\\caption{" + THREE + "}\r\n\\end{figure}\r\n"
    )
    assert [v.line for v in precision_hits(_rule_03(text, "x.tex"))] == [3]
    assert [v.line for v in caption_hits(_rule_03(text, "x.tex"))] == [6]


ODD_INPUTS = [
    "",
    " ",
    "\n",
    "\\caption",
    "\\caption{",
    "\\caption{{{{{",
    "\\caption}}}}}",
    "\\captionof{",
    "\\captionof{figure}",
    "\\captionof*{figure}{",
    "\\caption[",
    "\\caption[]{}",
    "\\caption{}",
    "\\begin{figure}\\caption{ 0.1 0.2 0.3 0.4 }",
    "\\begin{verbatim}\\caption{0.1 0.2 0.3}",
    "\\begin{document}\\begin{document}\\end{document}\\end{document}0.1234 0.1234 0.1234 0.1234",
    "\\end{document}\\begin{document}",
    "0.1234 0.2345 0.3456 0.4567 0.5678",
    ".0000 .0000 .0000 .0000",
    "-0.1234 +.1234 \u22120.1234 $-$0.1234 $-0.1234$ $+$",
    "$-$ $-$ $-$ $-$ 0.1234 0.1234",
    "\\appendix \\caption{0.1 0.2 0.3} 0.1234 0.1234 0.1234 0.1234",
    "\\begin{appendices}\\caption{0.1 0.2 0.3}",
    "\x00\x01\x02 \\caption{0.1\x00 0.2 0.3}\x00",
    "\\caption{\\href{x}{0.1} \\url{0.2} \\cite{0.3} 0.4 0.5 \\label{0.6}}",
    "\\caption{$ $ $ $ $ 0.1 0.2 0.3 0.4}",
    "\\caption{\\( 0.1 0.2 0.3 0.4 \\) \\(}",
    "\\caption{\\\\ \\\\\\ \\{ \\} \\% 0.1 0.2 0.3}",
    "\\caption{a}\\caption{b}\\caption{" + "w " * 150 + "}",
    "".join(chr(i) for i in range(0, 0x300)),
    "9" * 5000,
    "." * 5000,
    "0." * 5000,
    "{" * 2000 + "}" * 2000,
    "\\caption{" + "{" * 2000 + "0.1 0.2 0.3 0.4" + "}" * 2000 + "}",
]


@pytest.mark.parametrize("text", ODD_INPUTS, ids=[f"odd-{i}" for i in range(len(ODD_INPUTS))])
@pytest.mark.parametrize("path", ["", "main.tex", "appendix.tex", "notes.md"])
def test_never_raises(text, path):
    # The scan itself, not the public wrapper, so a bug cannot hide behind the
    # wrapper's catch-all.
    assert isinstance(detectors_mech._rule_03_scan(text, path), list)
    assert isinstance(_rule_03(text, path), list)


# Built inside a list with short ids: pytest copies a test id into the
# PYTEST_CURRENT_TEST environment variable, and Windows caps one variable at
# 32,767 characters, so a raw 200 KB parameter breaks setup there.
HOSTILE_INPUTS = [
    "\\caption{" * 100_000, "\\caption[" * 50_000, "\\captionof{" * 50_000, "\\caption{a}" * 50_000,
    "\\caption{" + "x " * 100_000 + "}", "\\caption{" + "$" * 200_000 + "}",
    "\\caption{" + "\\a[" * 60_000 + "}", "\\caption{" + "\\href{" * 30_000 + "}",
    "\\caption{" + "\\citep{a} " * 20_000 + "}", "\\caption{" + "0.1 " * 60_000 + "}",
    "\\caption  " * 50_000, "\\caption" + " " * 200_000 + "{x}",
    "\\begin{figure}\\caption{x}" * 20_000, "\\appendix " * 50_000 + "\\caption{x}",
    "\\begin{verbatim}" * 20_000, "\\begin{document}" * 20_000,
    "0.12345 " * 30_000, "0." * 100_000, ".0000" * 40_000, "-0.12345 " * 25_000,
    "$-$0.1234 " * 20_000, "1,234.5678 " * 18_000, "0.1234\n\n" * 30_000,
    "\\begin{abstract}" + "0.1234 0.2345. " * 14_000, "\\section{Results}\n" + "0.12. 0.34. " * 30_000,
    # Legend patterns in a caption: lists that almost match, runs of one keyword.
    "\\caption{" + "quantile 1,1,1,1," * 12_000 + "}", "\\caption{" + "1 - " * 60_000 + "quantile}",
    "\\caption{" + "p < 0.05, " * 20_000 + "}", "\\caption{" + "lines at 0.5, " * 15_000 + "}",
    "\\caption{" + "0.5 and " * 40_000 + "quantiles}", "\\caption{" + "1," * 100_000 + "}",
    "\\caption{" + "0.5, " * 60_000 + "percentile}", "\\caption{" + "stars mark " * 20_000 + "}",
    "\\caption{" + "0.5 " * 50_000 + "significance}", "\\caption{" + "9" * 200_000 + " quantile}",
    # Setup headings, thousands groups.
    "\\section[" * 50_000, "\\paragraph{Method}" * 20_000, "\\subsection{Setup}\n\\section{Results}\n" * 15_000,
    "\\section{" * 100_000, "\\paragraph{" + "x" * 150_000, "\\section{Setup} 0.9 and 0.999. " * 10_000,
    "\\section{Results}\n" + "123," * 50_000, "\\section{Results}\n" + "1,234,567.8901 " * 15_000,
]


@pytest.mark.parametrize("text", HOSTILE_INPUTS, ids=[f"hostile-{i}" for i in range(len(HOSTILE_INPUTS))])
def test_hostile_inputs_are_fast(text):
    for path in ("main.tex", "00-abstract.tex"):
        start = time.perf_counter()
        _rule_03(text, path)
        assert time.perf_counter() - start < 3.0, path


def test_two_hundred_kilobytes_of_latex_is_fast():
    paragraph = (
        "\\begin{figure}\n\\caption{Hit rate was 41.6, 45.3 and 47.1 on three traces, "
        "with Section 3.2 and Table 4 as context.}\n\\end{figure}\n"
        "The build gave 0.62 on the first split and 0.52 on the second, with 0.8123 and 0.8234. "
        "Prefetching lowers the miss rate by 8.9 points at full load. v0.9.0 shipped on 2026-10-16.\n\n"
    )
    text = paragraph * (200_000 // len(paragraph) + 1)
    assert len(text) >= 200_000
    for path in ("main.tex", ""):
        start = time.perf_counter()
        found = _rule_03(text, path)
        assert time.perf_counter() - start < 3.0, path
        assert len(caption_hits(found)) > 100


def test_a_broken_caption_scan_is_swallowed_not_raised(monkeypatch):
    def boom(*_args, **_kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(detectors_mech, "_r03_captions", boom)
    assert _rule_03("\\caption{" + THREE + "}", "main.tex") == []
