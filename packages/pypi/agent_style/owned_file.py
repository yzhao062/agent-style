# SPDX-License-Identifier: MIT
"""Owned-file signature: agent-style-owned files carry a content-hash signature
at the last line so enable/disable can detect tampering.

Signature line format:

    <!-- owned-by: agent-style; version: v0.2.0; sha256: <64-hex-chars> -->

Hash is sha256 over a canonical byte stream (Python and Node compute the same bytes):

1. Read file as UTF-8 (no BOM assumed).
2. Strip a leading UTF-8 BOM if present.
3. Normalize all `\\r\\n` and bare `\\r` to `\\n`.
4. Remove exactly the final owned-file signature line (if present).
5. Ensure exactly one trailing `\\n`.
6. Do NOT apply Unicode normalization.
7. Encode to UTF-8 bytes.
8. sha256 over those bytes.
"""

from __future__ import annotations

import hashlib
import re
from typing import NamedTuple


SIGNATURE_RE = re.compile(
    r"<!-- owned-by: agent-style; version: v([\w.\-+]+); sha256: ([0-9a-f]{64}) -->\n?$"
)


class OwnedFileError(Exception):
    """Raised when signature verification fails or input is malformed."""


class Signature(NamedTuple):
    """Parsed signature: version and declared sha256 hex."""

    version: str
    sha256_hex: str


def canonicalize(content: str) -> bytes:
    """Produce the canonical byte stream used for hashing."""
    # Strip BOM
    if content.startswith("\ufeff"):
        content = content[1:]
    # Normalize line endings
    content = content.replace("\r\n", "\n").replace("\r", "\n")
    # Ensure exactly one trailing newline
    content = content.rstrip("\n") + "\n"
    return content.encode("utf-8")


def compute_hash(content_without_signature: str) -> str:
    """Return the sha256 hex digest of the canonicalized content."""
    return hashlib.sha256(canonicalize(content_without_signature)).hexdigest()


def extract_signature(text: str) -> Signature | None:
    """Return the trailing signature if present, else None."""
    m = SIGNATURE_RE.search(text)
    if m is None:
        return None
    return Signature(version=m.group(1), sha256_hex=m.group(2))


def strip_signature(text: str) -> str:
    """Return `text` with the trailing signature line removed (if present)."""
    return SIGNATURE_RE.sub("", text)


def sign(content: str, version: str) -> str:
    """Return `content` with the agent-style owned-file signature appended as the last line.

    The content is canonicalized before hashing so the hash is stable across platforms.
    """
    stripped = strip_signature(content)
    body = strip_signature(stripped).rstrip("\n") + "\n"
    digest = compute_hash(body)
    sig_line = f"<!-- owned-by: agent-style; version: v{version}; sha256: {digest} -->\n"
    return body + sig_line


def verify(text: str) -> Signature:
    """Verify the owned-file signature; return the Signature or raise OwnedFileError.

    Raises if: no signature found, or signature's sha256 does not match the recomputed hash.
    """
    sig = extract_signature(text)
    if sig is None:
        raise OwnedFileError("no agent-style owned-file signature found")
    body = strip_signature(text).rstrip("\n") + "\n"
    actual = compute_hash(body)
    if actual != sig.sha256_hex:
        raise OwnedFileError(
            f"agent-style owned-file signature mismatch: declared {sig.sha256_hex}, "
            f"recomputed {actual}; file has been edited since enable"
        )
    return sig
