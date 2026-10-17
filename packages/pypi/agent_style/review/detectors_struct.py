# SPDX-License-Identifier: MIT
"""Structural detectors: line/paragraph-level heuristics.

Rules with deterministic structural detectors:
  RULE-A  bullet overuse (lists whose items read as prose shredded into bullets)
  RULE-C  consecutive same-starts (≥ 2 of 3 adjacent sentences share opening token)
  RULE-E  paragraph-closing summaries (last sentence restates the paragraph topic)

Rules in the structural bucket that still have no detector and report
"skipped" (as of v0.7.0):
  RULE-02  passive voice when agent matters
  RULE-07  positive form for affirmative claims
  RULE-09  parallel structure across coordinate items
  RULE-10  keep related words together (subject/verb proximity)

These skipped rules return ``status="skipped"`` with a note explaining why, so
the JSON output remains schema-complete for every rule in the matrix.
"""

from __future__ import annotations

import re
from typing import Callable

from agent_style.review.loader import Rule
from agent_style.review.primitive import RuleResult, Violation


def run(rule: Rule, text: str, file_path: str) -> RuleResult:
    """Dispatch to the structural detector for ``rule.id``."""
    func = _DISPATCH.get(rule.id)
    if func is None:
        return RuleResult(
            rule=rule.id,
            severity=rule.severity,
            detector="structural",
            status="skipped",
            count=0,
            note=f"structural detector for {rule.id} is deferred to a future release",
        )
    violations = func(text)
    status = "violation" if violations else "ok"
    return RuleResult(
        rule=rule.id,
        severity=rule.severity,
        detector="structural",
        status=status,
        count=len(violations),
        violations=violations,
    )


# ---------- Helpers ---------------------------------------------------------


def _excerpt(text: str, span: tuple[int, int], width: int = 120) -> str:
    start = max(0, span[0] - 10)
    end = min(len(text), start + width)
    out = text[start:end].strip()
    if start > 0:
        out = "…" + out
    if end < len(text):
        out = out + "…"
    return out


_FENCE_OPEN_RE = re.compile(r"^\s*(```|~~~)")


def _fence_mask(text: str) -> list[bool]:
    """Return a list parallel to text.splitlines() marking lines inside fences."""
    lines = text.splitlines()
    inside = False
    mask = []
    for line in lines:
        if _FENCE_OPEN_RE.match(line):
            inside = not inside
            mask.append(True)  # fence markers themselves count as inside
            continue
        mask.append(inside)
    return mask


def _paragraphs(text: str) -> list[tuple[int, list[str]]]:
    """Yield (start_line_number, paragraph_lines) for each prose paragraph.

    Skips fenced code blocks and table rows entirely.
    """
    lines = text.splitlines()
    fence = _fence_mask(text)
    out: list[tuple[int, list[str]]] = []
    cur_start = None
    cur_lines: list[str] = []
    for i, line in enumerate(lines, start=1):
        idx = i - 1
        if fence[idx] or line.lstrip().startswith(("|", "#", ">")):
            if cur_lines:
                out.append((cur_start or 1, cur_lines))
                cur_start, cur_lines = None, []
            continue
        if not line.strip():
            if cur_lines:
                out.append((cur_start or 1, cur_lines))
                cur_start, cur_lines = None, []
            continue
        if cur_start is None:
            cur_start = i
        cur_lines.append(line)
    if cur_lines:
        out.append((cur_start or 1, cur_lines))
    return out


def _sentences_in_paragraph(lines: list[str]) -> list[str]:
    """Join paragraph lines and split into sentences."""
    joined = " ".join(l.strip() for l in lines)
    # Conservative sentence splitter: period/exclamation/question followed by space + capital.
    raw = re.split(r"(?<=[.!?])\s+(?=[A-Z\"'\(\[])", joined)
    return [s.strip() for s in raw if s.strip()]


def _first_word(sentence: str) -> str:
    m = re.match(r"[A-Za-z][A-Za-z'-]*", sentence.lstrip())
    return m.group(0).lower() if m else ""


# ---------- RULE-A bullet overuse -------------------------------------------


# Groups: (1) leading indentation, (2) marker, (3) item content. The indent is
# captured so a nested list is not collected into its parent's group.
_BULLET_RE = re.compile(r"^(\s*)([*+-]|\d+\.)\s+(.*)$")


def _indent_columns(indent: str, tab_stop: int = 4) -> int:
    """Width of ``indent`` in columns, expanding tabs to the next tab stop.

    Comparing raw character length would call one space and one tab the same
    depth, and four spaces and one tab different depths, so a list's nesting
    would depend on which whitespace the author typed.
    """
    width = 0
    for ch in indent:
        width += tab_stop - (width % tab_stop) if ch == "\t" else 1
    return width

# Coordinators, subordinators and relative pronouns. An item opening with one
# of these points back at something the bullet was severed from. Bare
# prepositions are deliberately absent: `For Linux, use apt` heads a genuine
# per-platform enumeration, so treating `for`/`to`/`with`/`from` as evidence
# flags exactly the lists RULE-A's directive permits.
_CONNECTIVE_OPENERS = frozenset(
    """
    and but or nor so yet because therefore thus hence however although though
    while whereas since unless until then also moreover furthermore
    additionally rather which who whom whose that
    """.split()
)
# A repeated template is only evidence when it is an actual clause opening.
# Keying on the first two words of anything flags `Run the migration` /
# `Run the tests`, which is the directive's own checklist case.
_CLAUSE_SUBJECTS = frozenset(
    {"i", "we", "you", "he", "she", "it", "they", "this", "that", "these", "those"}
)
_COPULAS = frozenset({"am", "are", "is", "was", "were"})


def _item_words(content: str) -> list[str]:
    """Lowercase word tokens of a list item, punctuation and emphasis stripped."""
    return [w.strip(".,;:!?()[]`\"'*_~").lower() for w in content.split()]


def _reads_as_shredded_prose(items: list[tuple[int, str]]) -> tuple[str, str] | None:
    """Name the shape that marks the items as one sentence split across bullets.

    Returns ``(strength, reason)``, or None when the list reads as a genuine
    enumeration. A ``strong`` signal is self-sufficient evidence; a ``weak`` one
    only counts when every item is also short.
    """
    tokenized = [[w for w in _item_words(content) if w] for _, content in items]
    for words in tokenized:
        # A bare `And` / `But` / `Or` is a label, not connective tissue. Only a
        # connective that actually leads into something continues a sentence.
        if len(words) > 1 and words[0] in _CONNECTIVE_OPENERS:
            return "strong", f"an item opens with the connective '{words[0]}'"
    # `Per minute` / `Per user` trailing `Free tier` are fragments continuing a
    # stem. Two boundaries keep this from swallowing genuine enumerations: a
    # list where *every* item leads with `per` is a real enumeration, and so is
    # one where only a single item does not (`Global` / `Per user` /
    # `Per project`). Fragments need at least two items to continue from.
    per_count = sum(bool(words) and words[0] == "per" for words in tokenized)
    if 1 < per_count < len(tokenized) - 1:
        return "strong", "later items are repeated 'per' fragments"
    templates: dict[tuple[str, str], int] = {}
    for words in tokenized:
        if len(words) < 2 or words[0] not in _CLAUSE_SUBJECTS or words[1] not in _COPULAS:
            continue
        key = (words[0], words[1])
        templates[key] = templates.get(key, 0) + 1
        if templates[key] >= 2:
            return "weak", f"items repeat the clause template '{key[0]} {key[1]}'"
    return None


def _rule_a(text: str) -> list[Violation]:
    """Flag short lists that read as fragmented prose rather than enumeration.

    The marker is not evidence either way: RULE-A's directive permits genuine
    enumerations (API endpoints, config options, checklist steps) without
    privileging ordered over unordered, and a numbered causal chain is exactly
    the fragmented prose the rule targets. Shortness is not evidence on its own
    either -- a checklist of terse imperative steps is short *and* genuine.

    So the test is the directive's own: "bullets are sentence shards with
    connective tissue stripped". Two shapes betray a shredded sentence, graded
    by how much they prove on their own:

    1. **Strong.** An item opens with a coordinator, subordinator or relative
       pronoun (``Because``, ``Which``, ``And``, ``Rather``), or some but not
       all items lead with ``Per``. Either is self-sufficient evidence, so it
       fires regardless of item length; an explicit ``Because`` shard is no
       less a shard for sitting in a list with one long item.
    2. **Weak.** Two or more items repeat a subject-and-copula opening
       (``It is fast`` / ``It is accurate``). Only counts when every item is
       also short.

    Bare prepositions are not evidence, and neither is an arbitrary repeated
    first-two-words key. ``For Linux, use apt`` heads a genuine per-platform
    enumeration and ``Run the migration`` / ``Run the tests`` is the
    directive's own checklist case; both stay clean, as do short independent
    labels. The cost is recall on ambiguous triads such as ``It accelerates
    retrieval`` / ``It improves accuracy``, where the second token varies.
    Those need a semantic judge, not a sharper regex.
    """
    out: list[Violation] = []
    lines = text.splitlines()
    fence = _fence_mask(text)
    i = 0
    while i < len(lines):
        if fence[i]:
            i += 1
            continue
        m = _BULLET_RE.match(lines[i])
        if not m:
            i += 1
            continue
        # Start of a bullet group; collect the siblings of this bullet. Ignoring
        # indentation flattens a nested list into its parent, so `- Rate limits:`
        # plus two indented `- Per …` children reads as one three-item group
        # that no author wrote. Deeper lines are skipped rather than ending the
        # group, so a parent list that resumes after a nested block stays one
        # list.
        group_start = i + 1  # 1-indexed line number
        group_indent = _indent_columns(m.group(1))
        items: list[tuple[int, str]] = []
        while i < len(lines) and not fence[i]:
            bullet = _BULLET_RE.match(lines[i])
            if not bullet:
                break
            indent = _indent_columns(bullet.group(1))
            if indent > group_indent:
                i += 1  # a child of the current item, not a sibling
                continue
            if indent < group_indent:
                break
            items.append((i + 1, bullet.group(3).strip()))
            i += 1
        n = len(items)
        short_items = sum(1 for _, content in items if len(content.split()) <= 8)
        signal = _reads_as_shredded_prose(items) if n >= 3 else None
        if signal is not None and (signal[0] == "strong" or short_items == n):
            reason = signal[1]
            out.append(
                Violation(
                    rule="RULE-A",
                    line=group_start,
                    column=1,
                    excerpt=_excerpt(lines[group_start - 1], (0, len(lines[group_start - 1]))),
                    detail=f"list has {n} items and {reason}; consider prose",
                )
            )
    return out


# ---------- RULE-C consecutive same-starts ----------------------------------


def _rule_c(text: str) -> list[Violation]:
    """Flag when ≥ 2 of any 3 consecutive sentences share their opening word."""
    out: list[Violation] = []
    for start_line, para_lines in _paragraphs(text):
        sentences = _sentences_in_paragraph(para_lines)
        if len(sentences) < 2:
            continue
        firsts = [_first_word(s) for s in sentences]
        for i in range(len(firsts) - 1):
            # Window of 3 (or 2 at the tail): flag if ≥ 2 match.
            window = firsts[i : i + 3]
            if len(window) < 2:
                continue
            # Count duplicates in the window.
            seen: dict[str, int] = {}
            for w in window:
                if not w:
                    continue
                seen[w] = seen.get(w, 0) + 1
            if any(count >= 2 for word, count in seen.items() if word):
                # Report the first offending sentence's starting word.
                dup_word = next(w for w, c in seen.items() if c >= 2 and w)
                out.append(
                    Violation(
                        rule="RULE-C",
                        line=start_line,
                        column=1,
                        excerpt=_excerpt(sentences[i], (0, len(sentences[i]))),
                        detail=f"consecutive sentences start with '{dup_word}'",
                    )
                )
                break  # one finding per paragraph is enough
    return out


# ---------- RULE-E paragraph-closing summaries ------------------------------


_CLOSER_STARTERS = (
    "Overall,",
    "In summary,",
    "In conclusion,",
    "To summarize,",
    "All in all,",
    "In short,",
    "Ultimately,",
    "Thus,",
    "Therefore,",
)
_CLOSER_PATTERNS = (
    re.compile(r"^(?:" + "|".join(re.escape(s) for s in _CLOSER_STARTERS) + r")", re.IGNORECASE),
    re.compile(r"\bthese (?:changes|contributions|improvements|updates|results) (?:represent|demonstrate|reflect)\b", re.IGNORECASE),
    re.compile(r"\ba significant step (?:forward|change|improvement)\b", re.IGNORECASE),
    re.compile(r"\brepresents? a (?:significant|major|substantial) (?:advance|step|improvement)\b", re.IGNORECASE),
)


def _rule_e(text: str) -> list[Violation]:
    """Flag paragraph-closing sentences that restate or summarize."""
    out: list[Violation] = []
    for start_line, para_lines in _paragraphs(text):
        sentences = _sentences_in_paragraph(para_lines)
        if not sentences:
            continue
        last = sentences[-1]
        for pat in _CLOSER_PATTERNS:
            if pat.search(last):
                # Line number is start_line + number of lines before the last
                out.append(
                    Violation(
                        rule="RULE-E",
                        line=start_line + max(0, len(para_lines) - 1),
                        column=1,
                        excerpt=_excerpt(last, (0, len(last))),
                        detail="paragraph ends with a summary / restatement",
                    )
                )
                break
    return out


# ---------- Dispatch --------------------------------------------------------


_DISPATCH: dict[str, Callable[[str], list[Violation]]] = {
    "RULE-A": _rule_a,
    "RULE-C": _rule_c,
    "RULE-E": _rule_e,
    # RULE-02, RULE-07, RULE-09, RULE-10 fall through to "skipped" in run()
}
