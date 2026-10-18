# SPDX-License-Identifier: MIT
"""Tests for the hook-only RULE-08 repeated-caveat detector.

``_rule_08_repeats`` finds scope and limitation sentences by cue ("does not
establish", "we do not claim", "cannot rule out", "is limited to", "remains
untested", "beyond the scope", "we leave ... to future work"), reduces each to
content stems, groups near-duplicates, and reports a group of three or more once,
outside a limitations-style section and outside an appendix. A limitation stated
once in the text and once under Limitations stays quiet.

Every text here is synthetic: invented subjects, no real paper.
"""

from __future__ import annotations

import re
import time

import pytest

from agent_style.review.detectors_mech import (
    _PF_DOCUMENT_PREFIX,
    _R08_MIN_SHARED,
    _R08_REPEATS,
    _r08_signature,
    _r08_similar,
    _rule_08_repeats,
)

FILLER = [
    "The harbor survey covered forty orchards over two seasons.",
    "Copper ribbons raised the measured yield in most plots.",
    "Lantern spacing followed the layout shown in the figure.",
    "Pruning dates were set by the local extension office.",
]

CAVEATS = [
    "The orchard survey does not establish that pruning raises the fruit yield for every tree variety.",
    "Again, our orchard data do not establish that pruning raises fruit yield across tree varieties.",
    "This analysis does not establish that fruit yield rises with pruning for any tree variety.",
]


def latex(*sections) -> str:
    """A LaTeX body: (title, [paragraph, ...]) pairs, each paragraph one source line."""
    out = []
    for title, paras in sections:
        out.append("\\section{" + title + "}")
        out.extend(paras)
        out.append("")
    return "\n".join(out)


def markdown(*sections, level: int = 2) -> str:
    out = []
    for title, paras in sections:
        out.append("#" * level + " " + title)
        out.append("")
        for para in paras:
            out.append(para)
            out.append("")
    return "\n".join(out)


def three_sections(caveats=CAVEATS, build=latex) -> str:
    return build(
        ("Introduction", [FILLER[0] + " " + caveats[0]]),
        ("Results", [FILLER[1], FILLER[2] + " " + caveats[1]]),
        ("Discussion", [FILLER[3] + " " + caveats[2]]),
    )


# ---------- what reports -----------------------------------------------------------------


def test_a_caveat_stated_three_times_is_reported_once():
    text = three_sections()
    found = _rule_08_repeats(text, "paper.tex")
    assert len(found) == 1
    v = found[0]
    assert v.rule == "RULE-08"
    assert v.detail.startswith(_PF_DOCUMENT_PREFIX + "the same caveat framing is stated 3 times outside a limitations section")
    lines = text.splitlines()
    first = next(i for i, ln in enumerate(lines, 1) if CAVEATS[0] in ln)
    others = [i for i, ln in enumerate(lines, 1) if CAVEATS[1] in ln or CAVEATS[2] in ln]
    assert v.line == first
    assert f"also on lines {others[0]}, {others[1]}" in v.detail


def test_the_message_quotes_at_most_ten_words_of_the_first_instance():
    found = _rule_08_repeats(three_sections(), "paper.tex")
    quote = re.search(r'\("(.*?)"; also', found[0].detail).group(1)
    assert quote == "The orchard survey does not establish that pruning raises the ..."
    assert len(quote.replace(" ...", "").split()) == 10
    short = _rule_08_repeats(
        three_sections(["Pruning does not establish yield gains.", CAVEATS[1], CAVEATS[2]]), "paper.tex"
    )
    # A first instance that is short is quoted whole, with no ellipsis.
    assert not short or '..."' not in short[0].detail


def test_a_paraphrase_joins_the_group():
    paraphrases = [
        "The orchard survey does not establish that pruning raises the fruit yield for every tree variety.",
        "We cannot say that pruning raised fruit yield, because the orchard survey covers only a few tree varieties.",
        "Our orchard survey does not show that pruning increases the fruit yield for every tree variety.",
    ]
    found = _rule_08_repeats(three_sections(paraphrases), "paper.tex")
    assert len(found) == 1 and "stated 3 times" in found[0].detail


def test_two_groups_are_reported_separately_in_order():
    other = [
        "Winter survival of copper ribbons in the north meadow remains untested.",
        "Survival of copper ribbons through winter in the north meadow remains untested here.",
        "The north meadow winter survival of copper ribbons remains untested.",
    ]
    text = latex(
        ("Introduction", [CAVEATS[0], other[0]]),
        ("Results", [CAVEATS[1], other[1]]),
        ("Discussion", [CAVEATS[2], other[2]]),
    )
    found = _rule_08_repeats(text, "paper.tex")
    assert [v.line for v in found] == sorted(v.line for v in found) and len(found) == 2
    assert "orchard" in found[0].detail and "copper ribbons" in found[1].detail


def test_a_fragment_needs_three_instances_of_its_own():
    # No minimum size: the group is what is counted. Two repeats never report.
    two = CAVEATS[0] + " " + FILLER[0] + " " + CAVEATS[1] + "\n"
    assert _rule_08_repeats(two, "notes.md") == []
    three = " ".join(CAVEATS) + "\n"
    found = _rule_08_repeats(three, "notes.md")
    assert len(found) == 1 and "also on line 1" in found[0].detail  # one distinct line, singular


# ---------- what stays quiet --------------------------------------------------------------


def test_a_limitation_stated_once_in_the_text_and_once_under_limitations_is_quiet():
    text = latex(
        ("Results", [FILLER[0], CAVEATS[0]]),
        ("Limitations", [CAVEATS[1]]),
    )
    assert _rule_08_repeats(text, "paper.tex") == []


def test_instances_under_limitations_are_not_counted():
    text = latex(
        ("Results", [CAVEATS[0]]),
        ("Discussion", [CAVEATS[1]]),
        ("Limitations", [CAVEATS[2], "Once more, pruning does not establish yield gains for any orchard tree variety."]),
    )
    assert _rule_08_repeats(text, "paper.tex") == []
    four = latex(
        ("Introduction", [CAVEATS[0]]),
        ("Results", [CAVEATS[1]]),
        ("Discussion", [CAVEATS[2]]),
        ("Limitations", [CAVEATS[0]]),
    )
    found = _rule_08_repeats(four, "paper.tex")
    assert len(found) == 1 and "stated 3 times" in found[0].detail  # the fourth sits where it belongs


@pytest.mark.parametrize("title", [
    "\\section*{Limitations}", "\\section{Limitations and Future Work}", "\\section{Threats to Validity}",
    "\\subsection{Limitations}", "\\paragraph{Limitations.}", "\\section{Caveats}",
])
def test_every_limitations_style_heading_opens_a_section_in_latex(title):
    text = "\n".join([
        "\\section{Results}", FILLER[0] + " " + CAVEATS[0], "",
        title, CAVEATS[1], "", CAVEATS[2], "",
    ])
    assert _rule_08_repeats(text, "paper.tex") == [], title


def test_the_limitations_section_ends_at_the_next_heading_of_its_level():
    text = latex(
        ("Results", [CAVEATS[0]]),
        ("Limitations", [CAVEATS[1]]),
        ("Conclusion", [CAVEATS[2]]),
    )
    assert _rule_08_repeats(text, "paper.tex") == []  # two outside, one inside
    after = latex(
        ("Results", [CAVEATS[0]]),
        ("Limitations", [FILLER[0]]),
        ("Conclusion", [CAVEATS[1]]),
        ("Outlook", [CAVEATS[2]]),
    )
    assert len(_rule_08_repeats(after, "paper.tex")) == 1


def test_a_subsection_limitations_ends_at_the_next_subsection():
    text = "\n".join([
        "\\section{Discussion}", CAVEATS[0], "",
        "\\subsection{Limitations}", CAVEATS[1], "",
        "\\subsection{Outlook}", CAVEATS[2], "",
    ])
    assert _rule_08_repeats(text, "paper.tex") == []  # two outside, one inside
    more = text + "\n\\subsection{Closing}\n" + CAVEATS[0] + "\n"
    assert len(_rule_08_repeats(more, "paper.tex")) == 1


@pytest.mark.parametrize("heading", ["Limitations", "Threats to validity", "Limitations and future work"])
def test_markdown_limitations_headings(heading):
    text = markdown(
        ("Results", [CAVEATS[0]]),
        (heading, [CAVEATS[1], CAVEATS[2]]),
    )
    assert _rule_08_repeats(text, "paper.md") == []
    nested = "## Discussion\n\n" + CAVEATS[0] + "\n\n### " + heading + "\n\n" + CAVEATS[1] + "\n\n## Conclusion\n\n" + CAVEATS[2] + "\n"
    assert _rule_08_repeats(nested, "paper.md") == []


def test_markdown_repeats_report_like_latex():
    found = _rule_08_repeats(three_sections(build=markdown), "paper.md")
    assert len(found) == 1 and found[0].rule == "RULE-08"


def test_a_file_named_for_limitations_is_all_limitations():
    text = " ".join(CAVEATS) + "\n"
    assert _rule_08_repeats(text, "13-limitations.tex") == []
    assert _rule_08_repeats(text, "limitations.md") == []
    assert len(_rule_08_repeats(text, "results.md")) == 1


LEADS = [
    "\\textbf{Limitations.}", "\\noindent\\textbf{Limitations}", "\\noindent \\textbf{Limitations and caveats.}",
    "\\textit{Threats to validity.}", "\\emph{Limitations}", "\\textsc{Caveats.}", "  \\textbf{Limitations:}",
]


@pytest.mark.parametrize("lead", LEADS)
def test_a_bold_run_in_lead_opens_a_limitations_paragraph_in_latex(lead):
    text = "\n".join([
        "\\section{Results}", FILLER[0] + " " + CAVEATS[0], "",
        "\\section{Discussion}",
        lead + " " + CAVEATS[1] + " " + FILLER[1], CAVEATS[2], "",
    ])
    # The lead's paragraph holds two of the three caveats; only the first is counted.
    assert _rule_08_repeats(text, "paper.tex") == [], lead


@pytest.mark.parametrize("lead", ["**Limitations.**", "**Limitations**", "__Limitations.__", "**Threats to validity.**"])
def test_a_bold_run_in_lead_opens_a_limitations_paragraph_in_markdown(lead):
    text = "\n".join([
        "## Results", "", FILLER[0] + " " + CAVEATS[0], "",
        "## Discussion", "",
        lead + " " + CAVEATS[1] + " " + FILLER[1], CAVEATS[2], "",
    ])
    assert _rule_08_repeats(text, "paper.md") == [], lead


def test_a_run_in_lead_covers_its_paragraph_only():
    lead = "\\textbf{Limitations.}"
    text = "\n".join([
        "\\section{Discussion}", lead + " " + CAVEATS[0], "",
        CAVEATS[1], "", CAVEATS[2], "", CAVEATS[0].replace("orchard", "Orchard"), "",
    ])
    found = _rule_08_repeats(text, "paper.tex")
    assert len(found) == 1 and "stated 3 times" in found[0].detail  # the three after the blank line


def test_a_run_in_lead_without_a_limitations_word_opens_nothing():
    for lead in ("\\textbf{Results.}", "\\textbf{Our approach.}", "**Setup.**", "\\emph{Note}"):
        build = markdown if lead.startswith("*") else latex
        text = build(
            ("Introduction", [lead + " " + FILLER[0] + " " + CAVEATS[0]]),
            ("Results", [FILLER[1] + " " + CAVEATS[1]]),
            ("Discussion", [FILLER[3] + " " + CAVEATS[2]]),
        )
        assert len(_rule_08_repeats(text, "paper.md" if lead.startswith("*") else "paper.tex")) == 1, lead


def test_a_bold_phrase_inside_a_line_is_not_a_run_in_lead():
    # The lead has to start the line (the paragraph); a mention in running text is not one.
    text = latex(
        ("Introduction", ["See \\textbf{Limitations.} " + CAVEATS[0]]),
        ("Results", [CAVEATS[1]]),
        ("Discussion", [CAVEATS[2]]),
    )
    assert len(_rule_08_repeats(text, "paper.tex")) == 1


def test_footnotes_and_acknowledgments_are_not_prose_for_the_repeats():
    # One of the three caveats sits in a footnote body: it is not a sentence of the text.
    note = FILLER[0] + "\\footnote{" + CAVEATS[0] + "}"
    text = latex(("Introduction", [note]), ("Results", [CAVEATS[1]]), ("Discussion", [CAVEATS[2]]))
    assert _rule_08_repeats(text, "paper.tex") == []
    ack = latex(
        ("Results", [CAVEATS[0]]), ("Discussion", [CAVEATS[1]]), ("Conclusion", [CAVEATS[2]]),
    ) + "\\section*{Acknowledgments}\n" + CAVEATS[0] + "\n\n" + CAVEATS[1] + "\n"
    assert len(_rule_08_repeats(ack, "paper.tex")) == 1
    assert "stated 3 times" in _rule_08_repeats(ack, "paper.tex")[0].detail  # the two thanks are not counted


@pytest.mark.parametrize("name", ["paper.md", "notes.txt", ""])
def test_markdown_footnote_definitions_are_not_prose_for_the_repeats(name):
    # Three definitions that state the same caveat are notes, not three sentences of the text.
    notes = "\n".join("[^%d]: %s" % (i, CAVEATS[i - 1]) for i in (1, 2, 3))
    text = "\n\n".join([FILLER[0] + "[^1]", FILLER[1] + "[^2]", FILLER[2] + "[^3]", notes]) + "\n"
    assert _rule_08_repeats(text, name) == []
    # The same three sentences as body text report.
    assert len(_rule_08_repeats(text.replace("[^1]: ", "").replace("[^2]: ", "").replace("[^3]: ", ""), name)) == 1


def test_a_continuation_paragraph_of_a_footnote_is_not_prose_for_the_repeats():
    text = (
        FILLER[0] + " " + CAVEATS[0] + "[^a]\n\n" + FILLER[1] + " " + CAVEATS[1] + "\n\n"
        "[^a]: A first note.\n\n    " + CAVEATS[2] + "\n"
    )
    assert _rule_08_repeats(text, "notes.txt") == []
    assert _rule_08_repeats(text, "notes.md") == []
    # Without the note's markup, the third caveat is a paragraph of the text and the group reports.
    body = text.replace("[^a]: A first note.\n\n    ", "\n").replace("[^a]", "")
    assert len(_rule_08_repeats(body, "notes.txt")) == 1


def test_a_caveat_after_a_footnote_definition_still_counts():
    text = (
        FILLER[0] + " " + CAVEATS[0] + "\n\n" + FILLER[1] + " " + CAVEATS[1] + "[^a]\n\n"
        "[^a]: A short note.\n\n" + FILLER[2] + " " + CAVEATS[2] + "\n"
    )
    found = _rule_08_repeats(text, "paper.md")
    assert len(found) == 1 and "stated 3 times" in found[0].detail


def test_a_latex_file_is_not_read_for_markdown_footnotes_in_the_repeats():
    text = latex(("Results", [FILLER[0] + " " + CAVEATS[0]])) + "\n[^1]: " + CAVEATS[1] + "\n\n[^2]: " + CAVEATS[2] + "\n"
    assert len(_rule_08_repeats(text, "paper.tex")) == 1


def test_appendix_text_is_not_counted():
    after = "\\appendix\n\\section{Details}\n" + "\n\n".join(CAVEATS) + "\n"
    text = latex(("Results", [FILLER[0]])) + after
    assert _rule_08_repeats(text, "paper.tex") == []
    assert _rule_08_repeats("\n\n".join(CAVEATS) + "\n", "appendix-b.tex") == []
    md = "## Results\n\n" + FILLER[0] + "\n\n## Appendix A\n\n" + "\n\n".join(CAVEATS) + "\n"
    assert _rule_08_repeats(md, "paper.md") == []


def test_different_caveats_stay_quiet():
    different = [
        "The orchard survey does not establish that pruning raises the fruit yield for every tree variety.",
        "Winter survival of copper ribbons in the north meadow remains untested.",
        "We leave the effect of lantern spacing on harbor traffic to future work.",
    ]
    assert _rule_08_repeats(three_sections(different), "paper.tex") == []


def test_three_sentences_that_are_not_caveats_stay_quiet():
    plain = ["The orchard survey raised fruit yield with pruning for every tree variety."] * 3
    assert _rule_08_repeats(three_sections(plain), "paper.tex") == []


# ---------- the cues --------------------------------------------------------------------------

CUE_FAMILIES = {
    "does not establish": "{lead}The orchard survey does not establish that pruning raises fruit yield in other trees.",
    "does not directly show": "{lead}The orchard survey does not directly show that pruning raises fruit yield in other trees.",
    "we do not claim": "{lead}We do not claim that pruning raises fruit yield in other orchard trees.",
    "we have not tested": "{lead}We have not tested whether pruning raises fruit yield in other orchard trees.",
    "cannot rule out": "{lead}The orchard data cannot rule out that pruning raises fruit yield in other trees.",
    "cannot distinguish": "{lead}The orchard survey cannot distinguish pruning effects on fruit yield in other trees.",
    "is limited to": "{lead}The pruning result is limited to orchard trees of one variety grown in loam.",
    "remains untested": "{lead}Whether pruning raises fruit yield in other orchard trees remains untested.",
    "remains open": "{lead}Whether pruning raises fruit yield in other orchard trees remains an open question.",
    "beyond the scope": "{lead}Pruning effects on fruit yield in other orchard trees are beyond the scope of this survey.",
    "leave to future work": "{lead}We leave pruning effects on fruit yield in other orchard trees to future work.",
    "unclear whether": "{lead}It is unclear whether pruning raises fruit yield in other orchard trees.",
    "should not be read as": "{lead}This should not be read as a claim that pruning raises fruit yield in other orchard trees.",
    "one limitation": "{lead}One limitation is that pruning was studied only in one orchard of one tree variety.",
    "may not generalize": "{lead}The pruning effect on fruit yield may not generalize to other orchard trees.",
}


@pytest.mark.parametrize("cue", sorted(CUE_FAMILIES))
def test_each_cue_family_is_recognized(cue):
    template = CUE_FAMILIES[cue]
    sentences = [template.format(lead=lead) for lead in ("", "Again, ", "Also, ")]
    sentences = [s[0].upper() + s[1:] if s else s for s in sentences]
    found = _rule_08_repeats(three_sections(sentences), "paper.tex")
    assert len(found) == 1, (cue, [v.detail for v in found])


def test_markup_inside_a_cue_does_not_hide_it():
    emph = [s.replace("does not establish", "does \\emph{not} establish") for s in CAVEATS]
    assert len(_rule_08_repeats(three_sections(emph), "paper.tex")) == 1
    bold = [s.replace("does not establish", "does **not** establish").replace("do not establish", "do **not** establish") for s in CAVEATS]
    assert len(_rule_08_repeats(three_sections(bold, build=markdown), "paper.md")) == 1
    math = [s.replace("fruit yield", "fruit yield $y$") for s in CAVEATS]
    assert len(_rule_08_repeats(three_sections(math), "paper.tex")) == 1


def test_a_caveat_in_a_comment_or_a_code_block_is_not_counted():
    commented = latex(
        ("Results", ["% " + CAVEATS[0], "% " + CAVEATS[1], CAVEATS[2]]),
    )
    assert _rule_08_repeats(commented, "paper.tex") == []
    fenced = "## Results\n\n```\n" + "\n".join(CAVEATS) + "\n```\n"
    assert _rule_08_repeats(fenced, "notes.md") == []


# ---------- the helpers ---------------------------------------------------------------------


def test_the_signature_drops_function_words_cue_words_and_inflection():
    a = _r08_signature("The orchard survey does not establish that pruning raises the fruit yield.")
    b = _r08_signature("Orchard surveys do not establish that pruned trees raise fruit yields.")
    assert {"orchard", "survey", "fruit"} <= a
    assert "establish" not in a and "the" not in a and "does" not in a
    assert {"orchard", "survey", "fruit", "yield"} <= b
    assert _r08_signature("walks walked walking") == frozenset({"walk"})
    assert _r08_signature("raise raises raised") == frozenset({"rais"})
    assert _r08_signature("variety varieties") == frozenset({"variety"})


def test_similarity_needs_shared_stems_overlap_and_jaccard():
    base = frozenset({"orchard", "survey", "prun", "fruit", "yield", "variety"})
    assert _r08_similar(base, base)
    assert not _r08_similar(base, frozenset({"orchard", "survey", "harbor", "ribbon", "lantern", "copper"}))
    assert not _r08_similar(base, frozenset({"orchard", "survey"}))  # two shared stems are too few
    assert _R08_REPEATS == 3


# ---------- shape -------------------------------------------------------------------------------


def test_the_message_is_one_or_two_sentences_and_never_a_violation():
    for text in (three_sections(), three_sections(build=markdown)):
        for v in _rule_08_repeats(text, "paper.tex"):
            assert "violation" not in v.detail.lower()
            assert v.detail.startswith(_PF_DOCUMENT_PREFIX)
            assert "the same caveat framing is stated" in v.detail
            assert "consider cutting the copies that add nothing" in v.detail
            assert v.detail.count(". ") <= 1
            assert v.line >= 1 and v.column >= 1 and v.excerpt


def test_the_shared_stem_floor_is_three():
    # The corpus shows no pair of caveats near the thresholds. The floor stays where it was.
    assert _R08_MIN_SHARED == 3


def test_default_path_and_keyword_path_agree():
    text = three_sections()
    assert _rule_08_repeats(text) == _rule_08_repeats(text, None)
    assert _rule_08_repeats(text, file_path="paper.tex") == _rule_08_repeats(text, "paper.tex")


@pytest.mark.parametrize("bad", ["", None, 12, b"bytes", ["a"], "\x00\x00", "\\section{", "## ", "\\appendix"])
def test_it_never_raises(bad):
    assert _rule_08_repeats(bad, "paper.tex") == []
    assert _rule_08_repeats(bad) == []


def test_crlf_keeps_the_line_numbers():
    text = three_sections().replace("\n", "\r\n")
    expected = _rule_08_repeats(three_sections(), "paper.tex")
    assert [(v.line, v.detail) for v in _rule_08_repeats(text, "paper.tex")] == [(v.line, v.detail) for v in expected]


def test_a_large_document_is_read_quickly():
    body = [FILLER[i % 4] + " " + CAVEATS[i % 3].replace("orchard", "orchard%d" % (i // 3)) for i in range(3000)]
    text = latex(("Results", body))
    started = time.time()
    _rule_08_repeats(text, "paper.tex")
    assert time.time() - started < 5.0


def test_hostile_inputs_are_fast():
    hostile = [
        "does not establish " * 30_000,
        "We do not claim " * 30_000,
        "\\section{Limitations}\n" * 20_000,
        "## Limitations\n" * 20_000,
        "leaves " + "x " * 50_000 + "to future work.",
        "**Limitations.** x\n" * 30_000,
        "\\textbf{Limitations.} x\n" * 30_000,
        "\\textbf{Limitations.}\n\n" * 30_000,
        "\\footnote{" * 20_000,
        "\\acks " * 20_000,
        "[^1]: does not establish x\n" * 30_000,
        "[^" * 100_000,
        "[^1]: x\n\n    y\n\n" * 20_000,
    ]
    for text in hostile:
        started = time.time()
        _rule_08_repeats(text, "paper.tex")
        assert time.time() - started < 5.0, text[:20]
