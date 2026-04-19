// SPDX-License-Identifier: MIT
'use strict';
/**
 * Owned-file signature & content hash. Mirrors agent_style.owned_file in Python.
 *
 * Hash is sha256 over a canonical UTF-8 byte stream:
 *   1. Read as UTF-8 (no BOM assumed).
 *   2. Strip leading BOM if present.
 *   3. Normalize \r\n and \r to \n.
 *   4. Remove trailing signature line (if present).
 *   5. Ensure exactly one trailing \n.
 *   6. No Unicode normalization.
 *   7. Encode to UTF-8 bytes.
 *   8. sha256 over those bytes.
 */

const crypto = require('crypto');

const SIGNATURE_RE = /<!-- owned-by: agent-style; version: v([\w.\-+]+); sha256: ([0-9a-f]{64}) -->\n?$/;

class OwnedFileError extends Error {
  constructor(msg) {
    super(msg);
    this.name = 'OwnedFileError';
  }
}

function canonicalize(content) {
  if (content.startsWith('\ufeff')) content = content.slice(1);
  content = content.replace(/\r\n/g, '\n').replace(/\r/g, '\n');
  content = content.replace(/\n+$/, '') + '\n';
  return Buffer.from(content, 'utf8');
}

function computeHash(contentWithoutSignature) {
  return crypto.createHash('sha256').update(canonicalize(contentWithoutSignature)).digest('hex');
}

function extractSignature(text) {
  const m = text.match(SIGNATURE_RE);
  if (!m) return null;
  return { version: m[1], sha256_hex: m[2] };
}

function stripSignature(text) {
  return text.replace(SIGNATURE_RE, '');
}

function sign(content, version) {
  const stripped = stripSignature(content);
  const body = stripSignature(stripped).replace(/\n+$/, '') + '\n';
  const digest = computeHash(body);
  const sigLine = `<!-- owned-by: agent-style; version: v${version}; sha256: ${digest} -->\n`;
  return body + sigLine;
}

function verify(text) {
  const sig = extractSignature(text);
  if (sig === null) {
    throw new OwnedFileError('no agent-style owned-file signature found');
  }
  const body = stripSignature(text).replace(/\n+$/, '') + '\n';
  const actual = computeHash(body);
  if (actual !== sig.sha256_hex) {
    throw new OwnedFileError(
      `agent-style owned-file signature mismatch: declared ${sig.sha256_hex}, recomputed ${actual}; file has been edited since enable`
    );
  }
  return sig;
}

module.exports = { canonicalize, computeHash, extractSignature, stripSignature, sign, verify, OwnedFileError };
