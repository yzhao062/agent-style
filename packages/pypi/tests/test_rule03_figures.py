# SPDX-License-Identifier: MIT
"""Tests for the RULE-03 mechanical detector (intervals in prose, stacked figures).

The detector has two checks. A flags a numeric interval written into a
sentence. B flags precise figures stacked in an abstract or introduction.
These tests pin the behaviours the calibration depends on: what must flag,
what must stay quiet, how the abstract/introduction is found, and that no input
makes the detector raise, because the guard treats a raise as a broken package.

Check A also has masks and exemptions pinned here: tables with or without outer
pipes, CommonMark fences, indented code in Markdown, sentences that end inside
emphasis, and appendix prose.

Every text here is synthetic: the sentences are invented for the test, about
caches, networks, compilers, batteries and crop yields, with made-up numbers.
Nothing is copied or paraphrased from a real document. The abstracts the
thresholds were calibrated against are not committed to this repository.
"""

from __future__ import annotations

import ast
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from agent_style.review import detectors_mech
from agent_style.review.detectors_mech import _rule_03, _rule_a


def interval_hits(violations):
    return [v for v in violations if "numeric interval" in v.detail]


def stack_hits(violations):
    return [v for v in violations if "consecutive sentences" in v.detail]


def crowd_hits(violations):
    return [v for v in violations if v.detail.startswith("one sentence")]


# Three consecutive sentences with at least three figures each (5, 3, 3): a stack.
STACKED = (
    "We study eviction policies for web caches. "
    "Raising the cache from 2\\% to 100\\% of memory changes the hit rate by 3.7 points, "
    "from 41.6 to 45.3 on the shared trace. "
    "Prefetching lowers the miss rate by 8.9 points at full load and by 5.2 points "
    "at idle load, against 73.4 for the baseline policy. "
    "A second layout gives 0.57 and 0.43 with a 6\\% floor. "
    "Operators should expect little change."
)

# The same figures with prose between the sentences that carry them.
SPARSE = (
    "We study eviction policies for web caches. "
    "Prefetching lowers the miss rate by 8.9 points at full load. "
    "Changing the block size or the associativity moves them by under one point. "
    "Operators that raise either should expect little change. "
    "Production kernels already enable the prefetch path."
)


# ---------- check A: intervals in prose ---------------------------------------


@pytest.mark.parametrize(
    "sentence",
    [
        "Heating lowers cell capacity by $-0.052$ [$-0.083$, $-0.031$] at full charge.",
        "Doubling the buffer lowers stall time by 0.63 (95\\% interval 0.48 to 0.81).",
        "The gap is 0.36 with a 95% CI 0.6-0.9 over eighteen sensors.",
        "Crop yield was 4.81 [4.52, 5.07] on the held-out plots.",
        "The difference is -0.06 (95\\% CI: -0.12 to 0.03).",
        "Germination reached 71.3\\% (68.2 to 74.9) against 69.8\\%.",
        "The median is 4 (95% CI 3 to 5).",
        "The median is 4 (95% bootstrap interval 3 to 5).",
        "The median is 4 (95% percentile bootstrap interval 3 to 5).",
        "The 95% CI, 0.57 to 0.68, is narrow.",
        "The 95% CI 0.57 and 0.68 is narrow.",
        "The interval between 0.57 and 0.68 is wide.",
        "The interval 0.57 to 0.68 is wide.",
        "The interval: 0.57-0.68 is wide.",
    ],
)
def test_interval_sentence_flags(sentence):
    violations = _rule_03(sentence)
    assert len(interval_hits(violations)) == 1, [v.detail for v in violations]
    assert all(v.rule == "RULE-03" for v in violations)


def test_interval_check_runs_outside_abstract_and_introduction():
    text = "Results.\n\nPrefetching lowers the miss rate by 0.052 [0.031, 0.083] at full load.\n"
    assert len(interval_hits(_rule_03(text, "04-results.tex"))) == 1


def test_one_finding_per_sentence_that_carries_intervals():
    text = "Compression gives 0.31 [0.22, 0.46] and caching gives 0.06 [-0.03, 0.15]."
    found = interval_hits(_rule_03(text))
    assert len(found) == 1
    assert "2 numeric intervals" in found[0].detail


@pytest.mark.parametrize(
    "sentence",
    [
        "Raising the pool size from 1 to 100 changes nothing.",
        "As shown by prior work [1, 2], the effect is small.",
        "Citations [12-15] agree.",
        "The score lies in [0, 1] and is normalised.",
        "Scores are scaled to [0.0, 1.0] before averaging.",
        "We set the damping ratio in $[0.15, 0.65]$ for every run.",
        "The analytic bounds reach $[0.08, 0.62]$ at 40 cycles.",
        "Polling every interval of 1.5 to 4 seconds keeps the load low.",
        "The two compilers scored 58 (0.91 and 0.86) respectively.",
        "Intervals are 90\\% percentile intervals of 4,000 bootstrap resamples.",
        "The build used a 5 to 10 slot window.",
        # A percentage that merely precedes the word "interval" is a result, not a level.
        "Throughput drops by 15% over an interval of 2 to 4 hours.",
        "Error drops by 5% when the retry interval is 1 to 3 seconds.",
        "Memory falls by 30% across an interval of 100 to 200 steps.",
        "Throughput drops by 15% across an interval of 2 to 4 retries.",
        "Latency drops by 15% over an interval of 1.5 to 4.5 hours.",
        # A clause around a bare "interval" is not an interval estimate.
        "In the second interval, 0.57 and 0.68 are the two rates.",
        "In the second interval, 0.57 to 0.68 of the requests fail.",
        "During this interval, 12.4% and 15.8% of requests fail.",
        "During this interval 12.4% and 15.8% of requests fail.",
        # A word that is not a statistical modifier means the percentage is no level.
        "The gain is 4 (95% in each interval 3 to 5).",
        # With an interval keyword the duration filter holds even for an explicit level.
        "The wait is 3 hours (95% confidence interval 2 to 4 hours).",
    ],
)
def test_non_interval_brackets_stay_quiet(sentence):
    assert interval_hits(_rule_03(sentence)) == []


def test_a_percentage_before_the_word_interval_is_still_a_figure():
    # 14.6% would be read as a confidence level (and dropped from the count) if a
    # few arbitrary words could stand between it and the keyword.
    middle = "Accuracy rose by 14.6% in the second interval and by 9.3% overall. "
    text = middle + "Latency fell by 21.6% and 17.8%. Energy fell by 11.2% and 6.7%."
    assert interval_hits(_rule_03(text, "abstract.md")) == []
    found = stack_hits(_rule_03(text, "abstract.md"))
    assert len(found) == 1 and "6 precise figures" in found[0].detail, [v.detail for v in _rule_03(text, "abstract.md")]
    # A real level, with or without a modifier, is still metadata and not a figure.
    level = "Yield rose by 3.2% (95% bootstrap interval 3 to 5). Latency fell by 21.6% and 17.8%. Energy fell by 11.2% and 6.7%."
    assert stack_hits(_rule_03(level, "abstract.md")) == []


@pytest.mark.parametrize("modifier", [
    "confidence", "credible", "prediction", "tolerance", "bootstrap", "bootstrapped", "percentile", "central",
    "posterior", "highest-density", "equal-tailed", "simultaneous", "two-sided", "one-sided", "Wald", "Wilson",
    "asymptotic", "exact", "coverage", "BOOTSTRAP",
])
def test_statistical_modifiers_keep_a_level_explicit(modifier):
    sentence = f"The median is 4 (95% {modifier} interval 3 to 5)."
    assert len(interval_hits(_rule_03(sentence))) == 1, sentence


def test_interval_inside_tabular_is_skipped():
    text = (
        "The table lists the estimates.\n"
        "\\begin{tabular}{lcc}\n"
        "Model & Effect & Interval\\\\\n"
        "A & 0.62 & [0.51, 0.83]\\\\\n"
        "B & 0.52 & 0.4 to 0.6\\\\\n"
        "\\end{tabular}\n"
    )
    assert _rule_03(text) == []


def test_interval_inside_markdown_table_row_is_skipped():
    text = (
        "| Model | Effect | CI |\n"
        "| --- | --- | --- |\n"
        "| A | 0.62 | [0.51, 0.83] |\n"
        "| B | 0.52 | (95% CI 0.4 to 0.6) |\n"
    )
    assert _rule_03(text) == []


def test_interval_inside_code_is_skipped():
    md = "Run `score --ci [0.51, 0.83]` first.\n\n```\nresult: 0.62 [0.51, 0.83]\n```\n"
    assert _rule_03(md, "notes.md") == []


# ---------- check B: stacked figures ------------------------------------------


def test_stacked_abstract_flags_a_run():
    violations = _rule_03(STACKED, "00-abstract.tex")
    runs = stack_hits(violations)
    assert len(runs) == 1, [v.detail for v in violations]
    assert "in the abstract" in runs[0].detail
    assert runs[0].line == 1


def test_sparse_abstract_is_quiet():
    assert _rule_03(SPARSE, "00-abstract.tex") == []


def test_crowded_single_sentence_flags():
    text = (
        "We compare battery chemistries. "
        "Capacity fades from 18.4\\% to 7.3\\% and resistance from 52.6\\% to 31.8\\% "
        "at 85.2\\% charge. "
        "Cells still swell at the edges."
    )
    violations = _rule_03(text, "abstract.md")
    assert len(crowd_hits(violations)) == 1
    assert "5 precise figures" in crowd_hits(violations)[0].detail


def test_four_figures_in_one_sentence_is_below_the_crowded_threshold():
    text = "Capacity fades from 18.4\\% to 7.3\\% at 85.2\\% charge against 90.1\\%."
    assert _rule_03(text, "abstract.md") == []


def test_two_stacked_sentences_are_below_the_run_threshold():
    text = (
        "Prefetching lowers misses by 8.9 points and 5.2 points. "
        "Tuning moves them by 0.6 and 0.8 points. "
        "Operators should expect little change."
    )
    assert _rule_03(text, "00-abstract.tex") == []


def test_results_paragraph_outside_abstract_and_introduction_is_quiet():
    # Only Markdown, plain text and unnamed non-LaTeX text: a LaTeX file reads its
    # body prose too since 0.7.0 (tests/test_rule03_displays.py).
    text = (
        "## Results\n\n"
        + STACKED
        + "\n\n## Discussion\n\nThe gap is 0.15, 0.26, 0.48, 0.59, 0.67, 0.82.\n"
    )
    assert _rule_03(text, "paper.md") == []
    assert _rule_03(STACKED, "notes.md") == []
    assert _rule_03(STACKED, "notes.txt") == []
    assert _rule_03(STACKED) == []


def test_changelog_like_text_is_quiet_even_as_an_abstract():
    text = (
        "Release v0.9.0 (2026-10-16) ships 38 tests and 2,417 fixtures. "
        "It follows 0.4.2 and 0.4.1, and runs on Python 3.9-3.13 with Node 20.11.1. "
        "The matrix is ubuntu x 3.9/3.10/3.11/3.12/3.13 and macos x 3.12/3.13. "
        "See Section 3.2, Tables 4 and 5, Figure 2.1, Appendix B.3, and Eq. 7.1. "
        "Evaluated on Claude Opus 4.5, Gemini 2.5 Pro, GPT-4.1 and Llama-3.3-70B with Qwen2.5-72B. "
        "The job started at 12:30:45.123 and cites arXiv:2310.12345 and doi 10.1145/3331184.3331185. "
        "Logs live at https://example.org/v1.2/run-0.5 and docs/v1.2/guide-0.5.md. "
        "The rule refs are \\cref{sec:3.2} and \\citep{smith2020.5}, with `0.62` in code. "
        "```\nscore = 0.62\nscore = 0.52\nscore = 0.63\n```\n"
    )
    for path in ("CHANGELOG.md", "00-abstract.md", "intro.md", "notes.md"):
        assert _rule_03(text, path) == [], path


def test_table_body_does_not_count_toward_a_stack():
    text = (
        "\\begin{abstract}\n"
        "We study caches.\n"
        "\\begin{tabular}{lcc}\n"
        "A & 0.62 & 0.52 \\\\ B & 0.63 & 0.46 \\\\ C & 0.85 & 0.96 \\\\\n"
        "\\end{tabular}\n"
        "Operators should expect little change.\n"
        "\\end{abstract}\n"
    )
    assert _rule_03(text, "main.tex") == []


def test_markdown_table_in_an_abstract_does_not_count():
    text = (
        "## Abstract\n\n"
        "We study caches.\n\n"
        "| a | b | c |\n| - | - | - |\n| 0.62 | 0.52 | 0.63 |\n| 0.46 | 0.85 | 0.96 |\n\n"
        "Operators should expect little change.\n"
    )
    assert _rule_03(text, "paper.md") == []


def test_layout_lengths_and_references_are_not_figures():
    text = (
        "\\begin{abstract}\n"
        "\\includegraphics[width=0.9\\textwidth]{fig/a.pdf} Wide at 0.45\\linewidth and 1.5cm. "
        "Shown in \\Cref{tab:0.5} and \\eqref{eq:1.2}. "
        "Spacing is \\vspace{-0.5em} then \\hspace{1.25em}. "
        "\\end{abstract}\n"
    )
    assert _rule_03(text, "main.tex") == []


# ---------- region detection --------------------------------------------------


@pytest.mark.parametrize(
    "name",
    ["00-abstract.tex", "ABSTRACT.md", "paper-Abstract-draft.txt", "01-introduction.tex",
     "INTRO.md", "intro-draft.rst", "/tmp/x/sections/01-Introduction.tex"],
)
def test_file_name_makes_the_whole_text_a_region(name):
    assert len(stack_hits(_rule_03(STACKED, name))) == 1, name


@pytest.mark.parametrize("name", ["", "notes.md", "README.md", "results.txt", "results.rst"])
def test_other_file_names_do_not(name):
    assert _rule_03(STACKED, name) == []


def test_region_label_follows_the_file_name():
    assert "in the abstract" in stack_hits(_rule_03(STACKED, "00-abstract.tex"))[0].detail
    assert "in the introduction" in stack_hits(_rule_03(STACKED, "01-introduction.tex"))[0].detail


def test_latex_abstract_environment_is_a_region():
    text = (
        "\\documentclass{article}\n\\begin{document}\n\\begin{abstract}\n"
        + STACKED
        + "\n\\end{abstract}\n\\section{Method}\nWe run it.\n\\end{document}\n"
    )
    found = stack_hits(_rule_03(text, "main.tex"))
    assert len(found) == 1
    assert found[0].line == 4  # the line the abstract body starts on


def test_latex_introduction_section_ends_at_the_next_section():
    inside = "\\section{Introduction}\n" + STACKED + "\n\\section{Method}\nWe run it.\n"
    assert len(stack_hits(_rule_03(inside, "main.tex"))) == 1
    after = "\\section{Introduction}\nWe study caches.\n\\section{Results}\n" + STACKED + "\n"
    found = stack_hits(_rule_03(after, "main.tex"))
    # The stack after the introduction is body prose, reported as such.
    assert len(found) == 1 and "in the body text" in found[0].detail and found[0].line == 4
    assert [v for v in _rule_03(after, "main.tex") if "introduction" in v.detail] == []
    starred = "\\section*{Introduction}\n" + STACKED + "\n"
    assert len(stack_hits(_rule_03(starred, "main.tex"))) == 1


def test_commented_out_section_heading_does_not_open_a_region():
    text = "% \\section{Introduction}\n" + STACKED + "\n"
    found = stack_hits(_rule_03(text, "main.tex"))
    assert len(found) == 1 and "in the body text" in found[0].detail
    assert [v for v in _rule_03(text, "main.tex") if "introduction" in v.detail] == []


def test_markdown_heading_region_ends_at_a_heading_of_the_same_or_higher_level():
    inside = "# Paper\n\n## Abstract\n\n" + STACKED + "\n\n### Detail\n\nMore text.\n\n## Method\n\nWe run it.\n"
    found = stack_hits(_rule_03(inside, "paper.md"))
    assert len(found) == 1
    assert found[0].line == 5

    after = "## Abstract\n\nWe study caches.\n\n## Method\n\n" + STACKED + "\n"
    assert _rule_03(after, "paper.md") == []

    # A deeper heading does not end the region.
    deeper = "## Introduction\n\nWe study caches.\n\n### Setup\n\n" + STACKED + "\n"
    assert len(stack_hits(_rule_03(deeper, "paper.md"))) == 1

    # Numbered headings count, and so does a heading inside no fence.
    numbered = "## 1. Introduction\n\n" + STACKED + "\n"
    assert len(stack_hits(_rule_03(numbered, "paper.md"))) == 1
    fenced = "```\n## Abstract\n```\n\n" + STACKED + "\n"
    assert _rule_03(fenced, "paper.md") == []


def test_a_stack_is_not_built_across_two_regions():
    text = (
        "## Abstract\n\nPrefetching lowers misses by 8.9 and 5.2 points.\n"
        "Tuning moves them by 0.6 and 0.8 points.\n\n"
        "## Method\n\nThe step size is 0.5 and 0.25 points.\n"
    )
    assert _rule_03(text, "paper.md") == []


def test_run_needs_adjacent_sentences():
    text = (
        "Prefetching lowers misses by 8.9 and 5.2 points. "
        "Tuning moves them by 0.6 and 0.8 points. "
        "Operators should expect little change. "
        "The block size moves them by 0.3 and 0.2 points. "
        "A second layout agrees at 0.5 and 0.4 points."
    )
    assert _rule_03(text, "00-abstract.tex") == []


# ---------- masking: tables without outer pipes, fences, indented code ---------

# A prose sentence that carries one interval; each test below asks whether it is
# reached, so the line it lands on tells where a mask ended.
IV = "Gain is 0.62 [0.51, 0.83] here."
TABLE_NO_PIPES = (
    "Metric | Gain | CI\n"
    "--- | --- | ---\n"
    "Latency | 0.62 | 95% CI 0.51 to 0.83\n"
)


def interval_lines(text, path="notes.md"):
    return [v.line for v in interval_hits(_rule_03(text, path))]


@pytest.mark.parametrize("path", ["", "notes.md", "results.txt"])
def test_markdown_table_without_outer_pipes_is_skipped(path):
    assert _rule_03(TABLE_NO_PIPES, path) == []
    longer = TABLE_NO_PIPES + "Energy | 0.12 | [0.04, 0.2]\n"
    assert _rule_03(longer, path) == []
    aligned = "Metric | Gain | CI\n:--- | :---: | ---:\nLatency | 0.62 | 95% CI 0.51 to 0.83\n"
    assert _rule_03(aligned, path) == []


def test_table_with_outer_pipes_also_masks_body_rows_that_lack_them():
    assert _rule_03("| a | b |\n|---|---|\nx | 0.62 [0.51, 0.83]\n") == []
    assert _rule_03("a | b |\n--|--\nx | 0.62 [0.51, 0.83]\n") == []


def test_table_ends_at_a_blank_line_or_at_a_line_without_a_pipe():
    assert interval_lines(TABLE_NO_PIPES + "\n" + IV + "\n") == [5]
    assert interval_lines(TABLE_NO_PIPES + IV + "\n") == [4]


@pytest.mark.parametrize(
    "text",
    [
        "Metric | Gain | CI\nLatency | 0.62 | 95% CI 0.51 to 0.83\n",             # no delimiter row
        "Metric | Gain | CI\n--- | ---\nLatency | 0.62 | 95% CI 0.51 to 0.83\n",  # cell counts differ
        "Metric | Gain | CI\n---\nLatency | 0.62 | 95% CI 0.51 to 0.83\n",         # a rule has no pipe
        "Metric | Gain | CI\n--- | x | ---\nLatency | 0.62 | 95% CI 0.51 to 0.83\n",  # not a delimiter cell
    ],
)
def test_pipes_alone_do_not_make_a_table(text):
    assert len(interval_hits(_rule_03(text, "notes.md"))) == 1


def test_table_without_outer_pipes_in_an_abstract_does_not_count():
    text = (
        "## Abstract\n\nWe study caches.\n\n"
        "a | b | c\n- | - | -\n0.62 | 0.52 | 0.63\n0.46 | 0.85 | 0.96\n\n"
        "Operators should expect little change.\n"
    )
    assert _rule_03(text, "paper.md") == []


def test_longer_fence_holds_a_shorter_one():
    text = "````\n```\nresult: 0.62 [0.51, 0.83]\n```\nalso 0.5 [0.4, 0.6]\n````\n\n" + IV + "\n"
    assert interval_lines(text) == [8]


def test_tilde_fence_is_not_closed_by_backticks():
    text = "~~~\n```\nx 0.62 [0.51, 0.83]\n```\nmore 0.5 [0.4, 0.6]\n~~~\n\n" + IV + "\n"
    assert interval_lines(text) == [8]
    # A longer tilde run does close a tilde fence.
    assert interval_lines("~~~\nx 0.62 [0.51, 0.83]\n~~~~\n\n" + IV + "\n") == [5]


def test_fence_closes_on_a_run_at_least_as_long_and_without_an_info_string():
    assert interval_lines("```\nresult: 0.62 [0.51, 0.83]\n`````\n\n" + IV + "\n") == [5]
    assert interval_lines("```\nx\n```python\nresult: 0.62 [0.51, 0.83]\n```\n\n" + IV + "\n") == [7]
    # A shorter run does not close, so the fence runs to the end of the text.
    assert _rule_03("````\nresult: 0.62 [0.51, 0.83]\n```\nmore 0.5 [0.4, 0.6]\n", "notes.md") == []


def test_backtick_run_with_a_backtick_in_its_info_string_is_not_a_fence():
    text = "```inline``` and 0.62 [0.51, 0.83] here.\n\nMore prose.\n"
    assert interval_lines(text) == [1]


@pytest.mark.parametrize("path", ["notes.md", "README.markdown", "DOC.MD", ""])
def test_indented_code_block_is_masked_in_markdown(path):
    spaced = "Intro text.\n\n    result: 0.62 [0.51, 0.83]\n    other: 0.5 [0.4, 0.6]\n\nProse follows.\n"
    assert _rule_03(spaced, path) == []
    tabbed = "Intro text.\n\n\tresult: 0.62 [0.51, 0.83]\n\nProse follows.\n"
    assert _rule_03(tabbed, path) == []
    # The prose after the block is still read.
    assert interval_lines(spaced + "\n" + IV + "\n", path) == [8]


@pytest.mark.parametrize("path", ["notes.txt", "main.tex", "results.rst", "README"])
def test_indented_text_is_prose_outside_markdown(path):
    assert interval_lines("Intro text.\n\n    result: 0.62 [0.51, 0.83]\n\nProse follows.\n", path) == [3]


def test_indented_text_with_latex_markers_and_no_file_name_is_prose():
    assert interval_lines("\\section{Results}\n\n    " + IV + "\n", "") == [3]
    assert interval_lines("\\begin{document}\n\n    " + IV + "\n", "") == [3]


@pytest.mark.parametrize(
    "text",
    [
        "- Item one.\n\n    " + IV + "\n",                      # list continuation paragraph
        "1. Step one.\n\n    " + IV + "\n",
        "- Item\ncontinues here.\n\n    " + IV + "\n",           # lazy continuation keeps the list open
        "* Outer\n  - Inner\n\n      " + IV + "\n",              # nested item, two columns past its content
        "Gain is\n    0.62 [0.51, 0.83] here.\n",                # paragraph continuation
    ],
)
def test_list_and_paragraph_continuation_stay_prose(text):
    assert len(interval_hits(_rule_03(text, "notes.md"))) == 1, text


def test_indented_block_after_a_closed_list_is_code():
    assert _rule_03("- Item.\n\nPlain paragraph.\n\n    result: 0.62 [0.51, 0.83]\n", "notes.md") == []
    assert _rule_03("- Item.\n## Next\n\n    result: 0.62 [0.51, 0.83]\n", "notes.md") == []


# CommonMark 0.31.2: an indented code block may begin the document or follow a
# heading, an item's code is indented four columns past its content column, and a
# fence is indented at most three spaces.

CODE = "result: 0.62 [0.51, 0.83]"


@pytest.mark.parametrize("path", ["notes.md", "README.markdown", ""])
def test_indented_code_at_the_start_of_the_document_is_masked(path):
    assert _rule_03("    " + CODE + "\n", path) == []
    assert _rule_03("\t" + CODE + "\n", path) == []
    assert interval_lines("    " + CODE + "\n\n" + IV + "\n", path) == [3]
    # A paragraph that starts the document keeps its indented continuation as prose.
    assert interval_lines("Gain is\n    0.62 [0.51, 0.83] here.\n", path) == [2]


def test_indented_code_at_the_start_of_the_document_stays_prose_outside_markdown():
    assert interval_lines("    " + IV + "\n", "notes.txt") == [1]
    assert interval_lines("    " + IV + "\n", "main.tex") == [1]


@pytest.mark.parametrize("gap", ["", "\n"])
def test_indented_code_right_after_a_heading_is_masked(gap):
    assert _rule_03("## Results\n" + gap + "    " + CODE + "\n", "notes.md") == []
    assert _rule_03("# Results\n" + gap + "\t" + CODE + "\n", "notes.md") == []
    assert interval_lines("## Results\n" + gap + "    " + CODE + "\n\n" + IV + "\n") == [4 + len(gap)]


def test_indented_line_after_a_paragraph_is_not_code_even_with_a_heading_earlier():
    assert interval_lines("## Results\nGain is\n    0.62 [0.51, 0.83] here.\n") == [3]


@pytest.mark.parametrize(
    "text",
    [
        "- Example:\n\n      " + CODE + "\n",                       # content column 2, indent 6
        "- Example:\n\n\t\t" + CODE + "\n",                        # tabs: columns 8
        "* Example:\n\n      " + CODE + "\n",
        "+ Example:\n\n      " + CODE + "\n",
        "1. Step one:\n\n       " + CODE + "\n",                   # content column 3, indent 7
        "10. Step ten:\n\n        " + CODE + "\n",                 # content column 4, indent 8
        "-   Wide marker gap.\n\n        " + CODE + "\n",          # content column 4, indent 8
        "* Outer\n  - Inner\n\n        " + CODE + "\n",           # inner content column 4, indent 8
        "- Item.\n\n      " + CODE + "\n      other 0.5 [0.4, 0.6]\n",
        "- Item\ncontinues here.\n\n      " + CODE + "\n",        # lazy continuation keeps the item open
    ],
)
def test_indented_code_beneath_a_list_item_is_masked(text):
    assert _rule_03(text, "notes.md") == [], text
    assert interval_lines(text + "\n" + IV + "\n") == [text.count("\n") + 2], text


@pytest.mark.parametrize(
    "text",
    [
        "- Example:\n\n  " + IV + "\n",                       # at the content column
        "- Example:\n\n     " + IV + "\n",                    # one column short of code
        "1. Step one:\n\n      " + IV + "\n",                 # content column 3, indent 6
        "10. Step ten:\n\n       " + IV + "\n",              # content column 4, indent 7
        "* Outer\n  - Inner\n\n      " + IV + "\n",          # inner content column 4, indent 6
    ],
)
def test_list_continuation_paragraph_below_the_code_threshold_is_prose(text):
    assert len(interval_hits(_rule_03(text, "notes.md"))) == 1, text


def test_list_item_ends_when_a_line_is_indented_less_than_its_content_column():
    # One space is less than the content column of two, so the item is closed and
    # the line after the blank is a paragraph of the document, then code follows it.
    assert _rule_03("- Item.\n\n Para.\n\n    " + CODE + "\n", "notes.md") == []
    # Indented to the content column, the paragraph stays in the item and four
    # further columns are code, while two are prose.
    assert _rule_03("- Item.\n\n  Para.\n\n      " + CODE + "\n", "notes.md") == []
    assert len(interval_hits(_rule_03("- Item.\n\n  Para.\n\n    " + IV + "\n", "notes.md"))) == 1


def test_list_item_code_threshold_follows_the_innermost_open_item():
    text = "* Outer\n\n      " + CODE + "\n\n  * Inner\n\n      " + IV + "\n"
    # Under the outer item (content column 2) six spaces are code; under the inner
    # item (content column 4) the same six spaces are a continuation paragraph.
    assert interval_lines(text) == [7]


def test_deep_nesting_with_many_lazy_lines_is_scanned_in_linear_time():
    nest = "".join(" " * (2 * i) + "- item\n" for i in range(400))
    text = nest + "lazy\n" * 60000
    start = time.perf_counter()
    _rule_03(text, "notes.md")
    assert time.perf_counter() - start < 3.0


def test_a_fence_indented_four_spaces_does_not_close_a_block():
    text = "```\n    ```\n" + CODE + "\n```\n\n" + IV + "\n"
    # Line 2 is code inside the block, so line 3 stays masked and line 6 is read.
    assert interval_lines(text) == [6]
    assert interval_lines(text, "notes.txt") == [6]
    tilde = "~~~\n    ~~~\n" + CODE + "\n~~~\n\n" + IV + "\n"
    assert interval_lines(tilde) == [6]


def test_a_fence_may_be_indented_up_to_three_spaces():
    for indent in ("", " ", "  ", "   "):
        text = indent + "```\n" + CODE + "\n" + indent + "```\n\n" + IV + "\n"
        assert interval_lines(text) == [5], indent
    # Three spaces still close a block that opened flush left.
    assert interval_lines("```\n" + CODE + "\n   ```\n\n" + IV + "\n") == [5]


def test_a_fence_indented_four_spaces_does_not_open_a_block():
    # After a blank line it is an indented code block; the block is masked either way.
    assert _rule_03("Intro.\n\n    ```\n    " + CODE + "\n    ```\n", "notes.md") == []
    assert interval_lines("Intro.\n\n    ```\n    " + CODE + "\n    ```\n\n" + IV + "\n") == [7]
    # Directly after a paragraph the line is text, not a fence: nothing is masked.
    assert interval_lines("Intro.\n    ```\n" + IV + "\n") == [3]
    assert interval_lines("    ```\n" + IV + "\n", "notes.txt") == [2]


def test_fence_indentation_inside_a_list_item_counts_from_the_content_column():
    inner = "- Item.\n\n  ```\n  " + CODE + "\n  ```\n\n" + IV + "\n"
    assert interval_lines(inner) == [7]
    deeper = "- Item.\n\n  ```\n  " + CODE + "\n      ```\n  more 0.5 [0.4, 0.6]\n  ```\n\n" + IV + "\n"
    # A closer six columns in is four past the content column: still code.
    assert interval_lines(deeper) == [9]


def test_a_fence_inside_a_list_item_ends_with_the_item():
    text = "- Item.\n\n  ```\n  " + CODE + "\n\n" + IV + "\n"
    assert interval_lines(text) == [6]
    # At the top level an unclosed fence still runs to the end of the text.
    assert _rule_03("```\n" + CODE + "\n\n" + IV + "\n", "notes.md") == []


def test_a_list_item_that_cannot_interrupt_a_paragraph_opens_no_list():
    # `10.` after a paragraph line is text, so four spaces after a blank line are
    # top-level code; `1.` and a bullet do open an item, and the same four spaces
    # are then a continuation paragraph.
    assert _rule_03("Notes.\n10. Step ten.\n\n    " + CODE + "\n", "notes.md") == []
    assert len(interval_hits(_rule_03("Notes.\n1. Step one.\n\n    " + IV + "\n", "notes.md"))) == 1
    assert len(interval_hits(_rule_03("Notes.\n- Step.\n\n    " + IV + "\n", "notes.md"))) == 1
    # A text-less marker is not an item either.
    assert _rule_03("Notes.\n-\n\n    " + CODE + "\n", "notes.md") == []
    # A sibling of an open list may carry any number.
    assert len(interval_hits(_rule_03("1. One.\n10. Ten.\n\n    " + IV + "\n", "notes.md"))) == 1
    assert _rule_03("1. One.\n10. Ten.\n\n        " + CODE + "\n", "notes.md") == []


def test_a_list_item_whose_first_content_is_indented_code_is_masked():
    assert _rule_03("-     " + CODE + "\n", "notes.md") == []
    # The next flush-left line follows code, not a paragraph, so it ends the item.
    assert interval_lines("-     " + CODE + "\n" + IV + "\n") == [2]
    assert interval_lines("-     " + CODE + "\n" + "\n      more 0.5 [0.4, 0.6]\n\n" + IV + "\n") == [5]


# A fence may start on the line of a list item marker or after a blockquote marker.
# The fence lines are masked; the prose of the list or the quote stays visible.

CONTAINER_FENCES = [
    # (opening line, prefix of the lines inside the container, closing fence)
    ("- ```text", "  ", "```"),
    ("* ```", "  ", "```"),
    ("+ ~~~", "  ", "~~~"),
    ("1. ```", "   ", "```"),            # content column 3
    ("10) ```", "    ", "```"),           # content column 4
    ("-   ```", "    ", "```"),           # content column 4
    ("> ```", "> ", "```"),
    ("> ```text", "> ", "```"),
    (">```", ">", "```"),
    ("> > ```", "> > ", "```"),
    (">> ```", ">> ", "```"),
    ("   > ```", "   > ", "```"),        # a quote may be indented three spaces
    ("- - ```", "    ", "```"),           # nested items
    ("- > ```", "  > ", "```"),          # a quote inside an item
    ("> - ```", ">   ", "```"),          # an item inside a quote
    ("1. > ```", "   > ", "```"),
]


def test_a_fence_on_a_list_item_or_blockquote_line_is_masked():
    listed = "- ```text\n  result: 0.62 [0.51, 0.83]\n  ```\n\n  Gain is 0.62 [0.51, 0.83] here.\n"
    assert interval_lines(listed) == [5]
    quoted = "> ```text\n> result: 0.62 [0.51, 0.83]\n> ```\n\nGain is 0.62 [0.51, 0.83] here.\n"
    assert interval_lines(quoted) == [5]


@pytest.mark.parametrize("first,prefix,closer", CONTAINER_FENCES)
def test_container_fence_is_masked_and_the_prose_after_it_is_read(first, prefix, closer):
    body = [first, prefix + CODE, prefix + closer]
    assert _rule_03("\n".join(body) + "\n", "notes.md") == [], first
    # Prose in the same container right after the fence, and flush left after a blank line.
    assert interval_lines("\n".join(body + [prefix + IV]) + "\n") == [4], first
    assert interval_lines("\n".join(body + ["", IV]) + "\n") == [5], first


def test_container_prose_stays_visible_around_a_fence():
    listed = "- " + IV + "\n- ```\n  " + CODE + "\n  ```\n- " + IV + "\n"
    assert interval_lines(listed) == [1, 5]
    quoted = "> " + IV + "\n> ```\n> " + CODE + "\n> ```\n> " + IV + "\n"
    assert interval_lines(quoted) == [1, 5]
    ordered = "1. " + IV + "\n2. ```\n   " + CODE + "\n   ```\n3. " + IV + "\n"
    assert interval_lines(ordered) == [1, 5]


def test_a_fence_in_a_blockquote_ends_at_a_line_without_a_marker():
    # The blank line ends the quote, so the prose after it is read.
    assert interval_lines("> ```\n> " + CODE + "\n\n" + IV + "\n") == [4]
    # A flush-left line ends it too, with no blank line between.
    assert interval_lines("> ```\n> " + CODE + "\n" + IV + "\n") == [3]
    # A nested quote ends when one marker is missing.
    assert interval_lines("> > ```\n> > " + CODE + "\n> " + IV + "\n") == [3]


def test_a_fence_on_a_list_item_line_ends_with_the_item():
    assert interval_lines("- ```\n  " + CODE + "\n\n" + IV + "\n") == [4]
    assert interval_lines("- ```\n  " + CODE + "\n" + IV + "\n") == [3]
    # A blank line alone does not end the item, so the fence goes on.
    assert _rule_03("- ```\n  " + CODE + "\n\n  more 0.5 [0.4, 0.6]\n", "notes.md") == []
    # A quote inside the item ends the fence when its marker is missing.
    assert interval_lines("- > ```\n  > " + CODE + "\n  " + IV + "\n") == [3]


def test_a_container_fence_closes_only_at_its_content_position():
    # Four columns past the content column is code, not a closing fence.
    listed = "- ```\n  " + CODE + "\n      ```\n  more 0.5 [0.4, 0.6]\n  ```\n\n  " + IV + "\n"
    assert interval_lines(listed) == [7]
    quoted = "> ```\n> " + CODE + "\n>     ```\n> more 0.5 [0.4, 0.6]\n> ```\n\n" + IV + "\n"
    assert interval_lines(quoted) == [7]
    # Up to three columns past it still closes.
    assert interval_lines("> ```\n> " + CODE + "\n>    ```\n\n" + IV + "\n") == [5]
    assert interval_lines("- ```\n  " + CODE + "\n     ```\n\n  " + IV + "\n") == [5]
    # A longer fence holds a shorter one, and a tilde fence is not closed by backticks.
    assert interval_lines("> ````\n> ```\n> " + CODE + "\n> ````\n\n" + IV + "\n") == [6]
    assert interval_lines("- ~~~\n  ```\n  " + CODE + "\n  ~~~\n\n  " + IV + "\n") == [6]


def test_a_blockquote_line_ends_the_list_item_it_is_not_indented_into():
    assert interval_lines("- Item.\n> ```\n> " + CODE + "\n> ```\n\n" + IV + "\n") == [6]
    # Indented to the content column, the quote belongs to the item and stays inside it.
    assert interval_lines("- Item.\n  > ```\n  > " + CODE + "\n  > ```\n  " + IV + "\n") == [5]


@pytest.mark.parametrize(
    "text",
    [
        "- ```inline``` and 0.62 [0.51, 0.83] here.\n",          # a backtick in the info string
        "> ```inline``` and 0.62 [0.51, 0.83] here.\n",
        "-```\n" + IV + "\n",                                     # no space after the marker: not an item
        "- Text\n  ```inline``` " + IV + "\n",
        "- " + IV + "\n",                                         # a marker line with no fence
        "> " + IV + "\n",
    ],
)
def test_a_marker_line_that_opens_no_fence_masks_nothing(text):
    assert len(interval_hits(_rule_03(text, "notes.md"))) == 1, text


def test_a_container_fence_needs_markdown_input():
    # Outside Markdown a marker line is text, as everywhere else in this mask.
    assert interval_lines("- ```\n  " + IV + "\n", "notes.txt") == [2]


# A setext underline or a thematic break ends the paragraph, so an indented line
# after it is code, as it is after a heading (CommonMark example 115).


@pytest.mark.parametrize("underline", ["-------", "=======", "---", "===", "-", "=", "   -----", "---   ", "-- "])
def test_a_setext_underline_ends_the_paragraph(underline):
    assert _rule_03("Example\n" + underline + "\n    " + CODE + "\n", "notes.md") == [], underline
    text = "Example\n" + underline + "\n    " + CODE + "\n\n" + IV + "\n"
    assert interval_lines(text) == [5], underline
    assert interval_lines("Example\n-------\n    " + CODE + "\n\n" + IV + "\n", "") == [5]


def test_a_setext_underline_below_a_longer_paragraph_ends_it():
    text = "Gain rose\nacross trials\n---\n    " + CODE + "\n\n" + IV + "\n"
    assert interval_lines(text) == [6]


@pytest.mark.parametrize(
    "rule",
    ["---", "***", "___", "* * *", "- - -", "_ _ _", "----------", " ---", "   ***", "-  -  -", "--- ---"],
)
def test_a_thematic_break_ends_the_paragraph(rule):
    after_blank = "Before.\n\n" + rule + "\n    " + CODE + "\n\n" + IV + "\n"
    assert interval_lines(after_blank) == [6], rule
    after_text = "Before.\n" + rule + "\n    " + CODE + "\n\n" + IV + "\n"
    assert interval_lines(after_text) == [5], rule


def test_a_spaced_rule_is_a_thematic_break_not_a_list_item():
    # `- - -` is not an item, so the line below sits four columns past the document.
    assert interval_lines("- - -\n    " + CODE + "\n\n" + IV + "\n") == [4]
    assert interval_lines("* * *\n    " + CODE + "\n\n" + IV + "\n") == [4]


@pytest.mark.parametrize(
    "text",
    [
        "Example\n    -------\n    " + IV + "\n",       # four spaces: continuation, not an underline
        "Example\n----- x\n    " + IV + "\n",           # text after the dashes
        "Example\n== ==\n    " + IV + "\n",              # a space inside an `=` underline
        "Example\n--x\n    " + IV + "\n",
        "Gain is\n    0.62 [0.51, 0.83] here.\n",        # plain paragraph continuation
        "Gain is\n  0.62 [0.51, 0.83] here.\n",
        "- Item\n===\n    " + IV + "\n",                  # `===` is a lazy continuation of the item
    ],
)
def test_lines_that_are_no_underline_or_break_leave_the_paragraph_open(text):
    assert len(interval_hits(_rule_03(text, "notes.md"))) == 1, text


def test_a_break_or_underline_closes_the_list_item_it_is_not_indented_into():
    assert interval_lines("- Item\n---\n    " + CODE + "\n\n" + IV + "\n") == [5]
    # Indented to the content column, an underline stays inside the item and ends its paragraph.
    assert interval_lines("- Item\n  ---\n      " + CODE + "\n\n  " + IV + "\n") == [5]


def test_an_underline_does_not_end_a_blockquote_or_html_paragraph():
    # A paragraph that holds a quote or an HTML line is not underlined by `-`.
    assert interval_lines("<!-- note -->\n-\n    " + IV + "\n") == [3]
    assert interval_lines("> Quote.\n-\n    " + IV + "\n") == [3]
    # A thematic break ends a quote's paragraph, as it ends the quote.
    assert interval_lines("> Quote.\n---\n    " + CODE + "\n\n" + IV + "\n") == [5]


# ---------- sentence boundaries inside emphasis -----------------------------------

BOLD_THREE = (
    "**Soil moisture rises by 11.3% and 13.8%.** **Yield rises by 22.3% and 26.5%.** "
    "**Cost falls by 2.5%.**"
)


def test_sentences_ending_inside_emphasis_are_split():
    # 2 + 2 + 1 figures: no run of three, and no single crowded sentence.
    assert _rule_03(BOLD_THREE, "abstract.md") == []
    stacked = BOLD_THREE.replace("falls by 2.5%", "falls by 2.5% and 3.5%")
    found = _rule_03(stacked, "abstract.md")
    assert len(stack_hits(found)) == 1 and crowd_hits(found) == [], [v.detail for v in found]
    assert "3 consecutive sentences" in stack_hits(found)[0].detail


@pytest.mark.parametrize("wrap", ["**{}**", "__{}__", "*{}*", "_{}_", "(**{}**)", "**{}**)", "\u201c**{}**\u201d"])
def test_every_closing_marker_ends_a_sentence(wrap):
    sentences = [
        "Soil moisture rises by 11.3% and 13.8%.",
        "Yield rises by 22.3% and 26.5%.",
        "Cost falls by 2.5%.",
    ]
    text = " ".join(wrap.format(s) for s in sentences)
    assert _rule_03(text, "abstract.md") == [], wrap


def test_a_run_of_closers_is_scanned_in_linear_time():
    for text in ("*" * 200_000, "a." + "*" * 100_000 + "b", "._" * 100_000, "x.**" * 50_000):
        start = time.perf_counter()
        _rule_03(text, "abstract.md")
        assert time.perf_counter() - start < 3.0


# ---------- appendix exemption (check A only) ---------------------------------------


@pytest.mark.parametrize(
    "name",
    ["appendix.tex", "02-Appendix.tex", "A_appendices.md", "supplement.md", "Supplementary-Materials.tex",
     "paper supp results.tex", "supp.tex", "/tmp/x/sections/appendix_b.tex", "C:\\x\\appendix.md",
     "results.appendix.tex", "app-prereg.tex", "app_results.tex", "appx.tex", "apx-b.tex"],
)
def test_appendix_and_supplement_file_names_skip_check_a(name):
    assert interval_hits(_rule_03(IV, name)) == [], name


@pytest.mark.parametrize("name", ["support.md", "supportive-notes.md", "results.tex", "notes.md", "",
                                  "application.tex", "apps.tex", "mapping.tex"])
def test_other_file_names_keep_check_a(name):
    assert len(interval_hits(_rule_03(IV, name))) == 1, name


def test_check_b_is_unaffected_by_the_appendix_exemption():
    assert len(stack_hits(_rule_03(STACKED, "abstract-appendix.tex"))) == 1
    found = _rule_03(STACKED + " " + IV, "supp-abstract.md")
    assert interval_hits(found) == [] and len(stack_hits(found)) == 1
    text = "\\appendix\n\\section{Details}\n" + STACKED + "\n"
    assert _rule_03(text, "main.tex") == []  # no abstract region: nothing for check B either


def test_text_after_the_appendix_command_skips_check_a():
    text = "\\section{Results}\n" + IV + "\n\\appendix\n\\section{Details}\n" + IV + "\n"
    assert interval_lines(text, "main.tex") == [2]


def test_appendices_environment_skips_check_a():
    text = IV + "\n\\begin{appendices}\n" + IV + "\n\\end{appendices}\n" + IV + "\n"
    assert interval_lines(text, "main.tex") == [1, 5]
    unclosed = IV + "\n\\begin{appendices}\n" + IV + "\n"
    assert interval_lines(unclosed, "main.tex") == [1]


def test_appendix_command_in_a_comment_or_a_longer_name_does_not_count():
    assert interval_lines("% \\appendix\n" + IV + "\n", "main.tex") == [2]
    assert interval_lines("\\appendixname\n" + IV + "\n", "main.tex") == [2]
    assert interval_lines("\\verb|\\appendix| " + IV + "\n", "main.tex") == [1]


def test_markdown_appendix_heading_skips_check_a_until_the_next_other_heading():
    text = (
        "# Paper\n\n## Results\n\n" + IV + "\n\n"
        "## Appendix A: Details\n\n" + IV + "\n\n### Sub-detail\n\n" + IV + "\n\n"
        "## Appendix B\n\n" + IV + "\n\n"
        "## Discussion\n\n" + IV + "\n"
    )
    assert interval_lines(text, "paper.md") == [5, 21]
    assert interval_lines(text.replace("\n", "\r\n"), "paper.md") == [5, 21]
    nested = "# Paper\n\n## Method\n\n### Appendix note\n\n" + IV + "\n\n### Other\n\n" + IV + "\n"
    assert interval_lines(nested, "paper.md") == [11]
    deeper_ends_nothing = "## Appendix\n\n" + IV + "\n\n#### Deep\n\n" + IV + "\n"
    assert interval_lines(deeper_ends_nothing, "paper.md") == []


def test_appendix_heading_rules_stay_inside_their_format():
    assert interval_lines("## See the appendix\n\n" + IV + "\n", "paper.md") == [3]
    assert interval_lines("Type \\appendix to start. " + IV + "\n", "notes.md") == [1]
    assert interval_lines("# Appendix\n\n" + IV + "\n", "main.tex") == [3]


def test_interval_message_keeps_the_claim_and_names_the_display():
    one = interval_hits(_rule_03(IV))[0].detail
    assert one == (
        "a numeric interval in prose; keep what the reader needs to judge the claim, "
        "in words where possible, and give the interval in a table or figure"
    )
    two = interval_hits(_rule_03("Compression gives 0.31 [0.22, 0.46] and caching gives 0.06 [-0.03, 0.15]."))[0].detail
    assert two.startswith("2 numeric intervals in prose; keep what the reader needs")
    assert "state the effect here" not in one


# ---------- positions and the public surface ----------------------------------


def test_violation_positions_survive_comments_and_crlf():
    text = "% a comment line\r\n% another 0.1 [0.0, 0.2]\r\n\r\nGain is 0.62 [0.51, 0.83] here.\r\n"
    found = interval_hits(_rule_03(text, "x.tex"))
    assert len(found) == 1
    assert found[0].line == 4
    assert found[0].column >= 1
    assert isinstance(found[0].excerpt, str) and found[0].excerpt


def test_findings_are_ordered_by_position():
    text = (
        "Gain is 0.62 [0.51, 0.83] here.\n\n"
        "Another gain is 0.58 [0.46, 0.69] there.\n"
    )
    lines = [v.line for v in _rule_03(text)]
    assert lines == sorted(lines) and len(lines) == 2


def test_registered_and_dispatched_with_the_file_path():
    assert "RULE-03" in detectors_mech._DISPATCH
    rule = SimpleNamespace(id="RULE-03", severity="high")
    quiet = detectors_mech.run(rule, STACKED, "results.md")
    assert quiet.status == "ok" and quiet.count == 0
    loud = detectors_mech.run(rule, STACKED, "00-abstract.tex")
    assert loud.status == "violation" and loud.count == 1
    assert loud.detector == "mechanical"
    assert loud.violations[0].rule == "RULE-03"


def test_other_rules_still_dispatch_on_text_alone():
    rule = SimpleNamespace(id="RULE-I", severity="low")
    result = detectors_mech.run(rule, "It's fine.", "x.md")
    assert result.count == 1


def test_default_file_path_is_empty_string():
    assert _rule_03("Gain is 0.62 [0.51, 0.83].") == _rule_03("Gain is 0.62 [0.51, 0.83].", "")


# ---------- robustness --------------------------------------------------------

ODD_INPUTS = [
    "",
    " ",
    "\n",
    "\r",
    "\x00\x01\x02 0.5 [0.1, 0.2]\x00",
    "".join(chr(i) for i in range(0, 0x300)),
    "{{{{ \\begin{abstract} 0.5, 0.6, 0.65, 0.8, 0.9, 1.1 }}}} ((((",
    "\\begin{abstract}\n0.1 0.2 0.3 0.4 0.5 0.6.",
    "\\begin{tabular}{ll} 0.1 & 0.2 \\\\",
    "\\begin{figure} 0.1 [0.0, 0.2]",
    "$$ 0.5 [0.1, 0.2] ",
    "\\[ 0.5 ",
    "\\href{http://x.y/1.2}{0.5 [0.1, 0.2]",
    "\\cite{ \\cite{ \\ref{ [0.1, 0.2] (0.3 to 0.4)",
    "[[[[[[[[ 0.1, 0.2 ]]]]]]]] ((((( 0.1 - 0.2 )))))",
    "```\n0.5 [0.1, 0.2]",
    "<!-- 0.5 [0.1, 0.2]",
    "## \n#\n######## Abstract\n## Introduction",
    "\u2212\u2212 0.5\u2212 [\u22120.1, \u22120.2] 5\u00a0% \u00a7 3.2",
    "9" * 5000,
    "." * 5000,
    "0." * 5000,
    "1,234," * 2000,
    "95% CI " * 500,
    "interval 0.5 to " * 500,
    "e.g. i.e. vs. Fig. 3. Dr. X. 0.5. 0.6. 0.65. 0.8. " * 200,
    "a | b\n--- | ---\n0.5 [0.1, 0.2]\n",
    "a | b\r\n--- | ---\r\n0.5\r\n",
    "|\n|-\n||\n| |\n-|-",
    "````\n```\n~~~\n`````\n",
    "    0.5 [0.1, 0.2]\n\n\t0.6 [0.2, 0.3]\n- a\n\n    0.85 [0.3, 0.4]",
    "- ```\n  0.5 [0.1, 0.2]",
    "> ```\n> 0.5 [0.1, 0.2]\n\n0.6",
    "> > - > ```\n> > - > 0.5\n>\n>>\n- - - ```\n",
    "-\t```\n\t0.5\n>\t```\n>\t0.5\n> \t\t```\n",
    "Foo\n---\n    0.5 [0.1, 0.2]\n===\n-\n= =\n***\n_ _ _\n- - -\n",
    "1. ```\n2. ```\n10) ~~~\n123456789. ```\n1234567890. ```\n",
    "\\appendix \\begin{appendices} 0.5 [0.1, 0.2]",
    "## Appendix\n#### Appendix\n# Results\n####### Appendix",
    "**0.5.** __0.6.__ *0.85.* _0.8._ `0.9.`",
]


@pytest.mark.parametrize("text", ODD_INPUTS, ids=[f"odd-{i}" for i in range(len(ODD_INPUTS))])
@pytest.mark.parametrize("path", ["", "00-abstract.tex", "main.tex", "notes.md"])
def test_never_raises(text, path):
    # The scan itself, not the public wrapper, so a bug cannot hide behind the
    # wrapper's catch-all.
    result = detectors_mech._rule_03_scan(text, path)
    assert isinstance(result, list)
    assert isinstance(_rule_03(text, path), list)
    assert isinstance(detectors_mech._rule_a_scan(text, path), list)
    assert isinstance(_rule_a(text, path), list)


def test_never_raises_on_odd_argument_types():
    assert _rule_03(None) == []  # type: ignore[arg-type]
    assert _rule_03("0.5 [0.1, 0.2]", None) is not None  # type: ignore[arg-type]
    assert _rule_03("0.5 [0.1, 0.2]", Path("00-abstract.tex")) is not None  # type: ignore[arg-type]


def test_a_broken_scan_is_swallowed_not_raised(monkeypatch):
    def boom(*_args, **_kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(detectors_mech, "_r03_stage_one", boom)
    assert _rule_03("0.5 [0.1, 0.2]", "x.md") == []


def test_two_hundred_kilobytes_is_fast():
    paragraph = (
        "The build gave 0.62 on the first split and 0.52 on the second, with "
        "Section 3.2 and Table 4 as context. Prefetching lowers the miss rate by 8.9 points "
        "(95\\% interval 0.51 to 0.83) at full load. v0.9.0 shipped on 2026-10-16.\n\n"
    )
    text = paragraph * (200_000 // len(paragraph) + 1)
    assert len(text) >= 200_000
    for path in ("", "00-abstract.tex", "main.tex"):
        start = time.perf_counter()
        _rule_03(text, path)
        _rule_a(text, path)
        assert time.perf_counter() - start < 3.0, path


# Built inside a list with short ids: pytest copies a test id into the
# PYTEST_CURRENT_TEST environment variable, and Windows caps one variable at
# 32,767 characters, so a raw 200 KB parameter breaks setup there.
HOSTILE_INPUTS = ["0" * 200_000, "!" * 200_000, "(1.5" + " " * 100_000 + "2.5)", "\\begin{figure} 0.5 " * 10_000,
    "$$ 0.5 " * 20_000, "123," * 50_000, "a/" * 100_000,
    "|\n" * 100_000, "a | b\n- | -\n" * 50_000, "|" * 200_000, "-|" * 100_000 + "\n",
    "## Appendix\n" * 100_000, "    x\n\n" * 50_000, "- a\n\n    b\n" * 50_000,
    "````\n```\n" * 50_000, "```x`\n" * 50_000, "\\appendix " * 20_000,
    "> ```\n> x\n" * 50_000, "- ```\n  x\n" * 50_000, "> " * 150_000 + "```\n" + "x\n" * 100_000,
    "- " * 100_000 + "```\n" + "  x\n" * 100_000, "> " * 1000 + "```\n" + ("> " * 1000 + "x\n") * 100,
    ">" * 200_000 + "\n" + "> x\n" * 50_000, "Foo\n---\n" * 50_000, "***\n    x\n" * 50_000,
    "- - -\n" * 100_000, "- > " * 50_000 + "```\n" + "  > x\n" * 50_000]


@pytest.mark.parametrize("text", HOSTILE_INPUTS, ids=[f"hostile-{i}" for i in range(len(HOSTILE_INPUTS))])
def test_hostile_inputs_are_fast(text):
    # `main.tex` reaches the body-prose, caption and precision checks, and
    # `_rule_a` the table check, which the abstract path does not.
    for path in ("00-abstract.tex", "notes.md", "main.tex"):
        start = time.perf_counter()
        _rule_03(text, path)
        _rule_a(text, path)
        assert time.perf_counter() - start < 3.0, path


def test_module_parses_for_python_39():
    source = Path(detectors_mech.__file__).read_text(encoding="utf-8")
    ast.parse(source, feature_version=(3, 9))
