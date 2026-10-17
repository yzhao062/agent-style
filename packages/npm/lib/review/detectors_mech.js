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
  // Python's str.strip(): U+001C-U+001F and U+0085 count as blanks and U+FEFF
  // does not, which is the reverse of trim().
  let out = r03PyStrip(lineText.slice(start, end));
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
// Mirrors the RULE-03 section of agent_style.review.detectors_mech. Checks:
//   A. a numeric interval written into a sentence, anywhere outside a table and
//      outside an appendix (appendix prose is where intervals cut from an
//      abstract belong)
//   B. precise figures (decimals, percentages) stacked in an abstract or an
//      introduction and, in a LaTeX file, in the body prose (run criterion only)
//   C. a LaTeX caption that carries precise figures or runs long (0.7.0)
//   D. numbers written to many decimal places in LaTeX prose (0.7.0)
// plus the hook-only RULE-A table-cell check (`ruleA`). See the Python module
// for the full semantics and the calibration. Every
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
  'tabular', 'tabular*', 'tabularx', 'tabulary', 'tblr', 'longtable', 'array',
  'supertabular', 'tabu', 'equation', 'equation*', 'align', 'align*', 'alignat', 'alignat*',
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
// Paper repositories also split appendices into app-*.tex, appx.tex, or apx-*.tex;
// tokens split on -, _, ., and spaces, so application.tex stays a body file.
const R03_APPENDIX_NAME_TOKENS = new Set(['appendix', 'appendices', 'supplement', 'supplementary', 'supp', 'app', 'appx', 'apx']);
const R03_APPENDIX_CMD_SRC = String.raw`\\appendix` + R03_NOT_W_AFTER;

// ---------- RULE-03 checks C and D, body-prose check B, RULE-A table cells ----
//
// Mirrors the 0.7.0 block of agent_style.review.detectors_mech. These checks
// extend the hook-only figure checks from the abstract and the introduction to
// the rest of a LaTeX paper, and they read LaTeX only: the Markdown tables of
// agent documents carry long cells by design (30-40% of the ones measured), so
// the same limits there would flood. The appendix and supplement exemptions are
// those of check A.
//
//   B (body)  the run criterion of check B, in LaTeX body prose outside a
//             method or setup section
//   C         a caption that carries precise figures or runs long; the numbers
//             of a legend (quantile lines, significance levels, markers) are
//             keys and not figures
//   D         numbers written to four or more decimal places and three or more
//             significant digits (0.0143 counts, 0.0001 does not), outside a
//             method or setup section
//   RULE-A    a LaTeX table cell that holds prose (`ruleA` below)
//
// Measured in 2026-10 on the .tex files of 12 pre-2023 arXiv papers (169 files
// after content-hash dedupe) and of agent-assisted drafts (335 files), with each
// path passed so the file-name exemptions apply. Findings as human | drafts:
//
//   B body run          0 | 53 (18 files; none sit in files named app-*, which
//                       the name exemption covers). The method and setup
//                       exemption removes 4 of the draft findings.
//   B body crowded      limit 5: 6 | 76 (5 distinct human sentences), limit 6:
//                       4 | 54. A human body sentence with five figures is not
//                       rare, so the crowded criterion stays in the abstract
//                       and the introduction.
//   C caption           5 of 202 human captions | 98 of 373 at 3 figures or over
//                       100 words (human: 3 by figures, 2 by words; drafts: 44
//                       and 71, each limit alone). Legend numbers removed 2
//                       draft findings and no human one. One step up on both
//                       (4 figures, 120 words) leaves 3 | 62. The human hits
//                       restate results or run to a paragraph, which is the
//                       pattern.
//   D excess precision  numbers at 4+ places and 3+ significant digits. A
//                       paragraph with 3 numbers at 3+ places: 5 | 145; at 4+
//                       places: 3 | 20; a sentence with 2 at 4+ places: 5 | 39.
//                       None keeps the human count at 2 or fewer. A paragraph
//                       with 4 numbers at 4+ places does: 2 | 14 (each human
//                       paragraph holds eight such numbers). Three places is
//                       ordinary reporting (an AUC of 0.824), and a paragraph
//                       at 3+ places stays above 2 human at every count up to 7
//                       (8 gives 2 | 45, but that counts density and not
//                       precision). A sentence with 5 numbers at 3+ places
//                       gives 2 | 35 and measures crowding, so it is not
//                       shipped. The significant-digit rule removed 6 draft
//                       findings (21 to 15) and the setup exemption 1 more; the
//                       human count stayed at 2.
//   RULE-A table cell   0 of 103 human tables | 29 of 292 (24 files; none in
//                       app-* files). The longest human cell holds 6 words.
//
// The detectors are advisory and the guard caps what it shows, so each value
// below was set to miss some of the pattern rather than flood. Change a value
// only with a new measurement.

const R03_BODY = 'body'; // label of a sentence in LaTeX body prose

// The values the Python module holds as _R03_* constants, in one object so a
// test can set them the way the Python tests monkeypatch the module (exported
// as r03Tuning). Shipped values:
//   bodyCrowded     null: off. Five figures in one human body sentence is not
//                   rare (6 of them in the human corpora at a limit of 5).
//   captionFigures  precise figures that make a caption a results table; 5 of
//   captionWords    202 human, 98 of 373 draft captions (3 | 44 by figures,
//                   2 | 71 by words). A caption over this many words is a paragraph.
//   decimalPlaces   numbers with at least this many decimal places and
//   decimalSignificant  this many significant digits (leading zeros after the
//                   point are scale, so 0.0001 is one), decimalCount of them in
//   decimalCount    one decimalUnit ('paragraph' or 'sentence'): 2 human
//   decimalUnit     paragraphs | 14 draft paragraphs.
const R03_TUNING = {
  bodyCrowded: null,
  captionFigures: 3,
  captionWords: 100,
  decimalPlaces: 4,
  decimalCount: 4,
  decimalUnit: 'paragraph',
  decimalSignificant: 3,
};

// A table cell holds a number, a label, or a short phrase. 0 of 103 human tables |
// 29 of 292 draft tables (26 by words, 3 by sentences). A sentence of one or two
// words is not counted: at 1, eight more draft tables flag, each on the period
// of an abbreviation.
const RA_CELL_WORDS = 15; // words above which a cell is prose
const RA_CELL_SENTENCES = 2; // sentences that make a cell prose
const RA_SENTENCE_WORDS = 3; // words a piece needs to count as a sentence
const RA_MAX_DEPTH = 4; // nested tables read; deeper ones stay inside their parent's cell

// Python's str.split(), str.strip() and \s treat U+001C-U+001F and U+0085 as
// whitespace and U+FEFF as text; JavaScript's \s does the opposite. The new
// checks count words and trim cells, so they use this class and the two engines
// agree on every character.
const R03_PY_SPACE = String.raw`\t\n\v\f\r \x1c-\x1f\x85\xa0  -     　`;
const R03_PY_SPACE_RUN_RE = new RegExp('[' + R03_PY_SPACE + ']+', 'u');
const R03_PY_SPACE_RUN_G_SRC = '[' + R03_PY_SPACE + ']+';

// Environments whose body is code or a comment: a \caption or a \begin{tabular}
// in one of them is an example, not a display.
const R03_CODE_ENV_SRC = String.raw`\\begin\{(verbatim\*?|lstlisting|minted|comment)\}`;

// \caption{, \caption*{, \caption[short]{, \captionof{figure}{. A command such
// as \captionsetup is not one.
const R03_CAPTION_SRC = String.raw`\\caption(?<of>of)?\*?(?![A-Za-z@])`;

// Commands whose first brace argument is layout or style, and rule commands with
// their arguments. Removed before words are counted, so \cmidrule(lr){2-3} and
// \cellcolor{gray} add none. \multicolumn and \multirow lose their two layout
// arguments and keep the text.
const R03_FIRST_ARG_SRC =
  String.raw`\\(?:parbox|makebox|framebox|raisebox|rotatebox|resizebox|scalebox|textcolor|` +
  String.raw`colorbox|fcolorbox|cellcolor|rowcolor|columncolor|arrayrulecolor)\*?` +
  String.raw`(?:[ \t]{0,3}\[[^\]]{0,50}\]){0,3}[ \t\n]{0,3}\{[^{}]{0,100}\}`;
const R03_SPAN_ARGS_SRC =
  String.raw`\\(?:multicolumn|multirow)\*?[ \t\n]{0,3}\{[^{}]{0,60}\}[ \t\n]{0,3}` +
  String.raw`(?:\[[^\]]{0,50}\][ \t\n]{0,3})?\{[^{}]{0,60}\}`;
const R03_RULE_ARGS_SRC =
  String.raw`\\(?:cmidrule|cline|specialrule|noalign|hhline)\*?(?![A-Za-z@])` +
  String.raw`(?:[ \t]{0,3}(?:\[[^\]]{0,30}\]|\([^)]{0,20}\))){0,2}` +
  String.raw`(?:[ \t\n]{0,3}\{[^{}]{0,60}\}){0,3}` +
  String.raw`|\\(?:toprule|midrule|bottomrule|hline|addlinespace)\*?(?![A-Za-z@])(?:[ \t]{0,3}\[[^\]]{0,30}\])?`;
// What opens a table cell without being its text: blanks and rule commands.
const RA_LEAD_SRC = '^(?:[' + R03_PY_SPACE + ']|' + R03_RULE_ARGS_SRC + ')*';
const R03_COMMAND_SRC = String.raw`\\[A-Za-z@]+\*?(?:\[[^\]\n]{0,200}\])?`;
const R03_ESCAPED_SRC = String.raw`\\([%&_#$])`;
const R03_DOLLAR_SRC = String.raw`(?<!\\)\$`;
// Python's [^\W\d_]{2,}: a letter or a non-decimal number character, twice or more.
const R03_WORD_SRC = String.raw`[\p{L}\p{Nl}\p{No}]{2,}`;
const R03_WORD_RE = new RegExp(R03_WORD_SRC, 'u');
const R03_BRACE_TOKEN_SRC = String.raw`\\.|[{}]`;
// A sentence end inside a table cell, after cleaning (single spaces). The
// lookbehind keeps a long run of full stops from being retried at every offset.
const RA_BOUNDARY_SRC = String.raw`(?<![.!?])[.!?]+["')\]]*[ ]+(?=[A-Z0-9"'(\[])`;

// A table environment, its begin and end tokens.
const RA_ENV_SRC = String.raw`\\(begin|end)\{(tabular\*|tabular|tabularx|tabulary|longtable|tblr)\}`;
const RA_ARG_COUNT = { tabular: 1, 'tabular*': 2, tabularx: 2, tabulary: 2, longtable: 1, tblr: 1 };
// Inside a table body: a row break (\\, \\*, \\[2pt]), a command name, an
// escaped character, a brace, a cell separator.
const RA_TOKEN_SRC = String.raw`\\\\\*?(?:\[[^\]\n]{0,20}\])?|\\[A-Za-z@]+|\\.|[{}&]`;

// Legend and decoding metadata in a caption (check C). A caption names its lines,
// markers, bands and thresholds so the reader can decode the display: "Lines mark
// the 25%, 50% and 75% quantiles", "Stars denote p < 0.05, 0.01 and 0.001". Those
// numbers are keys and not results, so the figure count skips them. Each pattern
// takes one run of numbers beside the word that names it, never the rest of the
// sentence, so a result written next to a legend still counts. Digits are ASCII and
// blanks are spelled out, so both engines read every input the same way. Compiled
// case-insensitively.
const LG_WS = String.raw`[ \t\r\n~]`;
const LG_NUM =
  String.raw`\$?[-+−]?[0-9]+(?:\.[0-9]+)?\$?` +
  String.raw`(?:(?:[ \t~]|\\,)?(?:\\%|%|percent` + R03_NOT_W_AFTER +
  String.raw`|(?:st|nd|rd|th)` + R03_NOT_W_AFTER + String.raw`))?\$?`;
const LG_SEP =
  String.raw`(?:` + LG_WS + String.raw`{0,3}(?:,|;|/|&|--|–|-)` + LG_WS + String.raw`{0,3}` +
  String.raw`|` + LG_WS + String.raw`{0,3},?` + LG_WS + String.raw`{1,3}(?:and|or|to)` + LG_WS + String.raw`{1,3})`;
// One to six numbers. The lookbehind starts a list at its first number, so a long
// run of digits or of "1,1,1" is entered once.
const LG_LIST = LG_NUM + String.raw`(?:` + LG_SEP + LG_NUM + String.raw`){0,5}`;
const LG_WORD_BEFORE = String.raw`(?:` + LG_WS + String.raw`{1,3}[A-Za-z-]{1,15}){0,1}` + LG_WS + String.raw`{1,3}`;
const LG_QUANTILE = String.raw`(?:quantiles?|percentiles?|quartiles?|deciles?)` + R03_NOT_W_AFTER;
const LG_SIGNIFICANCE =
  String.raw`(?:\\?alpha|α|significan(?:ce|t)(?:` + LG_WS +
  String.raw`{1,3}(?:levels?|thresholds?|codes?|stars?))?|thresholds?)` + R03_NOT_W_AFTER;
const LG_COMPARE = String.raw`\$?(?:[<>=≤≥]|\\(?:leqslant|geqslant|leq|geq|le|ge|lt|gt)(?![A-Za-z]))\$?`;
// A p-value is a key only beside an inequality or a threshold word: "p < 0.05" and
// "p-value thresholds of 0.05 and 0.01" define stars, while "p = 0.03" and "p-values
// of 0.041, 0.023 and 0.012" report results and stay in the count.
const LG_P = String.raw`p(?:[ -]?values?)?` + R03_NOT_W_AFTER;
const LG_INEQ = String.raw`\$?(?:[<>≤≥]|\\(?:leqslant|geqslant|leq|geq|le|ge|lt|gt)(?![A-Za-z]))\$?`;
const LG_P_KEY = String.raw`(?:levels?|thresholds?|cut-?offs?)` + R03_NOT_W_AFTER;
// A confidence level names a band: "the 68%, 95% and 99.7% confidence intervals".
const LG_CONF = String.raw`(?:confidence|credible|prediction|highest[ -]density)` + R03_NOT_W_AFTER;
// The singular "a confidence interval of 79.4% to 83.0%" is an estimate; the plural
// and a level name the bands of a legend.
const LG_CONF_NOUN = String.raw`(?:levels?|intervals|bands|regions|ellipses)` + R03_NOT_W_AFTER;
// A level is a percentage, so "a confidence interval of 39.8 to 42.7" stays a result.
const LG_PCT =
  String.raw`\$?[0-9]+(?:\.[0-9]+)?\$?(?:[ \t~]|\\,)?(?:\\%|%|percent` + R03_NOT_W_AFTER + String.raw`)\$?`;
const LG_PCT_LIST = LG_PCT + String.raw`(?:` + LG_SEP + LG_PCT + String.raw`){0,5}`;
const LG_MARKER =
  R03_NOT_W_BEFORE +
  String.raw`(?:lines?|markers?|symbols?|stars?|asterisks?|daggers?|bands?|shad(?:ing|ed)|` +
  String.raw`whiskers?|ticks?|contours?|isolines?|circles?|triangles?|squares?|diamonds?|crosses|arrows?)` +
  R03_NOT_W_AFTER;
const R03_LEGEND_SRCS = [
  // "25%, 50% and 75% quantiles", "the 5th and 95th percentiles"
  String.raw`(?<![0-9.,])` + LG_LIST + LG_WORD_BEFORE + LG_QUANTILE,
  // "quantiles at 25%, 50% and 75%", "percentiles (5, 50, 95)", "quantile levels 0.1, 0.5 and 0.9"
  R03_NOT_W_BEFORE + LG_QUANTILE +
    String.raw`(?:` + LG_WS + String.raw`{0,3}(?:at|of|are|is|for|to|the|from|between|set|levels?|values?|bands?|lines?|ranges?|\(|:|=|,)){0,4}` +
    LG_WS + String.raw`{0,3}` + LG_LIST,
  // "p < 0.05, 0.01 and 0.001", "alpha = 0.05", "significance thresholds at 0.05, 0.01 and 0.001"
  String.raw`(?<![\p{L}\p{N}_\\])` + LG_SIGNIFICANCE +
    String.raw`(?:` + LG_WS + String.raw`{0,3}(?:` + LG_COMPARE +
    String.raw`|is|are|was|were|at|of|set|to|below|under|above|for|levels?|values?|\(|:|\\,|\\;)){0,4}` +
    LG_WS + String.raw`{0,3}` + LG_LIST,
  // "p < 0.05, 0.01 and 0.001", "$p \le 0.05$", "p-value thresholds of 0.05 and 0.01"
  String.raw`(?<![\p{L}\p{N}_\\])` + LG_P +
    String.raw`(?:` + LG_WS + String.raw`{0,3}` + LG_INEQ + String.raw`|` + LG_WS + String.raw`{1,3}` + LG_P_KEY +
    String.raw`(?:` + LG_WS + String.raw`{0,3}(?:` + LG_COMPARE + String.raw`|is|are|at|of|set|to|below|under|\(|:)){0,3})` +
    LG_WS + String.raw`{0,3}` + LG_LIST,
  // "0.05, 0.01 and 0.001 significance levels", "the 0.05 and 0.01 p-value thresholds"
  String.raw`(?<![0-9.,])` + LG_LIST + LG_WORD_BEFORE +
    String.raw`(?:significance|thresholds?|\\?alpha|α|p[- ]?levels?|p[- ]?values?` + LG_WS +
    String.raw`{1,3}` + LG_P_KEY + String.raw`)` + R03_NOT_W_AFTER,
  // "the 68%, 95% and 99.7% confidence intervals", "95% CIs"
  String.raw`(?<![0-9.,])` + LG_PCT_LIST + LG_WORD_BEFORE + String.raw`(?:` + LG_CONF +
    String.raw`|CIs?` + R03_NOT_W_AFTER + String.raw`|HDIs?` + R03_NOT_W_AFTER + String.raw`)`,
  // "confidence levels of 68%, 95% and 99.7%"
  R03_NOT_W_BEFORE + LG_CONF + LG_WS + String.raw`{1,3}` + LG_CONF_NOUN +
    String.raw`(?:` + LG_WS + String.raw`{0,3}(?:at|of|are|is|for|the|=|:|\(|,)){0,3}` + LG_WS + String.raw`{0,3}` + LG_PCT_LIST,
  // "Lines mark the 0.5 chance level", "Dashed lines at 0.25, 0.50 and 0.75"
  LG_MARKER +
    String.raw`(?:` + LG_WS + String.raw`{0,3}(?:mark(?:s|ed|ing)?|denote[sd]?|indicate[sd]?|indicating|at|the|an?|chance|random|` +
    String.raw`baseline|reference|threshold|target|levels?|values?|of|for|=|:|\(|,)){1,5}` +
    LG_WS + String.raw`{0,3}` + LG_LIST,
  // "Solid, dashed and dotted lines correspond to dropout rates of 0.1, 0.2 and 0.5,
  // respectively": a style mapped to a setting. "respectively" must follow the list,
  // so "Lines represent accuracies of 0.81, 0.83 and 0.85" still counts.
  LG_MARKER +
    String.raw`(?:` + LG_WS + String.raw`{1,3}(?:correspond(?:s|ing)?` + LG_WS + String.raw`{1,3}to|denote[sd]?|indicate[sd]?|` +
    String.raw`represent(?:s|ed|ing)?|mark(?:s|ed)?|encode[sd]?|use[sd]?))` +
    String.raw`(?:` + LG_WS + String.raw`{1,3}(?:[A-Za-z$\\-]{1,20}|=)){0,4}` +
    LG_WS + String.raw`{0,3}` + LG_LIST + String.raw`(?=` + LG_WS + String.raw`{0,3},?` + LG_WS +
    String.raw`{0,3}respectively` + R03_NOT_W_AFTER + String.raw`)`,
];

// A heading that opens a method or setup section: its title names a method or an
// experimental setup and does not also name an outcome, so "Implementation Details"
// and "Hyperparameters" are exempt and "Experiments", "Evaluation", "Results" and
// "Setup and Results" are read. Words are ASCII, so both engines read every title
// the same way.
const R03_TEX_HEADING_SRC =
  String.raw`\\(chapter|section|subsection|subsubsection|paragraph|subparagraph)\*?[ \t]{0,3}` +
  String.raw`(?:\[[^\]\n]{0,200}\])?[ \t]{0,3}\{([^{}\n]{0,200})\}`;
const R03_HEADING_LEVELS = { chapter: 0, section: 1, subsection: 2, subsubsection: 3, paragraph: 4, subparagraph: 5 };
const R03_SETUP_WORDS = new Set([
  'method', 'methods', 'methodology', 'approach', 'setup', 'setups', 'setting', 'settings',
  'implementation', 'hyperparameter', 'hyperparameters', 'configuration', 'configurations',
  'dataset', 'datasets', 'details', 'protocol', 'protocols',
]);
const R03_OUTCOME_WORDS = new Set([
  'result', 'results', 'finding', 'findings', 'analysis', 'analyses', 'discussion', 'ablation', 'ablations',
]);

// Fresh global matcher each time: a shared one carries lastIndex between calls.
function r03Re(src, flags) {
  return new RegExp(src, flags === undefined ? 'gu' : flags);
}

// Compiled patterns by flags and source. Building a RegExp cost more than running it
// on a file of many short captions (84% of a scan of 50,000), so the scanners below
// compile each pattern once. Each use sets lastIndex before it reads, and r03Matches
// marks its pattern busy while it iterates, so any use of the same pattern meanwhile
// gets a fresh one and never shares lastIndex with the scan in progress.
// Keyed by flags, then by the source string itself: the sources are module constants,
// so a lookup reuses the string's hash instead of hashing a fresh concatenation.
const R03_RE_CACHE = new Map();
function r03Cached(src, flags) {
  let bySrc = R03_RE_CACHE.get(flags);
  if (bySrc === undefined) {
    bySrc = new Map();
    R03_RE_CACHE.set(flags, bySrc);
  }
  let re = bySrc.get(src);
  if (re === undefined) {
    re = new RegExp(src, flags);
    bySrc.set(src, re);
  } else if (re.r03Busy) {
    return new RegExp(src, flags);
  }
  return re;
}

function* r03Matches(src, text, flags) {
  const f = flags === undefined ? 'gu' : flags;
  const re = r03Cached(src, f);
  re.r03Busy = true;
  re.lastIndex = 0;
  try {
    let m;
    while ((m = re.exec(text)) !== null) {
      if (m[0].length === 0) re.lastIndex++;
      yield m;
    }
  } finally {
    re.r03Busy = false;
  }
}

// Anchored match at `pos`, like Python's pattern.match(text, pos).
function r03MatchAt(src, text, pos, flags) {
  const re = r03Cached(src, flags);
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

// Spans of material that carries digits without being a result: labels,
// citations, layout lengths, identifiers, reference numbers, link targets, and
// paths. Shared by the prose pass and by the caption check, which reads a
// caption in isolation.
function r03MaskSpans(text) {
  const spans = [];
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
  return spans;
}

// `extra` holds further display spans, such as the captions of a LaTeX file.
function r03StageTwo(text, latex, extra = []) {
  const spans = [];
  const display = extra.slice();
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

  // Loops, not push(...): a long file holds more spans than a call takes.
  for (const s of display) spans.push(s);
  for (const s of r03MaskSpans(text)) spans.push(s);
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
  // Neither global nor sticky, so the shared compiled patterns carry no state.
  const numberBefore = r03Cached(R03_NUMBER_BEFORE_SRC, 'u');
  const ciWordBefore = r03Cached(R03_CI_WORD_BEFORE_SRC, 'iu');
  const wordBeforeKeyword = r03Cached(R03_WORD_BEFORE_KEYWORD_SRC, 'iu');
  const levelBefore = r03Cached(R03_LEVEL_BEFORE_SRC, 'iu');

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

// ---------- LaTeX helpers for checks C and D and for RULE-A -----------------------

// Python's str.isspace() for one UTF-16 unit (all of its whitespace is in the
// BMP).
function r03IsPySpace(c) {
  return (
    (c >= 9 && c <= 13) || (c >= 28 && c <= 32) || c === 0x85 || c === 0xa0 || c === 0x1680 ||
    (c >= 0x2000 && c <= 0x200a) || c === 0x2028 || c === 0x2029 || c === 0x202f ||
    c === 0x205f || c === 0x3000
  );
}

// Python's str.strip() with no argument. A loop and not a regex: a trailing
// `\s+$` retried at every offset of a long run of blanks is quadratic.
function r03PyStrip(s) {
  let a = 0;
  let b = s.length;
  while (a < b && r03IsPySpace(s.charCodeAt(a))) a++;
  while (b > a && r03IsPySpace(s.charCodeAt(b - 1))) b--;
  return s.slice(a, b);
}

// Length in code points, which is what Python's len() counts.
function r03CodePointLength(s) {
  let n = 0;
  for (const _ch of s) n++; // eslint-disable-line no-unused-vars
  return n;
}

// Python's str.find(ch, start, end) for one character, bounded so a scan for a
// closing bracket costs a fixed number of steps.
function r03FindBounded(s, ch, start, end) {
  const stop = Math.min(end, s.length);
  for (let k = start; k < stop; k++) if (s[k] === ch) return k;
  return -1;
}

// Spans of each environment whose \begin token `beginSrc` finds. Found by
// search, so an unclosed environment costs one scan and not one per opener.
function r03EnvSpans(text, beginSrc) {
  const spans = [];
  let covered = 0;
  const exhausted = new Set();
  for (const m of r03Matches(beginSrc, text)) {
    if (m.index < covered || exhausted.has(m[1])) continue;
    const endTok = '\\end{' + m[1] + '}';
    const j = text.indexOf(endTok, m.index + m[0].length);
    if (j < 0) {
      exhausted.add(m[1]);
      continue;
    }
    covered = j + endTok.length;
    spans.push([m.index, covered]);
  }
  return spans;
}

// Map the offset of each `{` to the offset of its closing `}`. A backslash
// escapes the next character, so `\{` and `\\{` read as they do in LaTeX. One
// pass with a stack, so a file of unclosed groups costs nothing extra per group.
function r03BraceMap(text) {
  const match = new Map();
  const stack = [];
  for (const m of r03Matches(R03_BRACE_TOKEN_SRC, text, 'gsu')) {
    const ch = m[0];
    if (ch === '{') stack.push(m.index);
    else if (ch === '}' && stack.length > 0) match.set(stack.pop(), m.index);
  }
  return match;
}

function r03SkipBlanks(text, i) {
  while (i < text.length) {
    const c = text.charCodeAt(i);
    if (c === 32 || c === 9 || c === 13 || c === 10) i++;
    else break;
  }
  return i;
}

// [command start, body start, body end, offset after the closing brace] per
// caption: \caption{..}, \caption*{..}, \caption[short]{..} and
// \captionof{type}{..}, braces balanced. A caption inside a code environment is
// an example and is not read; a caption that opens inside another one is part
// of it.
function r03Captions(text) {
  if (!text.includes('\\caption')) return [];
  const src = r03Blank(text, r03EnvSpans(text, R03_CODE_ENV_SRC));
  const n = src.length;
  let braces = null;
  const out = [];
  let covered = 0;
  for (const m of r03Matches(R03_CAPTION_SRC, src)) {
    if (m.index < covered) continue;
    if (braces === null) braces = r03BraceMap(src);
    let i = r03SkipBlanks(src, m.index + m[0].length);
    if (m.groups.of) {
      if (i >= n || src[i] !== '{' || !braces.has(i)) continue;
      i = r03SkipBlanks(src, braces.get(i) + 1);
    }
    if (i < n && src[i] === '[') {
      const j = r03FindBounded(src, ']', i, i + 600);
      if (j < 0) continue;
      i = r03SkipBlanks(src, j + 1);
    }
    if (i < n && src[i] === '{' && braces.has(i)) {
      covered = braces.get(i) + 1;
      out.push([m.index, i + 1, braces.get(i), covered]);
    }
  }
  return out;
}

// Blank $..$ and \(..\) math, length-preserving. A \$ is a dollar sign.
function r03StripMath(text) {
  const marks = [];
  for (const m of r03Matches(R03_DOLLAR_SRC, text)) marks.push(m.index);
  const spans = [];
  for (let i = 0; i < marks.length - 1; i += 2) spans.push([marks[i], marks[i + 1] + 1]);
  for (const s of r03Pairs(text, '\\(', '\\)')) spans.push(s);
  return r03Blank(text, spans);
}

// The words of a LaTeX fragment: no citations, references, math or commands. A
// command is dropped and its text argument is kept, so `\textbf{Left:} the run`
// reads `Left: the run`.
function r03PlainText(raw) {
  // A line break first: the two words in `one\\two` are not a word and a command.
  let t = raw.split('\\\\').join(' ');
  for (const src of [R03_ARG1_SRC, R03_ARGN_SRC, R03_FIRST_ARG_SRC, R03_RULE_ARGS_SRC, R03_SPAN_ARGS_SRC]) {
    t = t.replace(r03Cached(src, 'gu'), ' ');
  }
  t = r03StripMath(t);
  t = t.replace(r03Cached(R03_COMMAND_SRC, 'gu'), ' ');
  t = t.replace(r03Cached(R03_ESCAPED_SRC, 'gu'), '$1');
  t = t.replace(/[{}~\\]/gu, ' ');
  return r03PyStrip(t.replace(r03Cached(R03_PY_SPACE_RUN_G_SRC, 'gu'), ' '));
}

// Tokens with at least two letters in a row; numbers and single letters are not words.
function r03CountWords(plain) {
  let n = 0;
  for (const token of plain.split(R03_PY_SPACE_RUN_RE)) {
    if (token !== '' && R03_WORD_RE.test(token)) n++;
  }
  return n;
}

// Spans of legend and decoding metadata: quantile lines, significance levels,
// markers. Used on a caption only. A number beside the word that names a line, a
// threshold or a symbol is a key to the display and not a result.
function r03LegendSpans(text) {
  const spans = [];
  for (const src of R03_LEGEND_SRCS) {
    for (const m of r03Matches(src, text, 'giu')) spans.push([m.index, m.index + m[0].length]);
  }
  return spans;
}

// Precise figures in a fragment read alone, with the masks and the level rule of
// check A. A confidence level and the numbers of a legend are not figures.
function r03SpanFigures(segment) {
  // The fragment is only counted, never located, so its blanks can be collapsed: a
  // caption wrapped and indented in the source reads like one written on one line.
  const masked = r03Blank(segment, r03MaskSpans(segment)).replace(/[ \t\r\n~]+/g, ' ');
  const levels = r03Intervals(masked)[1];
  // Legends are read before the levels are blanked: blanking "99.7% confidence"
  // first would cut the end off "68%, 95% and 99.7% confidence intervals".
  return r03Figures(r03Blank(masked, levels.concat(r03LegendSpans(masked)))).length;
}

// True when a heading title names a method or a setup and no outcome.
function r03IsSetupTitle(raw) {
  const words = new Set();
  for (const m of r03Matches(String.raw`[A-Za-z]+`, raw.replace(/(?<=[A-Za-z])-(?=[A-Za-z])/g, ''), 'g')) {
    words.add(m[0].toLowerCase());
  }
  let setup = false;
  for (const w of words) {
    if (R03_OUTCOME_WORDS.has(w)) return false;
    if (R03_SETUP_WORDS.has(w)) setup = true;
  }
  return setup;
}

// Sorted [start, end] spans of LaTeX method and setup sections. A \section,
// \subsection, \subsubsection or \paragraph heading (a star or a short title in
// brackets allowed) whose title names a method or a setup opens a span that runs to
// the next heading of the same or a higher level, or to the end of the text. Exact
// settings (learning rates, dropout, splits) belong there. One pass, so a file of
// headings costs a single scan.
function r03SetupSpans(text) {
  const spans = [];
  let openLevel = -1;
  let openStart = 0;
  for (const m of r03Matches(R03_TEX_HEADING_SRC, text)) {
    const level = R03_HEADING_LEVELS[m[1]];
    if (openLevel >= 0 && level <= openLevel) {
      spans.push([openStart, m.index]);
      openLevel = -1;
    }
    if (openLevel < 0 && r03IsSetupTitle(m[2])) {
      openLevel = level;
      openStart = m.index + m[0].length;
    }
  }
  if (openLevel >= 0) spans.push([openStart, text.length]);
  return spans;
}

// [start, end] of the LaTeX document body: after \begin{document}, before
// \end{document}. A fragment with neither command is all body.
function r03DocumentRange(stageOne) {
  let start = 0;
  let end = stageOne.length;
  const tok = '\\begin{document}';
  const i = stageOne.indexOf(tok);
  if (i >= 0) start = i + tok.length;
  const j = stageOne.indexOf('\\end{document}', start);
  if (j >= 0) end = j;
  return [start, end];
}

// A number with at least `places` decimal places, sign included. The sign is a
// minus, a plus, U+2212, or one wrapped in math ($-$0.05, $-0.05$). A hyphen
// inside a name (ResNet-18.1234) is not a sign, and a number glued to a word or
// to another number is an identifier. Up to five thousands groups belong to the
// number (1,234.5678); the bound keeps a long run of 123,123,123 from being
// rescanned at every group.
function r03DecimalSrc(places) {
  return (
    String.raw`(?<![\p{L}\p{N}_.])(?:\$?[-+−]\$?)?(?<![\p{L}\p{N}_.])` +
    String.raw`(?:\p{Nd}{1,3}(?:,\p{Nd}{3}){1,5}|\p{Nd}*)\.\p{Nd}{` + places + String.raw`,}(?!\p{Nd})(?!\.\p{Nd})`
  );
}

// Significant digits of a matched number: its digits without the leading zeros.
// 0.0143 has three, 0.00025 two and 0.0001 one; a zero after the first digit counts
// (0.1000 has four). Leading zeros are the ASCII zero only, so both engines count
// exotic digits the same way.
function r03Significant(number) {
  return r03CodePointLength(number.replace(/[^\p{Nd}]/gu, '').replace(/^0+/, ''));
}

// A function from an offset to [line, column, line text], for findings.
function r03MakeLocate(text) {
  const spans = lineSpans(text);
  const starts = spans.map((s) => s[0]);
  return (offset) => {
    const lineNo = Math.max(1, r03BisectRight(starts, offset));
    const [lineStart, lineEnd] = spans[lineNo - 1];
    return [lineNo, offset - lineStart + 1, text.slice(lineStart, lineEnd)];
  };
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
  // A method or setup section holds the exact settings a reader needs to repeat the
  // work, so the body run of check B and check D skip it.
  const setup = latex ? r03SetupSpans(stageOne) : [];
  const setupStarts = setup.map((s) => s[0]);
  // A caption is display material: it feeds check C and neither A nor B, in or
  // out of a figure or table environment.
  const captions = latex ? r03Captions(stageOne) : [];
  const [masked, display] = r03StageTwo(stageOne, latex, captions.map((c) => [c[0], c[3]]));
  const [docStart, docEnd] = latex ? r03DocumentRange(stageOne) : [0, 0];

  const inAppendix = (offset) => {
    const slot = r03BisectRight(appendixStarts, offset) - 1;
    return slot >= 0 && offset < appendix[slot][1];
  };

  const inSetup = (offset) => {
    const slot = r03BisectRight(setupStarts, offset) - 1;
    return slot >= 0 && offset < setup[slot][1];
  };

  const cuts = display.map((s) => s[0]).concat(display.map((s) => s[1]));
  for (const [start, end] of regions) cuts.push(start, end);
  for (const [start, end] of setup) cuts.push(start, end);
  const sentences = r03Sentences(masked, cuts);
  if (sentences.length === 0 && captions.length === 0) return [];
  const sentenceStarts = sentences.map((s) => s[0]);

  const [intervals, levels] = r03Intervals(masked);
  const figuresText = r03Blank(masked, levels);
  const figureStarts = r03Figures(figuresText);

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

  // Check B: stacked figures, inside an abstract or an introduction and, in a
  // LaTeX file, in the body prose between them.
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

  const labelOf = (offset) => {
    const label = regionOf(offset);
    if (label === null && latex && docStart <= offset && offset < docEnd && !inAppendix(offset) && !inSetup(offset)) {
      return R03_BODY;
    }
    return label;
  };

  const counts = sentences.map(([start, end]) => [
    start,
    end,
    r03BisectLeft(figureStarts, end) - r03BisectLeft(figureStarts, start),
    labelOf(start),
  ]);

  const reportRun = (run) => {
    const start = run[0][0];
    const total = run.reduce((acc, item) => acc + item[2], 0);
    const [lineNo, col, line] = locate(start);
    const detail =
      run[0][3] === R03_BODY
        ? `${run.length} consecutive sentences in the body text carry ${total} precise figures. ` +
          'Keep the few magnitudes behind the main findings, round them, ' +
          'and move the rest to a table or an appendix'
        : `${run.length} consecutive sentences in the ${run[0][3]} carry ${total} precise figures; ` +
          'keep the few magnitudes behind the main findings and move the rest to a table';
    out.push({
      rule: 'RULE-03',
      line: lineNo,
      column: col,
      excerpt: excerpt(line, [col - 1, col - 1 + Math.min(run[0][1] - start, 80)]),
      detail,
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
        const limit = lab === R03_BODY ? R03_TUNING.bodyCrowded : R03_CROWDED;
        if (limit !== null && n >= limit) {
          const [lineNo, col, line] = locate(start);
          const where = lab === R03_BODY ? 'the body text' : `the ${lab}`;
          out.push({
            rule: 'RULE-03',
            line: lineNo,
            column: col,
            excerpt: excerpt(line, [col - 1, col - 1 + Math.min(end - start, 80)]),
            detail:
              `one sentence in ${where} carries ${n} precise figures; ` +
              'keep the one the claim rests on and move the rest to a table',
          });
        }
      }
    }
    run = label !== null && item[2] >= R03_RUN_FIGURES ? [item] : [];
  }
  // A crowded sentence below the run threshold of figures per sentence cannot
  // exist (crowded implies at least the run threshold), so nothing is missed.

  // Check C: a caption that carries precise figures or runs long. LaTeX only,
  // outside an appendix.
  const capTail =
    'A caption names the display, its pattern, and what the marks mean. Keep decoding ' +
    'values such as error-bar definitions; move repeated results, setup narration, ' +
    'and caveats to the text or an appendix';
  for (const [cmdStart, bodyStart, bodyEnd] of captions) {
    if (inAppendix(cmdStart)) continue;
    const body = stageOne.slice(bodyStart, bodyEnd);
    const words = r03CountWords(r03PlainText(body));
    const figs = r03SpanFigures(body);
    let head;
    if (figs >= R03_TUNING.captionFigures) head = `a caption carries ${figs} precise figures`;
    else if (words > R03_TUNING.captionWords) head = `a caption runs ${words} words`;
    else continue;
    const [lineNo, col, line] = locate(cmdStart);
    out.push({
      rule: 'RULE-03',
      line: lineNo,
      column: col,
      excerpt: excerpt(line, [col - 1, col - 1 + 80]),
      detail: `${head}. ${capTail}`,
    });
  }

  // Check D: numbers written to many decimal places, in LaTeX body prose (the
  // abstract and introduction included) outside an appendix.
  if (latex && sentences.length > 0) {
    const places = R03_TUNING.decimalPlaces;
    const need = R03_TUNING.decimalCount;
    const perSentence = R03_TUNING.decimalUnit === 'sentence';
    const digits = R03_TUNING.decimalSignificant;
    const longStarts = [];
    for (const m of r03Matches(r03DecimalSrc(places), figuresText)) {
      if (
        docStart <= m.index && m.index < docEnd && !inAppendix(m.index) &&
        !inSetup(m.index) && r03Significant(m[0]) >= digits
      ) {
        longStarts.push(m.index);
      }
    }
    if (longStarts.length > 0) {
      let units;
      if (perSentence) {
        units = sentences;
      } else {
        const points = new Set([0, masked.length]);
        for (const m of r03Matches(R03_BLOCK_SRC, masked)) points.add(m.index);
        // A heading ends a paragraph even when its body runs on in the same
        // source line, as a \paragraph{} heading does.
        for (const m of r03Matches(R03_TEX_HEADING_SRC, stageOne)) points.add(m.index);
        const ordered = [...points].sort((x, y) => x - y);
        units = [];
        for (let i = 0; i + 1 < ordered.length; i++) units.push([ordered[i], ordered[i + 1]]);
      }
      const unit = perSentence ? 'sentence' : 'paragraph';
      for (const [start, end] of units) {
        const lo = r03BisectLeft(longStarts, start);
        const hi = r03BisectLeft(longStarts, end);
        if (hi - lo < need) continue;
        const [lineNo, col, line] = locate(longStarts[lo]);
        out.push({
          rule: 'RULE-03',
          line: lineNo,
          column: col,
          excerpt: excerpt(line, [col - 1, col - 1 + 20]),
          detail:
            `${hi - lo} numbers written to ${places} or more decimal places in one ${unit}. ` +
            'Report the precision the measurement supports, usually two or three ' +
            'significant digits, and keep the full values in a table or an appendix',
        });
      }
    }
  }

  out.sort((x, y) => x.line - y.line || x.column - y.column);
  return out;
}

// ---------- RULE-A table cells (hook-only, LaTeX only) -----------------------

// Table environments as [begin, body start, body end, end, nested spans, env].
// `text` is LaTeX with comments and code blanked. A table nested in a table cell
// is its own entry and its span is listed under its parent, whose cells then
// skip it. Only the outer RA_MAX_DEPTH levels are returned, so a file of deeply
// nested tables costs a bounded number of rescans.
function raTables(text) {
  const stack = [];
  const openCount = new Map();
  const out = [];
  for (const m of r03Matches(RA_ENV_SRC, text)) {
    const env = m[2];
    const endAt = m.index + m[0].length;
    if (m[1] === 'begin') {
      stack.push([env, m.index, endAt, [], stack.length]);
      openCount.set(env, (openCount.get(env) || 0) + 1);
      continue;
    }
    if (!openCount.get(env)) continue;
    let k = stack.length - 1;
    while (stack[k][0] !== env) k--;
    const node = stack[k];
    for (let q = k; q < stack.length; q++) {
      openCount.set(stack[q][0], openCount.get(stack[q][0]) - 1);
    }
    stack.length = k;
    if (node[4] < RA_MAX_DEPTH) out.push([node[1], node[2], m.index, endAt, node[3], node[0]]);
    if (stack.length > 0) stack[stack.length - 1][3].push([node[1], endAt]);
  }
  out.sort((x, y) => x[0] - y[0]);
  return out;
}

// Offset after the optional and brace arguments that open a table environment.
function raSkipArgs(text, braces, i, nargs) {
  const n = text.length;
  let got = 0;
  while (got < nargs) {
    const j = r03SkipBlanks(text, i);
    if (j < n && text[j] === '[') {
      const k = r03FindBounded(text, ']', j, j + 200);
      if (k < 0) break;
      i = k + 1;
    } else if (j < n && text[j] === '{' && braces.has(j)) {
      i = braces.get(j) + 1;
      got++;
    } else {
      break;
    }
  }
  return i;
}

// [offset, text] of each cell of a table body, split at `&` and at row breaks.
// `work` is the body with nested tables and captions blanked, and `base` the
// offset it starts at. A separator inside braces, such as the `\\` of a
// `\makecell`, does not split.
function raCells(work, base) {
  const cells = [];
  let depth = 0;
  let start = 0;
  for (const m of r03Matches(RA_TOKEN_SRC, work, 'gsu')) {
    const tok = m[0];
    if (tok === '{') {
      depth++;
    } else if (tok === '}') {
      depth = Math.max(0, depth - 1);
    } else if (depth > 0) {
      continue;
    } else if (tok === '&' || tok.slice(0, 2) === '\\\\' || tok === '\\tabularnewline' || tok === '\\cr') {
      cells.push([base + start, work.slice(start, m.index)]);
      start = m.index + tok.length;
    }
  }
  cells.push([base + start, work.slice(start)]);
  return cells;
}

// Pieces of a cleaned cell that hold at least RA_SENTENCE_WORDS words. A full
// stop after an abbreviation, an initial, or a dotted abbreviation such as `e.g.`
// does not end a sentence.
function raSentenceCount(plain) {
  const pieces = [];
  let start = 0;
  const tokenRe = new RegExp(R03_PRECEDING_TOKEN_SRC, 'u');
  for (const m of r03Matches(RA_BOUNDARY_SRC, plain)) {
    const token = tokenRe.exec(plain.slice(Math.max(0, m.index - 16), m.index));
    if (token !== null) {
      const word = token[1].toLowerCase();
      if (
        R03_ABBREVIATIONS.has(word) ||
        word.length === 1 ||
        (word.includes('.') && word.split('.').every((p) => p.length === 1))
      ) {
        continue;
      }
    }
    const end = m.index + m[0].length;
    pieces.push(plain.slice(start, end));
    start = end;
  }
  pieces.push(plain.slice(start));
  let n = 0;
  for (const piece of pieces) if (r03CountWords(piece) >= RA_SENTENCE_WORDS) n++;
  return n;
}

// Flag a LaTeX table cell that holds prose. A table environment (tabular,
// tabular*, tabularx, tabulary, longtable, tblr) outside an appendix or a
// supplement is flagged, once, when a cell holds more than RA_CELL_WORDS words
// or RA_CELL_SENTENCES sentences. A word is a token with two or more letters
// once commands, math, citations and references are stripped. The finding sits
// on the first such cell. LaTeX only: a Markdown table in an agent document may
// carry long cells by design, so a `.md` file is never read.
//
// Hook-only, like rule03: the CLI audit classifies RULE-A as structural and
// never calls this. Never throws: the guard treats an exception from any
// advisory detector as a broken package.
function ruleA(text, filePath = '') {
  try {
    return ruleAScan(text, filePath);
  } catch (err) {
    return [];
  }
}

function ruleAScan(text, filePath) {
  if (typeof text !== 'string' || text.length === 0) return [];
  const base = String(filePath || '').split(/[\\/]/).pop().toLowerCase();
  if (!r03IsLatex(base, text) || r03AppendixNamed(base)) return [];
  const stageOne = r03StageOne(text, true, false);
  if (!stageOne.includes('\\begin{')) return [];
  const src = r03Blank(stageOne, r03EnvSpans(stageOne, R03_CODE_ENV_SRC));
  const tables = raTables(src);
  if (tables.length === 0) return [];
  const appendix = r03AppendixSpans(stageOne, true);
  const appendixStarts = appendix.map((s) => s[0]);
  const braces = r03BraceMap(src);
  const captions = r03Captions(src).map((c) => [c[0], c[3]]);
  const captionStarts = captions.map((c) => c[0]);
  const locate = r03MakeLocate(text);
  const leadRe = new RegExp(RA_LEAD_SRC, 'u');
  const out = [];
  for (const [begin, bodyStart, bodyEnd, , nested, env] of tables) {
    const slot = r03BisectRight(appendixStarts, begin) - 1;
    if (slot >= 0 && begin < appendix[slot][1]) continue;
    const start = raSkipArgs(src, braces, bodyStart, RA_ARG_COUNT[env]);
    if (start >= bodyEnd) continue;
    const lo = r03BisectLeft(captionStarts, start);
    const hi = r03BisectLeft(captionStarts, bodyEnd);
    const skip = [];
    for (const [a, b] of nested.concat(captions.slice(lo, hi))) {
      if (a >= start) skip.push([a - start, b - start]);
    }
    const work = r03Blank(src.slice(start, bodyEnd), skip);
    for (const [offset, raw] of raCells(work, start)) {
      if (raw.length < 18 || r03CodePointLength(r03PyStrip(raw)) < 18) continue;
      const plain = r03PlainText(raw);
      const words = r03CountWords(plain);
      let head;
      if (words > RA_CELL_WORDS) {
        head = `a table cell of ${words} words`;
      } else if (words >= 2 * RA_SENTENCE_WORDS && raSentenceCount(plain) >= RA_CELL_SENTENCES) {
        head = `a table cell of ${raSentenceCount(plain)} sentences`;
      } else {
        continue;
      }
      const [lineNo, col, line] = locate(offset + leadRe.exec(raw)[0].length);
      out.push({
        rule: 'RULE-A',
        line: lineNo,
        column: col,
        excerpt: excerpt(line, [col - 1, col - 1 + 80]),
        detail:
          `${head}; a table cell holds a number, a label, or a short phrase, ` +
          'so move content that needs a sentence into the text',
      });
      break;
    }
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
  'RULE-A': ruleA,
};

// Detectors that also take the file path. RULE-03 locates the abstract and the
// introduction by file name as well as by markup, and RULE-03 and RULE-A read
// LaTeX only and exempt appendix and supplement files by name.
//
// RULE-A is registered here so a hook can reach it as `ruleA`, but the audit
// never runs it: CLASSIFICATION in primitive.js holds RULE-A as structural only,
// and `audit` calls this module for a rule only when its bucket holds
// 'mechanical'. The structural RULE-A (bullet overuse) stays what `agent-style
// review` reports under that id, and the mechanical scope the benchmark pins
// does not change. RULE-03 is registered the same way.
const FILE_PATH_RULES = new Set(['RULE-03', 'RULE-A']);

// lineSpans is exported for the boundary tests: it is the detector's own
// CR/LF/CRLF line model, and `audit` normalises on read, so a direct-text
// caller is the only path that exercises it. rule03 and ruleA are exported for
// the same reason: the tests call them on text with a file path, and a hook
// imports ruleA the way it imports rule03. r03Tuning is the object that holds
// the 0.7.0 limits of check B (body), C and D, which the Python module holds as
// _R03_* constants; a test sets a field the way a Python test monkeypatches
// the constant, and restores it. rule03Scan and ruleAScan are the scans without
// the catch-all, so a never-throws test cannot hide a bug behind the wrapper, as
// the Python tests call _rule_03_scan and _rule_a_scan. r03Significant is the
// significant-digit count of check D, which the Python tests call as
// _r03_significant.
module.exports = {
  run, lineSpans, rule03, ruleA, rule03Scan, ruleAScan, r03Tuning: R03_TUNING, r03Significant,
};
