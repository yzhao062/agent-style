# SPDX-License-Identifier: MIT
"""Mechanical detectors: regex / word-list rules. Deterministic by construction.

Rules covered (per PLAN Rev 3 detector matrix):
  RULE-B  em/en-dash casual use (excludes numeric ranges and paired names)
  RULE-D  transition openers Additionally / Furthermore / Moreover / In addition
  RULE-G  heading title-case per RULE-G's own convention (lowercase articles,
          short prepositions, coordinating conjunctions; capitalize everything else)
  RULE-I  contractions in formal prose
  RULE-05 dying metaphors / clichés (regex against a small cliché list derived
          from Orwell 1946 and the rule's BAD examples)
  RULE-06 avoidable jargon (regex against the jargon list from Orwell 1946 Rule 5
          plus the 45-word banned AI-tell list adjacent to RULE-06)
  RULE-12 sentence length > 30 words

Plus a single "banned AI-tell list" detector which is covered under RULE-06's
mechanical pass (the banned list IS the jargon surface we check against).

Each detector takes a parsed Rule record, the file text, and the file path, and
returns a RuleResult with zero or more Violation entries.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable

from agent_style.review.loader import Rule
from agent_style.review.primitive import RuleResult, Violation


# ---------- Rule dispatch ---------------------------------------------------


def run(rule: Rule, text: str, file_path: str) -> RuleResult:
    """Dispatch to the detector for ``rule.id``; return the RuleResult."""
    func = _DISPATCH.get(rule.id)
    if func is None:
        return RuleResult(
            rule=rule.id,
            severity=rule.severity,
            detector="mechanical",
            status="skipped",
            count=0,
            note=f"no mechanical detector registered for {rule.id}",
        )
    violations = func(text)
    status = "violation" if violations else "ok"
    return RuleResult(
        rule=rule.id,
        severity=rule.severity,
        detector="mechanical",
        status=status,
        count=len(violations),
        violations=violations,
    )


# ---------- Helpers ---------------------------------------------------------


def _excerpt(line_text: str, span: tuple[int, int], width: int = 120) -> str:
    """Return up to ``width`` chars of the line around the match span."""
    start = max(0, span[0] - 20)
    end = min(len(line_text), start + width)
    out = line_text[start:end].strip()
    if start > 0:
        out = "…" + out
    if end < len(line_text):
        out = out + "…"
    return out


def _iter_lines(text: str):
    """Yield (line_no, col_start, line_text) for each line (1-indexed)."""
    pos = 0
    for i, line in enumerate(text.splitlines(keepends=False), start=1):
        yield i, pos, line
        pos += len(line) + 1  # +1 for the stripped newline


def _inside_code_fence(lines: list[str], target_idx: int) -> bool:
    """True if ``target_idx`` (0-based line index) is inside a fenced code block."""
    fence_open = False
    for i, line in enumerate(lines):
        stripped = line.lstrip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            fence_open = not fence_open
        if i == target_idx:
            return fence_open
    return False


def _inside_inline_code(line: str, col: int) -> bool:
    """True if the column offset is inside a `backtick` span on that line."""
    ticks = 0
    for i, ch in enumerate(line):
        if ch == "`":
            ticks += 1
        if i == col:
            break
    return (ticks % 2) == 1


# ---------- RULE-B em/en-dash casual use ------------------------------------


# En-dash used as numeric range: preceding digit and following digit.
_NUMERIC_EN_DASH = re.compile(r"(?<=\d)[\u2013](?=\d)")

# Any em-dash or en-dash we want to flag (we subtract numeric-range en-dashes).
_ANY_DASH = re.compile(r"[\u2014\u2013]")


def _rule_b(text: str) -> list[Violation]:
    """Flag em or en dashes used as casual sentence punctuation.

    Excludes:
      - en-dashes in numeric ranges (e.g. 2022–2026)
      - anything inside code fences or inline backtick spans
    """
    lines_all = text.splitlines()
    out: list[Violation] = []
    for line_no, _col0, line in _iter_lines(text):
        if _inside_code_fence(lines_all, line_no - 1):
            continue
        # Build allow-list: positions of numeric-range en-dashes on this line.
        allowed = {m.start() for m in _NUMERIC_EN_DASH.finditer(line)}
        for m in _ANY_DASH.finditer(line):
            if m.start() in allowed:
                continue
            if _inside_inline_code(line, m.start()):
                continue
            out.append(
                Violation(
                    rule="RULE-B",
                    line=line_no,
                    column=m.start() + 1,
                    excerpt=_excerpt(line, (m.start(), m.end())),
                    detail=f"{'em' if m.group() == '\u2014' else 'en'}-dash as casual punctuation",
                )
            )
    return out


# ---------- RULE-D transition openers ---------------------------------------


_TRANSITION_OPENERS = (
    "Additionally",
    "Furthermore",
    "Moreover",
    "In addition",
)
_TRANSITION_OPENER_RE = re.compile(
    r"(?:^|\n)\s*(?:>\s*|[*-]\s+)*(" + "|".join(re.escape(t) for t in _TRANSITION_OPENERS) + r")\b",
    re.IGNORECASE,
)


def _rule_d(text: str) -> list[Violation]:
    """Flag transition openers at sentence start on any line."""
    out: list[Violation] = []
    lines_all = text.splitlines()
    for line_no, _col0, line in _iter_lines(text):
        if _inside_code_fence(lines_all, line_no - 1):
            continue
        # Match only at the start of the logical sentence/line.
        stripped = line.lstrip()
        if not stripped:
            continue
        # Detect leading blockquote/list markers so we compare against the first
        # word token after them.
        prefix_len = len(line) - len(stripped)
        after_markup = re.sub(r"^(>+\s*|[*-]\s+)+", "", stripped)
        first_word = re.match(r"([A-Za-z][A-Za-z-]*)", after_markup)
        if not first_word:
            continue
        word = first_word.group(1)
        for opener in _TRANSITION_OPENERS:
            if word.lower() == opener.split()[0].lower():
                # For multi-word openers ("In addition"), check the full phrase.
                if " " in opener:
                    if not after_markup.lower().startswith(opener.lower()):
                        continue
                col = prefix_len + (len(stripped) - len(after_markup)) + 1
                out.append(
                    Violation(
                        rule="RULE-D",
                        line=line_no,
                        column=col,
                        excerpt=_excerpt(line, (col - 1, col - 1 + len(opener))),
                        detail=f"transition opener '{opener}'",
                    )
                )
                break
    return out


# ---------- RULE-G title-case headings --------------------------------------


# Words always lowercase in title case (Chicago-lite used by RULE-G):
_LC_WORDS = frozenset(
    {
        "a", "an", "and", "as", "at", "but", "by", "for", "in", "nor",
        "of", "on", "or", "so", "the", "to", "up", "via", "vs", "yet",
        "with", "over", "per", "into", "from", "onto",
    }
)


def _rule_g(text: str) -> list[Violation]:
    """Flag Markdown headings that violate RULE-G title case."""
    out: list[Violation] = []
    lines_all = text.splitlines()
    for line_no, _col0, line in _iter_lines(text):
        if _inside_code_fence(lines_all, line_no - 1):
            continue
        m = re.match(r"^\s*(#{1,6})\s+(.*?)(?:\s+#*\s*)?$", line)
        if not m:
            continue
        heading_text = m.group(2).strip()
        if not heading_text:
            continue
        # Strip inline code spans and links when evaluating case.
        cleaned = re.sub(r"`[^`]*`", "", heading_text)
        cleaned = re.sub(r"\[([^\]]*)\]\([^\)]*\)", r"\1", cleaned)
        # Remove punctuation that isn't a word boundary (hyphens kept).
        tokens = re.findall(r"[A-Za-z][A-Za-z0-9'/-]*", cleaned)
        if not tokens:
            continue
        problem: list[str] = []
        for idx, tok in enumerate(tokens):
            if "-" in tok:
                # Hyphenated compound: capitalize each sub-token.
                parts = tok.split("-")
                for sub in parts:
                    if sub and not _is_titlecased(sub, is_first=(idx == 0 and sub == parts[0]), is_lc=False):
                        problem.append(tok)
                        break
                continue
            is_first = (idx == 0)
            is_last = (idx == len(tokens) - 1)
            should_be_lc = tok.lower() in _LC_WORDS
            if is_first or is_last:
                # Always capitalize the first and last word.
                if not _is_titlecased(tok, is_first=True, is_lc=False):
                    problem.append(tok)
                continue
            if should_be_lc:
                if tok != tok.lower():
                    problem.append(tok)
            else:
                if not _is_titlecased(tok, is_first=False, is_lc=False):
                    problem.append(tok)
        if problem:
            out.append(
                Violation(
                    rule="RULE-G",
                    line=line_no,
                    column=1,
                    excerpt=_excerpt(line, (0, len(line))),
                    detail=f"heading not in title case; violating tokens: {', '.join(problem)}",
                )
            )
    return out


def _is_titlecased(word: str, is_first: bool, is_lc: bool) -> bool:
    """Return True if ``word`` is correctly cased for its role."""
    if not word:
        return True
    if is_lc and not is_first:
        return word == word.lower()
    # Capitalized: first letter upper, rest may be mixed (acronyms, "RULES.md", etc.)
    return word[0].isupper() or word[0].isdigit()


# ---------- RULE-I contractions ---------------------------------------------


# Common contractions that RULE-I flags in formal prose.
_CONTRACTION_RE = re.compile(
    r"\b(?:[A-Za-z]+'(?:s|t|re|ll|d|ve|m)|it's|don't|won't|can't|shan't|isn't|aren't|wasn't|weren't|I'm)\b",
    re.IGNORECASE,
)


def _rule_i(text: str) -> list[Violation]:
    """Flag contractions outside code spans."""
    out: list[Violation] = []
    lines_all = text.splitlines()
    for line_no, _col0, line in _iter_lines(text):
        if _inside_code_fence(lines_all, line_no - 1):
            continue
        for m in _CONTRACTION_RE.finditer(line):
            if _inside_inline_code(line, m.start()):
                continue
            # Skip possessives like "Strunk & White's" (proper-noun possessive) by
            # looking at the preceding token; we treat these as contractions too
            # per RULE-I's strict reading, but we can exempt single-letter 'd/'s
            # after proper names if needed. Keep strict for now.
            out.append(
                Violation(
                    rule="RULE-I",
                    line=line_no,
                    column=m.start() + 1,
                    excerpt=_excerpt(line, (m.start(), m.end())),
                    detail=f"contraction '{m.group()}'",
                )
            )
    return out


# ---------- RULE-12 sentence length > 30 words ------------------------------


_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z\"'\(\[])")


def _rule_12(text: str) -> list[Violation]:
    """Flag sentences longer than 30 words."""
    out: list[Violation] = []
    lines_all = text.splitlines()
    for line_no, _col0, line in _iter_lines(text):
        if _inside_code_fence(lines_all, line_no - 1):
            continue
        # Skip headings and list markup lines.
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("|"):
            continue
        # Split into sentences and count words per sentence.
        for sentence in _SENTENCE_SPLIT_RE.split(stripped):
            words = re.findall(r"\b[\w'-]+\b", sentence)
            if len(words) > 30:
                out.append(
                    Violation(
                        rule="RULE-12",
                        line=line_no,
                        column=1,
                        excerpt=_excerpt(sentence, (0, len(sentence))),
                        detail=f"sentence length {len(words)} words (>30)",
                    )
                )
    return out


# ---------- RULE-05 dying metaphors / clichés -------------------------------
# Small, conservative cliché list drawn from Orwell 1946 and the RULE-05 BAD
# examples in RULES.md. Kept short to keep false-positive rate low; the
# semantic pass catches novel clichés.

_CLICHE_PHRASES = [
    "ring the changes",
    "take up the cudgels",
    "toe the line",
    "ride roughshod over",
    "stand shoulder to shoulder with",
    "play into the hands of",
    "no axe to grind",
    "grist to the mill",
    "fishing in troubled waters",
    "at the end of the day",
    "think outside the box",
    "level playing field",
    "low-hanging fruit",
    "paradigm shift",
    "moving the needle",
    "push the envelope",
    "circle back",
    "deep dive",
    "cutting-edge",
    "state of the art",
    "state-of-the-art",
    "paves the way",
    "pave the way",
    "a novel",
    "novel approach",
    "novel framework",
    "novel method",
    "novel optimization",
    "advance the state of the art",
    "game-changer",
    "game changer",
    "significant step forward",
    "paradigm-shifting",
    "best-in-class",
    "world-class",
    "next-generation",
    "next generation",
]


def _rule_05(text: str) -> list[Violation]:
    """Flag cliché phrases (small conservative list)."""
    out: list[Violation] = []
    lines_all = text.splitlines()
    lowered = text.lower()
    for phrase in _CLICHE_PHRASES:
        p_low = phrase.lower()
        start = 0
        while True:
            idx = lowered.find(p_low, start)
            if idx == -1:
                break
            line_no = text.count("\n", 0, idx) + 1
            line_start = text.rfind("\n", 0, idx) + 1
            col = idx - line_start + 1
            if not _inside_code_fence(lines_all, line_no - 1):
                line_text = text[line_start : text.find("\n", line_start) if text.find("\n", line_start) != -1 else len(text)]
                if not _inside_inline_code(line_text, col - 1):
                    out.append(
                        Violation(
                            rule="RULE-05",
                            line=line_no,
                            column=col,
                            excerpt=_excerpt(line_text, (col - 1, col - 1 + len(phrase))),
                            detail=f"cliché phrase '{phrase}'",
                        )
                    )
            start = idx + len(p_low)
    return out


# ---------- RULE-06 avoidable jargon ----------------------------------------
# The 45-word banned AI-tell list from .agent-config AGENTS.md Writing Defaults
# plus a few Orwell 1946 Rule 5 instances. This is both the RULE-06 jargon
# surface AND the "banned AI-tell list" detector — one regex.

_JARGON_WORDS = [
    # 45-word banned AI-tell list
    "encompass", "burgeoning", "pivotal", "realm", "keen", "adept", "endeavor",
    "uphold", "imperative", "profound", "ponder", "cultivate", "hone", "delve",
    "embrace", "pave", "embark", "monumental", "scrutinize", "vast", "versatile",
    "paramount", "foster", "necessitates", "provenance", "multifaceted", "nuance",
    "obliterate", "articulate", "acquire", "underpin", "underscore", "harmonize",
    "garner", "undermine", "gauge", "facet", "bolster", "groundbreaking",
    "game-changing", "reimagine", "turnkey", "intricate", "trailblazing",
    "unprecedented",
    # Additional jargon specifically called out in RULE-06 BAD examples
    "leverages", "leveraging", "leverage",
    "utilize", "utilizes", "utilizing",
    "facilitate", "facilitates", "facilitating",
]

_JARGON_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(w) for w in sorted(set(_JARGON_WORDS), key=len, reverse=True)) + r")\b",
    re.IGNORECASE,
)


def _rule_06(text: str) -> list[Violation]:
    """Flag avoidable jargon words (45-word banned list + Orwell-Rule-5 words)."""
    out: list[Violation] = []
    lines_all = text.splitlines()
    for line_no, _col0, line in _iter_lines(text):
        if _inside_code_fence(lines_all, line_no - 1):
            continue
        for m in _JARGON_RE.finditer(line):
            if _inside_inline_code(line, m.start()):
                continue
            out.append(
                Violation(
                    rule="RULE-06",
                    line=line_no,
                    column=m.start() + 1,
                    excerpt=_excerpt(line, m.span()),
                    detail=f"jargon / AI-tell '{m.group()}'",
                )
            )
    return out


# ---------- Dispatch table --------------------------------------------------


_DISPATCH: dict[str, Callable[[str], list[Violation]]] = {
    "RULE-B": _rule_b,
    "RULE-D": _rule_d,
    "RULE-G": _rule_g,
    "RULE-I": _rule_i,
    "RULE-12": _rule_12,
    "RULE-05": _rule_05,
    "RULE-06": _rule_06,
}
