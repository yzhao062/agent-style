# SPDX-License-Identifier: MIT
"""Marker-block parsing and manipulation for agent-style's import-marker and append-block install modes.

A marker block is a region between HTML comments:

    <!-- BEGIN agent-style v0.1.1 -->
    ...generated content...
    <!-- END agent-style -->

The opener carries the version string; the closer does not. `disable` matches on any
`BEGIN agent-style` prefix so older blocks written by earlier CLIs are still removable.

The `agent-style-local` block is user-owned and must never be touched by enable/disable.
"""

from __future__ import annotations

import re
from typing import NamedTuple


BEGIN_RE = re.compile(r"<!-- BEGIN agent-style(?: v([\w.\-+]+))? -->")
END_RE = re.compile(r"<!-- END agent-style -->")


class MarkerParseError(Exception):
    """Raised when the marker-block parse finds a malformed or ambiguous region."""


class MarkerBlock(NamedTuple):
    """Parsed marker block: before (text before BEGIN), version, content (between), after (after END)."""

    before: str
    version: str | None
    content: str
    after: str


def find_block(text: str) -> MarkerBlock | None:
    """Find the agent-style marker block in `text`. Return None if not present.

    Raises MarkerParseError if BEGIN/END counts are inconsistent.
    """
    begins = list(BEGIN_RE.finditer(text))
    ends = list(END_RE.finditer(text))
    if not begins and not ends:
        return None
    if len(begins) != 1 or len(ends) != 1:
        raise MarkerParseError(
            f"ambiguous agent-style marker region: {len(begins)} BEGIN vs {len(ends)} END; "
            "expected exactly one of each"
        )
    b = begins[0]
    e = ends[0]
    if e.start() <= b.end():
        raise MarkerParseError("END agent-style appears before BEGIN agent-style in file")
    before = text[: b.start()]
    version = b.group(1)  # may be None if BEGIN has no version
    content_start = b.end()
    content_end = e.start()
    content = text[content_start:content_end]
    after = text[e.end() :]
    return MarkerBlock(before=before, version=version, content=content, after=after)


def upsert_block(text: str, new_version: str, new_content: str) -> tuple[str, str]:
    """Insert or update the agent-style marker block.

    Returns `(new_text, action)` where action is `"create"` if no marker was present
    (block added at end of file), or `"update-marker"` if an existing marker was replaced.
    """
    block = find_block(text)
    begin_line = f"<!-- BEGIN agent-style v{new_version} -->"
    end_line = "<!-- END agent-style -->"
    # Ensure the generated content has exactly one leading and one trailing newline
    # inside the block (stripped of leading/trailing blank lines on input).
    body = new_content.strip("\n")
    block_text = f"{begin_line}\n{body}\n{end_line}"
    if block is None:
        # Append to end of file, preserving a trailing newline.
        needs_nl = text and not text.endswith("\n")
        prefix = text + ("\n\n" if needs_nl else ("\n" if text and not text.endswith("\n\n") else ""))
        return prefix + block_text + "\n", "create"
    # Update in place
    return block.before + block_text + block.after, "update-marker"


def remove_block(text: str) -> tuple[str, str]:
    """Remove the agent-style marker block.

    Returns `(new_text, action)` where action is `"remove-marker"` if the block was
    removed or `"noop"` if no block was found.
    """
    block = find_block(text)
    if block is None:
        return text, "noop"
    # Collapse separating newlines between before/after to at most one blank line.
    before = block.before.rstrip("\n")
    after = block.after.lstrip("\n")
    if before and after:
        return before + "\n\n" + after, "remove-marker"
    return (before or after), "remove-marker"


def content_hash_placeholder() -> str:
    """Return a fixed hash placeholder used when generating the marker block pre-signing.

    Marker blocks (unlike owned files) do not carry a content hash; the block's presence
    and version are the only identification. This helper exists for symmetry with
    owned_file.py's signature logic and is not used in v0.1.1.
    """
    return "n/a"
