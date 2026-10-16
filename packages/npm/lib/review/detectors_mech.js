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
  const violations = FILE_PATH_RULES.has(rule.id) ? fn(text, filePath) : fn(text);
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

const LINE_BREAK_RE = /\r\n|[\n\r]/g;

// (start, end) offset of each line under the same CR/LF/CRLF model the line
// splitter uses. Advancing by `line.length + 1` instead is one character short
// after every CRLF, which shifts every offset reported past it.
function lineSpans(text) {
  const spans = [];
  let pos = 0;
  LINE_BREAK_RE.lastIndex = 0;
  let m;
  while ((m = LINE_BREAK_RE.exec(text)) !== null) {
    spans.push([pos, m.index]);
    pos = m.index + m[0].length;
  }
  if (pos < text.length) spans.push([pos, text.length]);
  return spans;
}

function* iterLines(text) {
  const spans = lineSpans(text);
  for (let i = 0; i < spans.length; i++) {
    yield [i + 1, spans[i][0], text.slice(spans[i][0], spans[i][1])];
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
const LETTER_TOKEN_END = /\p{L}+$/u;
const LETTER_TOKEN_START = /^\p{L}+/u;
const ANY_DASH = /[\u2014\u2013]/g;

function isPairedNameEnDash(line, col) {
  if (line[col] !== '\u2013') return false;
  const left = line.slice(0, col).match(LETTER_TOKEN_END);
  const right = line.slice(col + 1).match(LETTER_TOKEN_START);
  if (!left || !right) return false;
  const leftInitial = Array.from(left[0])[0];
  const rightInitial = Array.from(right[0])[0];
  return leftInitial === leftInitial.toUpperCase()
    && leftInitial !== leftInitial.toLowerCase()
    && rightInitial === rightInitial.toUpperCase()
    && rightInitial !== rightInitial.toLowerCase();
}

function ruleB(text) {
  const linesAll = text.split(/\r\n|[\n\r]/);
  const out = [];
  for (const [lineNo, , line] of iterLines(text)) {
    if (fenceMaskForLineIdx(linesAll, lineNo - 1)) continue;
    // Allow-list: positions of legitimate joining en-dashes.
    const allowed = new Set();
    let m;
    const numRe = new RegExp(NUMERIC_EN_DASH.source, 'g');
    while ((m = numRe.exec(line)) !== null) allowed.add(m.index);
    const anyRe = new RegExp(ANY_DASH.source, 'g');
    while ((m = anyRe.exec(line)) !== null) {
      if (allowed.has(m.index) || isPairedNameEnDash(line, m.index)) continue;
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

const TRANSITION_OPENERS = [
  'Additionally', 'Furthermore', 'Moreover', 'In addition', "What's more", 'Notably',
];
const TRANSITION_SENTENCE_RE = new RegExp(
  '(?:^|[.!?](?:["\')\\]]*)[ \\t]+)(?:["\'(]*)(?<opener>' +
    [...TRANSITION_OPENERS].sort((a, b) => b.length - a.length)
      .map((w) => w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|') +
    ')(?![A-Za-z0-9_-])',
  'gi'
);
const TRANSITION_ALLOWANCE_PER_PARAGRAPH = 1;
// Markdown constructs that open a new block even without a blank line before
// them: an ATX heading, a table row, a thematic break, and each list item.
const BLOCK_BOUNDARY_RE = /^(?:#{1,6}[ \t]|\||(?:-{3,}|\*{3,}|_{3,})[ \t]*$|(?:[*+-]|\d+\.)[ \t])/;

function ruleD(text) {
  const linesAll = text.split(/\r\n|[\n\r]/);
  const out = [];
  const paragraphMatches = [];
  function flushParagraph() {
    const total = paragraphMatches.length;
    for (const match of paragraphMatches.slice(TRANSITION_ALLOWANCE_PER_PARAGRAPH)) {
      const { lineNo, col, line, opener } = match;
      out.push({
        rule: 'RULE-D',
        line: lineNo,
        column: col,
        excerpt: excerpt(line, [col - 1, col - 1 + opener.length]),
        detail: `overused transition opener '${opener}' (${total} in paragraph; first is allowed)`,
      });
    }
    paragraphMatches.length = 0;
  }
  for (const [lineNo, , line] of iterLines(text)) {
    if (!line.trim()) {
      flushParagraph();
      continue;
    }
    if (/^\s*(?:```|~~~)/.test(line) || fenceMaskForLineIdx(linesAll, lineNo - 1)) {
      flushParagraph();
      continue;
    }
    const stripped = line.replace(/^\s+/, '');
    const prefixLen = line.length - stripped.length;
    // Test the boundary on the text inside any blockquote, not on the raw
    // line: `> ## Heading` and `> - item` open new blocks just as their
    // unquoted forms do, and matching before the `>` is stripped misses them.
    const unquoted = stripped.replace(/^>+\s*/, '');
    if (BLOCK_BOUNDARY_RE.test(unquoted)) {
      // A heading, table row, thematic break or new list item starts a new
      // block. Without this the one-transition allowance leaks across the
      // boundary, so `Additionally, first.` under one heading makes
      // `Moreover, second.` under the next read as the paragraph's second
      // opener.
      flushParagraph();
    }
    const afterMarkup = stripped.replace(/^(>+\s*|[*-]\s+)+/, '');
    if (!afterMarkup.trim()) {
      // A markup-only line (a bare ">" inside a blockquote, or a lone bullet
      // marker) separates paragraphs just as a blank line does.
      flushParagraph();
      continue;
    }
    const contentOffset = prefixLen + stripped.length - afterMarkup.length;
    const re = new RegExp(TRANSITION_SENTENCE_RE.source, 'gi');
    let match;
    while ((match = re.exec(afterMarkup)) !== null) {
      const opener = match.groups.opener;
      const openerOffset = match.index + match[0].lastIndexOf(opener);
      const col = contentOffset + openerOffset + 1;
      if (!insideInlineCode(line, col - 1)) {
        paragraphMatches.push({ lineNo, col, line, opener });
      }
    }
  }
  flushParagraph();
  return out;
}

// ---------- RULE-G title-case headings -------------------------------------

const LC_WORDS = new Set([
  'a','an','the','and','but','or','nor','of','in','on',
  'to','for','by','at','with',
]);

const QUESTION_OPENERS = new Set([
  'how','what','when','where','which','who','whom','whose','why',
]);
const FINITE_AUXILIARIES = new Set([
  'am','are','is','was','were','do','does','did','have','has','had','can',
  'could','may','might','must','shall','should','will','would',
]);
const HEADING_TOKEN_RE = /\.?[A-Za-z0-9](?:[A-Za-z0-9'./\\:_-]*[A-Za-z0-9])?/g;
const VERSION_RE = /^v?\d+(?:\.\d+)+(?:[-+][A-Za-z0-9.-]+)?$/i;
const FILE_NAME_RE = /^\.?[A-Za-z0-9_-]+\.[A-Za-z0-9]{1,10}$/;
const UPPER_ID_RE = /^[A-Z]{2,}-[A-Z0-9]+$/;

function stripHeadingMarkup(text) {
  return text
    .replace(/(`+)[^`\n]*?\1/g, '')
    .replace(/!?\[[^\]\n]*\](?:\([^\)\n]*\)|\[[^\]\n]*\])?/g, '')
    .replace(/<[^>\n]+>/g, '');
}

function isSentenceStyleHeading(text) {
  const visible = stripHeadingMarkup(text).trim();
  if (/[.?!](?:["')\]}*_]+)?$/.test(visible)) return true;
  const words = visible.match(/[A-Za-z]+(?:'[A-Za-z]+)?/g) || [];
  if (words.length === 0) return false;
  const lowered = words.map((word) => word.toLowerCase());
  return QUESTION_OPENERS.has(lowered[0]) || lowered.some((word) => FINITE_AUXILIARIES.has(word));
}

function tokenCannotCarryCase(token) {
  return token[0] >= '0' && token[0] <= '9'
    || VERSION_RE.test(token)
    || UPPER_ID_RE.test(token)
    || token.startsWith('.')
    || token.includes('/')
    || token.includes('\\')
    || token.includes('_')
    || FILE_NAME_RE.test(token);
}

function ruleG(text) {
  const linesAll = text.split(/\r\n|[\n\r]/);
  const out = [];
  for (const [lineNo, , line] of iterLines(text)) {
    if (fenceMaskForLineIdx(linesAll, lineNo - 1)) continue;
    const m = line.match(/^\s*(#{1,6})\s+(.*?)(?:\s+#*\s*)?$/);
    if (!m) continue;
    const headingText = m[2].trim();
    if (!headingText) continue;
    if (isSentenceStyleHeading(headingText)) continue;
    const cleaned = stripHeadingMarkup(headingText);
    const tokens = (cleaned.match(HEADING_TOKEN_RE) || [])
      .filter((token) => /[A-Za-z]/.test(token));
    if (tokens.length === 0) continue;
    const problem = [];
    for (let idx = 0; idx < tokens.length; idx++) {
      const tok = tokens[idx];
      if (tokenCannotCarryCase(tok)) continue;
      const isFirst = idx === 0;
      const isLast = idx === tokens.length - 1;
      const parts = tok.split('-');
      for (let partIdx = 0; partIdx < parts.length; partIdx++) {
        const part = parts[partIdx];
        if (!part || tokenCannotCarryCase(part)) continue;
        const partIsFirst = isFirst && partIdx === 0;
        const partIsLast = isLast && partIdx === parts.length - 1;
        const shouldBeLc = LC_WORDS.has(part.toLowerCase()) && !partIsFirst && !partIsLast;
        const valid = shouldBeLc ? part === part.toLowerCase() : isTitlecased(part);
        if (!valid) {
          problem.push(tok);
          break;
        }
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

function isTitlecased(word) {
  if (!word) return true;
  return /[A-Z]/.test(word[0]);
}

// ---------- RULE-I contractions --------------------------------------------

// Ambiguous 's and 'd endings require closed host-word lists.
const CONTRACTION_RE = /\b(?:(?:it|that|he|she|there|here|what|who|where|when|how|let)'s|(?:i|you|he|she|it|we|they|that|who|what|which|why|there|where|how)'d|[A-Za-z]+n't|[A-Za-z]+'(?:re|ll|ve|m))\b/gi;

function ruleI(text) {
  const linesAll = text.split(/\r\n|[\n\r]/);
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
  const linesAll = text.split(/\r\n|[\n\r]/);
  const out = [];
  for (const [lineNo, , line] of iterLines(text)) {
    if (fenceMaskForLineIdx(linesAll, lineNo - 1)) continue;
    const stripped = line.trim();
    if (!stripped || stripped.startsWith('#') || stripped.startsWith('|')) continue;
    // Two alternatives, mirroring _SENTENCE_SPLIT_RE in the Python engine.
    // First: the original conservative split on punct + space + Capital or
    // open-quote. Second: an inline-code opener, because technical prose
    // routinely starts a sentence with a code span, and without it two ordinary
    // sentences were counted as one over-long sentence.
    //
    // The code-span branch is guarded against the abbreviations that routinely
    // precede a code span: dotted initialisms (`e.g.`, `i.e.`) and the one-token
    // forms `vs.`, `cf.` and `Fig.`. Unguarded, any of them reads as a sentence
    // end and silently suppresses a genuine violation, trading a visible false
    // positive for an invisible false negative. `etc.` is deliberately absent:
    // mid-sentence it takes a comma, and at a sentence end it is a real boundary
    // a guard would wrongly merge.
    //
    // Both branches also handle Markdown emphasis on either side of the
    // boundary. The optional closing run absorbs markup after the punctuation,
    // because a sentence ending `.**` puts that markup between the period and
    // the whitespace. That run sits outside the lookbehind to stay identical to
    // the Python engine, which cannot express it inside one (`re` rejects a
    // variable-width lookbehind).
    //
    // Every markup opener lives in the SECOND branch so it inherits the
    // abbreviation guards. In the first branch they would bypass every guard,
    // and `e.g. *json*` would silently suppress a real violation.
    const sentences = stripped.split(
      /(?<=[.!?])(?:\*\*|__|\*|_|`)?\s+(?=[A-Z"'(\[])|(?<!\b(?:[A-Za-z]\.){2})(?<!\b(?:[Vv][Ss]|[Cc][Ff])\.)(?<!\b[Ff][Ii][Gg]\.)(?<=[.!?])(?:\*\*|__|\*|_|`)?\s+(?=[`*_])/,
    );
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
  const linesAll = text.split(/\r\n|[\n\r]/);
  const spans = lineSpans(text);
  const starts = spans.map((s) => s[0]);
  const out = [];
  for (const phrase of CLICHE_PHRASES) {
    const escaped = phrase.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const re = new RegExp(`(?<![A-Za-z0-9_])${escaped}(?![A-Za-z0-9_])`, 'gi');
    let match;
    while ((match = re.exec(text)) !== null) {
      const idx = match.index;
      // Locate the match against the same CR/LF/CRLF line model that produced
      // linesAll. Searching for "\n" alone puts a match that follows a bare CR
      // on the previous line and gives it that line's column.
      let lineNo = 1;
      for (let lo = 0, hi = starts.length; lo < hi; ) {
        const mid = (lo + hi) >> 1;
        if (starts[mid] <= idx) { lineNo = mid + 1; lo = mid + 1; } else hi = mid;
      }
      const [lineStart, lineEnd] = spans[lineNo - 1];
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
    }
  }
  return out;
}

// ---------- RULE-06 jargon / banned AI-tell list ---------------------------

// This 54-entry list combines the 45-word banned AI-tell list with 9 forms of
// 3 RULE-06 BAD-example callouts.
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
  // 9 forms of 3 RULE-06 BAD-example callouts
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
  const linesAll = text.split(/\r\n|[\n\r]/);
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

// ---------- RULE-03 precise figures: intervals in prose, stacked figures ----
// Mirrors the RULE-03 section of agent_style.review.detectors_mech. Two checks:
//   A. a numeric interval written into a sentence, anywhere outside a table and
//      outside an appendix (appendix prose is where intervals cut from an
//      abstract belong)
//   B. precise figures (decimals, percentages) stacked in an abstract or an
//      introduction
// See the Python module for the full semantics and the calibration. Every
// blanking step is length-preserving, so an offset in the blanked text is an
// offset in the original and line numbers stay correct.
//
// The patterns use the `u` flag and spell Python's Unicode `\w` as
// [\p{L}\p{N}_], so a number glued to a CJK or accented letter is treated the
// same by both engines. `$` is written (?=\n?$) because Python's `$` also
// matches before a final newline.

const R03_RUN_FIGURES = 2; // figures a sentence needs to count toward a run
const R03_RUN_LENGTH = 3; // consecutive such sentences that make a stack
const R03_CROWDED = 5; // figures in one sentence that make it crowded

const R03_NOT_W_AFTER = String.raw`(?![\p{L}\p{N}_])`;
const R03_NOT_W_BEFORE = String.raw`(?<![\p{L}\p{N}_])`;
const R03_END = String.raw`(?=\n?$)`;

function r03Escape(s) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

const R03_DISPLAY_ENVS = [
  'tabular', 'tabular*', 'tabularx', 'longtable', 'array', 'supertabular',
  'tabu', 'equation', 'equation*', 'align', 'align*', 'alignat', 'alignat*',
  'gather', 'gather*', 'multline', 'multline*', 'eqnarray', 'eqnarray*',
  'flalign', 'flalign*', 'displaymath', 'math', 'figure', 'figure*', 'table',
  'table*', 'wrapfigure', 'wraptable', 'tikzpicture', 'verbatim', 'verbatim*',
  'lstlisting', 'minted', 'algorithm', 'algorithm*', 'algorithmic',
  'thebibliography', 'comment',
];
const R03_BEGIN_ENV_SRC =
  String.raw`\\begin\{(` + R03_DISPLAY_ENVS.map(r03Escape).join('|') + String.raw`)\}`;

const R03_ARG1_CMDS =
  String.raw`(?:[A-Za-z]*ref|[A-Za-z]*cite[A-Za-z]*|label|url|href|nolinkurl|input|` +
  String.raw`include|bibliography|bibliographystyle|usepackage|documentclass|` +
  String.raw`hypertarget|hyperlink|vspace|hspace|vskip|hskip|texttt|path|lstinline|` +
  String.raw`setcounter|addtocounter|color)\*?`;
const R03_ARG1_SRC =
  String.raw`\\` + R03_ARG1_CMDS +
  String.raw`(?:[ \t]{0,3}\[[^\]]{0,200}\])*[ \t\n]{0,3}\{[^{}]{0,400}\}`;
const R03_ARGN_SRC =
  String.raw`\\(?:includegraphics|setlength|addtolength|rule|scalebox|fontsize|` +
  String.raw`linespread|definecolor|newcommand|renewcommand)\*?` +
  String.raw`(?:[ \t]{0,3}\[[^\]]{0,200}\])*(?:[ \t\n]{0,3}\{[^{}]{0,400}\}){1,3}`;
const R03_SECTIONING_SRC =
  String.raw`\\(?:chapter|(?:sub){0,2}section|(?:sub)?paragraph)\*?` +
  String.raw`(?:[ \t]{0,3}\[[^\]]{0,200}\])?[ \t]{0,3}\{[^{}]{0,300}\}`;
const R03_VERB_SRC = String.raw`\\verb\*?([^A-Za-z\s*])[^\n]{0,300}?\1`;
const R03_LENGTH_SRC =
  String.raw`(?<![\p{L}\p{N}_.])` +
  String.raw`(?:\d+(?:\.\d+)?|\.\d+)[ \t]{0,2}(?:\\(?:textwidth|linewidth|columnwidth|textheight|` +
  String.raw`paperwidth|paperheight|hsize|vsize|baselineskip)` + R03_NOT_W_AFTER +
  String.raw`|(?:pt|em|ex|cm|mm|bp|pc|px)` + R03_NOT_W_AFTER + String.raw`)`;
const R03_IDENT_SRC =
  String.raw`(?<![\p{L}\p{N}_.])(?:` +
  String.raw`https?://[^\s<>"')\]}]+|www\.[^\s<>"')\]}]+` +
  String.raw`|10\.\d{4,9}/[^\s<>"')\]}]+` +
  String.raw`|[Aa][Rr][Xx][Ii][Vv][ \t]{0,2}[:/]?[ \t]{0,2}\d{4}\.\d{4,5}(?:v\d+)?` +
  String.raw`|[A-Za-z]:\\[^\s]+` +
  String.raw`|\d{1,2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?!\d)` +
  String.raw`|\d{4}-\d{1,2}-\d{1,2}|\d{1,2}/\d{1,2}/\d{2,4}` +
  String.raw`|\d+\.\d+(?:/\d+(?:\.\d+)?){2,}` +
  String.raw`|[Vv]\d+(?:\.\d+)+` +
  String.raw`|\d+(?:\.\d+){2,}` +
  String.raw`)`;

const R03_REF_WORDS =
  String.raw`sections?|secs?\.?|subsections?|chapters?|ch\.|tables?|tabs?\.?|figures?|` +
  String.raw`figs?\.?|eqs?\.?|equations?|appendix|appendices|apps?\.?|theorems?|` +
  String.raw`thms?\.?|lemmas?|propositions?|props?\.?|corollar(?:y|ies)|definitions?|` +
  String.raw`defs?\.?|algorithms?|algs?\.?|listings?|pages?|pp?\.|nos?\.|versions?|` +
  String.raw`ver\.|releases?|rfcs?|phases?|rounds?|slices?|stages?|hypothes[ie]s|` +
  String.raw`rq|python|node(?:\.js)?|java|cuda|claude|gpt|gemini|llama|qwen|mistral|` +
  String.raw`gemma|deepseek|opus|sonnet|haiku|grok|windows|macos|ubuntu|ios|android|` +
  String.raw`chrome|pytorch|tensorflow|numpy|pandas|scipy|openai`;
const R03_NUMBER_LIST = String.raw`\d+(?:\.\d+)*[A-Za-z]?`;
const R03_REF_SRC =
  String.raw`(?<![A-Za-z])(?:` + R03_REF_WORDS + String.raw`)(?:[ \t ~]{1,3}|\\ )` +
  R03_NUMBER_LIST +
  String.raw`(?:[ \t]{0,2}(?:,|and|or|&|to|--|–|-)[ \t]{0,2}` + R03_NUMBER_LIST + String.raw`){0,6}`;
const R03_SECTION_SIGN_SRC = String.raw`§+[ \t]{0,2}\d+(?:\.\d+)*`;

const R03_FIGURE_SRC =
  String.raw`(?<![\p{L}\p{N}_.])(?<![A-Za-z]-)` +
  String.raw`(?<num>(?:\d{1,3}(?:,\d{3}){1,5}|\d+)(?<dec>\.\d+)?)(?!\d)(?!\.\d)` +
  String.raw`(?<pct>(?:[ \t~]|\\,)?(?:\\%|%|percent(?:age[ \t]+points?)?` + R03_NOT_W_AFTER + String.raw`))?`;

// Only a statistical modifier may stand between a confidence level and the
// keyword: any other word means the percentage is a result ("drops by 15% over
// an interval of 2 to 4 hours"). Compiled case-insensitively.
const R03_LEVEL_MODIFIERS =
  String.raw`(?:confidence|credible|prediction|tolerance|bootstrapped|bootstrap|percentile|` +
  String.raw`central|posterior|highest-density|equal-tailed|simultaneous|two-sided|one-sided|` +
  String.raw`wald|wilson|asymptotic|exact|coverage)`;
const R03_LEVEL_BEFORE_SRC =
  String.raw`(\d+(?:\.\d+)?[ \t]{0,2}(?:\\%|%|percent)[ \t]{0,2}(?:` + R03_LEVEL_MODIFIERS + String.raw`[ \t]{1,2}){0,3})` +
  R03_END;
const R03_LEVEL_AFTER_SRC =
  String.raw`(?:CIs?|intervals?|confidence)[ \t]{0,2}\(?[ \t]{0,2}(\d+(?:\.\d+)?[ \t]{0,2}(?:\\%|%|percent))`;

const R03_NUM =
  String.raw`[-+−]?\$?[-+−]?` +
  String.raw`(?:\d{1,3}(?:,\d{3}){1,5}(?:\.\d+)?(?!\d)|\d+\.\d+|\d+(?!,\d{3}(?!\d)))` +
  String.raw`(?:\\?%)?\$?`;
const R03_SEP =
  String.raw`(?:\s{0,6}[,;]\s{0,6}|\s{1,6}to\s{1,6}|\s{0,6}(?:--|–|—|-)\s{0,6}` +
  String.raw`|\s{1,6}and\s{1,6})`;
const R03_BRACKET_SEP =
  String.raw`(?:\s{0,6}[,;]\s{0,6}|\s{1,6}to\s{1,6}|\s{0,6}(?:--|–|—|-)\s{0,6})`;
const R03_BRACKET_SRC =
  String.raw`[\[(]\s{0,6}(?<a>` + R03_NUM + String.raw`)` + R03_BRACKET_SEP +
  String.raw`(?<b>` + R03_NUM + String.raw`)\s{0,6}[\])]`;
const R03_KEYWORD_SRC = R03_NOT_W_BEFORE + String.raw`(?:CIs?|intervals?)` + R03_NOT_W_AFTER;
// The lead and the words before the first endpoint are captured because a bare
// "interval" (no confidence level, no "CI") is read more strictly than an
// explicit one: not across a clause comma, and "X and Y" only after "between".
const R03_KEYED_TAIL_SRC =
  String.raw`(?<lead>[\s:=,]{0,4})(?<words>(?:(?:of|is|was|from|between|at|spanning|ranging)\s{1,3}){0,2})` +
  String.raw`[\[(]?\s{0,6}(?<a>` + R03_NUM + String.raw`)(?<sep>` + R03_SEP + String.raw`)` +
  String.raw`(?<b>` + R03_NUM + String.raw`)\s{0,6}[\])]?`;
const R03_WORD_BEFORE_KEYWORD_SRC =
  String.raw`(?:confidence|credible|prediction|tolerance|bootstrap(?:ped)?)\s{1,3}` + R03_END;
const R03_TIME_UNIT_SRC =
  String.raw`\s{0,2}(?:ms|s|sec|secs|seconds?|minutes?|mins?|hours?|hrs?|days?|weeks?|` +
  String.raw`months?|years?|steps?|iterations?|epochs?|tokens?|px)` + R03_NOT_W_AFTER;
const R03_NUMBER_BEFORE_SRC =
  String.raw`(?:[\d%]|(?<=[\d})])\$)[\s~,;:(]{0,6}\$?` + R03_END;
const R03_CI_WORD_BEFORE_SRC =
  String.raw`(?:CIs?|intervals?|confidence|credible)[^\p{L}\p{N}_]{0,12}` + R03_END;

// A closer is a quote, a bracket, a Markdown emphasis marker, or a backtick, so
// `**Gain is 0.4.** **Cost is 1.2.**` splits into two sentences. The closers are
// single characters in one class: an alternation of `**` and `*` would admit
// exponentially many ways to match a long run of asterisks.
const R03_BOUNDARY_SRC =
  String.raw`(?<![.!?])(?<end>[.!?]+["'”’)\]}*_` + '`' + String.raw`]*)\s+(?=[A-Z0-9\\$"'“‘(\[*_` + '`' + String.raw`<])`;
const R03_PRECEDING_TOKEN_SRC = String.raw`([A-Za-z]+(?:\.[A-Za-z]+)*)` + R03_END;
const R03_ABBREVIATIONS = new Set([
  'al', 'approx', 'ca', 'cf', 'cor', 'def', 'dr', 'eq', 'eqs', 'fig', 'figs',
  'inc', 'incl', 'jr', 'ltd', 'mr', 'mrs', 'ms', 'no', 'nos', 'prof', 'prop',
  'resp', 'sec', 'secs', 'sr', 'st', 'tab', 'thm', 'vs', 'vol', 'ref', 'refs',
]);
const R03_BLOCK_SRC =
  String.raw`\n[ \t\r]*(?=\n)|\n[ \t]*(?:[-*+]|\d+[.)])[ \t]+|\\item` + R03_NOT_W_AFTER +
  String.raw`|\\par` + R03_NOT_W_AFTER;

const R03_MD_HEADING_SRC = String.raw`(?<![^\n])[ \t]{0,3}(#{1,6})[ \t]+([^\n]*)`;
const R03_TEX_SECTION_SRC =
  String.raw`\\(?:section|chapter)\*?[ \t]{0,3}(?:\[[^\]\n]{0,200}\])?[ \t]{0,3}\{([^{}\n]{0,200})\}`;
const R03_TITLE_NUMBER_SRC = String.raw`^(?:\d+(?:\.\d+)*[.)]?|[IVX]+\.)\s+`;
const R03_LATEX_SIGNATURE_SRC =
  String.raw`\\(?:begin|section|cite[a-z]*|ref|emph|textbf|item)` + R03_NOT_W_AFTER;
const R03_COMMENT_SRC = String.raw`(?<!\\)(?:\\\\)*(%[^\n\r]*)`;

// Markdown input is a `.md` or `.markdown` file, or text with no file name and no
// LaTeX sectioning or environment command. An indented block is code only there.
const R03_LATEX_MARKER_SRC = String.raw`\\(?:begin|(?:sub){0,2}section)` + R03_NOT_W_AFTER;
// A list item marker opens a list item; the item's content column decides whether
// an indented line inside it is code or a continuation paragraph.
const R03_LIST_MARKER_SRC = String.raw`^(?:[-*+]|[0-9]{1,9}[.)])`;
const R03_HEADING_START_SRC = String.raw`^#{1,6}(?:[ \t]|$)`;
// A table row cell ends at an unescaped pipe. The delimiter row of a table holds
// only cells of dashes with optional colons; it needs a pipe, so a lone `---` is
// a rule or a setext underline and never a delimiter.
const R03_PIPE_SRC = String.raw`(?<!\\)\|`;
const R03_DELIMITER_CELL_SRC = String.raw`^[ \t]*:?-+:?[ \t]*$`;
// A file named for an appendix or a supplement holds detailed prose; so does the
// part of a LaTeX file after `\appendix`. `support` is not one of the tokens.
const R03_APPENDIX_NAME_TOKENS = new Set(['appendix', 'appendices', 'supplement', 'supplementary', 'supp']);
const R03_APPENDIX_CMD_SRC = String.raw`\\appendix` + R03_NOT_W_AFTER;

// Fresh global matcher each time: a shared one carries lastIndex between calls.
function r03Re(src, flags) {
  return new RegExp(src, flags === undefined ? 'gu' : flags);
}

function* r03Matches(src, text, flags) {
  const re = r03Re(src, flags);
  let m;
  while ((m = re.exec(text)) !== null) {
    if (m[0].length === 0) re.lastIndex++;
    yield m;
  }
}

// Anchored match at `pos`, like Python's pattern.match(text, pos).
function r03MatchAt(src, text, pos, flags) {
  const re = new RegExp(src, flags);
  re.lastIndex = pos;
  return re.exec(text);
}

function r03Blank(text, spans) {
  if (spans.length === 0) return text;
  const sorted = spans.slice().sort((x, y) => x[0] - y[0] || x[1] - y[1]);
  const parts = [];
  let pos = 0;
  for (let [start, end] of sorted) {
    start = Math.max(start, pos);
    if (end <= start) continue;
    parts.push(text.slice(pos, start));
    parts.push(text.slice(start, end).replace(/[^\n\r]/g, ' '));
    pos = end;
  }
  parts.push(text.slice(pos));
  return parts.join('');
}

// Spans from each open token to the next close token, in linear time.
function r03Pairs(text, openTok, closeTok) {
  const out = [];
  let pos = 0;
  for (;;) {
    const i = text.indexOf(openTok, pos);
    if (i < 0) break;
    const j = text.indexOf(closeTok, i + openTok.length);
    if (j < 0) break;
    pos = j + closeTok.length;
    out.push([i, pos]);
  }
  return out;
}

// Strip leading spaces and tabs only, so both engines agree on what is blank.
function r03LstripBlank(s) {
  let a = 0;
  while (a < s.length && (s[a] === ' ' || s[a] === '\t')) a++;
  return s.slice(a);
}

function r03IsBlankText(s) {
  for (let i = 0; i < s.length; i++) if (s[i] !== ' ' && s[i] !== '\t') return false;
  return true;
}

// [character, length] of the backtick or tilde run that opens `body`, or null.
function r03FenceRun(body) {
  const ch = body[0];
  if (ch !== '`' && ch !== '~') return null;
  let n = 0;
  while (n < body.length && body[n] === ch) n++;
  return n >= 3 ? [ch, n] : null;
}

// Columns of leading space and tab; a tab advances to the next multiple of 4.
function r03IndentWidth(line) {
  let width = 0;
  for (let i = 0; i < line.length; i++) {
    if (line[i] === ' ') width += 1;
    else if (line[i] === '\t') width += 4 - (width % 4);
    else break;
  }
  return width;
}

// Index after the list item marker that starts at line[pos], or -1. A marker is a
// bullet, or one to nine digits and a '.' or ')'. It opens an item only when a
// space, a tab or the end of the line follows it.
function r03MarkerEnd(line, pos) {
  const n = line.length;
  const ch = line[pos];
  let end;
  if (ch === '-' || ch === '*' || ch === '+') {
    end = pos + 1;
  } else {
    let j = pos;
    while (j < n && j - pos <= 9 && line[j] >= '0' && line[j] <= '9') j++;
    if (j === pos || j - pos > 9 || j >= n || (line[j] !== '.' && line[j] !== ')')) return -1;
    end = j + 1;
  }
  if (end < n && line[end] !== ' ' && line[end] !== '\t') return -1;
  return end;
}

// [content column, kind of first content, index of that content] of a list item
// whose marker starts at line[pos], in column `col`. The content starts after the
// marker and the one to four spaces that follow it. A marker followed by five or
// more spaces, or by nothing, puts the content one column after the marker
// (CommonMark, list items). The kind is '' for an empty item, 'code' when five or
// more spaces make the first content an indented code block, and 'text' otherwise.
function r03ListContentCol(line, pos, col) {
  const n = line.length;
  const end = r03MarkerEnd(line, pos);
  const after = col + (end - pos);
  let cur = after;
  let j = end;
  while (j < n && (line[j] === ' ' || line[j] === '\t')) {
    cur += line[j] === ' ' ? 1 : 4 - (cur % 4);
    j++;
  }
  const gap = cur - after;
  if (j >= n) return [after + 1, '', j];
  if (gap > 4) return [after + 1, 'code', j];
  return [after + gap, 'text', j];
}

// True when a list item line may interrupt a paragraph (CommonMark, list items).
// Only a bullet or an ordered item numbered 1 can, and only with text after the
// marker. Any other such line is paragraph text, so `10. step` after a paragraph
// line opens no list.
function r03ItemInterrupts(body) {
  const marker = r03Re(R03_LIST_MARKER_SRC, 'u').exec(body);
  if (marker === null) return false;
  const text = marker[0];
  const last = text[text.length - 1];
  if ((last === '.' || last === ')') && parseInt(text.slice(0, -1), 10) !== 1) return false;
  return !r03IsBlankText(body.slice(text.length));
}

// True for a thematic break: three or more of one of '-', '*', '_', with only
// spaces and tabs between and after them.
function r03IsBreak(body) {
  const ch = body[0];
  if (ch !== '-' && ch !== '*' && ch !== '_') return false;
  let count = 0;
  for (let i = 0; i < body.length; i++) {
    const c = body[i];
    if (c === ch) count++;
    else if (c !== ' ' && c !== '\t') return false;
  }
  return count >= 3;
}

// True for a setext underline: a run of '=' or of '-', then only blanks.
function r03IsSetext(body) {
  const ch = body[0];
  if (ch !== '=' && ch !== '-') return false;
  let i = 0;
  while (i < body.length && body[i] === ch) i++;
  return r03IsBlankText(body.slice(i));
}

// True when a line holds nothing but blockquote markers and blanks.
function r03OnlyQuoteMarks(body) {
  for (let i = 0; i < body.length; i++) {
    const c = body[i];
    if (c !== ' ' && c !== '\t' && c !== '>') return false;
  }
  return true;
}

// Marks a blockquote in the container list of an open fence; a list item is its
// content column, which is always positive.
const R03_QUOTE = -1;

// [containers, run] when a list item or blockquote line opens a fence, else null.
// line[pos] is the first character that is not a space or a tab and `col` its
// column. Every list item marker and every '>' is stepped over, nested ones
// included, and the text left must open a fence within three columns of the last
// container, as a fence line does on its own. `containers` holds the content column
// of each list item and R03_QUOTE for each blockquote, outermost first.
function r03ContainerFence(line, pos, col) {
  const n = line.length;
  const out = [];
  for (;;) {
    if (line[pos] === '>') {
      out.push(R03_QUOTE);
      col += 1;
      pos += 1;
      const floor = col + (pos < n && (line[pos] === ' ' || line[pos] === '\t') ? 1 : 0);
      while (pos < n && (line[pos] === ' ' || line[pos] === '\t')) {
        col += line[pos] === ' ' ? 1 : 4 - (col % 4);
        pos += 1;
      }
      if (pos >= n || col - floor > 3) return null;
      continue;
    }
    if (r03MarkerEnd(line, pos) < 0) break;
    const [contentCol, first, j] = r03ListContentCol(line, pos, col);
    if (first !== 'text') return null;
    out.push(contentCol);
    pos = j;
    col = contentCol;
  }
  const rest = line.slice(pos);
  const run = r03FenceRun(rest);
  if (run === null || (run[0] === '`' && rest.slice(run[1]).includes('`'))) return null;
  return [out, run];
}

// [held, index, rel] for `line` inside a fence whose containers are `ctx`. `held`
// is false when a container of the fence ends at this line: a list item when a
// non-blank line is indented less than its content column, a blockquote when the
// line has no '>' for it, at most three columns past the enclosing container.
// Otherwise `index` is where the text begins after the containers and `rel` its
// columns past the innermost one, which is where a closing fence may sit.
function r03FenceLine(line, ctx) {
  const n = line.length;
  let pos = 0;
  let col = 0;
  let floor = 0;
  for (const c of ctx) {
    while (pos < n && (line[pos] === ' ' || line[pos] === '\t')) {
      col += line[pos] === ' ' ? 1 : 4 - (col % 4);
      pos += 1;
    }
    if (c === R03_QUOTE) {
      if (pos >= n || line[pos] !== '>' || col - floor > 3) return [false, pos, 0];
      col += 1;
      pos += 1;
      floor = col + (pos < n && (line[pos] === ' ' || line[pos] === '\t') ? 1 : 0);
    } else {
      if (pos < n && col < c) return [false, pos, 0];
      floor = c;
    }
  }
  while (pos < n && (line[pos] === ' ' || line[pos] === '\t')) {
    col += line[pos] === ' ' ? 1 : 4 - (col % 4);
    pos += 1;
  }
  return [true, pos, col - floor];
}

// True when line.slice(pos) closes a fence: its character, at least as long, then
// only blanks.
function r03FenceCloses(line, pos, fenceCh, fenceLen) {
  if (line[pos] !== fenceCh) return false;
  const rest = line.slice(pos);
  const run = r03FenceRun(rest);
  return run !== null && run[0] === fenceCh && run[1] >= fenceLen && r03IsBlankText(rest.slice(run[1]));
}

// Line spans of fenced code and, in Markdown input, indented code blocks.
// A fence opens and closes on a line indented at most three spaces (CommonMark;
// inside a list item the three count from the item's content column). It closes
// only on a line of the opening character that is at least as long as the opener
// and carries nothing after it, so a four-backtick block can hold a three-backtick
// example, a tilde fence is not closed by backticks, and an over-indented fence
// line stays inside the block. A backtick opener whose info string holds a
// backtick is an inline code span, not a fence. An unclosed fence runs to the end
// of the text.
// In Markdown input a fence may also start on the line of a list item marker or
// after a blockquote '>', nested ones included. It closes on a fence line at the
// content position of the innermost container, and it ends where a container
// ends: a blockquote at a line without '>', a list item at a non-blank line
// indented less than its content column. Only the fence lines are masked, never
// the rest of the list or the quote.
// An indented line is code when it sits four or more columns past its container
// (the document, or the content column of the innermost open list item) and does
// not continue a paragraph: the first line of the document, a line after a blank
// line, a heading, a fence, a setext underline or a thematic break qualifies, and
// so does every further indented line of the same block. A line indented less than
// that is a continuation paragraph and stays prose, and so does a lazy
// continuation of a paragraph. A setext underline (a run of '=' or '-' below a
// paragraph line) and a thematic break (three or more of one of '-', '*', '_') end
// the paragraph, each at most three columns past its container. An underline ends
// only a paragraph that holds no blockquote or HTML line, whose own block it cannot
// underline. A list item stays open while its lines are indented to its content
// column, and a fence inside it ends with it. A list item cannot interrupt a
// paragraph unless it is a bullet or numbered 1. Missing a case is the safe error
// here, because masking real prose hides a finding.
function r03CodeSpans(text, markdown) {
  const spans = [];
  const headingStart = r03Re(R03_HEADING_START_SRC, 'u');
  let fenceCh = '';
  let fenceLen = 0;
  let fenceCtx = []; // containers of the open fence, outermost first
  let para = false; // the previous line was paragraph text
  let plain = false; // that paragraph has no blockquote or HTML line, so a setext underline can end it
  let inCode = false; // the previous non-blank line was indented code
  const items = []; // content columns of the open list items, ascending
  for (const [start, end] of lineSpans(text)) {
    const line = text.slice(start, end);
    if (fenceCh !== '') {
      const [held, at, atRel] = r03FenceLine(line, fenceCtx);
      if (held) {
        spans.push([start, end]);
        if (at < line.length && atRel <= 3 && r03FenceCloses(line, at, fenceCh, fenceLen)) fenceCh = '';
        continue;
      }
      fenceCh = ''; // a container of the fence ended; read this line afresh
    }
    const body = r03LstripBlank(line);
    if (body === '') {
      para = false;
      continue;
    }
    const pos = line.length - body.length;
    const indent = r03IndentWidth(line);
    const run = r03FenceRun(body);
    const k = r03BisectRight(items, indent); // items this line is indented into
    const col = k > 0 ? items[k - 1] : 0;
    const rel = indent - col;
    const brk = markdown && rel <= 3 && r03IsBreak(body);
    let isItem = markdown && rel <= 3 && !brk && r03MarkerEnd(line, pos) >= 0;
    if (isItem && para && k === items.length && !r03ItemInterrupts(body)) isItem = false;
    const isHeading = markdown && rel <= 3 && headingStart.test(body);
    const setext = markdown && para && plain && k === items.length && rel <= 3 && r03IsSetext(body);
    const opens = run !== null && rel <= 3 && !(run[0] === '`' && body.slice(run[1]).includes('`'));
    const quote = markdown && rel <= 3 && body[0] === '>';
    let nested = null;
    if (!opens && (isItem || quote)) nested = r03ContainerFence(line, pos, indent);
    if (k < items.length && para && !(opens || isItem || isHeading || brk || quote)) {
      continue; // a lazy continuation keeps its list item open
    }
    items.length = k;
    if (quote && r03OnlyQuoteMarks(body)) {
      para = false; // a blockquote line with nothing on it ends the paragraph, as a blank line does
      continue;
    }
    if (opens) {
      fenceCh = run[0];
      fenceLen = run[1];
      fenceCtx = col ? [col] : [];
      spans.push([start, end]);
      para = false;
      inCode = false;
      continue;
    }
    if (nested !== null) {
      fenceCtx = [];
      for (const c of (col ? [col] : []).concat(nested[0])) {
        if (c !== R03_QUOTE && fenceCtx.length > 0 && fenceCtx[fenceCtx.length - 1] !== R03_QUOTE) {
          fenceCtx[fenceCtx.length - 1] = c; // only the innermost of adjacent list items matters
        } else {
          fenceCtx.push(c);
        }
      }
      for (const c of nested[0]) {
        if (c === R03_QUOTE) break;
        items.push(c);
      }
      fenceCh = nested[1][0];
      fenceLen = nested[1][1];
      spans.push([start, end]);
      para = false;
      inCode = false;
      continue;
    }
    if (!markdown) continue;
    if (brk || setext) {
      para = false;
      inCode = false;
      continue;
    }
    if (rel >= 4) {
      if (inCode || !para) {
        spans.push([start, end]);
        inCode = true;
        para = false;
      }
      continue;
    }
    inCode = false;
    plain = (para ? plain : true) && body[0] !== '>' && body[0] !== '<';
    para = !isHeading;
    if (isItem) {
      plain = true;
      const [contentCol, first] = r03ListContentCol(line, pos, indent);
      items.push(contentCol);
      if (first === 'code') {
        spans.push([start, end]);
        inCode = true;
      }
      para = first === 'text';
    }
  }
  return spans;
}

function r03StageOne(text, latex, markdown = false) {
  const spans = r03CodeSpans(text, markdown);
  spans.push(...r03Pairs(text, '<!--', '-->'));
  if (latex) {
    // An unescaped percent sign opens a comment; Markdown uses it as a unit.
    for (const m of r03Matches(R03_COMMENT_SRC, text)) {
      const end = m.index + m[0].length;
      spans.push([end - m[1].length, end]);
    }
    for (const m of r03Matches(R03_VERB_SRC, text)) spans.push([m.index, m.index + m[0].length]);
  } else {
    for (const m of r03Matches('`[^`\\n]+`', text)) spans.push([m.index, m.index + m[0].length]);
  }
  return r03Blank(text, spans);
}

// Cells in a table row, ignoring one outer pipe on each side.
function r03CellCount(row) {
  let t = r03StripChars(row, ' \t');
  if (t.startsWith('|')) t = t.slice(1);
  if (t.endsWith('|') && !t.endsWith('\\|')) t = t.slice(0, -1);
  return t.split(r03Re(R03_PIPE_SRC, 'u')).length;
}

function r03IsDelimiterRow(row) {
  let t = r03StripChars(row, ' \t');
  if (!t.includes('|')) return false;
  if (t.startsWith('|')) t = t.slice(1);
  if (t.endsWith('|')) t = t.slice(0, -1);
  const cell = r03Re(R03_DELIMITER_CELL_SRC, 'u');
  return t.split('|').every((c) => cell.test(c));
}

// Spans of Markdown tables: a header row, a delimiter row, and body rows. The
// header and the delimiter hold the same number of cells (GitHub rule). The body
// runs until a blank line or a line without a pipe. Outer pipes are optional on
// every row.
function r03TableSpans(text, lines) {
  const spans = [];
  const count = lines.length;
  let i = 0;
  while (i + 1 < count) {
    const header = text.slice(lines[i][0], lines[i][1]);
    if (header.includes('|')) {
      const delimiter = text.slice(lines[i + 1][0], lines[i + 1][1]);
      if (r03IsDelimiterRow(delimiter) && r03CellCount(header) === r03CellCount(delimiter)) {
        let j = i + 2;
        while (j < count && text.slice(lines[j][0], lines[j][1]).includes('|')) j++;
        spans.push([lines[i][0], lines[j - 1][1]]);
        i = j;
        continue;
      }
    }
    i++;
  }
  return spans;
}

function r03StageTwo(text, latex) {
  const spans = [];
  const display = [];
  let covered = 0;
  const exhausted = new Set();
  for (const m of r03Matches(R03_BEGIN_ENV_SRC, text)) {
    if (m.index < covered || exhausted.has(m[1])) continue;
    const endTok = '\\end{' + m[1] + '}';
    const j = text.indexOf(endTok, m.index + m[0].length);
    if (j < 0) {
      exhausted.add(m[1]);
      continue;
    }
    covered = j + endTok.length;
    display.push([m.index, covered]);
  }
  display.push(...r03Pairs(text, '\\[', '\\]'));
  display.push(...r03Pairs(text, '$$', '$$'));

  // A line that starts with a pipe is a table row; a table without outer pipes
  // is found by its header and delimiter rows.
  const lines = lineSpans(text);
  for (const [start, end] of lines) {
    const stripped = text.slice(start, end).trimStart();
    if (stripped.startsWith('|')) display.push([start, end]);
    else if (!latex && stripped.startsWith('#')) spans.push([start, end]);
  }
  display.push(...r03TableSpans(text, lines));

  spans.push(...display);
  for (const [src, flags] of [
    [R03_ARG1_SRC, 'gu'], [R03_ARGN_SRC, 'gu'], [R03_SECTIONING_SRC, 'gu'],
    [R03_LENGTH_SRC, 'gu'], [R03_IDENT_SRC, 'gu'], [R03_REF_SRC, 'giu'],
    [R03_SECTION_SIGN_SRC, 'gu'],
  ]) {
    for (const m of r03Matches(src, text, flags)) spans.push([m.index, m.index + m[0].length]);
  }
  // Markdown link and image targets.
  for (const m of r03Matches(String.raw`\]\([^)\s]{0,500}\)`, text)) {
    spans.push([m.index, m.index + m[0].length]);
  }
  // A whitespace-delimited token that holds a slash and a letter is a path or a
  // file name. A bare ratio such as 0.93/1.00 has no letter and stays.
  for (const m of r03Matches(String.raw`(?<!\S)[^\s/]*/\S*`, text)) {
    if (/[A-Za-z]/.test(m[0].split('\\%').join(''))) spans.push([m.index, m.index + m[0].length]);
  }
  return [r03Blank(text, spans), display];
}

function r03IsLatex(base, text) {
  const ext = base.includes('.') ? base.slice(base.lastIndexOf('.') + 1) : '';
  if (['tex', 'sty', 'cls', 'ltx'].includes(ext)) return true;
  if (['md', 'markdown', 'rst', 'txt'].includes(ext)) return false;
  return r03Re(R03_LATEX_SIGNATURE_SRC, 'u').test(text);
}

// True for a .md or .markdown file, or for text with no name and no LaTeX.
function r03IsMarkdown(base, text, latex) {
  if (base.endsWith('.md') || base.endsWith('.markdown')) return true;
  return base === '' && !latex && !r03Re(R03_LATEX_MARKER_SRC, 'u').test(text);
}

// True when a token of the file name is appendix or supplement.
function r03AppendixNamed(base) {
  return base.split(/[-_. ]+/).some((t) => R03_APPENDIX_NAME_TOKENS.has(t));
}

// Sorted, merged [start, end] spans of appendix prose.
// LaTeX: everything after \appendix and the body of an appendices environment (an
// unclosed one runs to the end). Markdown: the text under a heading that begins
// with "Appendix", up to the next heading of the same or a higher level that does
// not. Only the six heading levels are tracked, so the scan stays linear however
// many headings the file holds.
function r03AppendixSpans(masked, latex) {
  const spans = [];
  if (latex) {
    const m = r03Re(R03_APPENDIX_CMD_SRC, 'u').exec(masked);
    if (m !== null) spans.push([m.index + m[0].length, masked.length]);
    const openTok = '\\begin{appendices}';
    const closeTok = '\\end{appendices}';
    let pos = 0;
    for (;;) {
      const i = masked.indexOf(openTok, pos);
      if (i < 0) break;
      const j = masked.indexOf(closeTok, i + openTok.length);
      if (j < 0) {
        spans.push([i, masked.length]);
        break;
      }
      pos = j + closeTok.length;
      spans.push([i, pos]);
    }
  } else {
    const openAt = [null, null, null, null, null, null, null];
    for (const m of r03Matches(R03_MD_HEADING_SRC, masked)) {
      const level = m[1].length;
      const key = r03TitleKey(m[2]);
      if (key.startsWith('appendix') || key.startsWith('appendices')) {
        if (openAt[level] === null) openAt[level] = m.index + m[0].length;
        continue;
      }
      for (let lv = level; lv < 7; lv++) {
        if (openAt[lv] !== null) {
          spans.push([openAt[lv], m.index]);
          openAt[lv] = null;
        }
      }
    }
    for (let lv = 1; lv < 7; lv++) if (openAt[lv] !== null) spans.push([openAt[lv], masked.length]);
  }
  spans.sort((x, y) => x[0] - y[0] || x[1] - y[1]);
  const merged = [];
  for (const [start, end] of spans) {
    if (merged.length > 0 && start <= merged[merged.length - 1][1]) {
      const last = merged[merged.length - 1];
      merged[merged.length - 1] = [last[0], Math.max(last[1], end)];
    } else {
      merged.push([start, end]);
    }
  }
  return merged;
}

// Python's str.strip(chars) for a character set.
function r03StripChars(s, chars) {
  let a = 0;
  let b = s.length;
  while (a < b && chars.includes(s[a])) a++;
  while (b > a && chars.includes(s[b - 1])) b--;
  return s.slice(a, b);
}

function r03TitleKey(raw) {
  let title = r03StripChars(raw.trim(), '#').trim();
  title = r03StripChars(title, '*_ ').toLowerCase();
  title = title.replace(r03Re(R03_TITLE_NUMBER_SRC, 'u'), '');
  return r03StripChars(title, '*_ .:');
}

function r03Regions(masked, base) {
  if (base.includes('abstract')) return [[0, masked.length, 'abstract']];
  if (base.includes('intro')) return [[0, masked.length, 'introduction']];
  const regions = [];
  const openTok = '\\begin{abstract}';
  const closeTok = '\\end{abstract}';
  for (const [start, end] of r03Pairs(masked, openTok, closeTok)) {
    regions.push([start + openTok.length, end - closeTok.length, 'abstract']);
  }
  const sections = [...r03Matches(R03_TEX_SECTION_SRC, masked)];
  sections.forEach((m, idx) => {
    const key = r03TitleKey(m[1]);
    if (key !== 'abstract' && key !== 'introduction') return;
    const mEnd = m.index + m[0].length;
    let end = idx + 1 < sections.length ? sections[idx + 1].index : masked.length;
    const stop = masked.indexOf('\\end{document}', mEnd);
    if (stop >= 0 && stop < end) end = stop;
    regions.push([mEnd, end, key]);
  });
  const headings = [...r03Matches(R03_MD_HEADING_SRC, masked)];
  headings.forEach((m, idx) => {
    const key = r03TitleKey(m[2]);
    if (key !== 'abstract' && key !== 'introduction') return;
    const level = m[1].length;
    let end = masked.length;
    for (let k = idx + 1; k < headings.length; k++) {
      if (headings[k][1].length <= level) {
        end = headings[k].index;
        break;
      }
    }
    regions.push([m.index + m[0].length, end, key]);
  });
  return regions.sort((x, y) => x[0] - y[0] || x[1] - y[1] || (x[2] < y[2] ? -1 : x[2] > y[2] ? 1 : 0));
}

function r03Sentences(masked, cuts) {
  const points = new Set([0, masked.length]);
  for (const c of cuts) if (c >= 0 && c <= masked.length) points.add(c);
  for (const m of r03Matches(R03_BLOCK_SRC, masked)) points.add(m.index);
  const ordered = [...points].sort((x, y) => x - y);
  const tokenRe = new RegExp(R03_PRECEDING_TOKEN_SRC, 'u');
  const sentences = [];
  for (let i = 0; i + 1 < ordered.length; i++) {
    const a = ordered[i];
    const b = ordered[i + 1];
    let pieceStart = a;
    // Python's finditer(text, pos, endpos): lookbehind sees before `a`, and
    // nothing at or past `b` is visible.
    const view = masked.slice(0, b);
    const re = r03Re(R03_BOUNDARY_SRC);
    re.lastIndex = a;
    let m;
    while ((m = re.exec(view)) !== null) {
      const found = tokenRe.exec(masked.slice(Math.max(a, m.index - 16), m.index));
      if (found !== null) {
        const word = found[1].toLowerCase();
        if (R03_ABBREVIATIONS.has(word) || (word.includes('.') && word.split('.').every((p) => p.length === 1))) {
          continue;
        }
      }
      sentences.push([pieceStart, m.index + m.groups.end.length]);
      pieceStart = m.index + m[0].length;
    }
    sentences.push([pieceStart, b]);
  }
  const trimmed = [];
  for (const [start, end] of sentences) {
    const chunk = masked.slice(start, end);
    const lead = chunk.length - chunk.trimStart().length;
    const tail = chunk.trimEnd().length;
    if (tail > lead) trimmed.push([start + lead, start + tail]);
  }
  return trimmed;
}

function r03ParseNumber(raw) {
  const cleaned = raw.split('−').join('-').replace(/[^0-9.+-]/g, '');
  if (!/^[+-]?(?:\d+\.?\d*|\.\d+)$/.test(cleaned)) return null;
  return parseFloat(cleaned);
}

function r03Intervals(masked) {
  const found = [];
  const levels = [];
  const domain = [-1, 0, 1, 100];
  const qualifies = (a, b, explicit) => {
    if (explicit) return true;
    if (!(a.includes('.') || b.includes('.') || a.includes('%') || b.includes('%'))) return false;
    const va = r03ParseNumber(a);
    const vb = r03ParseNumber(b);
    return !(domain.includes(va) && domain.includes(vb));
  };
  const numberBefore = r03Re(R03_NUMBER_BEFORE_SRC, 'u');
  const ciWordBefore = r03Re(R03_CI_WORD_BEFORE_SRC, 'iu');
  const wordBeforeKeyword = r03Re(R03_WORD_BEFORE_KEYWORD_SRC, 'iu');
  const levelBefore = r03Re(R03_LEVEL_BEFORE_SRC, 'iu');

  for (const m of r03Matches(R03_BRACKET_SRC, masked)) {
    const prefix = masked.slice(Math.max(0, m.index - 40), m.index);
    if (numberBefore.test(prefix) || ciWordBefore.test(prefix)) {
      if (qualifies(m.groups.a, m.groups.b, false)) found.push([m.index, m.index + m[0].length]);
    }
  }

  for (const kw of r03Matches(R03_KEYWORD_SRC, masked, 'giu')) {
    const window = Math.max(0, kw.index - 60);
    const prefix = masked.slice(window, kw.index);
    const level = levelBefore.exec(prefix);
    if (level !== null) {
      const lo = window + level.index;
      levels.push([lo, lo + level[1].replace(/\s+$/, '').length]);
    }
    const after = r03MatchAt(R03_LEVEL_AFTER_SRC, masked, kw.index, 'iuy');
    if (after !== null) {
      const afterEnd = after.index + after[0].length;
      levels.push([afterEnd - after[1].length, afterEnd]);
    }
    const tail = r03MatchAt(R03_KEYED_TAIL_SRC, masked, kw.index + kw[0].length, 'uy');
    if (tail === null) continue;
    const tailEnd = tail.index + tail[0].length;
    const lowered = kw[0].toLowerCase();
    const explicit = level !== null || lowered === 'ci' || lowered === 'cis' || wordBeforeKeyword.test(prefix);
    if (!explicit) {
      if (tail.groups.lead.includes(',')) continue; // a clause comma, not an interval
      if (tail.groups.sep.trim().toLowerCase() === 'and' && !tail.groups.words.includes('between')) continue;
    }
    const timed = !explicit || lowered === 'interval' || lowered === 'intervals';
    if (timed && r03MatchAt(R03_TIME_UNIT_SRC, masked, tailEnd, 'iuy') !== null) continue;
    if (qualifies(tail.groups.a, tail.groups.b, explicit)) {
      found.push([level !== null ? window + level.index : kw.index, tailEnd]);
    }
  }

  found.sort((x, y) => x[0] - y[0] || x[1] - y[1]);
  const merged = [];
  for (const span of found) {
    if (merged.length > 0 && span[0] < merged[merged.length - 1][1]) {
      const last = merged[merged.length - 1];
      merged[merged.length - 1] = [last[0], Math.max(last[1], span[1])];
    } else {
      merged.push(span);
    }
  }
  return [merged, levels];
}

function r03Figures(masked) {
  const out = [];
  for (const m of r03Matches(R03_FIGURE_SRC, masked)) {
    const hasDecimal = m.groups.dec !== undefined;
    const hasPercent = m.groups.pct !== undefined;
    if (!(hasDecimal || hasPercent)) continue;
    if (hasDecimal && !hasPercent) {
      const end = m.index + m[0].length;
      const nxt = masked.slice(end, end + 2);
      if ((nxt[0] === 'B' || nxt[0] === 'b') && !/[\p{L}\p{N}]/u.test(nxt.slice(1, 2))) continue;
    }
    out.push(m.index);
  }
  return out;
}

// Number of elements of sorted `arr` strictly below `x` (Python's bisect_left).
function r03BisectLeft(arr, x) {
  let lo = 0;
  let hi = arr.length;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (arr[mid] < x) lo = mid + 1;
    else hi = mid;
  }
  return lo;
}

// Number of elements of sorted `arr` at or below `x` (Python's bisect_right).
function r03BisectRight(arr, x) {
  let lo = 0;
  let hi = arr.length;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (x < arr[mid]) hi = mid;
    else lo = mid + 1;
  }
  return lo;
}

// Never throws: a malformed input must cost one rule's findings and nothing
// more, matching the Python detector the guard calls.
function rule03(text, filePath = '') {
  try {
    return rule03Scan(text, filePath);
  } catch (err) {
    return [];
  }
}

function rule03Scan(text, filePath) {
  if (typeof text !== 'string' || text.length === 0) return [];
  const base = String(filePath || '').split(/[\\/]/).pop().toLowerCase();
  const latex = r03IsLatex(base, text);
  const markdown = r03IsMarkdown(base, text, latex);
  const stageOne = r03StageOne(text, latex, markdown);
  const regions = r03Regions(stageOne, base);
  // Detailed appendix prose is where intervals removed from an abstract belong,
  // so check A skips it. Check B does not.
  const appendix = r03AppendixNamed(base) ? [[0, stageOne.length]] : r03AppendixSpans(stageOne, latex);
  const appendixStarts = appendix.map((s) => s[0]);
  const [masked, display] = r03StageTwo(stageOne, latex);

  const cuts = display.map((s) => s[0]).concat(display.map((s) => s[1]));
  for (const [start, end] of regions) cuts.push(start, end);
  const sentences = r03Sentences(masked, cuts);
  if (sentences.length === 0) return [];
  const sentenceStarts = sentences.map((s) => s[0]);

  const [intervals, levels] = r03Intervals(masked);
  const figureStarts = r03Figures(r03Blank(masked, levels));

  const spans = lineSpans(text);
  const lineStarts = spans.map((s) => s[0]);
  const locate = (offset) => {
    const lineNo = Math.max(1, r03BisectRight(lineStarts, offset));
    const [lineStart, lineEnd] = spans[lineNo - 1];
    return [lineNo, offset - lineStart + 1, text.slice(lineStart, lineEnd)];
  };

  const out = [];

  // Check A: one finding per sentence that carries an interval.
  const bySentence = new Map();
  for (const [start, end] of intervals) {
    const slot = r03BisectRight(appendixStarts, start) - 1;
    if (slot >= 0 && start < appendix[slot][1]) continue;
    const idx = r03BisectRight(sentenceStarts, start) - 1;
    if (idx >= 0 && start < sentences[idx][1]) {
      if (!bySentence.has(idx)) bySentence.set(idx, []);
      bySentence.get(idx).push([start, end]);
    }
  }
  for (const idx of [...bySentence.keys()].sort((x, y) => x - y)) {
    const hits = bySentence.get(idx);
    const [start, end] = hits[0];
    const [lineNo, col, line] = locate(start);
    const many = hits.length > 1 ? `${hits.length} numeric intervals` : 'a numeric interval';
    out.push({
      rule: 'RULE-03',
      line: lineNo,
      column: col,
      excerpt: excerpt(line, [col - 1, col - 1 + (end - start)]),
      detail:
        `${many} in prose; keep what the reader needs to judge the claim, ` +
        'in words where possible, and give the interval in a table or figure',
    });
  }

  // Check B: stacked figures, only inside an abstract or an introduction.
  const merged = [];
  for (const [start, end, label] of regions) {
    if (merged.length > 0 && start < merged[merged.length - 1][1]) {
      const last = merged[merged.length - 1];
      merged[merged.length - 1] = [last[0], Math.max(last[1], end), last[2]];
    } else {
      merged.push([start, end, label]);
    }
  }
  const regionStarts = merged.map((r) => r[0]);
  const regionOf = (offset) => {
    const idx = r03BisectRight(regionStarts, offset) - 1;
    if (idx >= 0 && offset < merged[idx][1]) return merged[idx][2];
    return null;
  };

  const counts = sentences.map(([start, end]) => [
    start,
    end,
    r03BisectLeft(figureStarts, end) - r03BisectLeft(figureStarts, start),
    regionOf(start),
  ]);

  const reportRun = (run) => {
    const start = run[0][0];
    const total = run.reduce((acc, item) => acc + item[2], 0);
    const [lineNo, col, line] = locate(start);
    out.push({
      rule: 'RULE-03',
      line: lineNo,
      column: col,
      excerpt: excerpt(line, [col - 1, col - 1 + Math.min(run[0][1] - start, 80)]),
      detail:
        `${run.length} consecutive sentences in the ${run[0][3]} carry ${total} precise figures; ` +
        'keep the few magnitudes behind the main findings and move the rest to a table',
    });
  };

  let run = [];
  for (const item of counts.concat([[0, 0, 0, null]])) {
    const label = item[3];
    if (label !== null && item[2] >= R03_RUN_FIGURES && (run.length === 0 || run[run.length - 1][3] === label)) {
      run.push(item);
      continue;
    }
    if (run.length >= R03_RUN_LENGTH) {
      reportRun(run);
    } else {
      for (const [start, end, n, lab] of run) {
        if (n >= R03_CROWDED) {
          const [lineNo, col, line] = locate(start);
          out.push({
            rule: 'RULE-03',
            line: lineNo,
            column: col,
            excerpt: excerpt(line, [col - 1, col - 1 + Math.min(end - start, 80)]),
            detail:
              `one sentence in the ${lab} carries ${n} precise figures; ` +
              'keep the one the claim rests on and move the rest to a table',
          });
        }
      }
    }
    run = label !== null && item[2] >= R03_RUN_FIGURES ? [item] : [];
  }

  out.sort((x, y) => x.line - y.line || x.column - y.column);
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
  'RULE-03': rule03,
};

// Detectors that also take the file path. RULE-03 locates the abstract and the
// introduction by file name as well as by markup.
const FILE_PATH_RULES = new Set(['RULE-03']);

// lineSpans is exported for the boundary tests: it is the detector's own
// CR/LF/CRLF line model, and `audit` normalises on read, so a direct-text
// caller is the only path that exercises it. rule03 is exported for the same
// reason: the RULE-03 tests call it on text with a file path.
module.exports = { run, lineSpans, rule03 };
