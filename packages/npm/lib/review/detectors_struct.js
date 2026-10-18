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
  const lines = text.split(/\r\n|[\n\r]/);
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
  const lines = text.split(/\r\n|[\n\r]/);
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

// Groups: (1) leading indentation, (2) marker, (3) item content. The indent is
// captured so a nested list is not collected into its parent's group.
const BULLET_RE = /^(\s*)([*+-]|\d+\.)\s+(.*)$/;

// Width of `indent` in columns, expanding tabs to the next tab stop. Comparing
// raw character length would call one space and one tab the same depth, and
// four spaces and one tab different depths, so a list's nesting would depend on
// which whitespace the author typed.
function indentColumns(indent, tabStop = 4) {
  let width = 0;
  for (const ch of indent) {
    width += ch === '\t' ? tabStop - (width % tabStop) : 1;
  }
  return width;
}

// Coordinators, subordinators and relative pronouns. An item opening with one
// of these points back at something the bullet was severed from. Bare
// prepositions are deliberately absent: `For Linux, use apt` heads a genuine
// per-platform enumeration, so treating `for`/`to`/`with`/`from` as evidence
// flags exactly the lists RULE-A's directive permits.
const CONNECTIVE_OPENERS = new Set(`
  and but or nor so yet because therefore thus hence however although though
  while whereas since unless until then also moreover furthermore
  additionally rather which who whom whose that
`.trim().split(/\s+/));
// A repeated template is only evidence when it is an actual clause opening.
// Keying on the first two words of anything flags `Run the migration` /
// `Run the tests`, which is the directive's own checklist case.
const CLAUSE_SUBJECTS = new Set(['i', 'we', 'you', 'he', 'she', 'it', 'they', 'this', 'that', 'these', 'those']);
const COPULAS = new Set(['am', 'are', 'is', 'was', 'were']);

// Lowercase word tokens of a list item, punctuation and emphasis stripped.
function itemWords(content) {
  return content.split(/\s+/).map((w) => w.replace(/^[.,;:!?()[\]`"'*_~]+|[.,;:!?()[\]`"'*_~]+$/g, '').toLowerCase());
}

// Name the shape that marks the items as one sentence split across bullets, as
// {strength, reason}; null when the list reads as a genuine enumeration. A
// `strong` signal is self-sufficient; a `weak` one needs every item short too.
function readsAsShreddedProse(items) {
  const tokenized = items.map((it) => itemWords(it.content).filter((w) => w));
  for (const words of tokenized) {
    // A bare `And` / `But` / `Or` is a label, not connective tissue. Only a
    // connective that actually leads into something continues a sentence.
    if (words.length > 1 && CONNECTIVE_OPENERS.has(words[0])) {
      return { strength: 'strong', reason: `an item opens with the connective '${words[0]}'` };
    }
  }
  // `Per minute` / `Per user` trailing `Free tier` are fragments continuing a
  // stem. Two boundaries keep this from swallowing genuine enumerations: a list
  // where *every* item leads with `per` is a real enumeration, and so is one
  // where only a single item does not (`Global` / `Per user` / `Per project`).
  // Fragments need at least two items to continue from.
  const perCount = tokenized.filter((words) => words.length && words[0] === 'per').length;
  if (perCount > 1 && perCount < tokenized.length - 1) {
    return { strength: 'strong', reason: "later items are repeated 'per' fragments" };
  }
  const templates = new Map();
  for (const words of tokenized) {
    if (words.length < 2 || !CLAUSE_SUBJECTS.has(words[0]) || !COPULAS.has(words[1])) continue;
    const key = `${words[0]} ${words[1]}`;
    const seen = (templates.get(key) || 0) + 1;
    templates.set(key, seen);
    if (seen >= 2) return { strength: 'weak', reason: `items repeat the clause template '${key}'` };
  }
  return null;
}

/**
 * Flag short lists that read as fragmented prose rather than enumeration.
 *
 * The marker is not evidence either way, and shortness is not evidence on its
 * own either -- a checklist of terse imperative steps is short *and* genuine.
 * The test is RULE-A's own directive: "bullets are sentence shards with
 * connective tissue stripped", graded by how much each shape proves alone. A
 * strong signal (an opening coordinator/subordinator/relative pronoun, or some
 * but not all items leading with `Per`) fires regardless of item length. A weak
 * one (a repeated subject-and-copula opening) needs every item short too.
 * Imperative checklist steps, preposition-led enumerations and short
 * independent labels match neither and stay clean.
 */
function ruleA(text) {
  const out = [];
  const lines = text.split(/\r\n|[\n\r]/);
  const fence = fenceMask(text);
  let i = 0;
  while (i < lines.length) {
    if (fence[i]) { i++; continue; }
    const head = BULLET_RE.exec(lines[i]);
    if (!head) { i++; continue; }
    // Collect the siblings of this bullet. Ignoring indentation flattens a
    // nested list into its parent, so `- Rate limits:` plus two indented
    // `- Per …` children reads as one three-item group that no author wrote.
    // Deeper lines are skipped rather than ending the group, so a parent list
    // that resumes after a nested block stays one list.
    const groupStart = i + 1;
    const groupIndent = indentColumns(head[1]);
    const items = [];
    while (i < lines.length && !fence[i]) {
      const m = BULLET_RE.exec(lines[i]);
      if (!m) break;
      const indent = indentColumns(m[1]);
      if (indent > groupIndent) { i++; continue; } // a child, not a sibling
      if (indent < groupIndent) break;
      items.push({ lineNo: i + 1, content: m[3].trim() });
      i++;
    }
    const n = items.length;
    const shortItems = items.filter((it) => it.content.split(/\s+/).length <= 8).length;
    const signal = n >= 3 ? readsAsShreddedProse(items) : null;
    if (signal !== null && (signal.strength === 'strong' || shortItems === n)) {
      out.push({
        rule: 'RULE-A',
        line: groupStart,
        column: 1,
        excerpt: excerpt(lines[groupStart - 1], [0, lines[groupStart - 1].length]),
        detail: `list has ${n} items and ${signal.reason}; consider prose`,
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

const LATEX_LIST_RE = /^\s*\\(?:item\b|(?:begin|end)\{(?:itemize|enumerate|description)\})/;

function ruleE(text) {
  const out = [];
  for (const p of paragraphs(text)) {
    // A Markdown or LaTeX list line starts a new sentence, so a lead-in such
    // as "... include:" stays its own sentence when a list follows it without
    // a blank line.
    const segments = [];
    for (const line of p.lines) {
      if (segments.length === 0 || BULLET_RE.test(line) || LATEX_LIST_RE.test(line)) segments.push([line]);
      else segments[segments.length - 1].push(line);
    }
    const sentences = segments.flatMap((seg) => sentencesInParagraph(seg));
    if (sentences.length === 0) continue;
    const last = sentences[sentences.length - 1];
    // A sentence ending in a colon leads into what follows, such as the House
    // Style's "In summary, the key contributions of this work include:"; it
    // restates nothing.
    if (last.trimEnd().endsWith(':')) continue;
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
