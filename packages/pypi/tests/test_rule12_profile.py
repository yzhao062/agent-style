# SPDX-License-Identifier: MIT
"""Tests for the hook-only RULE-12 profile detector.

``_rule_12_profile`` reads a whole document where ``_rule_12`` reads one line. It
reports under the label RULE-12 and replaces the per-sentence nag in a hook, while
the CLI audit keeps ``_rule_12``. Three checks:

* the share of sentences over 30 words, above 45% or below 6%, in a complete LaTeX
  paper (``\\begin{document}`` and ``\\end{document}``, a paper class, and no
  ``\\input`` of a body file). Markdown and text are never read for a share;
* ", so" clause joins: 6 or more, at 1.5 per 1,000 words or more, in 1,000 words or
  more, in a paper context;
* sentences over 80 words, reported once per document.

A finding about the document as a whole begins with ``_PF_DOCUMENT_PREFIX`` and the
profile emits those first. Every text here is synthetic: invented words, generated
sentence lengths.
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from agent_style.review import audit, detectors_mech, primitive
from agent_style.review.detectors_mech import (
    _PF_DOCUMENT_PREFIX,
    _R12_EXTREME_WORDS,
    _R12_SHARE_HIGH,
    _R12_SHARE_LOW,
    _R12_SHARE_MIN_SENTENCES,
    _R12_SO_DENSITY,
    _R12_SO_MIN_COUNT,
    _R12_SO_MIN_WORDS,
    _PF_EMPHASIS_RE,
    _pf_document,
    _pf_whole_document,
    _rule_12,
    _rule_12_profile,
)

WORDS = ("gadget", "river", "lantern", "orchard", "ribbon", "harbor", "meadow", "copper")


def sentence(n: int, seed: int = 0) -> str:
    """A sentence of exactly ``n`` words: invented content, no digits or abbreviations."""
    assert n >= 2
    return "The " + " ".join(WORDS[(seed + i) % len(WORDS)] for i in range(n - 1)) + "."


def paragraphs(sentences, per_paragraph: int = 8) -> str:
    chunks = [" ".join(sentences[i:i + per_paragraph]) for i in range(0, len(sentences), per_paragraph)]
    return "\n\n".join(chunks) + "\n"


def tex(sentences) -> str:
    """A LaTeX section file: a fragment, with no ``\\begin{document}``."""
    return "\\section{Results}\n" + paragraphs(sentences)


def paper(sentences, documentclass: str = "article") -> str:
    """A whole LaTeX document."""
    return (
        "\\documentclass{%s}\n\\begin{document}\n\\section{Results}\n" % documentclass
        + paragraphs(sentences)
        + "\\end{document}\n"
    )


def md_paper(sentences, heading: str = "# Abstract") -> str:
    return heading + "\n\n" + paragraphs(sentences)


def with_share(total: int, long_count: int, long_words: int = 35, short_words: int = 12) -> list:
    """``total`` sentences, ``long_count`` of them long, spread through the text."""
    out = []
    for i in range(total):
        is_long = (i * long_count) // total != ((i + 1) * long_count) // total
        out.append(sentence(long_words if is_long else short_words, seed=i))
    assert sum(1 for s in out if len(s.split()) > 30) == long_count
    return out


def lengths(text: str, name: str = "paper.tex") -> list:
    return [s[2] for s in _pf_document(text, name).sentences]


def kinds_of(found) -> list:
    """The kind of each finding, in the order the profile returned them."""
    return [
        "extreme" if ("a sentence of" in v.detail or "sentences over" in v.detail)
        else "so" if "join clauses" in v.detail
        else "share"
        for v in found
    ]


# ---------- sentences over 80 words, one finding per document ---------------------------


def test_a_sentence_over_eighty_words_is_reported():
    assert _R12_EXTREME_WORDS == 80
    text = tex([sentence(12), sentence(_R12_EXTREME_WORDS + 1), sentence(12)])
    found = _rule_12_profile(text, "paper.tex")
    assert len(found) == 1
    assert found[0].rule == "RULE-12"
    assert found[0].detail.startswith("a sentence of 81 words, a length that is uncommon in human-written papers;")
    # The paragraph sits on line 2, under the \section line; the long sentence is its second.
    assert found[0].line == 2 and found[0].column > 1


def test_eighty_words_and_the_per_sentence_nag_stay_quiet():
    # The old hook rule flagged every sentence over 30 words; the profile does not.
    assert _rule_12_profile(tex([sentence(80)]), "paper.tex") == []
    text = "\n\n".join(sentence(35, seed=i) for i in range(10)) + "\n"
    assert len(_rule_12(text)) == 10
    assert _rule_12_profile(text, "notes.md") == []


def test_extreme_sentences_collapse_into_one_finding_per_document():
    text = tex([sentence(100), sentence(10), sentence(110), sentence(10)])
    found = _rule_12_profile(text, "paper.tex")
    assert len(found) == 1
    assert found[0].detail.startswith("2 sentences over 80 words, the first at line 2, a length that is uncommon")
    assert "consider whether each carries one connected thought, and split where a separate claim begins" in found[0].detail
    assert found[0].line == 2


def test_thirty_extreme_sentences_are_still_one_finding():
    text = tex([sentence(85 + (i % 5), seed=i) for i in range(30)])
    found = _rule_12_profile(text, "paper.tex")
    assert len(found) == 1 and "30 sentences over 80 words, the first at line 2" in found[0].detail


def test_the_first_line_is_where_the_first_extreme_sentence_starts():
    text = "\\section{A}\n" + sentence(10) + "\n\n" + sentence(10) + "\n\n" + sentence(90) + " " + sentence(95) + "\n"
    found = _rule_12_profile(text, "paper.tex")
    assert len(found) == 1 and found[0].line == 6 and "the first at line 6" in found[0].detail


def test_an_extreme_sentence_is_found_in_a_fragment_too():
    # The sentence check needs no document: a single edit can carry one.
    found = _rule_12_profile(sentence(95), "notes.md")
    assert len(found) == 1 and "95 words" in found[0].detail


def test_the_extreme_message_names_papers_in_a_paper_and_prose_elsewhere():
    for text in (tex([sentence(95)]), paper([sentence(95)])):
        assert "uncommon in human-written papers;" in _rule_12_profile(text, "paper.tex")[0].detail
    # Markdown and text compare with prose, even under an Abstract heading.
    for text, name in ((sentence(95), "notes.md"), ("# Notes\n\n" + sentence(95), "CHANGELOG.md"),
                       (sentence(95), "log.txt"), (md_paper([sentence(95)]), "draft.md")):
        detail = _rule_12_profile(text, name)[0].detail
        assert "uncommon in human-written prose;" in detail and "papers" not in detail, name
    # Slides and letters are not papers, however the class declaration is laid out.
    for head in ("\\documentclass{beamer}\n", "\\documentclass[\n  aspectratio=169\n]{beamer}\n",
                 "\\documentclass\n  [11pt]\n  {letter}\n"):
        slides = head + "\\begin{document}\n" + paragraphs([sentence(95)]) + "\\end{document}\n"
        assert "human-written prose;" in _rule_12_profile(slides, "talk.tex")[0].detail, head


def test_latex_commands_citations_and_comments_are_not_words():
    limit = _R12_EXTREME_WORDS
    raw = (
        "The " + " ".join(["gadget"] * (limit - 32)) + " \\cite{alpha,beta} \\label{fig:x} "
        + "\\textbf{" + " ".join(["river"] * 30) + "} % " + " ".join(["lantern"] * 50) + "\n"
    )
    # limit - 2 words before and in the bold span: none from the cite, the label or the comment.
    assert len(raw.split("%")[0].split()) > limit  # the raw tokens alone would pass the limit
    assert _rule_12_profile(raw, "paper.tex") == []
    longer = raw.replace("\\textbf{", "\\textbf{river river ")
    found = _rule_12_profile(longer, "paper.tex")
    assert len(found) == 1 and f"{limit + 1} words" in found[0].detail


def test_inline_math_counts_as_one_word():
    body = " ".join(["$x_{%d}$" % i for i in range(91)])
    found = _rule_12_profile("The " + body + ".\n", "paper.tex")
    assert len(found) == 1 and "92 words" in found[0].detail


def test_markdown_extreme_sentence_and_code_are_read_like_prose():
    long = sentence(92)
    text = "# Notes\n\n" + long + "\n\n```\n" + " ".join(["gadget"] * 90) + ".\n```\n"
    found = _rule_12_profile(text, "notes.md")
    assert len(found) == 1 and "92 words" in found[0].detail and found[0].line == 3


# ---------- footnotes and acknowledgments are not part of the sentence ---------------------


def whole(body: str) -> str:
    return "\\documentclass{article}\n\\begin{document}\n" + body + "\n\\end{document}\n"


def test_a_footnote_body_is_not_part_of_the_sentence_that_carries_it():
    # 35 words, a footnote of two 20-word sentences (the second lowercase), then a sentence.
    host = "The " + " ".join(["gadget"] * 34) + "."
    note = "\\footnote{" + " ".join(["gadget"] * 20) + ". " + " ".join(["river"] * 20) + ".}"
    text = whole(host + note + " Next steps follow here.")
    assert lengths(text) == [35, 4]
    assert _rule_12_profile(text, "paper.tex") == []
    # The same text with the footnote body in the sentence is 75 words, over the limit.
    merged = whole(host[:-1] + " " + " ".join(["gadget"] * 20) + " " + " ".join(["river"] * 20) + ".")
    assert lengths(merged) == [75]


@pytest.mark.parametrize("opening", [
    "\\footnote{", "\\footnote[2]{", "\\footnotetext{", "\\footnotetext[3]{", "\\thanks{", "\\footnote {",
])
def test_every_note_command_leaves_the_host_sentence_alone(opening):
    host = "The " + " ".join(["lantern"] * 19) + "."
    text = whole(host + opening + " ".join(["copper"] * 80) + "} Next steps follow here.")
    assert lengths(text) == [20, 4], opening


def test_a_footnote_inside_a_sentence_is_dropped_and_the_sentence_stays_whole():
    text = whole("The gadget\\footnote{see the " + " ".join(["river"] * 90) + "} moved the meadow today.")
    assert lengths(text) == [6]


def test_a_footnote_with_nested_commands_and_braces_is_dropped_whole():
    note = "\\footnote{" + "\\textbf{" + " ".join(["gadget"] * 40) + "} and \\emph{" + " ".join(["river"] * 40) + "}.}"
    text = whole("The harbor moved quietly again." + note + " Done now, really.")
    assert lengths(text) == [5, 3]


def test_a_footnote_mark_without_a_body_is_not_a_note():
    text = whole("The gadget moved\\footnotemark[1] across the harbor today.")
    assert lengths(text) == [7]


def test_a_url_with_a_slash_in_a_footnote_does_not_swallow_the_text_after_it():
    # The RULE-03 pass blanks a whole path-like token, closing braces and all. The note
    # is found on the source with comments and code removed, where its braces still pair.
    text = whole(
        "The harbor moved quietly again\\footnote{Code: \\url{https://example.org/a/b.py}}.\n\n"
        + paragraphs(with_share(50, 10))
    )
    assert len(lengths(text)) >= 51


def test_a_footnote_longer_than_three_thousand_characters_is_left_in_the_count():
    # A match this long means an unbalanced brace; blanking it would drop the rest of the paper.
    fits = whole("The harbor moved. \\footnote{" + " ".join(["gadget"] * 350) + "}")
    assert lengths(fits) == [3]
    long = whole("The harbor moved. \\footnote{" + " ".join(["gadget"] * 450) + "}")
    assert lengths(long)[-1] == 450


@pytest.mark.parametrize("opening, closing", [
    ("\\section*{Acknowledgments}", ""),
    ("\\section{Acknowledgements}", ""),
    ("\\subsection*{Acknowledgments}", ""),
    ("\\paragraph{Acknowledgments.}", ""),
    ("\\section*{Acknowledgments and Disclosure of Funding}", ""),
    ("\\begin{ack}", "\\end{ack}"),
    ("\\begin{acks}", "\\end{acks}"),
    ("\\begin{acknowledgments}", "\\end{acknowledgments}"),
    ("\\begin{acknowledgements*}", "\\end{acknowledgements*}"),
    ("\\acks", ""),
    ("\\acknowledgments", ""),
])
def test_acknowledgment_sections_are_not_prose(opening, closing):
    names = " ".join(["Gadget Ribbon,"] * 45) + " and Copper Meadow."
    after = "\\section{Conclusion}\n" + sentence(100)
    text = whole("The harbor moved quietly again.\n\n" + opening + "\n" + names + "\n" + closing + "\n\n" + after)
    found = _rule_12_profile(text, "paper.tex")
    assert len(found) == 1 and found[0].detail.startswith("a sentence of 100 words"), opening


def test_an_acknowledgments_command_with_a_body_in_braces_is_dropped():
    names = " ".join(["Gadget Ribbon,"] * 45) + " and Copper Meadow."
    text = whole("The harbor moved quietly again.\n\n\\acks{" + names + "}\n\n\\section{Conclusion}\n" + sentence(10))
    assert lengths(text) == [5, 10]


@pytest.mark.parametrize("heading", ["## Acknowledgments", "### Acknowledgements", "## Acknowledgments and funding"])
def test_markdown_acknowledgments_end_at_the_next_heading(heading):
    names = " ".join(["Gadget Ribbon,"] * 45) + " and Copper Meadow."
    text = "# Notes\n\n" + sentence(10) + "\n\n" + heading + "\n\n" + names + "\n\n## Next\n\n" + sentence(100) + "\n"
    found = _rule_12_profile(text, "notes.md")
    assert len(found) == 1 and found[0].detail.startswith("a sentence of 100 words"), heading


def test_prose_before_and_after_an_acknowledgment_section_is_still_read():
    text = whole(
        "\\section{Intro}\n" + sentence(90) + "\n\n\\section*{Acknowledgments}\nWe thank the harbor crew today.\n\n"
        "\\section{Conclusion}\n" + sentence(110)
    )
    found = _rule_12_profile(text, "paper.tex")
    assert len(found) == 1 and found[0].detail.startswith("2 sentences over 80 words")


# ---------- a leading YAML front-matter block is not prose ---------------------------------


def test_a_leading_yaml_block_is_not_prose():
    front = (
        "---\nname: demo\ndescription: " + " ".join(["gadget"] * 80) + "\n"
        "allowed-tools: " + " ".join(["river"] * 15) + "\n---\n\n# Demo\n\n"
    )
    assert _rule_12_profile(front + sentence(12) + "\n", "SKILL.md") == []
    # The text after the block is read as before.
    found = _rule_12_profile(front + sentence(95) + "\n", "SKILL.md")
    assert len(found) == 1 and "95 words" in found[0].detail and found[0].line == 9
    assert lengths(front + sentence(12) + "\n", "SKILL.md") == [12]


def test_a_thematic_break_at_the_top_is_not_front_matter():
    text = "---\n\n" + sentence(100) + "\n\n---\n\nOther text follows here.\n"
    found = _rule_12_profile(text, "notes.md")
    assert len(found) == 1 and "100 words" in found[0].detail
    # An unclosed block is read as text too.
    assert len(_rule_12_profile("---\nname: demo\n\n" + sentence(100) + "\n", "notes.md")) == 1


def test_a_yaml_block_with_crlf_and_a_bom_is_dropped():
    front = "\ufeff---\r\nname: demo\r\ndescription: " + " ".join(["gadget"] * 100) + "\r\n---\r\n\r\n"
    assert _rule_12_profile(front + sentence(12) + "\r\n", "SKILL.md") == []


def test_yaml_looking_text_in_a_tex_file_is_left_alone():
    text = whole("---\nname: demo\n" + " ".join(["gadget"] * 80) + ".\n---\n")
    assert len(_rule_12_profile(text, "paper.tex")) == 1


# ---------- Markdown footnote definitions are notes, as \footnote is in LaTeX -----------------


def words_of(n: int, word: str = "gadget") -> str:
    return " ".join([word] * n)


@pytest.mark.parametrize("name", ["notes.md", "notes.markdown", "notes.txt", ""])
def test_a_footnote_definition_is_not_prose(name):
    # The marker would be an 85th word; the body is a sentence of its own.
    host = "The harbor moved quietly across the meadow.[^a]"
    text = host + "\n\n[^a]: " + words_of(84) + ".\n\nThe lantern rose over the orchard today.\n"
    assert lengths(text, name or "notes.md") == [7, 7], name
    assert _rule_12_profile(text, name) == [], name


@pytest.mark.parametrize("name", ["notes.md", "notes.txt", ""])
def test_a_footnote_definition_keeps_its_continuation_paragraphs(name):
    # Lazy continuation lines, and paragraphs indented four columns after a blank line.
    text = (
        "The harbor moved quietly across the meadow.[^a]\n\n"
        "[^a]: " + words_of(30) + ".\n"
        + words_of(30, "river") + ".\n"
        "\n"
        "    " + words_of(90, "lantern") + ".\n"
        "\n"
        "    " + words_of(40, "copper") + ".\n"
        "\n"
        "The lantern rose over the orchard today.\n"
    )
    assert lengths(text, name or "notes.md") == [7, 7], name
    assert _rule_12_profile(text, name) == [], name


def test_prose_after_a_footnote_definition_is_read_again():
    text = (
        "[^a]: " + words_of(20) + ".\n\n"
        "Plain text follows, and " + words_of(95, "river") + ".\n"
    )
    found = _rule_12_profile(text, "notes.md")
    assert len(found) == 1 and "a sentence of 99 words" in found[0].detail and found[0].line == 3


def test_a_footnote_definition_ends_at_the_next_definition_or_blank_line():
    text = (
        "[^a]: " + words_of(30) + ".\n"
        "[^b]: " + words_of(30) + ".\n"
        "[^c]: " + words_of(30) + ".\n"
        "\n"
        "Body text after the notes is short.\n"
    )
    assert lengths(text, "notes.md") == [7]


def test_a_footnote_marker_counts_as_no_word_and_does_not_join_the_sentences_around_it():
    # `.[^1] The` has no space before the bracket, which would keep two sentences in one.
    text = "The gadget moved the river.[^1] The lantern rose over the orchard today.[^2]\n\n[^1]: A note here.\n[^2]: Another note.\n"
    assert lengths(text, "notes.md") == [5, 7]
    assert lengths("The gadget[^note] moved the river today.\n", "notes.md") == [6]


def test_text_that_only_looks_like_a_footnote_is_prose():
    # Not at the start of a line, with a space in the label, empty, or in code: not a definition.
    for line in ("See [^a]: " + words_of(90) + ".", "[^a b]: " + words_of(90) + ".", "[^]: " + words_of(90) + ".",
                 "    [^a]: " + words_of(90) + "."):
        found = _rule_12_profile("Intro text first.\n\n" + line + "\n", "notes.md")
        # The indented line after a blank is a code block in Markdown and stays out of the count.
        assert len(found) == (0 if line.startswith("    ") else 1), line
    fenced = "```\n[^a]: " + words_of(90) + ".\n```\n\nShort text follows here.\n"
    assert _rule_12_profile(fenced, "notes.md") == []


def test_a_latex_file_is_not_read_for_markdown_footnotes():
    text = whole("The harbor moved quietly across the meadow.\n\n[^a]: " + words_of(90) + ".\n")
    found = _rule_12_profile(text, "paper.tex")
    assert len(found) == 1 and "a sentence of 91 words" in found[0].detail  # the marker is a word in LaTeX


# ---------- the share of long sentences, in a whole document -------------------------------


def test_too_many_long_sentences_is_reported_once():
    text = paper(with_share(50, 25))
    found = _rule_12_profile(text, "paper.tex")
    assert len(found) == 1
    assert found[0].rule == "RULE-12"
    assert found[0].detail.startswith(_PF_DOCUMENT_PREFIX + "about 50% of the 50 sentences run past 30 words")
    assert "above the 10% to 35% range of human-written papers" in found[0].detail


def test_too_few_long_sentences_is_reported_once():
    found = _rule_12_profile(paper(with_share(50, 0)), "paper.tex")
    assert len(found) == 1
    assert "none of the 50 sentences run past 30 words" in found[0].detail
    assert "below the 10% to 35% range of human-written papers" in found[0].detail
    assert "clipped" in found[0].detail


def test_a_few_long_sentences_read_as_fewer_than_five_percent():
    found = _rule_12_profile(paper(with_share(100, 2)), "paper.tex")
    assert len(found) == 1 and "fewer than 5% of the 100 sentences" in found[0].detail


def test_a_share_inside_the_human_range_stays_quiet():
    for long_count in (6, 8, 15, 20):  # 12% to 40% of 50
        assert _rule_12_profile(paper(with_share(50, long_count)), "paper.tex") == [], long_count


def test_the_share_bounds_are_strict():
    assert _R12_SHARE_HIGH == 0.45 and _R12_SHARE_LOW == 0.06
    # 45% of 40 is not above 45%; 19 of 40 is.
    assert _rule_12_profile(paper(with_share(40, 18)), "paper.tex") == []
    assert len(_rule_12_profile(paper(with_share(40, 19)), "paper.tex")) == 1
    # 6% of 50 is 3, which is not below 6%; 2 of 50 is.
    assert _rule_12_profile(paper(with_share(50, 3)), "paper.tex") == []
    assert len(_rule_12_profile(paper(with_share(50, 2)), "paper.tex")) == 1


def test_a_short_document_is_never_read_as_a_profile():
    # Below 40 prose sentences no share is judged, in either direction.
    assert _R12_SHARE_MIN_SENTENCES == 40
    assert _rule_12_profile(paper(with_share(39, 0)), "paper.tex") == []
    assert _rule_12_profile(paper(with_share(39, 39, long_words=35)), "paper.tex") == []
    assert len(_rule_12_profile(paper(with_share(40, 0)), "paper.tex")) == 1


def test_a_short_sentence_is_not_prose_and_does_not_count():
    # Two-word labels do not enter the denominator: 50 long-and-short sentences plus 30
    # fragments keep the share of the 50.
    labels = ["Fig one.", "Table two."] * 15
    assert _rule_12_profile(paper(with_share(50, 15) + labels), "paper.tex") == []


def test_a_latex_section_file_or_fragment_never_triggers_the_share_check():
    # No \begin{document}: a section file holds one part of a paper, however long it runs.
    for count in (50, 200, 800):
        text = tex(with_share(count, 0))
        assert _rule_12_profile(text, "04-method.tex") == [], count
        assert _rule_12_profile(text, "paper.tex") == [], count
    assert _rule_12_profile("\\begin{abstract}\n" + paragraphs(with_share(200, 0)) + "\\end{abstract}\n", "abstract.tex") == []


def test_a_commented_begin_document_does_not_make_a_whole_document():
    text = "% \\begin{document}\n\\section{Results}\n" + paragraphs(with_share(50, 0))
    assert _rule_12_profile(text, "paper.tex") == []


@pytest.mark.parametrize("declaration", [
    "{beamer}", "[t]{beamer}", "[11pt]{letter}", "{moderncv}", "[ aspectratio=169 ]{beamer}", "{powerdot}",
    "{tikzposter}", "{scrlttr2}", "{a0poster}", "{awesome-cv}", "{styles/Beamer}",
])
def test_slides_letters_and_cvs_are_not_papers(declaration):
    text = "\\documentclass" + declaration + "\n\\begin{document}\n" + paragraphs(with_share(80, 0)) + "\\end{document}\n"
    assert _rule_12_profile(text, "talk.tex") == [], declaration


def test_a_paper_class_with_options_is_read():
    text = "\\documentclass[11pt,twocolumn]{article}\n\\begin{document}\n" + paragraphs(with_share(80, 0)) + "\\end{document}\n"
    assert len(_rule_12_profile(text, "paper.tex")) == 1
    acm = "\\documentclass[sigconf]{acmart}\n\\begin{document}\n" + paragraphs(with_share(80, 0)) + "\\end{document}\n"
    assert len(_rule_12_profile(acm, "paper.tex")) == 1


@pytest.mark.parametrize("count, long_count", [(50, 0), (160, 0), (160, 160), (800, 0), (800, 800)])
def test_markdown_and_text_never_get_a_share_check(count, long_count):
    # Nothing in a Markdown file shows that it is whole or what genre it is. A section
    # file such as intro.md, a design note with an Introduction and a Conclusion, a
    # paper draft and a file with a front-matter title are all left alone, at any length
    # and at any share, in either direction.
    sentences = with_share(count, long_count)
    abstract = md_paper(sentences, "# Abstract")
    design = (
        "# Design\n\n## Introduction\n\n" + paragraphs(sentences[:count // 2])
        + "\n## Conclusion\n\n" + paragraphs(sentences[count // 2:]) + "\n## References\n\nOne source.\n"
    )
    cases = [
        (abstract, "draft.md"),
        (abstract, "notes.md"),
        (paragraphs(sentences), "intro.md"),
        (paragraphs(sentences), "abstract.txt"),
        (md_paper(sentences, "## 1. Introduction"), "paper.md"),
        (design, "design.md"),
        (design, "design.txt"),
        (design, ""),
        ("# Introduction\n\n" + paragraphs(sentences) + "\n# Conclusion\n\nDone for now.\n", "rfc.md"),
    ]
    for text, name in cases:
        assert _rule_12_profile(text, name) == [], (name, count, long_count)
    assert _rule_12_profile(abstract) == []


def test_a_markdown_file_is_never_a_whole_document():
    for text, name in ((md_paper(with_share(200, 0)), "draft.md"), (paragraphs(with_share(200, 0)), "intro.md")):
        assert _pf_whole_document(_pf_document(text, name)) is False, name
    assert _pf_whole_document(_pf_document(paper(with_share(50, 10)), "paper.tex")) is True
    assert not hasattr(detectors_mech, "_R12_SHARE_MIN_SENTENCES_TEXT")


def test_markdown_tables_headings_and_code_are_not_counted():
    sentences = with_share(150, 30)
    noise = "| a | b |\n|---|---|\n| " + " ".join(["gadget"] * 100) + " | x |\n\n```\n" + " ".join(["river"] * 100) + ".\n```\n"
    text = "# Abstract\n\n" + paragraphs(sentences) + "\n" + noise
    assert _rule_12_profile(text, "draft.md") == []
    assert lengths(text, "draft.md") == [len(s.split()) for s in sentences]


# ---------- a complete LaTeX document, and nothing less -----------------------------------


def latex_doc(body: str, preamble: str = "", end: bool = True) -> str:
    return "\\documentclass{article}\n" + preamble + "\\begin{document}\n" + body + ("\\end{document}\n" if end else "")


def test_a_main_file_that_pulls_its_sections_in_is_not_a_whole_document():
    # 40 clipped introduction sentences, then the other sections as \input lines. The prose
    # of the paper is elsewhere, so 40 short sentences say nothing about its profile.
    intro = "\\section{Introduction}\n" + paragraphs(with_share(40, 0))
    flat = latex_doc(intro)
    assert len(_rule_12_profile(flat, "main.tex")) == 1  # the same text, whole, is read
    for command in ("\\input{methods}", "\\input{sections/results.tex}", "\\include{results}",
                    "\\subfile{sections/results}", "\\subfileinclude{results}", "\\input {methods}"):
        main = latex_doc(intro + "\n" + command + "\n\\input{conclusion}\n")
        assert _rule_12_profile(main, "main.tex") == [], command
        assert _pf_whole_document(_pf_document(main, "main.tex")) is False, command
    # The include sits before the prose, after it, or inside a paragraph.
    for body in ("\\input{head}\n" + intro, intro + "\\input{tail}\n", intro.replace("\n\n", "\n\\input{mid}\n\n", 1)):
        assert _rule_12_profile(latex_doc(body), "main.tex") == [], body[:20]


def test_an_input_of_a_generated_table_or_a_figure_keeps_the_document_whole():
    body = "\\section{Results}\n" + paragraphs(with_share(40, 0))
    for wrapped in ("\\begin{table}\n\\input{tables/main.tex}\n\\end{table}\n",
                    "\\begin{figure}\n\\input{figs/plot.tex}\n\\end{figure}\n",
                    "\\begin{table*}\\centering\\input{tables/main}\\end{table*}\n"):
        found = _rule_12_profile(latex_doc(body + wrapped), "paper.tex")
        assert len(found) == 1 and "none of the 40 sentences" in found[0].detail, wrapped


def test_an_input_in_the_preamble_or_in_a_comment_or_a_longer_command_name_is_not_a_body_include():
    body = "\\section{Results}\n" + paragraphs(with_share(40, 0))
    for text in (
        latex_doc(body, preamble="\\input{macros}\n\\include{more}\n"),
        latex_doc(body + "% \\input{methods}\n"),
        latex_doc(body + "\\includegraphics[width=3cm]{plot}\n\\inputminted{python}{x.py}\n"),
        latex_doc(body + "\\includepdf{poster}\n\\inputenc\n"),
    ):
        assert len(_rule_12_profile(text, "paper.tex")) == 1, text[-60:]


def test_a_fragment_with_only_one_end_of_the_document_is_not_whole():
    body = "\\section{Results}\n" + paragraphs(with_share(60, 0))
    begin_only = latex_doc(body, end=False)
    end_only = "\\documentclass{article}\n" + body + "\\end{document}\n"
    backwards = "\\end{document}\n\\documentclass{article}\n\\begin{document}\n" + body
    for text in (begin_only, end_only, backwards, "\\begin{document}\n" + body, body + "\\end{document}\n"):
        assert _rule_12_profile(text, "edit.tex") == [], text[:40]
    assert len(_rule_12_profile(latex_doc(body), "edit.tex")) == 1


def test_a_commented_end_of_the_document_does_not_complete_it():
    body = "\\section{Results}\n" + paragraphs(with_share(60, 0))
    text = latex_doc(body, end=False) + "% \\end{document}\n"
    assert _rule_12_profile(text, "paper.tex") == []


def test_hard_wrapped_lines_join_into_one_sentence():
    # A paragraph wrapped at 60 columns is one sentence, not eleven lines of six words.
    words = ["gadget"] * 84
    wrapped = "\n".join(" ".join(words[i:i + 6]) for i in range(0, len(words), 6)) + ".\n"
    found = _rule_12_profile("\\section{Method}\n" + wrapped, "paper.tex")
    assert len(found) == 1 and "a sentence of 84 words" in found[0].detail
    shorter = "\n".join(" ".join(words[i:i + 6]) for i in range(0, 44, 6)) + ".\n"
    assert _rule_12_profile("\\section{Method}\n" + shorter + "\n" + paragraphs(with_share(50, 12)), "paper.tex") == []


def test_the_preamble_and_the_title_page_are_not_prose():
    front = (
        "\\documentclass{article}\n\\title{" + " ".join(["gadget"] * 90) + "}\n"
        "\\author{" + " ".join(["River Lantern."] * 60) + "}\n\\begin{document}\n\\maketitle\n"
    )
    text = front + "\\section{Results}\n" + paragraphs(with_share(50, 10)) + "\\end{document}\n"
    assert _rule_12_profile(text, "paper.tex") == []


# ---------- ", so" clause joins ----------------------------------------------------------


def so_text(joins: int, words_target: int, phrase: str = "so the") -> str:
    """About ``words_target`` words of 14-word sentences, ``joins`` of them joined with ", so"."""
    sentences = []
    count = max(1, words_target // 14)
    for i in range(count):
        if i < joins:
            sentences.append("The " + " ".join(WORDS[(i + j) % 8] for j in range(6)) + ", " + phrase + " "
                             + " ".join(WORDS[(i + j) % 8] for j in range(5)) + ".")
        else:
            sentences.append(sentence(14, seed=i))
    return paragraphs(sentences, per_paragraph=6)


def only_so(found) -> list:
    return [v for v in found if "join clauses" in v.detail]


def test_many_so_joins_are_reported_once():
    found = only_so(_rule_12_profile(so_text(10, 2000), "paper.tex"))
    assert len(found) == 1
    assert found[0].rule == "RULE-12"
    assert found[0].detail.startswith(_PF_DOCUMENT_PREFIX + '10 sentences join clauses with ", so"')
    assert "human-written papers rarely pass 1" in found[0].detail
    assert found[0].line == 1


def test_so_joins_need_density_and_count_and_words():
    assert (_R12_SO_DENSITY, _R12_SO_MIN_COUNT, _R12_SO_MIN_WORDS) == (1.5, 6, 1000)
    # Density: 6 joins in 5,000 words is 1.2 per 1,000.
    assert only_so(_rule_12_profile(so_text(6, 5000), "paper.tex")) == []
    assert len(only_so(_rule_12_profile(so_text(8, 5000), "paper.tex"))) == 1
    # Count: 5 joins in 1,400 words is dense but below 6.
    assert only_so(_rule_12_profile(so_text(5, 1400), "paper.tex")) == []
    assert len(only_so(_rule_12_profile(so_text(6, 1400), "paper.tex"))) == 1


def test_a_fragment_under_a_thousand_words_never_reports_so_joins():
    # Ten joins in a 700-word edit would be 14 per 1,000 words; it is still an edit.
    assert only_so(_rule_12_profile(so_text(10, 700), "paper.tex")) == []
    assert only_so(_rule_12_profile("The gadget moved, so the river rose.", "notes.md")) == []


def test_so_joins_are_read_in_any_latex_file_but_not_in_slides_or_letters():
    # A section file is a paper context: the density does not depend on the whole paper.
    assert len(only_so(_rule_12_profile(so_text(10, 2000), "03-method.tex"))) == 1
    assert len(only_so(_rule_12_profile(whole(so_text(10, 2000)), "paper.tex"))) == 1
    for cls in ("beamer", "letter", "moderncv"):
        text = "\\documentclass{%s}\n\\begin{document}\n" % cls + so_text(10, 2000) + "\\end{document}\n"
        assert only_so(_rule_12_profile(text, "talk.tex")) == [], cls


def test_so_joins_are_read_only_in_latex():
    # Notes, changelogs and design documents carry the join by design, and an Abstract
    # or Introduction heading opens design notes too: Markdown and text are never read.
    body = so_text(30, 2000)
    for name in ("CHANGELOG.md", "notes.md", "guard-hook.md", "design.txt", "draft.md", "intro.md"):
        assert only_so(_rule_12_profile(body, name)) == [], name
        for head in ("# Notes\n\n", "# Abstract\n\n", "## 1. Introduction\n\n"):
            assert only_so(_rule_12_profile(head + body, name)) == [], (head, name)
    # A LaTeX section file is read: the density and the word count decide.
    assert len(only_so(_rule_12_profile("\\section{Results}\n" + body, "results.tex"))) == 1
    assert len(only_so(_rule_12_profile("\\section{Results}\n" + so_text(10, 1500), "results.tex"))) == 1


def test_a_file_name_does_not_make_a_text_file_a_paper():
    body = so_text(10, 2000)
    for name in ("abstract.md", "intro.md", "introduction.md", "01-introduction.md", "paper_abstract.txt", "my intro.md",
                 "introspection.md", "notes.md"):
        assert only_so(_rule_12_profile(body, name)) == [], name


@pytest.mark.parametrize("heading", ["# Abstract", "## Introduction", "## 1. Introduction", "# **Abstract**", "### introduction"])
def test_an_abstract_or_introduction_heading_does_not_make_markdown_a_paper(heading):
    assert only_so(_rule_12_profile(md_paper(so_sentences_text(10, 2000), heading), "draft.md")) == [], heading


@pytest.mark.parametrize("heading", ["## Introduction to the harbor", "## Abstractions", "## Introductions", "## Intro"])
def test_a_heading_must_be_titled_abstract_or_introduction(heading):
    assert only_so(_rule_12_profile(md_paper(so_sentences_text(10, 2000), heading), "notes.md")) == [], heading


def so_sentences_text(joins: int, words_target: int) -> list:
    """The sentences of ``so_text`` as a list, for a Markdown body."""
    return [s for s in re.split(r"(?<=\.)\s+", so_text(joins, words_target).strip()) if s]


@pytest.mark.parametrize("phrase", [
    "so that the", "so far the", "so on the", "so forth the", "so as to the", "so much the",
    "so many the", "so long the", "so few the", "so little the", "so often the", "so well the",
])
def test_so_phrases_are_not_clause_joins(phrase):
    assert only_so(_rule_12_profile(so_text(40, 2000, phrase=phrase), "paper.tex")) == []


def test_so_called_is_not_a_clause_join():
    text = so_text(0, 2000).replace("The gadget", "The so-called gadget")
    sentences = ["The gadget works, so-called by many, and the rest follows."] * 12
    assert only_so(_rule_12_profile(text + paragraphs(sentences), "paper.tex")) == []


def test_so_before_math_or_a_quote_is_a_clause_join_in_latex():
    sentences = [f"The gadget {i} moved the river, so $x_{i}$ grew across the harbor and the meadow." for i in range(10)]
    text = paragraphs(sentences) + so_text(0, 1500)
    assert len(only_so(_rule_12_profile(text, "paper.tex"))) == 1


def test_so_joins_in_comments_and_code_do_not_count():
    sentence_so = "The gadget moved the river, so the lantern rose over the orchard and the meadow."
    commented = "".join("% " + sentence_so + "\n" for _ in range(20))
    assert only_so(_rule_12_profile(commented + so_text(0, 2000), "paper.tex")) == []
    fenced = "```\n" + "\n".join([sentence_so] * 20) + "\n```\n\n"
    assert only_so(_rule_12_profile("# Abstract\n\n" + fenced + so_text(0, 2000), "draft.md")) == []


# ---------- the order of the findings and the document-level marker -------------------------


def test_all_three_checks_can_report_in_one_document_in_a_fixed_order():
    so_sentences = ["The gadget moved the river, so the lantern rose over the orchard today."] * 12
    text = paper(so_sentences + with_share(50, 30) + [sentence(90)])
    found = _rule_12_profile(text, "paper.tex")
    # Findings about the document come first, the sentence finding last, wherever they sit in the file.
    assert kinds_of(found) == ["share", "so", "extreme"]


def test_the_extreme_finding_comes_last_even_when_it_sits_before_the_others_in_the_file():
    so_sentences = ["The gadget moved the river, so the lantern rose over the orchard today."] * 12
    text = paper([sentence(90)] + so_sentences + with_share(50, 30))
    found = _rule_12_profile(text, "paper.tex")
    assert kinds_of(found) == ["share", "so", "extreme"]
    # The join sits after the long sentence in the file, and its finding still comes first.
    assert (found[1].line, found[1].column) > (found[2].line, found[2].column)


def test_a_hook_that_shows_the_first_findings_sees_the_document_ones():
    # 30 extreme sentences make one finding. The profile never fills a cap of five on its own.
    so_sentences = ["The gadget moved the river, so the lantern rose over the orchard today."] * 12
    text = paper(so_sentences + with_share(50, 30) + [sentence(85 + i, seed=i) for i in range(30)])
    found = _rule_12_profile(text, "paper.tex")
    assert kinds_of(found) == ["share", "so", "extreme"] and len(found) == 3


def test_document_level_findings_start_with_the_marker_and_the_extreme_finding_does_not():
    assert _PF_DOCUMENT_PREFIX == "Across the document, "
    so_sentences = ["The gadget moved the river, so the lantern rose over the orchard today."] * 12
    text = paper(so_sentences + with_share(50, 30) + [sentence(90)])
    found = _rule_12_profile(text, "paper.tex")
    flags = [v.detail.startswith(_PF_DOCUMENT_PREFIX) for v in found]
    assert flags == [True, True, False]
    low = _rule_12_profile(paper(with_share(50, 0)), "paper.tex")
    assert [v.detail.startswith(_PF_DOCUMENT_PREFIX) for v in low] == [True]
    single = _rule_12_profile(tex([sentence(90)]), "paper.tex")
    assert not single[0].detail.startswith(_PF_DOCUMENT_PREFIX)


# ---------- shape ----------------------------------------------------------------------


def test_the_message_describes_a_departure_and_never_a_violation():
    texts = [
        tex([sentence(90)]),
        tex([sentence(90), sentence(100)]),
        paper(with_share(50, 30)),
        paper(with_share(50, 0)),
        so_text(10, 2000),
    ]
    for text in texts:
        for v in _rule_12_profile(text, "paper.tex"):
            assert "violation" not in v.detail.lower()
            assert "human-written" in v.detail
            assert "consider" in v.detail
            assert v.detail.count(". ") <= 1  # one or two sentences, like the RULE-03 messages
            assert v.column >= 1 and v.line >= 1 and v.excerpt


def test_signature_and_defaults_match_rule_03():
    assert _rule_12_profile(paper(with_share(50, 30))) == _rule_12_profile(paper(with_share(50, 30)), None)
    assert _rule_12_profile(paper(with_share(50, 30)), file_path="paper.tex") == _rule_12_profile(
        paper(with_share(50, 30)), "paper.tex"
    )


@pytest.mark.parametrize("bad", ["", None, 12, b"bytes", ["a"], "\x00\x00", "\\begin{document}", "\\author{", "---\nname:", "\\footnote{"])
def test_it_never_raises(bad):
    assert _rule_12_profile(bad, "paper.tex") == []
    assert _rule_12_profile(bad) == []


def test_crlf_and_bare_cr_keep_line_numbers():
    source = "\\section{Results}\n" + sentence(12) + "\n\n" + sentence(100) + "\n"
    found = _rule_12_profile(source.replace("\n", "\r\n"), "paper.tex")
    assert len(found) == 1 and found[0].line == 4
    assert _rule_12_profile(source.replace("\n", "\r"), "paper.tex")[0].line == 4


# ---------- the CLI audit and the bench scope do not move -------------------------------


def test_the_registered_detectors_and_the_audit_scope_are_unchanged():
    assert set(detectors_mech._DISPATCH) == {
        "RULE-B", "RULE-D", "RULE-G", "RULE-I", "RULE-12", "RULE-05", "RULE-06", "RULE-03", "RULE-A",
    }
    assert detectors_mech._DISPATCH["RULE-12"] is _rule_12
    assert detectors_mech._FILE_PATH_RULES == frozenset({"RULE-03", "RULE-A"})
    assert primitive._CLASSIFICATION["RULE-12"] == {"mechanical"}
    assert primitive._CLASSIFICATION["RULE-08"] == {"semantic"}


def test_the_cli_audit_still_flags_every_sentence_over_thirty_words(tmp_path):
    source = tmp_path / "draft.md"
    source.write_text("# Notes\n\n" + sentence(35) + "\n\n" + sentence(80) + "\n", encoding="utf-8")
    for only in (True, False):
        result = audit(str(source), mechanical_only=only)
        rule12 = [r for r in result.rule_results if r.rule == "RULE-12"]
        assert len(rule12) == 1 and rule12[0].detector == "mechanical"
        assert [v.detail for v in rule12[0].violations] == [
            "sentence length 35 words (>30)", "sentence length 80 words (>30)",
        ]
        mech = {r.rule for r in result.rule_results if r.detector == "mechanical"}
        assert "RULE-08" not in mech
        assert not any("human-written" in v.detail for r in result.rule_results for v in r.violations)


def test_run_dispatches_rule_12_to_the_per_sentence_detector():
    rule = SimpleNamespace(id="RULE-12", severity="low")
    result = detectors_mech.run(rule, sentence(35), "paper.tex")
    assert result.count == 1 and result.violations[0].detail == "sentence length 35 words (>30)"
    assert detectors_mech.run(SimpleNamespace(id="RULE-08", severity="low"), sentence(35), "paper.tex").status == "skipped"


def test_the_benchmark_scope_is_unchanged():
    rescore_path = Path(__file__).resolve().parent.parent.parent.parent / "scripts" / "bench" / "rescore.py"
    if not rescore_path.is_file():
        pytest.skip(f"missing (not a source checkout): {rescore_path}")
    bench = str(rescore_path.parent)
    if bench not in sys.path:
        sys.path.insert(0, bench)
    spec = importlib.util.spec_from_file_location("agent_style_rescore_scope", rescore_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    assert module.EXPECTED_MECHANICAL == {
        "RULE-05", "RULE-06", "RULE-12", "RULE-B", "RULE-D", "RULE-G", "RULE-I",
    }


# ---------- speed --------------------------------------------------------------------


def test_a_large_document_is_read_quickly():
    import time

    body = paragraphs([sentence(18 + (i % 30), seed=i) for i in range(4000)])
    text = "\\documentclass{article}\n\\begin{document}\n\\section{Results}\n" + body + "\\end{document}\n"
    assert len(text) > 400_000
    started = time.time()
    _rule_12_profile(text, "paper.tex")
    assert time.time() - started < 5.0


def test_hostile_inputs_are_fast():
    import time

    hostile = [
        (", so " * 50_000, "paper.tex"),
        ("$" * 100_000, "paper.tex"),
        ("\\author{" * 20_000, "paper.tex"),
        ("{" * 100_000, "paper.tex"),
        ("The gadget moved. " * 30_000, "paper.tex"),
        ("\\begin{equation}\n" * 20_000, "paper.tex"),
        ("\\footnote{" * 20_000, "paper.tex"),
        ("\\footnote{a}" * 20_000, "paper.tex"),
        ("\\acks " * 20_000, "paper.tex"),
        ("\\section{Acknowledgments}\n" * 20_000, "paper.tex"),
        ("## Acknowledgments\n" * 20_000, "notes.md"),
        ("---\nname: x\n" + "a: b\n" * 50_000, "notes.md"),
        ("foo" + "_" * 40_000 + "bar. " + "The gadget moved. " * 10, "notes.md"),
        ("foo" + "*" * 40_000 + "bar. " + "The gadget moved. " * 10, "notes.md"),
        ("# Abstract\n" + "x_" * 40_000, "notes.md"),
        ("[^" * 100_000, "notes.md"),
        ("[^a" * 100_000 + "]", "notes.md"),
        ("[^1]: x\n" * 30_000, "notes.md"),
        ("[^1]: x\n\n    y\n\n" * 20_000, "notes.txt"),
        ("[^1]:\n" + "    z\n\n" * 20_000, "notes.txt"),
        ("A note.[^1] " * 20_000, "notes.md"),
        ("\\documentclass{article}\\begin{document}" + "\\input{a} " * 20_000 + "\\end{document}", "paper.tex"),
        ("\\documentclass{article}\\begin{document}" + "\\begin{figure}\\input{a}\\end{figure}" * 20_000
         + "\\end{document}", "paper.tex"),
        ("\\documentclass{article}\\begin{document}" + "\\begin{figure}\\input{a} " * 20_000 + "\\end{document}",
         "paper.tex"),
    ]
    for text, name in hostile:
        started = time.time()
        _rule_12_profile(text, name)
        assert time.time() - started < 5.0, text[:20]


def test_a_long_underscore_run_is_linear():
    import time

    text = "foo" + "_" * 40_000 + "bar. " + "The gadget moved over the harbor today. " * 20
    started = time.time()
    _PF_EMPHASIS_RE.sub("", text)
    assert time.time() - started < 0.5
    started = time.time()
    _rule_12_profile(text, "notes.md")
    assert time.time() - started < 1.0


def test_emphasis_markers_are_removed_only_when_a_non_word_character_flanks_them():
    for raw, expected in [
        ("a **bold** b", "a bold b"),
        ("_emph_ x", "emph x"),
        ("snake_case_name here", "snake_case_name here"),
        ("__init__ call", "init call"),
        ("x * y * z", "x  y  z"),
        ("2*3=6", "2*3=6"),
    ]:
        assert _PF_EMPHASIS_RE.sub("", raw) == expected, raw
