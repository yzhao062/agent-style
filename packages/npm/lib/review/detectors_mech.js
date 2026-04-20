// SPDX-License-Identifier: MIT
'use strict';
/**
 * Mechanical detectors. Deterministic regex / word-list rules.
 * Mirrors agent_style.review.detectors_mech in the Python package.
 * Must produce byte-identical counts + line numbers + excerpts as Python
 * for --cli-parity to stay at 12/12.
 */

// ---------- Entry point ----------------------------------------------------

function run(rule, text, filePath) {
  const fn = DISPATCH[rule.id];
  if (!fn) {
    return {
      rule: rule.id,
      severity: rule.severity,
      detector: 'mechanical',
      status: 'skipped',
      count: 0,
      note: `no mechanical detector registered for ${rule.id}`,
      violations: [],
    };
  }
  const violations = fn(text);
  return {
    rule: rule.id,
    severity: rule.severity,
    detector: 'mechanical',
    status: violations.length > 0 ? 'violation' : 'ok',
    count: violations.length,
    note: '',
    violations,
  };
}

// ---------- Helpers --------------------------------------------------------

function excerpt(lineText, span, width = 120) {
  const [s, e] = span;
  let start = Math.max(0, s - 20);
  let end = Math.min(lineText.length, start + width);
  let out = lineText.slice(start, end).trim();
  if (start > 0) out = '\u2026' + out;
  if (end < lineText.length) out = out + '\u2026';
  return out;
}

function* iterLines(text) {
  const parts = text.split('\n');
  let pos = 0;
  for (let i = 0; i < parts.length; i++) {
    yield [i + 1, pos, parts[i]];
    pos += parts[i].length + 1;
  }
}

function fenceMaskForLineIdx(lines, targetIdx) {
  let fenceOpen = false;
  for (let i = 0; i < lines.length; i++) {
    const stripped = lines[i].replace(/^\s+/, '');
    if (stripped.startsWith('```') || stripped.startsWith('~~~')) {
      fenceOpen = !fenceOpen;
    }
    if (i === targetIdx) return fenceOpen;
  }
  return false;
}

function insideInlineCode(line, col) {
  let ticks = 0;
  for (let i = 0; i < line.length; i++) {
    if (line[i] === '`') ticks++;
    if (i === col) break;
  }
  return ticks % 2 === 1;
}

// ---------- RULE-B em/en-dash ----------------------------------------------

const NUMERIC_EN_DASH = /(?<=\d)\u2013(?=\d)/g;
const ANY_DASH = /[\u2014\u2013]/g;

function ruleB(text) {
  const linesAll = text.split('\n');
  const out = [];
  for (const [lineNo, , line] of iterLines(text)) {
    if (fenceMaskForLineIdx(linesAll, lineNo - 1)) continue;
    // Allow-list: positions of numeric-range en-dashes.
    const allowed = new Set();
    let m;
    const numRe = new RegExp(NUMERIC_EN_DASH.source, 'g');
    while ((m = numRe.exec(line)) !== null) allowed.add(m.index);
    const anyRe = new RegExp(ANY_DASH.source, 'g');
    while ((m = anyRe.exec(line)) !== null) {
      if (allowed.has(m.index)) continue;
      if (insideInlineCode(line, m.index)) continue;
      const isEm = m[0] === '\u2014';
      out.push({
        rule: 'RULE-B',
        line: lineNo,
        column: m.index + 1,
        excerpt: excerpt(line, [m.index, m.index + 1]),
        detail: `${isEm ? 'em' : 'en'}-dash as casual punctuation`,
      });
    }
  }
  return out;
}

// ---------- RULE-D transition openers --------------------------------------

const TRANSITION_OPENERS = ['Additionally', 'Furthermore', 'Moreover', 'In addition'];

function ruleD(text) {
  const linesAll = text.split('\n');
  const out = [];
  for (const [lineNo, , line] of iterLines(text)) {
    if (fenceMaskForLineIdx(linesAll, lineNo - 1)) continue;
    const stripped = line.replace(/^\s+/, '');
    if (!stripped) continue;
    const prefixLen = line.length - stripped.length;
    const afterMarkup = stripped.replace(/^(>+\s*|[*-]\s+)+/, '');
    const firstWordMatch = afterMarkup.match(/^([A-Za-z][A-Za-z-]*)/);
    if (!firstWordMatch) continue;
    const word = firstWordMatch[1];
    for (const opener of TRANSITION_OPENERS) {
      const firstTok = opener.split(' ')[0];
      if (word.toLowerCase() === firstTok.toLowerCase()) {
        if (opener.includes(' ') && !afterMarkup.toLowerCase().startsWith(opener.toLowerCase())) {
          continue;
        }
        const col = prefixLen + (stripped.length - afterMarkup.length) + 1;
        out.push({
          rule: 'RULE-D',
          line: lineNo,
          column: col,
          excerpt: excerpt(line, [col - 1, col - 1 + opener.length]),
          detail: `transition opener '${opener}'`,
        });
        break;
      }
    }
  }
  return out;
}

// ---------- RULE-G title-case headings -------------------------------------

const LC_WORDS = new Set([
  'a','an','and','as','at','but','by','for','in','nor',
  'of','on','or','so','the','to','up','via','vs','yet',
  'with','over','per','into','from','onto',
]);

function ruleG(text) {
  const linesAll = text.split('\n');
  const out = [];
  for (const [lineNo, , line] of iterLines(text)) {
    if (fenceMaskForLineIdx(linesAll, lineNo - 1)) continue;
    const m = line.match(/^\s*(#{1,6})\s+(.*?)(?:\s+#*\s*)?$/);
    if (!m) continue;
    const headingText = m[2].trim();
    if (!headingText) continue;
    // Strip inline code and link targets.
    let cleaned = headingText.replace(/`[^`]*`/g, '');
    cleaned = cleaned.replace(/\[([^\]]*)\]\([^)]*\)/g, '$1');
    const tokens = cleaned.match(/[A-Za-z][A-Za-z0-9'/-]*/g) || [];
    if (tokens.length === 0) continue;
    const problem = [];
    for (let idx = 0; idx < tokens.length; idx++) {
      const tok = tokens[idx];
      if (tok.includes('-')) {
        for (const sub of tok.split('-')) {
          if (sub && !isTitlecased(sub, idx === 0, false)) {
            problem.push(tok);
            break;
          }
        }
        continue;
      }
      const isFirst = idx === 0;
      const isLast = idx === tokens.length - 1;
      const shouldBeLc = LC_WORDS.has(tok.toLowerCase());
      if (isFirst || isLast) {
        if (!isTitlecased(tok, true, false)) problem.push(tok);
        continue;
      }
      if (shouldBeLc) {
        if (tok !== tok.toLowerCase()) problem.push(tok);
      } else {
        if (!isTitlecased(tok, false, false)) problem.push(tok);
      }
    }
    if (problem.length > 0) {
      out.push({
        rule: 'RULE-G',
        line: lineNo,
        column: 1,
        excerpt: excerpt(line, [0, line.length]),
        detail: `heading not in title case; violating tokens: ${problem.join(', ')}`,
      });
    }
  }
  return out;
}

function isTitlecased(word, isFirst, isLc) {
  if (!word) return true;
  if (isLc && !isFirst) return word === word.toLowerCase();
  return /[A-Z0-9]/.test(word[0]);
}

// ---------- RULE-I contractions --------------------------------------------

const CONTRACTION_RE = /\b(?:[A-Za-z]+'(?:s|t|re|ll|d|ve|m)|it's|don't|won't|can't|shan't|isn't|aren't|wasn't|weren't|I'm)\b/gi;

function ruleI(text) {
  const linesAll = text.split('\n');
  const out = [];
  for (const [lineNo, , line] of iterLines(text)) {
    if (fenceMaskForLineIdx(linesAll, lineNo - 1)) continue;
    let m;
    const re = new RegExp(CONTRACTION_RE.source, 'gi');
    while ((m = re.exec(line)) !== null) {
      if (insideInlineCode(line, m.index)) continue;
      out.push({
        rule: 'RULE-I',
        line: lineNo,
        column: m.index + 1,
        excerpt: excerpt(line, [m.index, m.index + m[0].length]),
        detail: `contraction '${m[0]}'`,
      });
    }
  }
  return out;
}

// ---------- RULE-12 sentence length > 30 -----------------------------------

function rule12(text) {
  const linesAll = text.split('\n');
  const out = [];
  for (const [lineNo, , line] of iterLines(text)) {
    if (fenceMaskForLineIdx(linesAll, lineNo - 1)) continue;
    const stripped = line.trim();
    if (!stripped || stripped.startsWith('#') || stripped.startsWith('|')) continue;
    // Conservative split: punct + space + Capital/open-quote.
    const sentences = stripped.split(/(?<=[.!?])\s+(?=[A-Z"'(\[])/);
    for (const sentence of sentences) {
      const words = sentence.match(/\b[\w'-]+\b/g) || [];
      if (words.length > 30) {
        out.push({
          rule: 'RULE-12',
          line: lineNo,
          column: 1,
          excerpt: excerpt(sentence, [0, sentence.length]),
          detail: `sentence length ${words.length} words (>30)`,
        });
      }
    }
  }
  return out;
}

// ---------- RULE-05 clichés ------------------------------------------------

const CLICHE_PHRASES = [
  'ring the changes', 'take up the cudgels', 'toe the line', 'ride roughshod over',
  'stand shoulder to shoulder with', 'play into the hands of', 'no axe to grind',
  'grist to the mill', 'fishing in troubled waters', 'at the end of the day',
  'think outside the box', 'level playing field', 'low-hanging fruit',
  'paradigm shift', 'moving the needle', 'push the envelope', 'circle back',
  'deep dive', 'cutting-edge', 'state of the art', 'state-of-the-art',
  'paves the way', 'pave the way', 'a novel', 'novel approach', 'novel framework',
  'novel method', 'novel optimization', 'advance the state of the art',
  'game-changer', 'game changer', 'significant step forward', 'paradigm-shifting',
  'best-in-class', 'world-class', 'next-generation', 'next generation',
];

function rule05(text) {
  const linesAll = text.split('\n');
  const lowered = text.toLowerCase();
  const out = [];
  for (const phrase of CLICHE_PHRASES) {
    const pLow = phrase.toLowerCase();
    let start = 0;
    while (true) {
      const idx = lowered.indexOf(pLow, start);
      if (idx === -1) break;
      const lineNo = text.slice(0, idx).split('\n').length;
      const lineStart = text.lastIndexOf('\n', idx - 1) + 1;
      const nextNl = text.indexOf('\n', lineStart);
      const lineEnd = nextNl === -1 ? text.length : nextNl;
      const col = idx - lineStart + 1;
      if (!fenceMaskForLineIdx(linesAll, lineNo - 1)) {
        const lineText = text.slice(lineStart, lineEnd);
        if (!insideInlineCode(lineText, col - 1)) {
          out.push({
            rule: 'RULE-05',
            line: lineNo,
            column: col,
            excerpt: excerpt(lineText, [col - 1, col - 1 + phrase.length]),
            detail: `cliché phrase '${phrase}'`,
          });
        }
      }
      start = idx + pLow.length;
    }
  }
  return out;
}

// ---------- RULE-06 jargon / banned AI-tell list ---------------------------

const JARGON_WORDS = [
  // 45-word banned AI-tell list
  'encompass','burgeoning','pivotal','realm','keen','adept','endeavor',
  'uphold','imperative','profound','ponder','cultivate','hone','delve',
  'embrace','pave','embark','monumental','scrutinize','vast','versatile',
  'paramount','foster','necessitates','provenance','multifaceted','nuance',
  'obliterate','articulate','acquire','underpin','underscore','harmonize',
  'garner','undermine','gauge','facet','bolster','groundbreaking',
  'game-changing','reimagine','turnkey','intricate','trailblazing',
  'unprecedented',
  // Orwell Rule 5 jargon callouts
  'leverages','leveraging','leverage',
  'utilize','utilizes','utilizing',
  'facilitate','facilitates','facilitating',
];
const JARGON_RE = new RegExp(
  '\\b(?:' +
    [...new Set(JARGON_WORDS)].sort((a, b) => b.length - a.length)
      .map((w) => w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|') +
    ')\\b',
  'gi'
);

function rule06(text) {
  const linesAll = text.split('\n');
  const out = [];
  for (const [lineNo, , line] of iterLines(text)) {
    if (fenceMaskForLineIdx(linesAll, lineNo - 1)) continue;
    let m;
    const re = new RegExp(JARGON_RE.source, 'gi');
    while ((m = re.exec(line)) !== null) {
      if (insideInlineCode(line, m.index)) continue;
      out.push({
        rule: 'RULE-06',
        line: lineNo,
        column: m.index + 1,
        excerpt: excerpt(line, [m.index, m.index + m[0].length]),
        detail: `jargon / AI-tell '${m[0]}'`,
      });
    }
  }
  return out;
}

// ---------- Dispatch -------------------------------------------------------

const DISPATCH = {
  'RULE-B': ruleB,
  'RULE-D': ruleD,
  'RULE-G': ruleG,
  'RULE-I': ruleI,
  'RULE-12': rule12,
  'RULE-05': rule05,
  'RULE-06': rule06,
};

module.exports = { run };
