// SPDX-License-Identifier: MIT
'use strict';
/**
 * Structural detectors. Mirrors agent_style.review.detectors_struct in Python.
 * Implements RULE-A, RULE-C, RULE-E; RULE-02, 07, 09, 10 stub as "skipped".
 */

function run(rule, text, filePath) {
  const fn = DISPATCH[rule.id];
  if (!fn) {
    return {
      rule: rule.id,
      severity: rule.severity,
      detector: 'structural',
      status: 'skipped',
      count: 0,
      note: `structural detector for ${rule.id} is deferred to a future release`,
      violations: [],
    };
  }
  const violations = fn(text);
  return {
    rule: rule.id,
    severity: rule.severity,
    detector: 'structural',
    status: violations.length > 0 ? 'violation' : 'ok',
    count: violations.length,
    note: '',
    violations,
  };
}

function excerpt(textSlice, span, width = 120) {
  const [s, e] = span;
  let start = Math.max(0, s - 10);
  let end = Math.min(textSlice.length, start + width);
  let out = textSlice.slice(start, end).trim();
  if (start > 0) out = '\u2026' + out;
  if (end < textSlice.length) out = out + '\u2026';
  return out;
}

function fenceMask(text) {
  const lines = text.split('\n');
  let inside = false;
  const mask = [];
  for (const line of lines) {
    if (/^\s*(```|~~~)/.test(line)) {
      inside = !inside;
      mask.push(true);
      continue;
    }
    mask.push(inside);
  }
  return mask;
}

function paragraphs(text) {
  const lines = text.split('\n');
  const fence = fenceMask(text);
  const out = [];
  let curStart = null;
  let curLines = [];
  for (let i = 0; i < lines.length; i++) {
    const lineNo = i + 1;
    const line = lines[i];
    if (fence[i] || /^\s*[|#>]/.test(line)) {
      if (curLines.length > 0) {
        out.push({ start: curStart, lines: curLines });
        curStart = null;
        curLines = [];
      }
      continue;
    }
    if (!line.trim()) {
      if (curLines.length > 0) {
        out.push({ start: curStart, lines: curLines });
        curStart = null;
        curLines = [];
      }
      continue;
    }
    if (curStart === null) curStart = lineNo;
    curLines.push(line);
  }
  if (curLines.length > 0) out.push({ start: curStart, lines: curLines });
  return out;
}

function sentencesInParagraph(lines) {
  const joined = lines.map((l) => l.trim()).join(' ');
  const raw = joined.split(/(?<=[.!?])\s+(?=[A-Z"'(\[])/);
  return raw.map((s) => s.trim()).filter((s) => s.length > 0);
}

function firstWord(sentence) {
  const m = sentence.replace(/^\s+/, '').match(/[A-Za-z][A-Za-z'-]*/);
  return m ? m[0].toLowerCase() : '';
}

// ---------- RULE-A bullet overuse ------------------------------------------

const BULLET_RE = /^\s*(?:[*+-]|\d+\.)\s+(.*)$/;

function ruleA(text) {
  const out = [];
  const lines = text.split('\n');
  const fence = fenceMask(text);
  let i = 0;
  while (i < lines.length) {
    if (fence[i]) { i++; continue; }
    if (!BULLET_RE.test(lines[i])) { i++; continue; }
    const groupStart = i + 1;
    const items = [];
    while (i < lines.length && !fence[i]) {
      const m = BULLET_RE.exec(lines[i]);
      if (!m) break;
      items.push({ lineNo: i + 1, content: m[1].trim() });
      i++;
    }
    const n = items.length;
    const shortItems = items.filter((it) => it.content.split(/\s+/).length <= 8).length;
    if (n <= 2) {
      out.push({
        rule: 'RULE-A',
        line: groupStart,
        column: 1,
        excerpt: excerpt(lines[groupStart - 1], [0, lines[groupStart - 1].length]),
        detail: `list has only ${n} item(s); consider prose`,
      });
    } else if (shortItems === n && n >= 3) {
      out.push({
        rule: 'RULE-A',
        line: groupStart,
        column: 1,
        excerpt: excerpt(lines[groupStart - 1], [0, lines[groupStart - 1].length]),
        detail: `list has ${n} items all ≤ 8 words; consider prose`,
      });
    }
  }
  return out;
}

// ---------- RULE-C consecutive same-starts ---------------------------------

function ruleC(text) {
  const out = [];
  for (const p of paragraphs(text)) {
    const sentences = sentencesInParagraph(p.lines);
    if (sentences.length < 2) continue;
    const firsts = sentences.map((s) => firstWord(s));
    for (let i = 0; i < firsts.length - 1; i++) {
      const window = firsts.slice(i, i + 3);
      if (window.length < 2) continue;
      const counts = {};
      for (const w of window) {
        if (!w) continue;
        counts[w] = (counts[w] || 0) + 1;
      }
      const dup = Object.entries(counts).find(([w, c]) => c >= 2 && w);
      if (dup) {
        out.push({
          rule: 'RULE-C',
          line: p.start,
          column: 1,
          excerpt: excerpt(sentences[i], [0, sentences[i].length]),
          detail: `consecutive sentences start with '${dup[0]}'`,
        });
        break;
      }
    }
  }
  return out;
}

// ---------- RULE-E paragraph closers ---------------------------------------

const CLOSER_STARTERS = [
  'Overall,', 'In summary,', 'In conclusion,', 'To summarize,',
  'All in all,', 'In short,', 'Ultimately,', 'Thus,', 'Therefore,',
];
const CLOSER_STARTER_RE = new RegExp(
  '^(?:' + CLOSER_STARTERS.map((s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|') + ')',
  'i'
);
const CLOSER_PATTERNS = [
  CLOSER_STARTER_RE,
  /\bthese (?:changes|contributions|improvements|updates|results) (?:represent|demonstrate|reflect)\b/i,
  /\ba significant step (?:forward|change|improvement)\b/i,
  /\brepresents? a (?:significant|major|substantial) (?:advance|step|improvement)\b/i,
];

function ruleE(text) {
  const out = [];
  for (const p of paragraphs(text)) {
    const sentences = sentencesInParagraph(p.lines);
    if (sentences.length === 0) continue;
    const last = sentences[sentences.length - 1];
    for (const pat of CLOSER_PATTERNS) {
      if (pat.test(last)) {
        out.push({
          rule: 'RULE-E',
          line: p.start + Math.max(0, p.lines.length - 1),
          column: 1,
          excerpt: excerpt(last, [0, last.length]),
          detail: 'paragraph ends with a summary / restatement',
        });
        break;
      }
    }
  }
  return out;
}

const DISPATCH = {
  'RULE-A': ruleA,
  'RULE-C': ruleC,
  'RULE-E': ruleE,
};

module.exports = { run };
