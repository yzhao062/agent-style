# SPDX-License-Identifier: MIT
"""Structural detectors: line/paragraph-level heuristics.

Rules with deterministic structural detectors in v0.2.0:
  RULE-A  bullet overuse (short-item lists where prose would read better)
  RULE-C  consecutive same-starts (≥ 2 of 3 adjacent sentences share opening token)
  RULE-E  paragraph-closing summaries (last sentence restates the paragraph topic)

Rules stubbed as "skipped" in v0.2.0 (structural-bucket but non-trivial heuristics
deferred to v0.3.0+):
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


_BULLET_RE = re.compile(r"^\s*(?:[*+-]|\d+\.)\s+(.*)$")


def _rule_a(text: str) -> list[Violation]:
    """Flag bullet lists with ≤ 2 items OR all items ≤ 8 words.

    Two-item lists are often better as prose or as a table; all-short-item lists
    (≤ 8 words each) suggest genuine enumeration *or* list overuse — flagged so
    the author can decide.
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
        # Start of a bullet group; collect consecutive bullets.
        group_start = i + 1  # 1-indexed line number
        items: list[tuple[int, str]] = []
        while i < len(lines) and not fence[i] and _BULLET_RE.match(lines[i]):
            items.append((i + 1, _BULLET_RE.match(lines[i]).group(1).strip()))
            i += 1
        n = len(items)
        short_items = sum(1 for _, content in items if len(content.split()) <= 8)
        if n <= 2:
            out.append(
                Violation(
                    rule="RULE-A",
                    line=group_start,
                    column=1,
                    excerpt=_excerpt(lines[group_start - 1], (0, len(lines[group_start - 1]))),
                    detail=f"list has only {n} item(s); consider prose",
                )
            )
        elif short_items == n and n >= 3:
            # all items are short
            out.append(
                Violation(
                    rule="RULE-A",
                    line=group_start,
                    column=1,
                    excerpt=_excerpt(lines[group_start - 1], (0, len(lines[group_start - 1]))),
                    detail=f"list has {n} items all ≤ 8 words; consider prose",
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
