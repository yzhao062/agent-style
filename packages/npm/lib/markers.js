// SPDX-License-Identifier: MIT
'use strict';
/**
 * Marker-block parsing and manipulation. Mirrors agent_style.markers in Python.
 *
 * Format:
 *   <!-- BEGIN agent-style v0.1.0 -->
 *   ...content...
 *   <!-- END agent-style -->
 *
 * The opener carries the version; the closer does not. `disable` matches on any
 * `BEGIN agent-style` prefix.
 */

const BEGIN_RE = /<!-- BEGIN agent-style(?: v([\w.\-+]+))? -->/g;
const END_RE = /<!-- END agent-style -->/g;

class MarkerParseError extends Error {
  constructor(msg) {
    super(msg);
    this.name = 'MarkerParseError';
  }
}

function _findAll(re, text) {
  const out = [];
  let m;
  re.lastIndex = 0;
  while ((m = re.exec(text)) !== null) {
    out.push({ index: m.index, end: m.index + m[0].length, match: m });
  }
  return out;
}

function findBlock(text) {
  const begins = _findAll(BEGIN_RE, text);
  const ends = _findAll(END_RE, text);
  if (begins.length === 0 && ends.length === 0) return null;
  if (begins.length !== 1 || ends.length !== 1) {
    throw new MarkerParseError(
      `ambiguous agent-style marker region: ${begins.length} BEGIN vs ${ends.length} END; expected exactly one of each`
    );
  }
  const b = begins[0];
  const e = ends[0];
  if (e.index <= b.end) {
    throw new MarkerParseError('END agent-style appears before BEGIN agent-style in file');
  }
  return {
    before: text.slice(0, b.index),
    version: b.match[1] || null,
    content: text.slice(b.end, e.index),
    after: text.slice(e.end),
  };
}

function upsertBlock(text, newVersion, newContent) {
  const block = findBlock(text);
  const beginLine = `<!-- BEGIN agent-style v${newVersion} -->`;
  const endLine = '<!-- END agent-style -->';
  const body = newContent.replace(/^\n+|\n+$/g, '');
  const blockText = `${beginLine}\n${body}\n${endLine}`;
  if (block === null) {
    let prefix = text;
    if (prefix && !prefix.endsWith('\n')) prefix += '\n\n';
    else if (prefix && !prefix.endsWith('\n\n')) prefix += '\n';
    return [prefix + blockText + '\n', 'create'];
  }
  return [block.before + blockText + block.after, 'update-marker'];
}

function removeBlock(text) {
  const block = findBlock(text);
  if (block === null) return [text, 'noop'];
  const before = block.before.replace(/\n+$/, '');
  const after = block.after.replace(/^\n+/, '');
  if (before && after) return [before + '\n\n' + after, 'remove-marker'];
  return [before || after, 'remove-marker'];
}

module.exports = { findBlock, upsertBlock, removeBlock, MarkerParseError };
