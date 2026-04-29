# SPDX-License-Identifier: MIT
"""Generate docs/rule-pack-compact.md and refresh docs/rule-pack.md from RULES.md.

Tracks yzhao062/agent-style#6.

The compact render keeps each rule's heading, full directive paragraph, and
the first BAD -> GOOD example pair, dropping metadata bullets, additional
example pairs, and rationale. Output target: less than 30 KB; current full
RULES.md is ~89 KB.

markdown-it-py provides block boundaries. Output is sliced from the
normalized original source bytes; the AST is never round-tripped to
markdown (which would silently rewrite comment formatting, fenced-code
interiors, and blank-line counts).

Usage:
    python scripts/build-compact.py             # regenerate all 6 outputs
    python scripts/build-compact.py --check     # exit non-zero if any output
                                                # would change
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from markdown_it import MarkdownIt


REPO_ROOT = Path(__file__).resolve().parent.parent

SOURCE = REPO_ROOT / "RULES.md"

ALIAS_OUTPUT = REPO_ROOT / "docs" / "rule-pack.md"

COMPACT_OUTPUTS = [
    REPO_ROOT / "docs" / "rule-pack-compact.md",
    REPO_ROOT / "packages" / "pypi" / "agent_style" / "data" / "rule-pack-compact.md",
    REPO_ROOT / "packages" / "npm" / "data" / "rule-pack-compact.md",
]

BUNDLE_RULES_OUTPUTS = [
    REPO_ROOT / "packages" / "pypi" / "agent_style" / "data" / "RULES.md",
    REPO_ROOT / "packages" / "npm" / "data" / "RULES.md",
]

COMPACT_INTRO = (
    "This is the compact render of the agent-style rule pack. Each rule "
    "shows the directive and one illustrative BAD → GOOD pair. The full "
    "reference (5+ BAD/GOOD pairs per rule, agent-instruction evidence, "
    "severity classification, and rationale) lives in `rule-pack.md` "
    "(alias of repo-root `RULES.md`) at the same release."
)

EXPECTED_RULE_COUNT = 21


def _die(msg: str) -> None:
    sys.stderr.write(f"build-compact: {msg}\n")
    sys.exit(1)


def read_source(path: Path) -> str:
    """Read source file, reject BOM, normalize CRLF/CR -> LF, ensure single trailing LF."""
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        _die(f"{path}: UTF-8 BOM detected; refusing to parse")
    text = raw.decode("utf-8")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if not text.endswith("\n"):
        text += "\n"
    return text


def parse_headings(text: str) -> list[dict]:
    """Return [{level, line_start, line_end, text}, ...] for every heading.

    Line indices are 0-based; line_end is exclusive (matches token.map convention).
    """
    md = MarkdownIt("commonmark")
    tokens = md.parse(text)
    out: list[dict] = []
    for i, tok in enumerate(tokens):
        if tok.type == "heading_open" and tok.map:
            level = int(tok.tag[1])
            content = ""
            if i + 1 < len(tokens) and tokens[i + 1].type == "inline":
                content = tokens[i + 1].content
            out.append(
                {
                    "level": level,
                    "line_start": tok.map[0],
                    "line_end": tok.map[1],
                    "text": content,
                }
            )
    return out


def _extract_first_pair(lines: list[str], start: int, end: int) -> list[int]:
    """In [start, end), return line indices for the first complete BAD -> GOOD pair.

    Tracks fenced-code state so that "- BAD" / "- GOOD" appearing inside a
    fenced code block are ignored. Returns [] if a complete pair is not found.
    The returned range may include blank lines and indented continuations
    between the BAD bullet and the matching GOOD bullet.
    """
    in_fence = False
    bad_start: int | None = None
    for i in range(start, end):
        s = lines[i].lstrip()
        if s.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if lines[i].startswith("- BAD"):
            bad_start = i
            break
    if bad_start is None:
        return []

    in_fence = False
    good_start: int | None = None
    for i in range(bad_start + 1, end):
        s = lines[i].lstrip()
        if s.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if lines[i].startswith("- GOOD"):
            good_start = i
            break
    if good_start is None:
        return []

    in_fence = False
    good_end = end
    for i in range(good_start + 1, end):
        s = lines[i].lstrip()
        if s.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if lines[i].startswith("- BAD") or lines[i].startswith("- GOOD"):
            good_end = i
            break

    # Strip trailing blank lines.
    while good_end > good_start + 1 and lines[good_end - 1] == "":
        good_end -= 1

    return list(range(bad_start, good_end))


def _strip_trailing_blanks(lines: list[str]) -> list[str]:
    while lines and lines[-1] == "":
        lines.pop()
    return lines


def build_compact(text: str) -> str:
    """Build the compact rule-pack content from the full RULES.md text."""
    raw_lines = text.split("\n")
    # Drop the empty final element produced by the trailing LF; we re-append at write time.
    if raw_lines and raw_lines[-1] == "":
        raw_lines = raw_lines[:-1]

    headings = parse_headings(text)

    h1 = next((h for h in headings if h["level"] == 1), None)
    if h1 is None:
        _die("RULES.md has no h1 heading")

    rule_headings = [
        h for h in headings if h["level"] == 4 and h["text"].startswith("RULE-")
    ]
    if len(rule_headings) != EXPECTED_RULE_COUNT:
        _die(
            f"expected {EXPECTED_RULE_COUNT} RULE-XX h4 headings, found "
            f"{len(rule_headings)}"
        )

    out: list[str] = []

    # 1. Pre-h1 lines (SPDX comment + blank).
    out.extend(raw_lines[: h1["line_start"]])

    # 2. h1 title verbatim.
    out.extend(raw_lines[h1["line_start"] : h1["line_end"]])

    # 3. Compact intro replaces the original h1-following preamble.
    out.append("")
    out.append(COMPACT_INTRO)

    # 4. Walk all top-level boundaries (h2/h3/h4) after the title.
    boundaries = [
        h
        for h in headings
        if h["level"] in (2, 3, 4) and h["line_start"] >= h1["line_end"]
    ]

    for idx, h in enumerate(boundaries):
        section_end = (
            boundaries[idx + 1]["line_start"]
            if idx + 1 < len(boundaries)
            else len(raw_lines)
        )

        if h["level"] in (2, 3):
            section = raw_lines[h["line_start"] : section_end]
            section = _strip_trailing_blanks(list(section))
            out.append("")
            out.extend(section)
            continue

        # h4 -- expect a RULE-XX rule.
        if not h["text"].startswith("RULE-"):
            _die(f"unexpected non-rule h4 at line {h['line_start']+1}: {h['text']!r}")

        rule_h5s = [
            hh
            for hh in headings
            if hh["level"] == 5
            and h["line_start"] <= hh["line_start"] < section_end
        ]

        directive = next((hh for hh in rule_h5s if hh["text"] == "Directive"), None)
        if directive is None:
            _die(f"rule {h['text']!r} missing ##### Directive")

        directive_end = section_end
        for hh in rule_h5s:
            if hh["line_start"] > directive["line_start"]:
                directive_end = hh["line_start"]
                break

        bg = next(
            (hh for hh in rule_h5s if "BAD" in hh["text"] and "GOOD" in hh["text"]),
            None,
        )
        if bg is None:
            _die(f"rule {h['text']!r} missing ##### BAD -> GOOD")

        bg_content_end = section_end
        for hh in rule_h5s:
            if hh["line_start"] > bg["line_start"]:
                bg_content_end = hh["line_start"]
                break

        pair_idxs = _extract_first_pair(raw_lines, bg["line_end"], bg_content_end)
        if not pair_idxs:
            _die(f"rule {h['text']!r}: no first BAD -> GOOD pair found")

        # Emit rule heading.
        out.append("")
        out.extend(raw_lines[h["line_start"] : h["line_end"]])

        # Emit Directive section, stripped of trailing blanks.
        directive_block = list(raw_lines[directive["line_start"] : directive_end])
        directive_block = _strip_trailing_blanks(directive_block)
        out.append("")
        out.extend(directive_block)

        # Emit BAD -> GOOD heading + first pair only.
        out.append("")
        out.extend(raw_lines[bg["line_start"] : bg["line_end"]])
        out.append("")
        out.extend(raw_lines[i] for i in pair_idxs)

    # Trim trailing blanks; ensure exactly one trailing LF on join.
    out = _strip_trailing_blanks(out)
    return "\n".join(out) + "\n"


def build_rule_pack_alias(source_text: str, current_alias_text: str) -> str:
    """Refresh docs/rule-pack.md: keep BC header lines 1-10 of current alias verbatim,
    then attach RULES.md from its first h1 heading onward (separated by one blank line).
    """
    src_h1 = next(
        (h for h in parse_headings(source_text) if h["level"] == 1), None
    )
    if src_h1 is None:
        _die("RULES.md has no h1 heading")

    src_lines = source_text.split("\n")
    if src_lines and src_lines[-1] == "":
        src_lines = src_lines[:-1]
    rules_body = src_lines[src_h1["line_start"] :]

    alias_lines = current_alias_text.split("\n")
    if alias_lines and alias_lines[-1] == "":
        alias_lines = alias_lines[:-1]

    # Locate the alias's own first h1: keep everything before it as the BC header.
    alias_h1 = next(
        (h for h in parse_headings(current_alias_text) if h["level"] == 1), None
    )
    if alias_h1 is None:
        _die(f"{ALIAS_OUTPUT}: no h1 heading found; cannot determine BC header")

    bc_header = alias_lines[: alias_h1["line_start"]]
    # Strip trailing blanks from the BC header so the join produces a single blank.
    bc_header = _strip_trailing_blanks(list(bc_header))

    out = list(bc_header)
    out.append("")
    out.extend(rules_body)
    out = _strip_trailing_blanks(out)
    return "\n".join(out) + "\n"


def assert_invariants(compact_text: str, rule_headings_in_source: list[dict]) -> None:
    """Step-8 assertions from the plan."""
    headings = parse_headings(compact_text)
    rule_headings = [
        h for h in headings if h["level"] == 4 and h["text"].startswith("RULE-")
    ]
    if len(rule_headings) != EXPECTED_RULE_COUNT:
        _die(
            f"compact has {len(rule_headings)} RULE- headings, expected "
            f"{EXPECTED_RULE_COUNT}"
        )

    src_rule_texts = [h["text"] for h in rule_headings_in_source]
    out_rule_texts = [h["text"] for h in rule_headings]
    if src_rule_texts != out_rule_texts:
        for s, o in zip(src_rule_texts, out_rule_texts):
            if s != o:
                _die(f"rule order mismatch: source={s!r} compact={o!r}")
        _die(
            f"rule count mismatch even though prefixes equal: "
            f"src={len(src_rule_texts)} out={len(out_rule_texts)}"
        )

    directive_count = sum(1 for h in headings if h["level"] == 5 and h["text"] == "Directive")
    if directive_count != EXPECTED_RULE_COUNT:
        _die(f"compact has {directive_count} ##### Directive sections, expected {EXPECTED_RULE_COUNT}")

    bg_count = sum(
        1
        for h in headings
        if h["level"] == 5 and "BAD" in h["text"] and "GOOD" in h["text"]
    )
    if bg_count != EXPECTED_RULE_COUNT:
        _die(f"compact has {bg_count} ##### BAD -> GOOD sections, expected {EXPECTED_RULE_COUNT}")

    rationale_count = sum(
        1
        for h in headings
        if h["level"] == 5 and h["text"] == "Rationale for AI Agent"
    )
    if rationale_count != 0:
        _die(f"compact has {rationale_count} rationale headings, expected 0")

    # Per-rule pair completeness: in each [#### RULE- ... next h2/h3/h4) range, the
    # ##### BAD -> GOOD sub-section must hold exactly one BAD bullet and exactly one
    # following GOOD bullet outside fenced-code regions.
    compact_lines = compact_text.split("\n")
    if compact_lines and compact_lines[-1] == "":
        compact_lines = compact_lines[:-1]
    boundaries = [
        h for h in headings if h["level"] in (2, 3, 4)
    ]
    for idx, h in enumerate(boundaries):
        if h["level"] != 4:
            continue
        section_end = (
            boundaries[idx + 1]["line_start"]
            if idx + 1 < len(boundaries)
            else len(compact_lines)
        )
        bg = next(
            (
                hh
                for hh in headings
                if hh["level"] == 5
                and "BAD" in hh["text"]
                and "GOOD" in hh["text"]
                and h["line_start"] <= hh["line_start"] < section_end
            ),
            None,
        )
        if bg is None:
            _die(f"compact rule {h['text']!r}: no BAD -> GOOD heading inside section")
        bg_end = section_end
        for hh in headings:
            if hh["level"] == 5 and bg["line_start"] < hh["line_start"] < section_end:
                bg_end = hh["line_start"]
                break

        in_fence = False
        bad_count = 0
        good_count = 0
        for i in range(bg["line_end"], bg_end):
            s = compact_lines[i].lstrip()
            if s.startswith("```"):
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            if compact_lines[i].startswith("- BAD"):
                bad_count += 1
            elif compact_lines[i].startswith("- GOOD"):
                good_count += 1
        if bad_count != 1 or good_count != 1:
            _die(
                f"compact rule {h['text']!r}: expected exactly 1 BAD + 1 GOOD bullet, "
                f"found {bad_count} BAD / {good_count} GOOD"
            )

    # Metadata-bullet leakage check: no "- **source**:", "- **agent-instruction evidence**:",
    # "- **severity**:", "- **scope**:", "- **enforcement**:" should appear in compact.
    leaked_metadata_prefixes = (
        "- **source**:",
        "- **agent-instruction evidence**:",
        "- **severity**:",
        "- **scope**:",
        "- **enforcement**:",
    )
    in_fence = False
    for i, line in enumerate(compact_lines):
        s = line.lstrip()
        if s.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        for pref in leaked_metadata_prefixes:
            if line.startswith(pref):
                _die(f"compact line {i+1}: leaked metadata bullet {pref!r}")

    # Fence balance (each ``` is either open or close; total count even).
    fence_count = sum(1 for line in compact_lines if line.lstrip().startswith("```"))
    if fence_count % 2 != 0:
        _die(f"compact has unbalanced fenced-code count: {fence_count}")


def write_bytes_lf(path: Path, text: str) -> None:
    """Write text as UTF-8 with LF line endings, no BOM, exactly one trailing LF."""
    if "\r" in text:
        _die(f"{path}: refusing to write CR characters")
    if not text.endswith("\n"):
        text += "\n"
    while text.endswith("\n\n"):
        text = text[:-1]
    data = text.encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def assert_alias_parity(source_text: str, alias_text: str) -> None:
    """Verify that the title-and-rules slice of docs/rule-pack.md is byte-identical to RULES.md from its h1 heading onward."""
    src_h1 = next(
        (h for h in parse_headings(source_text) if h["level"] == 1), None
    )
    alias_h1 = next(
        (h for h in parse_headings(alias_text) if h["level"] == 1), None
    )
    if src_h1 is None or alias_h1 is None:
        _die("alias parity check: missing h1 in source or alias")
    src_lines = source_text.split("\n")
    alias_lines = alias_text.split("\n")
    src_slice = src_lines[src_h1["line_start"] :]
    alias_slice = alias_lines[alias_h1["line_start"] :]
    if src_slice != alias_slice:
        # Find first divergence for a precise error.
        for i, (a, b) in enumerate(zip(src_slice, alias_slice)):
            if a != b:
                _die(
                    f"alias parity mismatch at slice line {i}: "
                    f"src={a!r} alias={b!r}"
                )
        _die(
            f"alias parity mismatch: src has {len(src_slice)} body lines, "
            f"alias has {len(alias_slice)}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="exit non-zero if any output would change (no writes)",
    )
    args = parser.parse_args()

    if not SOURCE.exists():
        _die(f"{SOURCE}: not found")

    source_text = read_source(SOURCE)
    rule_headings_in_source = [
        h
        for h in parse_headings(source_text)
        if h["level"] == 4 and h["text"].startswith("RULE-")
    ]

    compact_text = build_compact(source_text)
    assert_invariants(compact_text, rule_headings_in_source)

    if not ALIAS_OUTPUT.exists():
        _die(f"{ALIAS_OUTPUT}: missing; cannot derive BC header")
    current_alias_text = read_source(ALIAS_OUTPUT)
    alias_text = build_rule_pack_alias(source_text, current_alias_text)
    assert_alias_parity(source_text, alias_text)

    targets: list[tuple[Path, str]] = []
    targets.append((ALIAS_OUTPUT, alias_text))
    for p in COMPACT_OUTPUTS:
        targets.append((p, compact_text))
    for p in BUNDLE_RULES_OUTPUTS:
        targets.append((p, source_text))

    if args.check:
        any_diff = False
        for path, expected in targets:
            if not path.exists():
                sys.stderr.write(f"check: {path}: missing\n")
                any_diff = True
                continue
            actual = path.read_bytes()
            expected_bytes = expected.encode("utf-8")
            if actual != expected_bytes:
                sys.stderr.write(f"check: {path}: out of date\n")
                any_diff = True
        if any_diff:
            sys.stderr.write(
                "rule-pack files out of date; run "
                "`python scripts/build-compact.py` and commit\n"
            )
            return 1
        return 0

    for path, content in targets:
        write_bytes_lf(path, content)

    sys.stderr.write(
        f"build-compact: wrote {len(targets)} files; "
        f"compact size {len(compact_text.encode('utf-8'))} bytes\n"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
