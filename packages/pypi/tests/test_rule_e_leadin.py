# SPDX-License-Identifier: MIT
"""RULE-E treats a sentence that ends in a colon as a lead-in, not a closer.

The House Style ends an introduction with "In summary, the key contributions of
this work include:" and a list, so a detector that flagged that line would
contradict the pack's own instruction.
"""

from __future__ import annotations

from agent_style.review.detectors_struct import _rule_e

LEAD_IN = "In summary, the key contributions of this work include:"
ITEMS = "- **First approach.** We propose a method.\n- **Effectiveness.** We show gains on two testbeds.\n"


def test_lead_in_on_its_own_line_is_not_a_closer() -> None:
    assert _rule_e(f"Model selection without labels is hard.\n\n{LEAD_IN}\n\n{ITEMS}") == []


def test_lead_in_closing_a_paragraph_is_not_a_closer() -> None:
    assert _rule_e(f"Model selection without labels is hard. {LEAD_IN}\n\n{ITEMS}") == []


def test_lead_in_followed_directly_by_a_list_is_not_a_closer() -> None:
    # CommonMark lets a list follow its lead-in without a blank line.
    assert _rule_e(f"{LEAD_IN}\n{ITEMS}") == []
    assert _rule_e(f"Model selection without labels is hard. {LEAD_IN}\n1. We propose a method.\n2. We show gains.\n") == []


def test_lead_in_followed_directly_by_a_latex_list_is_not_a_closer() -> None:
    for env in ("itemize", "enumerate"):
        tex = (f"{LEAD_IN}\n\\begin{{{env}}}\n\\item \\textbf{{Method.}} We introduce a method.\n"
               f"\\item \\textbf{{Effectiveness.}} We report measured accuracy.\n\\end{{{env}}}\n")
        assert _rule_e(tex) == []


def test_summary_closer_is_still_flagged() -> None:
    found = _rule_e("We trained the model on five benchmarks. In summary, the method works well.\n")
    assert [v.rule for v in found] == ["RULE-E"]
