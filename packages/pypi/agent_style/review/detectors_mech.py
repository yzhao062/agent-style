# SPDX-License-Identifier: MIT
"""Mechanical detectors: regex / word-list rules. Deterministic by construction.

Rules covered (see ``skills/style-review/references/rule-detectors.md``):
  RULE-03 numeric intervals written into prose, and precise figures (decimals,
          percentages) stacked in an abstract or introduction; takes the file
          path, because a file named for the abstract or introduction is one.
          In a LaTeX file it also reads the body prose for the same stack of
          three sentences, a caption that carries three precise figures or runs
          over 100 words, and a paragraph with four numbers at four or more
          decimal places (hook-only: the audit classifies RULE-03 as semantic)
  RULE-A  (hook-only, ``_rule_a``) a LaTeX table cell that holds more than 15
          words or two sentences; takes the file path and reads LaTeX only. The
          audit never calls it: it classifies RULE-A as structural (bullet
          overuse)
  RULE-B  em/en-dash casual use (excludes numeric ranges and paired names)
  RULE-D  overused sentence-initial transition openers from the six-item rule list
  RULE-G  heading title-case per RULE-G's own convention (lowercase articles,
          short prepositions, coordinating conjunctions; capitalize everything else)
  RULE-I  contractions in formal prose
  RULE-05 dying metaphors / clichés (regex against a small cliché list derived
          from Orwell 1946 and the rule's BAD examples)
  RULE-06 avoidable jargon (regex against a 54-entry list: the 45-word banned
          AI-tell list adjacent to RULE-06 plus 9 forms of 3 RULE-06 callouts)
  RULE-12 sentence length > 30 words

Plus a single "banned AI-tell list" detector which is covered under RULE-06's
mechanical pass (the banned list IS the jargon surface we check against).

Each detector takes a parsed Rule record, the file text, and the file path, and
returns a RuleResult with zero or more Violation entries.
"""

from __future__ import annotations

import bisect
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
    if rule.id in _FILE_PATH_RULES:
        violations = func(text, file_path)
    else:
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


_LINE_BREAK_RE = re.compile(r"\r\n|[\n\r]")


def _line_spans(text: str) -> list[tuple[int, int]]:
    """Return the (start, end) offset of each line, aligned 1:1 with splitlines().

    ``str.splitlines`` recognises CR, LF and CRLF. Any offset arithmetic that
    locates a match inside ``text`` has to recognise the same three, or a CRLF
    pair costs one character and a bare CR costs a whole line break, shifting
    every line and column reported after it.
    """
    spans: list[tuple[int, int]] = []
    pos = 0
    for match in _LINE_BREAK_RE.finditer(text):
        spans.append((pos, match.start()))
        pos = match.end()
    if pos < len(text):
        spans.append((pos, len(text)))
    return spans


def _iter_lines(text: str):
    """Yield (line_no, col_start, line_text) for each line (1-indexed)."""
    for i, (start, end) in enumerate(_line_spans(text), start=1):
        yield i, start, text[start:end]


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

# Letter-only tokens immediately before and after a candidate paired-name dash.
_LETTER_TOKEN_END = re.compile(r"[^\W\d_]+$")
_LETTER_TOKEN_START = re.compile(r"^[^\W\d_]+")

# Any em-dash or en-dash we want to flag (we subtract allowed en-dashes).
_ANY_DASH = re.compile(r"[\u2014\u2013]")
_EM_DASH = "\u2014"


def _is_paired_name_en_dash(line: str, col: int) -> bool:
    """Return whether ``col`` joins two capitalized name tokens with an en dash."""
    if line[col] != "\u2013":
        return False
    left = _LETTER_TOKEN_END.search(line[:col])
    right = _LETTER_TOKEN_START.match(line[col + 1 :])
    return bool(left and right and left.group()[0].isupper() and right.group()[0].isupper())


def _rule_b(text: str) -> list[Violation]:
    """Flag em or en dashes used as casual sentence punctuation.

    Excludes:
      - en-dashes in numeric ranges (e.g. 2022–2026)
      - en-dashes in paired names (e.g. Cauchy–Schwarz)
      - anything inside code fences or inline backtick spans
    """
    lines_all = text.splitlines()
    out: list[Violation] = []
    for line_no, _col0, line in _iter_lines(text):
        if _inside_code_fence(lines_all, line_no - 1):
            continue
        # Build allow-list: positions of legitimate joining en-dashes on this line.
        allowed = {m.start() for m in _NUMERIC_EN_DASH.finditer(line)}
        for m in _ANY_DASH.finditer(line):
            if m.start() in allowed or _is_paired_name_en_dash(line, m.start()):
                continue
            if _inside_inline_code(line, m.start()):
                continue
            # The dash kind is resolved before the f-string, not inside it.
            # A backslash escape in an f-string expression is a SyntaxError
            # before Python 3.12, where PEP 701 lifted the restriction. v0.4.1
            # wrote it inline while declaring Requires-Python >=3.8, so this
            # module raised at import on 3.8 through 3.11 and took every
            # review path down with it. The floor is >=3.9 now and CI runs it.
            kind = "em" if m.group() == _EM_DASH else "en"
            out.append(
                Violation(
                    rule="RULE-B",
                    line=line_no,
                    column=m.start() + 1,
                    excerpt=_excerpt(line, (m.start(), m.end())),
                    detail=f"{kind}-dash as casual punctuation",
                )
            )
    return out


# ---------- RULE-D transition openers ---------------------------------------


_TRANSITION_OPENERS = (
    "Additionally",
    "Furthermore",
    "Moreover",
    "In addition",
    "What's more",
    "Notably",
)
_TRANSITION_SENTENCE_RE = re.compile(
    r"(?:^|[.!?](?:[\"')\]]*)[ \t]+)(?:[\"'(]*)(?P<opener>"
    + "|".join(re.escape(t) for t in sorted(_TRANSITION_OPENERS, key=len, reverse=True))
    + r")(?![A-Za-z0-9_-])",
    re.IGNORECASE,
)
_TRANSITION_ALLOWANCE_PER_PARAGRAPH = 1
# Markdown constructs that open a new block even without a blank line before
# them: an ATX heading, a table row, a thematic break, and each list item.
_BLOCK_BOUNDARY_RE = re.compile(
    r"^(?:#{1,6}[ \t]|\||(?:-{3,}|\*{3,}|_{3,})[ \t]*$|(?:[*+-]|\d+\.)[ \t])"
)


def _rule_d(text: str) -> list[Violation]:
    """Flag transition openers after the first one in each paragraph."""
    out: list[Violation] = []
    lines_all = text.splitlines()
    paragraph_matches: list[tuple[int, int, str, str]] = []

    def flush_paragraph() -> None:
        total = len(paragraph_matches)
        excess_matches = paragraph_matches[_TRANSITION_ALLOWANCE_PER_PARAGRAPH:]
        for line_no, col, line, opener in excess_matches:
            out.append(
                Violation(
                    rule="RULE-D",
                    line=line_no,
                    column=col,
                    excerpt=_excerpt(line, (col - 1, col - 1 + len(opener))),
                    detail=(
                        f"overused transition opener '{opener}' "
                        f"({total} in paragraph; first is allowed)"
                    ),
                )
            )
        paragraph_matches.clear()

    for line_no, _col0, line in _iter_lines(text):
        if not line.strip():
            flush_paragraph()
            continue
        if (
            line.lstrip().startswith(("```", "~~~"))
            or _inside_code_fence(lines_all, line_no - 1)
        ):
            flush_paragraph()
            continue
        stripped = line.lstrip()
        prefix_len = len(line) - len(stripped)
        # Test the boundary on the text inside any blockquote, not on the raw
        # line: `> ## Heading` and `> - item` open new blocks just as their
        # unquoted forms do, and matching before the `>` is stripped misses them.
        unquoted = re.sub(r"^>+\s*", "", stripped)
        if _BLOCK_BOUNDARY_RE.match(unquoted):
            # A heading, table row, thematic break or new list item starts a new
            # block. Without this the one-transition allowance leaks across the
            # boundary, so `Additionally, first.` under one heading makes
            # `Moreover, second.` under the next read as the paragraph's second
            # opener.
            flush_paragraph()
        after_markup = re.sub(r"^(>+\s*|[*-]\s+)+", "", stripped)
        if not after_markup.strip():
            # A markup-only line (a bare ">" inside a blockquote, or a lone
            # bullet marker) separates paragraphs just as a blank line does.
            flush_paragraph()
            continue
        content_offset = prefix_len + len(stripped) - len(after_markup)
        for match in _TRANSITION_SENTENCE_RE.finditer(after_markup):
            opener = match.group("opener")
            col = content_offset + match.start("opener") + 1
            if not _inside_inline_code(line, col - 1):
                paragraph_matches.append((line_no, col, line, opener))
    flush_paragraph()
    return out


# ---------- RULE-G title-case headings --------------------------------------


# Words always lowercase in title case, exactly as enumerated by RULE-G.
_LC_WORDS = frozenset(
    {
        "a", "an", "the", "and", "but", "or", "nor", "of", "in", "on",
        "to", "for", "by", "at", "with",
    }
)

_QUESTION_OPENERS = frozenset(
    {"how", "what", "when", "where", "which", "who", "whom", "whose", "why"}
)
_FINITE_AUXILIARIES = frozenset(
    {
        "am", "are", "is", "was", "were", "do", "does", "did", "have",
        "has", "had", "can", "could", "may", "might", "must", "shall",
        "should", "will", "would",
    }
)
_HEADING_TOKEN_RE = re.compile(
    r"\.?[A-Za-z0-9](?:[A-Za-z0-9'./\\:_-]*[A-Za-z0-9])?"
)
_VERSION_RE = re.compile(
    r"v?\d+(?:\.\d+)+(?:[-+][A-Za-z0-9.-]+)?$", re.IGNORECASE
)
_FILE_NAME_RE = re.compile(r"\.?[A-Za-z0-9_-]+\.[A-Za-z0-9]{1,10}$")
_UPPER_ID_RE = re.compile(r"[A-Z]{2,}-[A-Z0-9]+$")


def _strip_heading_markup(text: str) -> str:
    """Remove heading content whose spelling must be preserved verbatim."""
    text = re.sub(r"(`+)[^`\n]*?\1", "", text)
    text = re.sub(
        r"!?\[[^\]\n]*\](?:\([^\)\n]*\)|\[[^\]\n]*\])?", "", text
    )
    return re.sub(r"<[^>\n]+>", "", text)


def _is_sentence_style_heading(text: str) -> bool:
    """Recognize question-form and conservatively identifiable full sentences."""
    visible = _strip_heading_markup(text).strip()
    if re.search(r"[.?!](?:[\"')\]}*_]+)?$", visible):
        return True
    words = re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)?", visible)
    if not words:
        return False
    lowered = [word.lower() for word in words]
    return lowered[0] in _QUESTION_OPENERS or any(
        word in _FINITE_AUXILIARIES for word in lowered
    )


def _token_cannot_carry_case(token: str) -> bool:
    """Return True for identifiers whose spelling title case must not alter."""
    return (
        token[0].isdigit()
        or bool(_VERSION_RE.fullmatch(token))
        or bool(_UPPER_ID_RE.fullmatch(token))
        or token.startswith(".")
        or "/" in token
        or "\\" in token
        or "_" in token
        or bool(_FILE_NAME_RE.fullmatch(token))
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
        if _is_sentence_style_heading(heading_text):
            continue
        cleaned = _strip_heading_markup(heading_text)
        tokens = [
            token for token in _HEADING_TOKEN_RE.findall(cleaned)
            if any(char.isalpha() for char in token)
        ]
        if not tokens:
            continue
        problem: list[str] = []
        for idx, tok in enumerate(tokens):
            if _token_cannot_carry_case(tok):
                continue
            is_first = (idx == 0)
            is_last = (idx == len(tokens) - 1)
            parts = tok.split("-")
            for part_idx, part in enumerate(parts):
                if not part or _token_cannot_carry_case(part):
                    continue
                part_is_first = is_first and part_idx == 0
                part_is_last = is_last and part_idx == len(parts) - 1
                should_be_lc = (
                    part.lower() in _LC_WORDS
                    and not part_is_first
                    and not part_is_last
                )
                if should_be_lc:
                    valid = part == part.lower()
                else:
                    valid = _is_titlecased(part)
                if not valid:
                    problem.append(tok)
                    break
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


def _is_titlecased(word: str) -> bool:
    """Return True if ``word`` begins with an uppercase letter."""
    if not word:
        return True
    # Capitalized: first letter upper, rest may be mixed (acronyms, "RULES.md", etc.)
    return word[0].isupper()


# ---------- RULE-I contractions ---------------------------------------------


# Ambiguous 's and 'd endings require closed host-word lists.
_CONTRACTION_RE = re.compile(
    r"\b(?:(?:it|that|he|she|there|here|what|who|where|when|how|let)'s|"
    r"(?:i|you|he|she|it|we|they|that|who|what|which|why|there|where|how)'d|"
    r"[A-Za-z]+n't|[A-Za-z]+'(?:re|ll|ve|m))\b",
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


# Two alternatives. The first is the original conservative split. The second
# adds an inline-code opener, because technical prose routinely starts a
# sentence with a code span and without it two ordinary sentences were counted
# as one over-long sentence.
#
# The code-span branch is guarded against the abbreviations that routinely
# precede a code span in technical prose: dotted initialisms (`e.g.`, `i.e.`)
# and the one-token forms `vs.`, `cf.` and `Fig.`. An unguarded backtick reads
# any of them as a sentence end and silently suppresses a genuine violation,
# which trades a visible false positive for an invisible false negative. Every
# guard is a fixed-width lookbehind, which is what Python accepts.
#
# `etc.` is deliberately absent. Mid-sentence it is followed by a comma, which
# never matches this branch anyway, and at the end of a sentence it is a real
# boundary that a guard would wrongly merge.
#
# Both branches also handle Markdown emphasis on either side of the boundary.
# The optional closing run absorbs markup after the punctuation, because a
# sentence ending `.**` puts that markup between the period and the whitespace
# and the lookbehind would otherwise never see the period. That run sits outside
# the lookbehind rather than inside it: Python `re` rejects a variable-width
# lookbehind, so `(?<=[.!?][*_`]{0,2})` does not compile.
#
# Every markup opener (`` ` ``, `*`, `_`) lives in the SECOND branch so it
# inherits the abbreviation guards. Putting them in the first branch instead
# looks equivalent and is not: `e.g. *json*` and `Fig. **2**` would bypass every
# guard and silently suppress a real violation, which is the same false negative
# the guards exist to prevent.
_SENTENCE_SPLIT_RE = re.compile(
    r"(?<=[.!?])(?:\*\*|__|\*|_|`)?\s+(?=[A-Z\"'\(\[])|"
    r"(?<!\b(?:[A-Za-z]\.){2})"
    r"(?<!\b(?:[Vv][Ss]|[Cc][Ff])\.)"
    r"(?<!\b[Ff][Ii][Gg]\.)"
    r"(?<=[.!?])(?:\*\*|__|\*|_|`)?\s+(?=[`*_])"
)


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
_CLICHE_PATTERNS = tuple(
    (
        phrase,
        re.compile(
            r"(?<![A-Za-z0-9_])" + re.escape(phrase) + r"(?![A-Za-z0-9_])",
            re.IGNORECASE,
        ),
    )
    for phrase in _CLICHE_PHRASES
)


def _rule_05(text: str) -> list[Violation]:
    """Flag cliché phrases (small conservative list)."""
    out: list[Violation] = []
    lines_all = text.splitlines()
    spans = _line_spans(text)
    starts = [start for start, _ in spans]
    for phrase, pattern in _CLICHE_PATTERNS:
        for match in pattern.finditer(text):
            idx = match.start()
            # Locate the match against the same CR/LF/CRLF line model that
            # produced ``lines_all``. Counting only "\n" here would put a match
            # after a bare CR on the wrong line, and disagree with the fence
            # mask indexed just below.
            line_no = bisect.bisect_right(starts, idx)
            line_start, line_end = spans[line_no - 1]
            col = idx - line_start + 1
            if not _inside_code_fence(lines_all, line_no - 1):
                line_text = text[line_start:line_end]
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
    return out


# ---------- RULE-06 avoidable jargon ----------------------------------------
# This 54-entry list combines the 45-word banned AI-tell list from
# .agent-config AGENTS.md Writing Defaults with 9 forms of 3 RULE-06
# BAD-example callouts. It is both the RULE-06 jargon surface and the
# "banned AI-tell list" detector.

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
    # 9 forms of 3 jargon terms called out in RULE-06 BAD examples
    "leverages", "leveraging", "leverage",
    "utilize", "utilizes", "utilizing",
    "facilitate", "facilitates", "facilitating",
]

_JARGON_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(w) for w in sorted(set(_JARGON_WORDS), key=len, reverse=True)) + r")\b",
    re.IGNORECASE,
)


def _rule_06(text: str) -> list[Violation]:
    """Flag the 54 avoidable-jargon and AI-tell entries."""
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


# ---------- RULE-03 precise figures: intervals in prose, stacked figures ----
# RULE-03 asks the writer to point to the display for per-item scores,
# intervals, and p-values, and to keep an abstract or introduction to the few
# magnitudes behind the main findings. Two checks make that mechanical:
#
#   A. a numeric interval written into a sentence, anywhere outside a table and
#      outside an appendix (appendix prose is where intervals cut from an
#      abstract belong)
#   B. precise figures stacked in an abstract or introduction
#
# A "precise figure" is a decimal number or a percentage. Integers are counts
# and are never figures. Everything that looks numeric but is not a result is
# blanked out before any figure is searched for: version strings, times, arXiv
# and DOI identifiers, section/table/figure/equation/appendix numbers, model
# names such as Llama-3.3-70B, LaTeX reference/citation/length arguments,
# URLs and paths, code spans, fences and (in Markdown) indented code blocks, and
# display material (tables with or without outer pipes, equations, figures,
# algorithms). Every blanking is length-preserving, so an
# offset in the blanked text is an offset in the original and line numbers
# stay correct.
#
# The detector is advisory and the guard caps what it shows, so the thresholds
# below were set to miss some stacking rather than flood. Measured on eight
# abstracts of two papers (three agents each generated one abstract per paper,
# six in all, and the other two were already in the drafts) and on 30 abstract
# and introduction regions of 18 papers: every setting with 2-3 figures per
# sentence, runs of 3-4 and a crowded sentence of 5-7 flags the same four of the
# six generated abstracts and none of the other four texts. Counting a single
# figure per sentence with a run of 2, or calling 4 figures crowded, starts to
# flag the sparse abstracts. Change a value only with a new measurement.

_R03_RUN_FIGURES = 2   # figures a sentence needs to count toward a run
_R03_RUN_LENGTH = 3    # consecutive such sentences that make a stack
_R03_CROWDED = 5       # figures in one sentence that make it crowded

_R03_NOT_NEWLINE = re.compile(r"[^\n\r]")

# Environments whose whole body is display material, not prose.
_R03_DISPLAY_ENVS = (
    "tabular", "tabular*", "tabularx", "tabulary", "tblr", "longtable", "array",
    "supertabular", "tabu", "equation", "equation*", "align", "align*", "alignat", "alignat*",
    "gather", "gather*", "multline", "multline*", "eqnarray", "eqnarray*",
    "flalign", "flalign*", "displaymath", "math", "figure", "figure*", "table",
    "table*", "wrapfigure", "wraptable", "tikzpicture", "verbatim", "verbatim*",
    "lstlisting", "minted", "algorithm", "algorithm*", "algorithmic",
    "thebibliography", "comment",
)
_R03_BEGIN_ENV_RE = re.compile(
    r"\\begin\{(" + "|".join(re.escape(n) for n in _R03_DISPLAY_ENVS) + r")\}"
)

# LaTeX commands whose brace arguments are labels, files, lengths, or
# identifiers. `\href` and the one-argument group keep only their first
# argument blanked so the visible link text of `\href{url}{text}` survives.
_R03_ARG1_CMDS = (
    r"(?:[A-Za-z]*ref|[A-Za-z]*cite[A-Za-z]*|label|url|href|nolinkurl|input|"
    r"include|bibliography|bibliographystyle|usepackage|documentclass|"
    r"hypertarget|hyperlink|vspace|hspace|vskip|hskip|texttt|path|lstinline|"
    r"setcounter|addtocounter|color)\*?"
)
_R03_ARG1_RE = re.compile(
    r"\\" + _R03_ARG1_CMDS + r"(?:[ \t]{0,3}\[[^\]]{0,200}\])*[ \t\n]{0,3}\{[^{}]{0,400}\}"
)
_R03_ARGN_RE = re.compile(
    r"\\(?:includegraphics|setlength|addtolength|rule|scalebox|fontsize|"
    r"linespread|definecolor|newcommand|renewcommand)\*?"
    r"(?:[ \t]{0,3}\[[^\]]{0,200}\])*(?:[ \t\n]{0,3}\{[^{}]{0,400}\}){1,3}"
)
_R03_SECTIONING_RE = re.compile(
    r"\\(?:chapter|(?:sub){0,2}section|(?:sub)?paragraph)\*?"
    r"(?:[ \t]{0,3}\[[^\]]{0,200}\])?[ \t]{0,3}\{[^{}]{0,300}\}"
)
_R03_VERB_RE = re.compile(r"\\verb\*?([^A-Za-z\s*]).{0,300}?\1")

# Layout lengths: `0.9\textwidth`, `12pt`, `1.5cm`.
_R03_LENGTH_RE = re.compile(
    r"(?<![\w.])(?:\d+(?:\.\d+)?|\.\d+)[ \t]{0,2}(?:\\(?:textwidth|linewidth|columnwidth|textheight|"
    r"paperwidth|paperheight|hsize|vsize|baselineskip)\b|(?:pt|em|ex|cm|mm|bp|pc|px)\b)"
)

# Identifiers and dates that carry digits and dots without being results.
_R03_IDENT_RE = re.compile(
    r"(?<![\w.])(?:"
    r"https?://[^\s<>\"')\]}]+|www\.[^\s<>\"')\]}]+"          # URLs
    r"|10\.\d{4,9}/[^\s<>\"')\]}]+"                              # DOIs
    r"|[Aa][Rr][Xx][Ii][Vv][ \t]{0,2}[:/]?[ \t]{0,2}\d{4}\.\d{4,5}(?:v\d+)?"  # arXiv
    r"|[A-Za-z]:\\[^\s]+"                                        # Windows paths
    r"|\d{1,2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?![\d])"               # times
    r"|\d{4}-\d{1,2}-\d{1,2}|\d{1,2}/\d{1,2}/\d{2,4}"            # dates
    r"|\d+\.\d+(?:/\d+(?:\.\d+)?){2,}"                           # 3.9/3.10/3.11 matrix
    r"|[Vv]\d+(?:\.\d+)+"                                        # v0.5, v1.2.3
    r"|\d+(?:\.\d+){2,}"                                         # 1.2.3, 16.10.2026
    r")"
)

# `Section 3.2`, `Tables 4 and 5`, `Python 3.12`, `Claude Opus 4.5`, `v0.5`.
_R03_REF_WORDS = (
    r"sections?|secs?\.?|subsections?|chapters?|ch\.|tables?|tabs?\.?|figures?|"
    r"figs?\.?|eqs?\.?|equations?|appendix|appendices|apps?\.?|theorems?|"
    r"thms?\.?|lemmas?|propositions?|props?\.?|corollar(?:y|ies)|definitions?|"
    r"defs?\.?|algorithms?|algs?\.?|listings?|pages?|pp?\.|nos?\.|versions?|"
    r"ver\.|releases?|rfcs?|phases?|rounds?|slices?|stages?|hypothes[ie]s|"
    r"rq|python|node(?:\.js)?|java|cuda|claude|gpt|gemini|llama|qwen|mistral|"
    r"gemma|deepseek|opus|sonnet|haiku|grok|windows|macos|ubuntu|ios|android|"
    r"chrome|pytorch|tensorflow|numpy|pandas|scipy|openai"
)
_R03_NUMBER_LIST = r"\d+(?:\.\d+)*[A-Za-z]?"
_R03_REF_RE = re.compile(
    r"(?<![A-Za-z])(?:" + _R03_REF_WORDS + r")(?:[ \t\u00a0~]{1,3}|\\ )"
    + _R03_NUMBER_LIST
    + r"(?:[ \t]{0,2}(?:,|and|or|&|to|--|\u2013|-)[ \t]{0,2}" + _R03_NUMBER_LIST + r"){0,6}",
    re.IGNORECASE,
)
_R03_SECTION_SIGN_RE = re.compile(r"\u00a7+[ \t]{0,2}\d+(?:\.\d+)*")

# A figure is a decimal or a percentage; integer counts are not figures.
_R03_FIGURE_RE = re.compile(
    r"(?<![\w.])(?<![A-Za-z]-)"
    r"(?P<num>(?:\d{1,3}(?:,\d{3}){1,5}|\d+)(?P<dec>\.\d+)?)(?![\d])(?!\.\d)"
    r"(?P<pct>(?:[ \t~]|\\,)?(?:\\%|%|percent(?:age[ \t]+points?)?\b))?"
)

# A confidence level is metadata of an interval, not a result: `95\% CI`,
# `95% bootstrap intervals`, `CI (95%)`. Only a statistical modifier may stand
# between the level and the keyword: any other word means the percentage is a
# result ("drops by 15% over an interval of 2 to 4 hours").
_R03_LEVEL_MODIFIERS = (
    r"(?:confidence|credible|prediction|tolerance|bootstrapped|bootstrap|percentile|"
    r"central|posterior|highest-density|equal-tailed|simultaneous|two-sided|one-sided|"
    r"wald|wilson|asymptotic|exact|coverage)"
)
_R03_LEVEL_BEFORE_RE = re.compile(
    r"(\d+(?:\.\d+)?[ \t]{0,2}(?:\\%|%|percent)[ \t]{0,2}(?:" + _R03_LEVEL_MODIFIERS + r"[ \t]{1,2}){0,3})$",
    re.IGNORECASE,
)
_R03_LEVEL_AFTER_RE = re.compile(
    r"(?:CIs?|intervals?|confidence)[ \t]{0,2}\(?[ \t]{0,2}(\d+(?:\.\d+)?[ \t]{0,2}(?:\\%|%|percent))",
    re.IGNORECASE,
)

# Interval notation. An endpoint is a signed number, optionally wrapped in
# `$...$`, optionally a percentage.
# A bare integer followed by a thousands group ("2,000") is one number, never
# an endpoint of "2" and "000".
_R03_NUM = (
    r"[-+\u2212]?\$?[-+\u2212]?"
    r"(?:\d{1,3}(?:,\d{3}){1,5}(?:\.\d+)?(?!\d)|\d+\.\d+|\d+(?!,\d{3}(?!\d)))"
    r"(?:\\?%)?\$?"
)
_R03_SEP = (
    r"(?:\s{0,6}[,;]\s{0,6}|\s{1,6}to\s{1,6}|\s{0,6}(?:--|\u2013|\u2014|-)\s{0,6}"
    r"|\s{1,6}and\s{1,6})"
)
# A bracketed pair has no "and" form: "76 (0.92 and 0.88)" lists two values.
_R03_BRACKET_SEP = (
    r"(?:\s{0,6}[,;]\s{0,6}|\s{1,6}to\s{1,6}|\s{0,6}(?:--|–|—|-)\s{0,6})"
)
_R03_BRACKET_RE = re.compile(
    r"[\[(]\s{0,6}(?P<a>" + _R03_NUM + r")" + _R03_BRACKET_SEP + r"(?P<b>" + _R03_NUM
    + r")\s{0,6}[\])]"
)
_R03_KEYWORD_RE = re.compile(r"\b(?:CIs?|intervals?)\b", re.IGNORECASE)
# The lead and the words before the first endpoint are captured because a bare
# "interval" (no confidence level, no "CI") is read more strictly than an
# explicit one: not across a clause comma, and "X and Y" only after "between".
_R03_KEYED_TAIL_RE = re.compile(
    r"(?P<lead>[\s:=,]{0,4})(?P<words>(?:(?:of|is|was|from|between|at|spanning|ranging)\s{1,3}){0,2})"
    r"[\[(]?\s{0,6}(?P<a>" + _R03_NUM + r")(?P<sep>" + _R03_SEP + r")(?P<b>" + _R03_NUM
    + r")\s{0,6}[\])]?"
)
_R03_WORD_BEFORE_KEYWORD_RE = re.compile(
    r"(?:confidence|credible|prediction|tolerance|bootstrap(?:ped)?)\s{1,3}$",
    re.IGNORECASE,
)
_R03_TIME_UNIT_RE = re.compile(
    r"\s{0,2}(?:ms|s|sec|secs|seconds?|minutes?|mins?|hours?|hrs?|days?|weeks?|"
    r"months?|years?|steps?|iterations?|epochs?|tokens?|px)\b",
    re.IGNORECASE,
)
# A bracketed pair is an estimate's interval only when a figure comes right
# before it. A `$` counts only when it closes a number (`$-0.052$ [`), never
# when it opens the math that holds the bracket (`reach $[0.08, 0.62]$`).
_R03_NUMBER_BEFORE_RE = re.compile(r"(?:[\d%]|(?<=[\d})])\$)[\s~,;:(]{0,6}\$?$")
_R03_CI_WORD_BEFORE_RE = re.compile(r"(?:CIs?|intervals?|confidence|credible)\W{0,12}$", re.IGNORECASE)

# Sentence ends. The candidate is a terminator run followed by closers,
# whitespace, and something that can start a sentence; the abbreviation check
# runs in code. A closer is a quote, a bracket, a Markdown emphasis marker, or a
# backtick, so `**Gain is 0.4.** **Cost is 1.2.**` splits into two sentences, as
# the RULE-12 splitter does. The closers are single characters in one class: an
# alternation of `**` and `*` would admit exponentially many ways to match a long
# run of asterisks.
_R03_BOUNDARY_RE = re.compile(
    r"(?<![.!?])(?P<end>[.!?]+[\"'\u201d\u2019)\]}*_`]*)\s+(?=[A-Z0-9\\$\"'\u201c\u2018(\[*_`<])"
)
_R03_PRECEDING_TOKEN_RE = re.compile(r"([A-Za-z]+(?:\.[A-Za-z]+)*)$")
_R03_ABBREVIATIONS = frozenset({
    "al", "approx", "ca", "cf", "cor", "def", "dr", "eq", "eqs", "fig", "figs",
    "inc", "incl", "jr", "ltd", "mr", "mrs", "ms", "no", "nos", "prof", "prop",
    "resp", "sec", "secs", "sr", "st", "tab", "thm", "vs", "vol", "ref", "refs",
})

# A new block starts a new sentence even without a terminator.
_R03_BLOCK_RE = re.compile(
    r"\n[ \t\r]*(?=\n)|\n[ \t]*(?:[-*+]|\d+[.)])[ \t]+|\\item\b|\\par\b"
)

_R03_MD_HEADING_RE = re.compile(r"^[ \t]{0,3}(#{1,6})[ \t]+(.*)$", re.MULTILINE)
_R03_TEX_SECTION_RE = re.compile(
    r"\\(?:section|chapter)\*?[ \t]{0,3}(?:\[[^\]\n]{0,200}\])?[ \t]{0,3}\{([^{}\n]{0,200})\}"
)
_R03_TITLE_NUMBER_RE = re.compile(r"^(?:\d+(?:\.\d+)*[.)]?|[IVX]+\.)\s+")
_R03_LATEX_SIGNATURE_RE = re.compile(r"\\(?:begin|section|cite[a-z]*|ref|emph|textbf|item)\b")

# Markdown input is a `.md` or `.markdown` file, or text with no file name and no
# LaTeX sectioning or environment command. An indented block is code only there.
_R03_LATEX_MARKER_RE = re.compile(r"\\(?:begin|(?:sub){0,2}section)(?!\w)")
# A list item marker opens a list item; the item's content column decides whether
# an indented line inside it is code or a continuation paragraph.
_R03_LIST_MARKER_RE = re.compile(r"(?:[-*+]|[0-9]{1,9}[.)])")
_R03_HEADING_START_RE = re.compile(r"#{1,6}(?:[ \t]|\Z)")

# A table row cell ends at an unescaped pipe. The delimiter row of a table holds
# only cells of dashes with optional colons; it needs a pipe, so a lone `---` is
# a rule or a setext underline and never a delimiter.
_R03_PIPE_RE = re.compile(r"(?<!\\)\|")
_R03_DELIMITER_CELL_RE = re.compile(r"[ \t]*:?-+:?[ \t]*")

# A file named for an appendix or a supplement holds detailed prose; so does the
# part of a LaTeX file after `\appendix`. `support` is not one of the tokens.
# Paper repositories also split appendices into `app-*.tex`, `appx.tex`, or
# `apx-*.tex`; tokens split on `-`, `_`, `.`, and spaces, so `application.tex`
# stays a body file.
_R03_APPENDIX_NAME_TOKENS = frozenset(
    {"appendix", "appendices", "supplement", "supplementary", "supp", "app", "appx", "apx"}
)
_R03_APPENDIX_NAME_SPLIT_RE = re.compile(r"[-_. ]+")
_R03_APPENDIX_CMD_RE = re.compile(r"\\appendix(?!\w)")


# ---------- RULE-03 checks C and D, body-prose check B, RULE-A table cells ----
#
# agent-style 0.7.0 extends the hook-only figure checks from the abstract and
# introduction to the rest of a LaTeX paper. Everything below reads LaTeX only:
# the Markdown tables of agent documents carry long cells by design (30-40% of
# the ones measured), so the same limits there would flood. The appendix and
# supplement exemptions are those of check A.
#
#   B (body)  the run criterion of check B, in LaTeX body prose outside a
#             method or setup section
#   C         a caption that carries precise figures or runs long; the numbers
#             of a legend (quantile lines, significance levels, markers) are
#             keys and not figures
#   D         numbers written to four or more decimal places and three or more
#             significant digits (0.0143 counts, 0.0001 does not), outside a
#             method or setup section
#   RULE-A    a LaTeX table cell that holds prose (``_rule_a`` below)
#
# Measured in 2026-10 on the .tex files of 12 pre-2023 arXiv papers (169 files
# after content-hash dedupe) and of agent-assisted drafts (335 files), with each
# path passed so the file-name exemptions apply. Findings as human | drafts:
#
#   B body run          0 | 53 (18 files; none sit in files named app-*, which
#                       the name exemption covers). The method and setup
#                       exemption removes 4 of the draft findings.
#   B body crowded      limit 5: 6 | 76 (5 distinct human sentences), limit 6:
#                       4 | 54. A human body sentence with five figures is not
#                       rare, so the crowded criterion stays in the abstract
#                       and the introduction.
#   C caption           5 of 202 human captions | 98 of 373 at 3 figures or over
#                       100 words (human: 3 by figures, 2 by words; drafts: 44
#                       and 71, each limit alone). Legend numbers removed 2
#                       draft findings and no human one. One step up on both
#                       (4 figures, 120 words) leaves 3 | 62. The human hits
#                       restate results or run to a paragraph, which is the
#                       pattern.
#   D excess precision  numbers at 4+ places and 3+ significant digits. A
#                       paragraph with 3 numbers at 3+ places: 5 | 145; at 4+
#                       places: 3 | 20; a sentence with 2 at 4+ places: 5 | 39.
#                       None keeps the human count at 2 or fewer. A paragraph
#                       with 4 numbers at 4+ places does: 2 | 14 (each human
#                       paragraph holds eight such numbers). Three places is
#                       ordinary reporting (an AUC of 0.824), and a paragraph
#                       at 3+ places stays above 2 human at every count up to 7
#                       (8 gives 2 | 45, but that counts density and not
#                       precision). A sentence with 5 numbers at 3+ places
#                       gives 2 | 35 and measures crowding, so it is not
#                       shipped. The significant-digit rule removed 6 draft
#                       findings (21 to 15) and the setup exemption 1 more; the
#                       human count stayed at 2.
#   RULE-A table cell   0 of 103 human tables | 29 of 292 (24 files; none in
#                       app-* files). The longest human cell holds 6 words.
#
# The detectors are advisory and the guard caps what it shows, so each value
# below was set to miss some of the pattern rather than flood. Change a value
# only with a new measurement.

_R03_BODY = "body"          # label of a sentence in LaTeX body prose
# Crowded sentences in body prose. None: off, because five figures in one human
# body sentence is not rare (6 of them in the human corpora at a limit of 5).
_R03_BODY_CROWDED = None

# Captions: 5 of 202 human, 98 of 373 draft captions (3 | 44 by figures, 2 | 71 by words).
_R03_CAPTION_FIGURES = 3    # precise figures that make a caption a results table
_R03_CAPTION_WORDS = 100    # words above which a caption is a paragraph

# Excess precision: numbers with at least _R03_DECIMAL_PLACES decimal places and
# _R03_DECIMAL_SIGNIFICANT significant digits, _R03_DECIMAL_COUNT of them in one
# _R03_DECIMAL_UNIT ("paragraph" or "sentence"). Leading zeros after the point are
# scale, so a learning rate of 0.0001 is one significant digit and not precision.
# Shipped values: 2 human paragraphs | 14 draft paragraphs.
_R03_DECIMAL_PLACES = 4
_R03_DECIMAL_COUNT = 4
_R03_DECIMAL_UNIT = "paragraph"
_R03_DECIMAL_SIGNIFICANT = 3

# A table cell holds a number, a label, or a short phrase. 0 of 103 human tables |
# 29 of 292 draft tables (26 by words, 3 by sentences). A sentence of one or two
# words is not counted: at 1, eight more draft tables flag, each on the period
# of an abbreviation.
_RA_CELL_WORDS = 15         # words above which a cell is prose
_RA_CELL_SENTENCES = 2      # sentences that make a cell prose
_RA_SENTENCE_WORDS = 3      # words a piece needs to count as a sentence
_RA_MAX_DEPTH = 4           # nested tables read; deeper ones stay inside their parent's cell

# Environments whose body is code or a comment: a `\caption` or a `\begin{tabular}`
# in one of them is an example, not a display.
_R03_CODE_ENV_RE = re.compile(r"\\begin\{(verbatim\*?|lstlisting|minted|comment)\}")

# `\caption{`, `\caption*{`, `\caption[short]{`, `\captionof{figure}{`. A command
# such as `\captionsetup` is not one.
_R03_CAPTION_RE = re.compile(r"\\caption(?P<of>of)?\*?(?![A-Za-z@])")
_R03_BLANKS_RE = re.compile(r"[ \t\r\n]*")

# Commands whose first brace argument is layout or style, and rule commands with
# their arguments. Removed before words are counted, so `\cmidrule(lr){2-3}` and
# `\cellcolor{gray}` add none. `\multicolumn` and `\multirow` lose their two
# layout arguments and keep the text.
_R03_FIRST_ARG_RE = re.compile(
    r"\\(?:parbox|makebox|framebox|raisebox|rotatebox|resizebox|scalebox|textcolor|"
    r"colorbox|fcolorbox|cellcolor|rowcolor|columncolor|arrayrulecolor)\*?"
    r"(?:[ \t]{0,3}\[[^\]]{0,50}\]){0,3}[ \t\n]{0,3}\{[^{}]{0,100}\}"
)
_R03_SPAN_ARGS_RE = re.compile(
    r"\\(?:multicolumn|multirow)\*?[ \t\n]{0,3}\{[^{}]{0,60}\}[ \t\n]{0,3}"
    r"(?:\[[^\]]{0,50}\][ \t\n]{0,3})?\{[^{}]{0,60}\}"
)
_R03_RULE_ARGS_RE = re.compile(
    r"\\(?:cmidrule|cline|specialrule|noalign|hhline)\*?(?![A-Za-z@])"
    r"(?:[ \t]{0,3}(?:\[[^\]]{0,30}\]|\([^)]{0,20}\))){0,2}"
    r"(?:[ \t\n]{0,3}\{[^{}]{0,60}\}){0,3}"
    r"|\\(?:toprule|midrule|bottomrule|hline|addlinespace)\*?(?![A-Za-z@])(?:[ \t]{0,3}\[[^\]]{0,30}\])?"
)
# What opens a table cell without being its text: blanks and rule commands.
_RA_LEAD_RE = re.compile(r"(?:\s|" + _R03_RULE_ARGS_RE.pattern + r")*")
_R03_COMMAND_RE = re.compile(r"\\[A-Za-z@]+\*?(?:\[[^\]\n]{0,200}\])?")
_R03_ESCAPED_RE = re.compile(r"\\([%&_#$])")
_R03_DOLLAR_RE = re.compile(r"(?<!\\)\$")
_R03_WORD_RE = re.compile(r"[^\W\d_]{2,}")
_R03_BRACE_TOKEN_RE = re.compile(r"\\.|[{}]", re.DOTALL)
# A sentence end inside a table cell, after cleaning (single spaces). The
# lookbehind keeps a long run of full stops from being retried at every offset.
_RA_BOUNDARY_RE = re.compile(r"(?<![.!?])[.!?]+[\"')\]]*[ ]+(?=[A-Z0-9\"'(\[])")

# A table environment, its begin and end tokens.
_RA_ENV_RE = re.compile(r"\\(begin|end)\{(tabular\*|tabular|tabularx|tabulary|longtable|tblr)\}")
_RA_ARG_COUNT = {"tabular": 1, "tabular*": 2, "tabularx": 2, "tabulary": 2, "longtable": 1, "tblr": 1}
# Inside a table body: a row break (`\\`, `\\*`, `\\[2pt]`), a command name, an
# escaped character, a brace, a cell separator.
_RA_TOKEN_RE = re.compile(r"\\\\\*?(?:\[[^\]\n]{0,20}\])?|\\[A-Za-z@]+|\\.|[{}&]", re.DOTALL)

# Legend and decoding metadata in a caption (check C). A caption names its lines,
# markers, bands and thresholds so the reader can decode the display: "Lines mark the
# 25%, 50% and 75% quantiles", "Stars denote p < 0.05, 0.01 and 0.001". Those numbers
# are keys and not results, so the figure count skips them. Each pattern takes one run
# of numbers beside the word that names it, never the rest of the sentence, so a result
# written next to a legend still counts. Digits are ASCII and blanks are spelled out, so
# the JavaScript port reads every input the same way.
_LG_WS = r"[ \t\r\n~]"
_LG_NUM = (
    r"\$?[-+\u2212]?[0-9]+(?:\.[0-9]+)?\$?"
    r"(?:(?:[ \t~]|\\,)?(?:\\%|%|percent(?!\w)|(?:st|nd|rd|th)(?!\w)))?\$?"
)
_LG_SEP = (
    r"(?:" + _LG_WS + r"{0,3}(?:,|;|/|&|--|\u2013|-)" + _LG_WS + r"{0,3}"
    r"|" + _LG_WS + r"{0,3},?" + _LG_WS + r"{1,3}(?:and|or|to)" + _LG_WS + r"{1,3})"
)
# One to six numbers. The lookbehind starts a list at its first number, so a long run of
# digits or of "1,1,1" is entered once.
_LG_LIST = _LG_NUM + r"(?:" + _LG_SEP + _LG_NUM + r"){0,5}"
_LG_WORD_BEFORE = r"(?:" + _LG_WS + r"{1,3}[A-Za-z-]{1,15}){0,1}" + _LG_WS + r"{1,3}"
_LG_QUANTILE = r"(?:quantiles?|percentiles?|quartiles?|deciles?)(?!\w)"
_LG_SIGNIFICANCE = (
    r"(?:\\?alpha|\u03b1|significan(?:ce|t)(?:" + _LG_WS
    + r"{1,3}(?:levels?|thresholds?|codes?|stars?))?|thresholds?)(?!\w)"
)
_LG_COMPARE = r"\$?(?:[<>=\u2264\u2265]|\\(?:leqslant|geqslant|leq|geq|le|ge|lt|gt)(?![A-Za-z]))\$?"
# A p-value is a key only beside an inequality or a threshold word: "p < 0.05" and
# "p-value thresholds of 0.05 and 0.01" define stars, while "p = 0.03" and "p-values of
# 0.041, 0.023 and 0.012" report results and stay in the count.
_LG_P = r"p(?:[ -]?values?)?(?!\w)"
_LG_INEQ = r"\$?(?:[<>\u2264\u2265]|\\(?:leqslant|geqslant|leq|geq|le|ge|lt|gt)(?![A-Za-z]))\$?"
_LG_P_KEY = r"(?:levels?|thresholds?|cut-?offs?)(?!\w)"
# A confidence level names a band: "the 68%, 95% and 99.7% confidence intervals".
_LG_CONF = r"(?:confidence|credible|prediction|highest[ -]density)(?!\w)"
# The singular "a confidence interval of 79.4% to 83.0%" is an estimate; the plural
# and a level name the bands of a legend.
_LG_CONF_NOUN = r"(?:levels?|intervals|bands|regions|ellipses)(?!\w)"
# A level is a percentage, so "a confidence interval of 39.8 to 42.7" stays a result.
_LG_PCT = r"\$?[0-9]+(?:\.[0-9]+)?\$?(?:[ \t~]|\\,)?(?:\\%|%|percent(?!\w))\$?"
_LG_PCT_LIST = _LG_PCT + r"(?:" + _LG_SEP + _LG_PCT + r"){0,5}"
_LG_MARKER = (
    r"(?<!\w)(?:lines?|markers?|symbols?|stars?|asterisks?|daggers?|bands?|shad(?:ing|ed)|"
    r"whiskers?|ticks?|contours?|isolines?|circles?|triangles?|squares?|diamonds?|crosses|arrows?)(?!\w)"
)
_R03_LEGEND_RES = tuple(
    re.compile(src, re.IGNORECASE)
    for src in (
        # "25%, 50% and 75% quantiles", "the 5th and 95th percentiles"
        r"(?<![0-9.,])" + _LG_LIST + _LG_WORD_BEFORE + _LG_QUANTILE,
        # "quantiles at 25%, 50% and 75%", "percentiles (5, 50, 95)", "quantile levels 0.1, 0.5 and 0.9"
        r"(?<!\w)" + _LG_QUANTILE
        + r"(?:" + _LG_WS + r"{0,3}(?:at|of|are|is|for|to|the|from|between|set|levels?|values?|bands?|lines?|ranges?|\(|:|=|,)){0,4}"
        + _LG_WS + r"{0,3}" + _LG_LIST,
        # "p < 0.05, 0.01 and 0.001", "alpha = 0.05", "significance thresholds at 0.05, 0.01 and 0.001"
        r"(?<![\w\\])" + _LG_SIGNIFICANCE
        + r"(?:" + _LG_WS + r"{0,3}(?:" + _LG_COMPARE + r"|is|are|was|were|at|of|set|to|below|under|above|for|levels?|values?|\(|:|\\,|\\;)){0,4}"
        + _LG_WS + r"{0,3}" + _LG_LIST,
        # "p < 0.05, 0.01 and 0.001", "$p \le 0.05$", "p-value thresholds of 0.05 and 0.01"
        r"(?<![\w\\])" + _LG_P
        + r"(?:" + _LG_WS + r"{0,3}" + _LG_INEQ + r"|" + _LG_WS + r"{1,3}" + _LG_P_KEY
        + r"(?:" + _LG_WS + r"{0,3}(?:" + _LG_COMPARE + r"|is|are|at|of|set|to|below|under|\(|:)){0,3})"
        + _LG_WS + r"{0,3}" + _LG_LIST,
        # "0.05, 0.01 and 0.001 significance levels", "the 0.05 and 0.01 p-value thresholds"
        r"(?<![0-9.,])" + _LG_LIST + _LG_WORD_BEFORE
        + r"(?:significance|thresholds?|\\?alpha|\u03b1|p[- ]?levels?|p[- ]?values?" + _LG_WS
        + r"{1,3}" + _LG_P_KEY + r")(?!\w)",
        # "the 68%, 95% and 99.7% confidence intervals", "95% CIs"
        r"(?<![0-9.,])" + _LG_PCT_LIST + _LG_WORD_BEFORE + r"(?:" + _LG_CONF + r"|CIs?(?!\w)|HDIs?(?!\w))",
        # "confidence levels of 68%, 95% and 99.7%"
        r"(?<!\w)" + _LG_CONF + _LG_WS + r"{1,3}" + _LG_CONF_NOUN
        + r"(?:" + _LG_WS + r"{0,3}(?:at|of|are|is|for|the|=|:|\(|,)){0,3}" + _LG_WS + r"{0,3}" + _LG_PCT_LIST,
        # "Lines mark the 0.5 chance level", "Dashed lines at 0.25, 0.50 and 0.75"
        _LG_MARKER
        + r"(?:" + _LG_WS + r"{0,3}(?:mark(?:s|ed|ing)?|denote[sd]?|indicate[sd]?|indicating|at|the|an?|chance|random|"
        r"baseline|reference|threshold|target|levels?|values?|of|for|=|:|\(|,)){1,5}"
        + _LG_WS + r"{0,3}" + _LG_LIST,
        # "Solid, dashed and dotted lines correspond to dropout rates of 0.1, 0.2 and 0.5,
        # respectively": a style mapped to a setting. "respectively" must follow the list,
        # so "Lines represent accuracies of 0.81, 0.83 and 0.85" still counts.
        _LG_MARKER
        + r"(?:" + _LG_WS + r"{1,3}(?:correspond(?:s|ing)?" + _LG_WS + r"{1,3}to|denote[sd]?|indicate[sd]?|"
        r"represent(?:s|ed|ing)?|mark(?:s|ed)?|encode[sd]?|use[sd]?))"
        + r"(?:" + _LG_WS + r"{1,3}(?:[A-Za-z$\\-]{1,20}|=)){0,4}"
        + _LG_WS + r"{0,3}" + _LG_LIST + r"(?=" + _LG_WS + r"{0,3},?" + _LG_WS + r"{0,3}respectively(?!\w))",
    )
)

# A heading that opens a method or setup section: its title names a method or an
# experimental setup and does not also name an outcome, so "Implementation Details"
# and "Hyperparameters" are exempt and "Experiments", "Evaluation", "Results" and
# "Setup and Results" are read. Words are ASCII, so the JavaScript port reads every title the same way.
_R03_TEX_HEADING_RE = re.compile(
    r"\\(chapter|section|subsection|subsubsection|paragraph|subparagraph)\*?[ \t]{0,3}"
    r"(?:\[[^\]\n]{0,200}\])?[ \t]{0,3}\{([^{}\n]{0,200})\}"
)
_R03_HEADING_LEVELS = {
    "chapter": 0, "section": 1, "subsection": 2, "subsubsection": 3, "paragraph": 4, "subparagraph": 5,
}
_R03_SETUP_WORDS = frozenset({
    "method", "methods", "methodology", "approach", "setup", "setups", "setting", "settings",
    "implementation", "hyperparameter", "hyperparameters", "configuration", "configurations",
    "dataset", "datasets", "details", "protocol", "protocols",
})
_R03_OUTCOME_WORDS = frozenset({
    "result", "results", "finding", "findings", "analysis", "analyses", "discussion", "ablation", "ablations",
})
_R03_TITLE_WORD_RE = re.compile(r"[A-Za-z]+")
_R03_TITLE_HYPHEN_RE = re.compile(r"(?<=[A-Za-z])-(?=[A-Za-z])")


def _r03_blank(text: str, spans: list) -> str:
    """Return ``text`` with every span replaced by spaces, newlines kept."""
    if not spans:
        return text
    parts: list[str] = []
    pos = 0
    for start, end in sorted(spans):
        start = max(start, pos)
        if end <= start:
            continue
        parts.append(text[pos:start])
        parts.append(_R03_NOT_NEWLINE.sub(" ", text[start:end]))
        pos = end
    parts.append(text[pos:])
    return "".join(parts)


def _r03_pairs(text: str, open_tok: str, close_tok: str) -> list:
    """Spans from each ``open_tok`` to the next ``close_tok``, in linear time.

    A regex with a lazy body rescans to the end of the text for every opener
    that is never closed, which is quadratic on a hostile file.
    """
    out = []
    pos = 0
    while True:
        i = text.find(open_tok, pos)
        if i < 0:
            break
        j = text.find(close_tok, i + len(open_tok))
        if j < 0:
            break
        pos = j + len(close_tok)
        out.append((i, pos))
    return out


def _r03_fence_run(body: str):
    """(character, length) of the backtick or tilde run that opens ``body``."""
    ch = body[:1]
    if ch != "`" and ch != "~":
        return None
    n = len(body) - len(body.lstrip(ch))
    return (ch, n) if n >= 3 else None


def _r03_indent_width(line: str) -> int:
    """Columns of leading space and tab; a tab advances to the next multiple of 4."""
    width = 0
    for ch in line:
        if ch == " ":
            width += 1
        elif ch == "\t":
            width += 4 - width % 4
        else:
            break
    return width


def _r03_marker_end(line: str, pos: int) -> int:
    """Index after the list item marker that starts at ``line[pos]``, or -1.

    A marker is a bullet, or one to nine digits and a ``.`` or ``)``. It opens an
    item only when a space, a tab or the end of the line follows it.
    """
    n = len(line)
    ch = line[pos:pos + 1]
    if ch == "-" or ch == "*" or ch == "+":
        end = pos + 1
    else:
        j = pos
        while j < n and j - pos <= 9 and "0" <= line[j] <= "9":
            j += 1
        if j == pos or j - pos > 9 or j >= n or (line[j] != "." and line[j] != ")"):
            return -1
        end = j + 1
    if end < n and line[end] != " " and line[end] != "\t":
        return -1
    return end


def _r03_list_content_col(line: str, pos: int, col: int) -> tuple:
    """(content column, kind of first content, index of that content) of a list item.

    The marker starts at ``line[pos]``, in column ``col``. The content starts
    after the marker and the one to four spaces that follow it. A marker followed
    by five or more spaces, or by nothing, puts the content one column after the
    marker (CommonMark, list items). The kind is "" for an empty item, "code" when
    five or more spaces make the first content an indented code block, and "text"
    otherwise.
    """
    n = len(line)
    end = _r03_marker_end(line, pos)
    after = col + (end - pos)
    cur = after
    j = end
    while j < n and (line[j] == " " or line[j] == "\t"):
        cur += 1 if line[j] == " " else 4 - cur % 4
        j += 1
    gap = cur - after
    if j >= n:
        return after + 1, "", j
    if gap > 4:
        return after + 1, "code", j
    return after + gap, "text", j


def _r03_item_interrupts(body: str) -> bool:
    """True when a list item line may interrupt a paragraph (CommonMark, list items).

    Only a bullet or an ordered item numbered 1 can, and only with text after
    the marker. Any other such line is paragraph text, so ``10. step`` after a
    paragraph line opens no list.
    """
    marker = _R03_LIST_MARKER_RE.match(body)
    if marker is None:
        return False
    text = marker.group()
    if text[-1] in ".)" and int(text[:-1]) != 1:
        return False
    return bool(body[marker.end():].strip(" \t"))


def _r03_is_break(body: str) -> bool:
    """True for a thematic break: three or more of one of ``-``, ``*``, ``_``.

    Spaces and tabs may sit between and after them, and nothing else.
    """
    ch = body[:1]
    if ch != "-" and ch != "*" and ch != "_":
        return False
    count = 0
    for c in body:
        if c == ch:
            count += 1
        elif c != " " and c != "\t":
            return False
    return count >= 3


def _r03_is_setext(body: str) -> bool:
    """True for a setext underline: a run of ``=`` or of ``-``, then only blanks."""
    ch = body[:1]
    if ch != "=" and ch != "-":
        return False
    return not body.lstrip(ch).strip(" \t")


# Marks a blockquote in the container list of an open fence; a list item is its
# content column, which is always positive.
_R03_QUOTE = -1


def _r03_container_fence(line: str, pos: int, col: int):
    """(containers, run) when a list item or blockquote line opens a fence.

    ``line[pos]`` is the first character that is not a space or a tab and ``col``
    its column. Every list item marker and every ``>`` is stepped over, nested ones
    included, and the text left must open a fence within three columns of the last
    container, as a fence line does on its own. ``containers`` holds the content
    column of each list item and ``_R03_QUOTE`` for each blockquote, outermost
    first. The result is None when what is left is not an opening fence.
    """
    n = len(line)
    out: list = []
    while True:
        if line[pos] == ">":
            out.append(_R03_QUOTE)
            col += 1
            pos += 1
            floor = col + (1 if pos < n and (line[pos] == " " or line[pos] == "\t") else 0)
            while pos < n and (line[pos] == " " or line[pos] == "\t"):
                col += 1 if line[pos] == " " else 4 - col % 4
                pos += 1
            if pos >= n or col - floor > 3:
                return None
            continue
        if _r03_marker_end(line, pos) < 0:
            break
        content_col, first, j = _r03_list_content_col(line, pos, col)
        if first != "text":
            return None
        out.append(content_col)
        pos = j
        col = content_col
    rest = line[pos:]
    run = _r03_fence_run(rest)
    if run is None or (run[0] == "`" and "`" in rest[run[1]:]):
        return None
    return out, run


def _r03_fence_line(line: str, ctx: list) -> tuple:
    """(held, index, rel) for ``line`` inside a fence whose containers are ``ctx``.

    ``held`` is False when a container of the fence ends at this line: a list item
    when a non-blank line is indented less than its content column, a blockquote
    when the line has no ``>`` for it, at most three columns past the enclosing
    container. Otherwise ``index`` is where the text begins after the containers
    and ``rel`` its columns past the innermost one, which is where a closing fence
    may sit.
    """
    n = len(line)
    pos = 0
    col = 0
    floor = 0
    for c in ctx:
        while pos < n and (line[pos] == " " or line[pos] == "\t"):
            col += 1 if line[pos] == " " else 4 - col % 4
            pos += 1
        if c == _R03_QUOTE:
            if pos >= n or line[pos] != ">" or col - floor > 3:
                return False, pos, 0
            col += 1
            pos += 1
            floor = col + (1 if pos < n and (line[pos] == " " or line[pos] == "\t") else 0)
        else:
            if pos < n and col < c:
                return False, pos, 0
            floor = c
    while pos < n and (line[pos] == " " or line[pos] == "\t"):
        col += 1 if line[pos] == " " else 4 - col % 4
        pos += 1
    return True, pos, col - floor


def _r03_fence_closes(line: str, pos: int, fence_ch: str, fence_len: int) -> bool:
    """True when ``line[pos:]`` closes a fence: its character, at least as long, then only blanks."""
    if line[pos] != fence_ch:
        return False
    rest = line[pos:]
    run = _r03_fence_run(rest)
    return (run is not None and run[0] == fence_ch and run[1] >= fence_len
            and not rest[run[1]:].strip(" \t"))


def _r03_code_spans(text: str, markdown: bool) -> list:
    """Line spans of fenced code and, in Markdown input, indented code blocks.

    A fence opens and closes on a line indented at most three spaces (CommonMark;
    inside a list item the three count from the item's content column). It closes
    only on a line of the opening character that is at least as long as the
    opener and carries nothing after it, so a four-backtick block can hold a
    three-backtick example, a tilde fence is not closed by backticks, and an
    over-indented fence line stays inside the block. A backtick opener whose
    info string holds a backtick is an inline code span, not a fence. An unclosed
    fence runs to the end of the text.

    In Markdown input a fence may also start on the line of a list item marker or
    after a blockquote ``>``, nested ones included. It closes on a fence line at
    the content position of the innermost container, and it ends where a
    container ends: a blockquote at a line without ``>``, a list item at a
    non-blank line indented less than its content column. Only the fence lines
    are masked, never the rest of the list or the quote.

    An indented line is code when it sits four or more columns past its
    container (the document, or the content column of the innermost open list
    item) and does not continue a paragraph: the first line of the document, a
    line after a blank line, a heading, a fence, a setext underline or a thematic
    break qualifies, and so does every further indented line of the same block. A
    line indented less than that is a continuation paragraph and stays prose, and
    so does a lazy continuation of a paragraph. A setext underline (a run of
    ``=`` or ``-`` below a paragraph line) and a thematic break (three or more of
    one of ``-``, ``*``, ``_``) end the paragraph, each at most three columns
    past its container. An underline ends only a paragraph that holds no
    blockquote or HTML line, whose own block it cannot underline. A list item stays open while its lines are indented to
    its content column, and a fence inside it ends with it. A list item cannot
    interrupt a paragraph unless it is a bullet or numbered 1. Missing a case is
    the safe error here, because masking real prose hides a finding.
    """
    spans: list = []
    fence_ch = ""
    fence_len = 0
    fence_ctx: list = []  # containers of the open fence, outermost first
    para = False      # the previous line was paragraph text
    plain = False     # that paragraph has no blockquote or HTML line, so a setext underline can end it
    in_code = False   # the previous non-blank line was indented code
    items: list = []  # content columns of the open list items, ascending
    for start, end in _line_spans(text):
        line = text[start:end]
        if fence_ch:
            held, at, at_rel = _r03_fence_line(line, fence_ctx)
            if held:
                spans.append((start, end))
                if at < len(line) and at_rel <= 3 and _r03_fence_closes(line, at, fence_ch, fence_len):
                    fence_ch = ""
                continue
            fence_ch = ""  # a container of the fence ended; read this line afresh
        body = line.lstrip(" \t")
        if not body:
            para = False
            continue
        pos = len(line) - len(body)
        indent = _r03_indent_width(line)
        run = _r03_fence_run(body)
        k = bisect.bisect_right(items, indent)  # items this line is indented into
        col = items[k - 1] if k else 0
        rel = indent - col
        brk = markdown and rel <= 3 and _r03_is_break(body)
        is_item = markdown and rel <= 3 and not brk and _r03_marker_end(line, pos) >= 0
        if is_item and para and k == len(items) and not _r03_item_interrupts(body):
            is_item = False
        is_heading = markdown and rel <= 3 and _R03_HEADING_START_RE.match(body) is not None
        setext = markdown and para and plain and k == len(items) and rel <= 3 and _r03_is_setext(body)
        opens = run is not None and rel <= 3 and not (run[0] == "`" and "`" in body[run[1]:])
        quote = markdown and rel <= 3 and body[0] == ">"
        nested = None
        if not opens and (is_item or quote):
            nested = _r03_container_fence(line, pos, indent)
        if k < len(items) and para and not (opens or is_item or is_heading or brk or quote):
            continue  # a lazy continuation keeps its list item open
        del items[k:]
        if quote and not body.lstrip(" \t>"):
            para = False  # a blockquote line with nothing on it ends the paragraph, as a blank line does
            continue
        if opens:
            fence_ch, fence_len = run
            fence_ctx = [col] if col else []
            spans.append((start, end))
            para = False
            in_code = False
            continue
        if nested:
            fence_ctx = []
            for c in ([col] if col else []) + nested[0]:
                if c != _R03_QUOTE and fence_ctx and fence_ctx[-1] != _R03_QUOTE:
                    fence_ctx[-1] = c  # only the innermost of adjacent list items matters
                else:
                    fence_ctx.append(c)
            for c in nested[0]:
                if c == _R03_QUOTE:
                    break
                items.append(c)
            fence_ch, fence_len = nested[1]
            spans.append((start, end))
            para = False
            in_code = False
            continue
        if not markdown:
            continue
        if brk or setext:
            para = False
            in_code = False
            continue
        if rel >= 4:
            if in_code or not para:
                spans.append((start, end))
                in_code = True
                para = False
            continue
        in_code = False
        plain = (plain if para else True) and body[0] != ">" and body[0] != "<"
        para = not is_heading
        if is_item:
            plain = True
            content_col, first, _ = _r03_list_content_col(line, pos, indent)
            items.append(content_col)
            if first == "code":
                spans.append((start, end))
                in_code = True
            para = first == "text"
    return spans


def _r03_stage_one(text: str, latex: bool, markdown: bool = False) -> str:
    """Blank code and comments; headings and sectioning commands stay."""
    spans: list = _r03_code_spans(text, markdown)
    spans.extend(_r03_pairs(text, "<!--", "-->"))
    if latex:
        # An unescaped percent sign opens a comment. A Markdown or plain-text
        # file uses it as a unit (`63%`), so this runs on LaTeX input only.
        for m in re.finditer(r"(?<!\\)(?:\\\\)*(%[^\n\r]*)", text):
            spans.append(m.span(1))
        spans.extend(m.span() for m in _R03_VERB_RE.finditer(text))
    else:
        spans.extend(m.span() for m in re.finditer(r"`[^`\n]+`", text))
    return _r03_blank(text, spans)


def _r03_cell_count(row: str) -> int:
    """Cells in a table row, ignoring one outer pipe on each side."""
    t = row.strip(" \t")
    if t.startswith("|"):
        t = t[1:]
    if t.endswith("|") and not t.endswith("\\|"):
        t = t[:-1]
    return len(_R03_PIPE_RE.split(t))


def _r03_is_delimiter_row(row: str) -> bool:
    t = row.strip(" \t")
    if "|" not in t:
        return False
    if t.startswith("|"):
        t = t[1:]
    if t.endswith("|"):
        t = t[:-1]
    return all(_R03_DELIMITER_CELL_RE.fullmatch(cell) for cell in t.split("|"))


def _r03_table_spans(text: str, line_spans: list) -> list:
    """Spans of Markdown tables: a header row, a delimiter row, and body rows.

    The header and the delimiter hold the same number of cells (GitHub rule).
    The body runs until a blank line or a line without a pipe. Outer pipes are
    optional on every row.
    """
    spans: list = []
    count = len(line_spans)
    i = 0
    while i + 1 < count:
        header = text[line_spans[i][0]:line_spans[i][1]]
        if "|" in header:
            delimiter = text[line_spans[i + 1][0]:line_spans[i + 1][1]]
            if _r03_is_delimiter_row(delimiter) and _r03_cell_count(header) == _r03_cell_count(delimiter):
                j = i + 2
                while j < count and "|" in text[line_spans[j][0]:line_spans[j][1]]:
                    j += 1
                spans.append((line_spans[i][0], line_spans[j - 1][1]))
                i = j
                continue
        i += 1
    return spans


def _r03_mask_spans(text: str) -> list:
    """Spans of material that carries digits without being a result.

    Labels, citations, layout lengths, identifiers, reference numbers, link
    targets, and paths. Shared by the prose pass and by the caption check, which
    reads a caption in isolation.
    """
    spans: list = []
    for pattern in (
        _R03_ARG1_RE, _R03_ARGN_RE, _R03_SECTIONING_RE, _R03_LENGTH_RE,
        _R03_IDENT_RE, _R03_REF_RE, _R03_SECTION_SIGN_RE,
    ):
        spans.extend(m.span() for m in pattern.finditer(text))
    # Markdown link and image targets.
    spans.extend(m.span() for m in re.finditer(r"\]\([^)\s]{0,500}\)", text))
    # A whitespace-delimited token that holds a slash and a letter is a path or
    # a file name. A bare ratio such as `0.93/1.00` has no letter and stays.
    for m in re.finditer(r"(?<!\S)[^\s/]*/\S*", text):
        token = m.group()
        if re.search(r"[A-Za-z]", token.replace("\\%", "")):
            spans.append(m.span())
    return spans


def _r03_stage_two(text: str, latex: bool, extra: tuple = ()) -> tuple:
    """Blank non-prose material. Returns (blanked text, display spans).

    ``extra`` holds further display spans, such as the captions of a LaTeX file.
    """
    spans: list = []
    display: list = list(extra)

    # Display environments, found by search so an unclosed one costs nothing.
    covered = 0
    exhausted = set()
    for m in _R03_BEGIN_ENV_RE.finditer(text):
        if m.start() < covered or m.group(1) in exhausted:
            continue
        end_tok = "\\end{" + m.group(1) + "}"
        j = text.find(end_tok, m.end())
        if j < 0:
            exhausted.add(m.group(1))
            continue
        covered = j + len(end_tok)
        display.append((m.start(), covered))
    display.extend(_r03_pairs(text, "\\[", "\\]"))
    display.extend(_r03_pairs(text, "$$", "$$"))

    # Markdown tables and headings, line by line. A line that starts with a
    # pipe is a table row; a table without outer pipes is found by its header
    # and delimiter rows.
    line_spans = _line_spans(text)
    for start, end in line_spans:
        stripped = text[start:end].lstrip()
        if stripped.startswith("|"):
            display.append((start, end))
        elif not latex and stripped.startswith("#"):
            spans.append((start, end))
    display.extend(_r03_table_spans(text, line_spans))

    spans.extend(display)
    spans.extend(_r03_mask_spans(text))
    return _r03_blank(text, spans), display


def _r03_is_latex(base: str, text: str) -> bool:
    ext = base.rsplit(".", 1)[-1] if "." in base else ""
    if ext in ("tex", "sty", "cls", "ltx"):
        return True
    if ext in ("md", "markdown", "rst", "txt"):
        return False
    return bool(_R03_LATEX_SIGNATURE_RE.search(text))


def _r03_is_markdown(base: str, text: str, latex: bool) -> bool:
    """True for a `.md` or `.markdown` file, or for text with no name and no LaTeX."""
    if base.endswith(".md") or base.endswith(".markdown"):
        return True
    return base == "" and not latex and _R03_LATEX_MARKER_RE.search(text) is None


def _r03_appendix_named(base: str) -> bool:
    """True when a token of the file name is appendix or supplement."""
    return any(t in _R03_APPENDIX_NAME_TOKENS for t in _R03_APPENDIX_NAME_SPLIT_RE.split(base))


def _r03_appendix_spans(masked: str, latex: bool) -> list:
    """Sorted, merged (start, end) spans of appendix prose.

    LaTeX: everything after `\\appendix` and the body of an `appendices`
    environment (an unclosed one runs to the end). Markdown: the text under a
    heading that begins with "Appendix", up to the next heading of the same or
    a higher level that does not. Only the six heading levels are tracked, so
    the scan stays linear however many headings the file holds.
    """
    spans: list = []
    if latex:
        m = _R03_APPENDIX_CMD_RE.search(masked)
        if m is not None:
            spans.append((m.end(), len(masked)))
        open_tok, close_tok = "\\begin{appendices}", "\\end{appendices}"
        pos = 0
        while True:
            i = masked.find(open_tok, pos)
            if i < 0:
                break
            j = masked.find(close_tok, i + len(open_tok))
            if j < 0:
                spans.append((i, len(masked)))
                break
            pos = j + len(close_tok)
            spans.append((i, pos))
    else:
        open_at: list = [None] * 7
        for m in _R03_MD_HEADING_RE.finditer(masked):
            level = len(m.group(1))
            key = _r03_title_key(m.group(2))
            if key.startswith("appendix") or key.startswith("appendices"):
                if open_at[level] is None:
                    open_at[level] = m.end()
                continue
            for lv in range(level, 7):
                if open_at[lv] is not None:
                    spans.append((open_at[lv], m.start()))
                    open_at[lv] = None
        for lv in range(1, 7):
            if open_at[lv] is not None:
                spans.append((open_at[lv], len(masked)))
    spans.sort()
    merged: list = []
    for start, end in spans:
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def _r03_title_key(raw: str) -> str:
    title = raw.strip().strip("#").strip().strip("*_ ").lower()
    title = _R03_TITLE_NUMBER_RE.sub("", title)
    return title.strip("*_ .:")


def _r03_regions(masked: str, base: str) -> list:
    """Return (start, end, label) for each abstract or introduction span."""
    if "abstract" in base:
        return [(0, len(masked), "abstract")]
    if "intro" in base:
        return [(0, len(masked), "introduction")]
    regions = []
    open_tok, close_tok = "\\begin{abstract}", "\\end{abstract}"
    for start, end in _r03_pairs(masked, open_tok, close_tok):
        regions.append((start + len(open_tok), end - len(close_tok), "abstract"))

    sections = list(_R03_TEX_SECTION_RE.finditer(masked))
    for idx, m in enumerate(sections):
        key = _r03_title_key(m.group(1))
        if key not in ("abstract", "introduction"):
            continue
        end = sections[idx + 1].start() if idx + 1 < len(sections) else len(masked)
        stop = masked.find("\\end{document}", m.end())
        if 0 <= stop < end:
            end = stop
        regions.append((m.end(), end, key))

    headings = list(_R03_MD_HEADING_RE.finditer(masked))
    for idx, m in enumerate(headings):
        key = _r03_title_key(m.group(2))
        if key not in ("abstract", "introduction"):
            continue
        level = len(m.group(1))
        end = len(masked)
        for later in headings[idx + 1:]:
            if len(later.group(1)) <= level:
                end = later.start()
                break
        regions.append((m.end(), end, key))
    return sorted(regions)


def _r03_sentences(masked: str, cuts: list) -> list:
    """Split into (start, end) sentences; ``cuts`` are extra hard boundaries."""
    points = {0, len(masked)}
    points.update(c for c in cuts if 0 <= c <= len(masked))
    points.update(m.start() for m in _R03_BLOCK_RE.finditer(masked))
    ordered = sorted(points)
    sentences = []
    for a, b in zip(ordered, ordered[1:]):
        piece_start = a
        for m in _R03_BOUNDARY_RE.finditer(masked, a, b):
            token = _R03_PRECEDING_TOKEN_RE.search(masked[max(a, m.start() - 16):m.start()])
            if token is not None:
                word = token.group(1).lower()
                if word in _R03_ABBREVIATIONS or ("." in word and all(len(p) == 1 for p in word.split("."))):
                    continue
            sentences.append((piece_start, m.end("end")))
            piece_start = m.end()
        sentences.append((piece_start, b))
    trimmed = []
    for start, end in sentences:
        chunk = masked[start:end]
        lead = len(chunk) - len(chunk.lstrip())
        tail = len(chunk.rstrip())
        if tail > lead:
            trimmed.append((start + lead, start + tail))
    return trimmed


def _r03_parse_number(raw: str):
    cleaned = raw.replace("\u2212", "-")
    cleaned = re.sub(r"[^0-9.+\-]", "", cleaned)
    try:
        return float(cleaned)
    except ValueError:
        return None


def _r03_intervals(masked: str) -> tuple:
    """Return ([(start, end)] intervals, [(start, end)] confidence levels)."""
    found = []
    levels = []

    def qualifies(a: str, b: str, explicit: bool) -> bool:
        # An explicit CI statement ("95% interval", "CI", "confidence
        # interval") qualifies with any endpoints. Otherwise an endpoint must
        # be a decimal or a percentage, and a domain such as [0, 1] or
        # [0.0, 1.0] is a range, not an estimate.
        if explicit:
            return True
        if not ("." in a or "." in b or "%" in a or "%" in b):
            return False
        va, vb = _r03_parse_number(a), _r03_parse_number(b)
        domain = (-1.0, 0.0, 1.0, 100.0)
        return not (va in domain and vb in domain)

    for m in _R03_BRACKET_RE.finditer(masked):
        prefix = masked[max(0, m.start() - 40):m.start()]
        if _R03_NUMBER_BEFORE_RE.search(prefix) or _R03_CI_WORD_BEFORE_RE.search(prefix):
            if qualifies(m.group("a"), m.group("b"), False):
                found.append(m.span())

    for kw in _R03_KEYWORD_RE.finditer(masked):
        window = max(0, kw.start() - 60)
        prefix = masked[window:kw.start()]
        level = _R03_LEVEL_BEFORE_RE.search(prefix)
        if level is not None:
            lo = window + level.start(1)
            levels.append((lo, lo + len(level.group(1).rstrip())))
        after = _R03_LEVEL_AFTER_RE.match(masked, kw.start())
        if after is not None:
            levels.append(after.span(1))
        tail = _R03_KEYED_TAIL_RE.match(masked, kw.end())
        if tail is None:
            continue
        keyword = kw.group().lower()
        explicit = (
            level is not None
            or keyword in ("ci", "cis")
            or bool(_R03_WORD_BEFORE_KEYWORD_RE.search(prefix))
        )
        if not explicit:
            if "," in tail.group("lead"):
                continue  # "in this interval, 12.4% and 15.8% fail": a clause, not an interval
            if tail.group("sep").strip().lower() == "and" and "between" not in tail.group("words"):
                continue  # "X and Y" is a pair of values unless "between" opens it
        if (not explicit or keyword in ("interval", "intervals")) and _R03_TIME_UNIT_RE.match(masked, tail.end()):
            continue  # "an interval of 0.5 to 2 seconds" is a duration
        if qualifies(tail.group("a"), tail.group("b"), explicit):
            found.append((window + level.start(1) if level is not None else kw.start(), tail.end()))

    found.sort()
    merged = []
    for span in found:
        if merged and span[0] < merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], span[1]))
        else:
            merged.append(span)
    return merged, levels


def _r03_figures(masked: str) -> list:
    """Start offsets of precise figures (decimals and percentages)."""
    out = []
    for m in _R03_FIGURE_RE.finditer(masked):
        has_decimal = m.group("dec") is not None
        has_percent = m.group("pct") is not None
        if not (has_decimal or has_percent):
            continue
        if has_decimal and not has_percent:
            nxt = masked[m.end():m.end() + 2]
            if nxt[:1] in ("B", "b") and not nxt[1:2].isalnum():
                continue  # a parameter count such as 0.5B, not a result
        out.append(m.start())
    return out


def _r03_env_spans(text: str, begin_re) -> list:
    """Spans of each environment whose ``\\begin`` token ``begin_re`` finds.

    Found by search, so an unclosed environment costs one scan and not one per
    opener.
    """
    spans: list = []
    covered = 0
    exhausted = set()
    for m in begin_re.finditer(text):
        if m.start() < covered or m.group(1) in exhausted:
            continue
        end_tok = "\\end{" + m.group(1) + "}"
        j = text.find(end_tok, m.end())
        if j < 0:
            exhausted.add(m.group(1))
            continue
        covered = j + len(end_tok)
        spans.append((m.start(), covered))
    return spans


def _r03_brace_map(text: str) -> dict:
    """Map the offset of each ``{`` to the offset of its closing ``}``.

    A backslash escapes the next character, so ``\\{`` and ``\\\\{`` read as they
    do in LaTeX. One pass with a stack, so a file of unclosed groups costs
    nothing extra per group.
    """
    match: dict = {}
    stack: list = []
    for m in _R03_BRACE_TOKEN_RE.finditer(text):
        ch = m.group()
        if ch == "{":
            stack.append(m.start())
        elif ch == "}" and stack:
            match[stack.pop()] = m.start()
    return match


def _r03_skip_blanks(text: str, i: int) -> int:
    return _R03_BLANKS_RE.match(text, i).end()


def _r03_captions(text: str) -> list:
    """(command start, body start, body end, offset after the closing brace) per caption.

    ``\\caption{..}``, ``\\caption*{..}``, ``\\caption[short]{..}`` and
    ``\\captionof{type}{..}``, braces balanced. A caption inside a code
    environment is an example and is not read; a caption that opens inside
    another one is part of it.
    """
    if "\\caption" not in text:
        return []
    src = _r03_blank(text, _r03_env_spans(text, _R03_CODE_ENV_RE))
    n = len(src)
    braces = None
    out: list = []
    covered = 0
    for m in _R03_CAPTION_RE.finditer(src):
        if m.start() < covered:
            continue
        if braces is None:
            braces = _r03_brace_map(src)
        i = _r03_skip_blanks(src, m.end())
        if m.group("of"):
            if i >= n or src[i] != "{" or i not in braces:
                continue
            i = _r03_skip_blanks(src, braces[i] + 1)
        if i < n and src[i] == "[":
            j = src.find("]", i, i + 600)
            if j < 0:
                continue
            i = _r03_skip_blanks(src, j + 1)
        if i < n and src[i] == "{" and i in braces:
            covered = braces[i] + 1
            out.append((m.start(), i + 1, braces[i], covered))
    return out


def _r03_strip_math(text: str) -> str:
    """Blank ``$..$`` and ``\\(..\\)`` math, length-preserving. A ``\\$`` is a dollar sign."""
    marks = [m.start() for m in _R03_DOLLAR_RE.finditer(text)]
    spans = [(marks[i], marks[i + 1] + 1) for i in range(0, len(marks) - 1, 2)]
    spans.extend(_r03_pairs(text, "\\(", "\\)"))
    return _r03_blank(text, spans)


def _r03_plain_text(raw: str) -> str:
    """The words of a LaTeX fragment: no citations, references, math or commands.

    A command is dropped and its text argument is kept, so ``\\textbf{Left:} the
    run`` reads ``Left: the run``.
    """
    # A line break first: the two words in `one\\two` are not a word and a command.
    t = raw.replace("\\\\", " ")
    t = _R03_ARG1_RE.sub(" ", t)
    t = _R03_ARGN_RE.sub(" ", t)
    t = _R03_FIRST_ARG_RE.sub(" ", t)
    t = _R03_RULE_ARGS_RE.sub(" ", t)
    t = _R03_SPAN_ARGS_RE.sub(" ", t)
    t = _r03_strip_math(t)
    t = _R03_COMMAND_RE.sub(" ", t)
    t = _R03_ESCAPED_RE.sub(r"\1", t)
    t = re.sub(r"[{}~\\]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _r03_count_words(plain: str) -> int:
    """Tokens with at least two letters in a row; numbers and single letters are not words."""
    return sum(1 for token in plain.split() if _R03_WORD_RE.search(token))


def _r03_legend_spans(text: str) -> list:
    """Spans of legend and decoding metadata: quantile lines, significance levels, markers.

    Used on a caption only. A number beside the word that names a line, a threshold
    or a symbol is a key to the display and not a result.
    """
    spans: list = []
    for pattern in _R03_LEGEND_RES:
        spans.extend(m.span() for m in pattern.finditer(text))
    return spans


_R03_SPAN_BLANKS_RE = re.compile(r"[ \t\r\n~]+")


def _r03_span_figures(segment: str) -> int:
    """Precise figures in a fragment read alone, with the masks and the level rule of check A.

    A confidence level and the numbers of a legend (``_r03_legend_spans``) are not figures.
    """
    masked = _r03_blank(segment, _r03_mask_spans(segment))
    # The fragment is only counted, never located, so its blanks can be collapsed: a
    # caption wrapped and indented in the source reads like one written on one line.
    masked = _R03_SPAN_BLANKS_RE.sub(" ", masked)
    _intervals, levels = _r03_intervals(masked)
    # Legends are read before the levels are blanked: blanking "99.7% confidence"
    # first would cut the end off "68%, 95% and 99.7% confidence intervals".
    return len(_r03_figures(_r03_blank(masked, levels + _r03_legend_spans(masked))))


def _r03_is_setup_title(raw: str) -> bool:
    """True when a heading title names a method or a setup and no outcome."""
    words = {w.lower() for w in _R03_TITLE_WORD_RE.findall(_R03_TITLE_HYPHEN_RE.sub("", raw))}
    return bool(words & _R03_SETUP_WORDS) and not (words & _R03_OUTCOME_WORDS)


def _r03_setup_spans(text: str) -> list:
    """Sorted (start, end) spans of LaTeX method and setup sections.

    A ``\\section``, ``\\subsection``, ``\\subsubsection`` or ``\\paragraph`` heading
    (a star or a short title in brackets allowed) whose title names a method or a
    setup opens a span that runs to the next heading of the same or a higher level,
    or to the end of the text. Exact settings (learning rates, dropout, splits)
    belong there. One pass, so a file of headings costs a single scan.
    """
    spans: list = []
    open_level = -1
    open_start = 0
    for m in _R03_TEX_HEADING_RE.finditer(text):
        level = _R03_HEADING_LEVELS[m.group(1)]
        if open_level >= 0 and level <= open_level:
            spans.append((open_start, m.start()))
            open_level = -1
        if open_level < 0 and _r03_is_setup_title(m.group(2)):
            open_level, open_start = level, m.end()
    if open_level >= 0:
        spans.append((open_start, len(text)))
    return spans


def _r03_document_range(stage_one: str) -> tuple:
    """(start, end) of the LaTeX document body: after ``\\begin{document}``, before ``\\end{document}``.

    A fragment with neither command is all body.
    """
    start, end = 0, len(stage_one)
    tok = "\\begin{document}"
    i = stage_one.find(tok)
    if i >= 0:
        start = i + len(tok)
    j = stage_one.find("\\end{document}", start)
    if j >= 0:
        end = j
    return start, end


_R03_DECIMAL_RES: dict = {}


def _r03_decimal_re(places: int):
    """A number with at least ``places`` decimal places, sign included.

    The sign is a minus, a plus, U+2212, or one wrapped in math (``$-$0.05``,
    ``$-0.05$``). A hyphen inside a name (``ResNet-18.1234``) is not a sign, and
    a number glued to a word or to another number is an identifier. Up to five
    thousands groups belong to the number (``1,234.5678``); the bound keeps a long
    run of ``123,123,123`` from being rescanned at every group.
    """
    pattern = _R03_DECIMAL_RES.get(places)
    if pattern is None:
        pattern = _R03_DECIMAL_RES[places] = re.compile(
            r"(?<![\w.])(?:\$?[-+−]\$?)?(?<![\w.])(?:\d{1,3}(?:,\d{3}){1,5}|\d*)\.\d{%d,}(?!\d)(?!\.\d)" % places
        )
    return pattern


def _r03_significant(number: str) -> int:
    """Significant digits of a matched number: its digits without the leading zeros.

    ``0.0143`` has three, ``0.00025`` two and ``0.0001`` one; a zero after the
    first digit counts (``0.1000`` has four). Leading zeros are the ASCII zero only,
    so the JavaScript port counts exotic digits the same way.
    """
    return len(re.sub(r"\D", "", number).lstrip("0"))


def _r03_make_locate(text: str):
    """A function from an offset to (line, column, line text), for findings."""
    spans = _line_spans(text)
    starts = [s for s, _e in spans]

    def locate(offset: int) -> tuple:
        line_no = max(1, bisect.bisect_right(starts, offset))
        line_start, line_end = spans[line_no - 1]
        return line_no, offset - line_start + 1, text[line_start:line_end]

    return locate


def _rule_03(text: str, file_path: str = "") -> list[Violation]:
    """Flag numeric intervals in prose and precise figures stacked up front.

    Check A reports a sentence that carries a numeric interval ("[0.51, 0.83]",
    "95% interval 0.51 to 0.83", "95% CI 0.6-0.9") anywhere outside a table and
    outside an appendix: a file named for an appendix or a supplement, the text
    after a LaTeX `\\appendix`, an `appendices` environment, or the text under a
    Markdown heading that begins with "Appendix". Check B reports, inside an
    abstract or introduction, a run of
    ``_R03_RUN_LENGTH`` consecutive sentences that each carry at least
    ``_R03_RUN_FIGURES`` precise figures, and any sentence that carries
    ``_R03_CROWDED`` or more. The abstract or introduction is the whole text
    when the file name contains "abstract" or "intro", else an abstract
    environment, an Introduction or Abstract section, or a Markdown heading
    of that name.

    A LaTeX file (a `.tex` name, or unnamed text with a LaTeX marker) is read
    further, and each check skips the same appendix and supplement text as check
    A. Check B also reports the run, but not the crowded sentence, in the body
    prose between the abstract and the introduction and the appendix, from
    `\\begin{document}` to `\\end{document}`, except in a method or setup section
    (`_r03_setup_spans`). Check C reports a `\\caption`,
    `\\caption*`, `\\caption[..]` or `\\captionof` that carries
    ``_R03_CAPTION_FIGURES`` precise figures or more than ``_R03_CAPTION_WORDS``
    words, once per caption; a caption feeds neither check A nor check B, and the
    numbers of a legend (`_r03_legend_spans`) are not figures. Check
    D reports a paragraph that holds ``_R03_DECIMAL_COUNT`` numbers written to
    ``_R03_DECIMAL_PLACES`` or more decimal places and ``_R03_DECIMAL_SIGNIFICANT``
    or more significant digits, once, at the first, in the abstract and the
    introduction too, except in a method or setup section. Every table
    environment RULE-A reads (tabular, tabularx, tabulary, longtable, tblr) is a
    display here, so its cells feed none of the checks. Markdown, plain text and
    reStructuredText are not read by B (body), C or D.

    Never raises: the guard treats an exception from any advisory detector as
    a broken package and drops every advisory, so a malformed input must cost
    one rule's findings and nothing more.
    """
    try:
        return _rule_03_scan(text, file_path)
    except Exception:
        return []


def _rule_03_scan(text: str, file_path: str) -> list[Violation]:
    if not isinstance(text, str) or not text:
        return []
    base = re.split(r"[\\/]", str(file_path or ""))[-1].lower()
    latex = _r03_is_latex(base, text)
    markdown = _r03_is_markdown(base, text, latex)
    stage_one = _r03_stage_one(text, latex, markdown)
    regions = _r03_regions(stage_one, base)
    # Detailed appendix prose is where intervals removed from an abstract belong,
    # so check A skips it. Check B does not.
    if _r03_appendix_named(base):
        appendix: list = [(0, len(stage_one))]
    else:
        appendix = _r03_appendix_spans(stage_one, latex)
    appendix_starts = [s for s, _e in appendix]
    # A method or setup section holds the exact settings a reader needs to repeat the
    # work, so the body run of check B and check D skip it.
    setup = _r03_setup_spans(stage_one) if latex else []
    setup_starts = [s for s, _e in setup]
    # A caption is display material: it feeds check C and neither A nor B, in or
    # out of a figure or table environment.
    captions = _r03_captions(stage_one) if latex else []
    masked, display = _r03_stage_two(stage_one, latex, tuple((c[0], c[3]) for c in captions))
    doc_start, doc_end = _r03_document_range(stage_one) if latex else (0, 0)

    def in_appendix(offset: int) -> bool:
        slot = bisect.bisect_right(appendix_starts, offset) - 1
        return slot >= 0 and offset < appendix[slot][1]

    def in_setup(offset: int) -> bool:
        slot = bisect.bisect_right(setup_starts, offset) - 1
        return slot >= 0 and offset < setup[slot][1]

    cuts = [s for s, _e in display] + [e for _s, e in display]
    for start, end, _label in regions:
        cuts.extend((start, end))
    for start, end in setup:
        cuts.extend((start, end))
    sentences = _r03_sentences(masked, cuts)
    if not sentences and not captions:
        return []
    sentence_starts = [s for s, _e in sentences]

    intervals, levels = _r03_intervals(masked)
    figures_text = _r03_blank(masked, levels)
    figure_starts = _r03_figures(figures_text)

    spans = _line_spans(text)
    line_starts = [s for s, _e in spans]

    def locate(offset: int) -> tuple:
        line_no = max(1, bisect.bisect_right(line_starts, offset))
        line_start, line_end = spans[line_no - 1]
        return line_no, offset - line_start + 1, text[line_start:line_end]

    out: list[Violation] = []

    # Check A: one finding per sentence that carries an interval.
    by_sentence: dict = {}
    for start, end in intervals:
        slot = bisect.bisect_right(appendix_starts, start) - 1
        if slot >= 0 and start < appendix[slot][1]:
            continue
        idx = bisect.bisect_right(sentence_starts, start) - 1
        if idx >= 0 and start < sentences[idx][1]:
            by_sentence.setdefault(idx, []).append((start, end))
    for idx in sorted(by_sentence):
        hits = by_sentence[idx]
        start, end = hits[0]
        line_no, col, line = locate(start)
        many = f"{len(hits)} numeric intervals" if len(hits) > 1 else "a numeric interval"
        out.append(Violation(
            rule="RULE-03",
            line=line_no,
            column=col,
            excerpt=_excerpt(line, (col - 1, col - 1 + (end - start))),
            detail=(
                f"{many} in prose; keep what the reader needs to judge the claim, "
                "in words where possible, and give the interval in a table or figure"
            ),
        ))

    # Check B: stacked figures, inside an abstract or an introduction and, in a
    # LaTeX file, in the body prose between them.
    merged: list = []
    for start, end, label in regions:
        if merged and start < merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end), merged[-1][2])
        else:
            merged.append((start, end, label))
    region_starts = [r[0] for r in merged]

    def region_of(offset: int):
        idx = bisect.bisect_right(region_starts, offset) - 1
        if idx >= 0 and offset < merged[idx][1]:
            return merged[idx][2]
        return None

    def label_of(offset: int):
        label = region_of(offset)
        if (
            label is None and latex and doc_start <= offset < doc_end
            and not in_appendix(offset) and not in_setup(offset)
        ):
            return _R03_BODY
        return label

    counts = []
    for start, end in sentences:
        n = bisect.bisect_left(figure_starts, end) - bisect.bisect_left(figure_starts, start)
        counts.append((start, end, n, label_of(start)))

    def report_run(run: list) -> None:
        start = run[0][0]
        total = sum(item[2] for item in run)
        line_no, col, line = locate(start)
        if run[0][3] == _R03_BODY:
            detail = (
                f"{len(run)} consecutive sentences in the body text carry {total} precise figures. "
                "Keep the few magnitudes behind the main findings, round them, "
                "and move the rest to a table or an appendix"
            )
        else:
            detail = (
                f"{len(run)} consecutive sentences in the {run[0][3]} carry {total} precise figures; "
                "keep the few magnitudes behind the main findings and move the rest to a table"
            )
        out.append(Violation(
            rule="RULE-03",
            line=line_no,
            column=col,
            excerpt=_excerpt(line, (col - 1, col - 1 + min(run[0][1] - start, 80))),
            detail=detail,
        ))

    run: list = []
    for item in counts + [(0, 0, 0, None)]:
        label = item[3]
        if label is not None and item[2] >= _R03_RUN_FIGURES and (not run or run[-1][3] == label):
            run.append(item)
            continue
        if len(run) >= _R03_RUN_LENGTH:
            report_run(run)
        else:
            for start, end, n, lab in run:
                limit = _R03_BODY_CROWDED if lab == _R03_BODY else _R03_CROWDED
                if limit is not None and n >= limit:
                    line_no, col, line = locate(start)
                    where = "the body text" if lab == _R03_BODY else f"the {lab}"
                    out.append(Violation(
                        rule="RULE-03",
                        line=line_no,
                        column=col,
                        excerpt=_excerpt(line, (col - 1, col - 1 + min(end - start, 80))),
                        detail=(
                            f"one sentence in {where} carries {n} precise figures; "
                            "keep the one the claim rests on and move the rest to a table"
                        ),
                    ))
        run = [item] if (label is not None and item[2] >= _R03_RUN_FIGURES) else []
    # A crowded sentence below the run threshold of figures per sentence cannot
    # exist (crowded implies at least the run threshold), so nothing is missed.

    # Check C: a caption that carries precise figures or runs long. LaTeX only,
    # outside an appendix.
    cap_tail = (
        "A caption names the display, its pattern, and what the marks mean. Keep decoding "
        "values such as error-bar definitions; move repeated results, setup narration, "
        "and caveats to the text or an appendix"
    )
    for cmd_start, body_start, body_end, _close in captions:
        if in_appendix(cmd_start):
            continue
        body = stage_one[body_start:body_end]
        words = _r03_count_words(_r03_plain_text(body))
        figs = _r03_span_figures(body)
        if figs >= _R03_CAPTION_FIGURES:
            head = f"a caption carries {figs} precise figures"
        elif words > _R03_CAPTION_WORDS:
            head = f"a caption runs {words} words"
        else:
            continue
        line_no, col, line = locate(cmd_start)
        out.append(Violation(
            rule="RULE-03",
            line=line_no,
            column=col,
            excerpt=_excerpt(line, (col - 1, col - 1 + 80)),
            detail=f"{head}. {cap_tail}",
        ))

    # Check D: numbers written to many decimal places, in LaTeX body prose
    # (the abstract and introduction included) outside an appendix.
    if latex and sentences:
        places = _R03_DECIMAL_PLACES
        need = _R03_DECIMAL_COUNT
        per_sentence = _R03_DECIMAL_UNIT == "sentence"
        digits = _R03_DECIMAL_SIGNIFICANT
        long_starts = [
            m.start() for m in _r03_decimal_re(places).finditer(figures_text)
            if doc_start <= m.start() < doc_end and not in_appendix(m.start())
            and not in_setup(m.start()) and _r03_significant(m.group()) >= digits
        ]
        if long_starts:
            if per_sentence:
                units = sentences
            else:
                points = {0, len(masked)}
                points.update(m.start() for m in _R03_BLOCK_RE.finditer(masked))
                # A heading ends a paragraph even when its body runs on in the same
                # source line, as a \paragraph{} heading does.
                points.update(m.start() for m in _R03_TEX_HEADING_RE.finditer(stage_one))
                ordered = sorted(points)
                units = list(zip(ordered, ordered[1:]))
            unit = "sentence" if per_sentence else "paragraph"
            for start, end in units:
                lo = bisect.bisect_left(long_starts, start)
                hi = bisect.bisect_left(long_starts, end)
                if hi - lo < need:
                    continue
                line_no, col, line = locate(long_starts[lo])
                out.append(Violation(
                    rule="RULE-03",
                    line=line_no,
                    column=col,
                    excerpt=_excerpt(line, (col - 1, col - 1 + 20)),
                    detail=(
                        f"{hi - lo} numbers written to {places} or more decimal places in one {unit}. "
                        "Report the precision the measurement supports, usually two or three "
                        "significant digits, and keep the full values in a table or an appendix"
                    ),
                ))

    out.sort(key=lambda v: (v.line, v.column))
    return out


# ---------- RULE-A table cells (hook-only, LaTeX only) -----------------------


def _ra_tables(text: str) -> list:
    """Table environments as (begin, body start, body end, end, nested spans).

    ``text`` is LaTeX with comments and code blanked. A table nested in a table
    cell is its own entry and its span is listed under its parent, whose cells
    then skip it. Only the outer ``_RA_MAX_DEPTH`` levels are returned, so a file
    of deeply nested tables costs a bounded number of rescans.
    """
    stack: list = []
    open_count: dict = {}
    out: list = []
    for m in _RA_ENV_RE.finditer(text):
        env = m.group(2)
        if m.group(1) == "begin":
            stack.append([env, m.start(), m.end(), [], len(stack)])
            open_count[env] = open_count.get(env, 0) + 1
            continue
        if not open_count.get(env):
            continue
        k = len(stack) - 1
        while stack[k][0] != env:
            k -= 1
        node = stack[k]
        for dropped in stack[k:]:
            open_count[dropped[0]] -= 1
        del stack[k:]
        if node[4] < _RA_MAX_DEPTH:
            out.append((node[1], node[2], m.start(), m.end(), node[3], node[0]))
        if stack:
            stack[-1][3].append((node[1], m.end()))
    out.sort()
    return out


def _ra_skip_args(text: str, braces: dict, i: int, nargs: int) -> int:
    """Offset after the optional and brace arguments that open a table environment."""
    n = len(text)
    got = 0
    while got < nargs:
        j = _r03_skip_blanks(text, i)
        if j < n and text[j] == "[":
            k = text.find("]", j, j + 200)
            if k < 0:
                break
            i = k + 1
        elif j < n and text[j] == "{" and j in braces:
            i = braces[j] + 1
            got += 1
        else:
            break
    return i


def _ra_cells(work: str, base: int) -> list:
    """(offset, text) of each cell of a table body, split at ``&`` and at row breaks.

    ``work`` is the body with nested tables and captions blanked, and ``base`` the
    offset it starts at. A separator inside braces, such as the ``\\\\`` of a
    ``\\makecell``, does not split.
    """
    cells: list = []
    depth = 0
    start = 0
    for m in _RA_TOKEN_RE.finditer(work):
        tok = m.group()
        if tok == "{":
            depth += 1
        elif tok == "}":
            depth = max(0, depth - 1)
        elif depth:
            continue
        elif tok == "&" or tok[:2] == "\\\\" or tok in ("\\tabularnewline", "\\cr"):
            cells.append((base + start, work[start:m.start()]))
            start = m.end()
    cells.append((base + start, work[start:]))
    return cells


def _ra_sentence_count(plain: str) -> int:
    """Pieces of a cleaned cell that hold at least ``_RA_SENTENCE_WORDS`` words.

    A full stop after an abbreviation, an initial, or a dotted abbreviation such
    as ``e.g.`` does not end a sentence.
    """
    pieces: list = []
    start = 0
    for m in _RA_BOUNDARY_RE.finditer(plain):
        token = _R03_PRECEDING_TOKEN_RE.search(plain[max(0, m.start() - 16):m.start()])
        if token is not None:
            word = token.group(1).lower()
            if (
                word in _R03_ABBREVIATIONS
                or len(word) == 1
                or ("." in word and all(len(p) == 1 for p in word.split(".")))
            ):
                continue
        pieces.append(plain[start:m.end()])
        start = m.end()
    pieces.append(plain[start:])
    return sum(1 for piece in pieces if _r03_count_words(piece) >= _RA_SENTENCE_WORDS)


def _rule_a(text: str, file_path: str = "") -> list[Violation]:
    """Flag a LaTeX table cell that holds prose.

    A table environment (tabular, tabular*, tabularx, tabulary, longtable, tblr)
    outside an appendix or a supplement is flagged, once, when a cell holds more
    than ``_RA_CELL_WORDS`` words or ``_RA_CELL_SENTENCES`` sentences. A word is a
    token with two or more letters once commands, math, citations and references
    are stripped. The finding sits on the first such cell. LaTeX only: a Markdown
    table in an agent document may carry long cells by design, so a ``.md`` file
    is never read.

    Hook-only, like ``_rule_03``: the CLI audit classifies RULE-A as structural
    and never calls this. Never raises: the guard treats an exception from any
    advisory detector as a broken package.
    """
    try:
        return _rule_a_scan(text, file_path)
    except Exception:
        return []


def _rule_a_scan(text: str, file_path: str) -> list[Violation]:
    if not isinstance(text, str) or not text:
        return []
    base = re.split(r"[\\/]", str(file_path or ""))[-1].lower()
    if not _r03_is_latex(base, text) or _r03_appendix_named(base):
        return []
    stage_one = _r03_stage_one(text, True, False)
    if "\\begin{" not in stage_one:
        return []
    src = _r03_blank(stage_one, _r03_env_spans(stage_one, _R03_CODE_ENV_RE))
    tables = _ra_tables(src)
    if not tables:
        return []
    appendix = _r03_appendix_spans(stage_one, True)
    appendix_starts = [s for s, _e in appendix]
    braces = _r03_brace_map(src)
    captions = [(c[0], c[3]) for c in _r03_captions(src)]
    caption_starts = [a for a, _b in captions]
    locate = _r03_make_locate(text)
    out: list[Violation] = []
    for begin, body_start, body_end, _end, nested, env in tables:
        slot = bisect.bisect_right(appendix_starts, begin) - 1
        if slot >= 0 and begin < appendix[slot][1]:
            continue
        start = _ra_skip_args(src, braces, body_start, _RA_ARG_COUNT[env])
        if start >= body_end:
            continue
        lo = bisect.bisect_left(caption_starts, start)
        hi = bisect.bisect_left(caption_starts, body_end)
        skip = [(a - start, b - start) for a, b in nested + captions[lo:hi] if a >= start]
        work = _r03_blank(src[start:body_end], skip)
        for offset, raw in _ra_cells(work, start):
            if len(raw.strip()) < 18:
                continue
            plain = _r03_plain_text(raw)
            words = _r03_count_words(plain)
            if words > _RA_CELL_WORDS:
                head = f"a table cell of {words} words"
            elif words >= 2 * _RA_SENTENCE_WORDS and _ra_sentence_count(plain) >= _RA_CELL_SENTENCES:
                head = f"a table cell of {_ra_sentence_count(plain)} sentences"
            else:
                continue
            line_no, col, line = locate(offset + _RA_LEAD_RE.match(raw).end())
            out.append(Violation(
                rule="RULE-A",
                line=line_no,
                column=col,
                excerpt=_excerpt(line, (col - 1, col - 1 + 80)),
                detail=(
                    f"{head}; a table cell holds a number, a label, or a short phrase, "
                    "so move content that needs a sentence into the text"
                ),
            ))
            break
    out.sort(key=lambda v: (v.line, v.column))
    return out


# ---------- Dispatch table --------------------------------------------------


_DISPATCH: dict[str, Callable[..., list[Violation]]] = {
    "RULE-B": _rule_b,
    "RULE-D": _rule_d,
    "RULE-G": _rule_g,
    "RULE-I": _rule_i,
    "RULE-12": _rule_12,
    "RULE-05": _rule_05,
    "RULE-06": _rule_06,
    "RULE-03": _rule_03,
    "RULE-A": _rule_a,
}

# Detectors that also take the file path. RULE-03 locates the abstract and the
# introduction by file name as well as by markup, and RULE-03 and RULE-A read
# LaTeX only and exempt appendix and supplement files by name.
#
# RULE-A is registered here so a hook can reach it as `_rule_a`, but the audit
# never runs it: `primitive._CLASSIFICATION` holds RULE-A as structural only, and
# `primitive.audit` calls this module for a rule only when its bucket holds
# "mechanical". The structural RULE-A (bullet overuse) stays what `agent-style
# review` reports under that id, and the mechanical scope the benchmark pins
# (`EXPECTED_MECHANICAL`) does not change. RULE-03 is registered the same way.
_FILE_PATH_RULES = frozenset({"RULE-03", "RULE-A"})
