// SPDX-License-Identifier: MIT
'use strict';
/**
 * Fixture-driven tests for the Node review primitive. Mirror of the Python
 * tests in packages/pypi/tests/test_review_fixtures.py. Loads the same
 * fixture-prose/*.md + <name>.expected.json pairs and asserts per-rule counts
 * match byte-for-byte with the Python detectors.
 *
 * Uses node --test (stdlib; zero new runtime dependencies).
 */

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs');
const path = require('path');

const { audit } = require('../lib/review');
const { CLASSIFICATION } = require('../lib/review/primitive');

const FIXTURES_DIR = path.resolve(
  __dirname,
  '..',
  'data',
  'skills',
  'style-review',
  'references',
  'fixture-prose'
);

function listFixtures() {
  if (!fs.existsSync(FIXTURES_DIR)) return [];
  return fs
    .readdirSync(FIXTURES_DIR)
    .filter((f) => f.endsWith('.md'))
    .map((md) => ({
      name: md,
      md: path.join(FIXTURES_DIR, md),
      expected: path.join(FIXTURES_DIR, md.replace(/\.md$/, '.expected.json')),
    }))
    .filter((x) => fs.existsSync(x.expected))
    .sort((a, b) => a.name.localeCompare(b.name));
}

// Per-fixture count checks.
for (const fx of listFixtures()) {
  test(`audit matches expected for ${fx.name}`, () => {
    const expected = JSON.parse(fs.readFileSync(fx.expected, 'utf8'));
    const result = audit(fx.md, { mechanicalOnly: false, skillHost: false });

    assert.equal(
      result.totalViolations,
      expected.total_violations,
      `${fx.name}: expected ${expected.total_violations} total, got ${result.totalViolations}`
    );

    // Aggregate counts across buckets per rule id.
    const actualCounts = {};
    for (const rr of result.ruleResults) {
      if (rr.count > 0) actualCounts[rr.rule] = (actualCounts[rr.rule] || 0) + rr.count;
    }
    const expectedCounts = expected.per_rule_count || {};
    assert.deepEqual(
      sortObj(actualCounts),
      sortObj(expectedCounts),
      `${fx.name}: per-rule count mismatch`
    );

    // Semantic / deferred-structural rules must all be skipped.
    const skippedIds = new Set(
      result.ruleResults.filter((rr) => rr.status === 'skipped').map((rr) => rr.rule)
    );
    for (const rid of expected.expected_skipped_rules || []) {
      assert.ok(
        skippedIds.has(rid),
        `${fx.name}: expected rule ${rid} to be skipped but it was not`
      );
    }
  });
}

// Explicit regression guards matching the Python test file.
test('clean-control has zero violations', () => {
  const fx = path.join(FIXTURES_DIR, 'clean-control.md');
  if (!fs.existsSync(fx)) return;
  const result = audit(fx, { mechanicalOnly: false, skillHost: false });
  const triggered = result.ruleResults
    .filter((rr) => rr.status === 'violation')
    .map((rr) => [rr.rule, rr.detector, rr.count]);
  assert.deepEqual(triggered, [], `clean-control produced violations: ${JSON.stringify(triggered)}`);
});

test('messy-real-world: fenced `leverages` is not flagged as RULE-06', () => {
  const fx = path.join(FIXTURES_DIR, 'messy-real-world.md');
  if (!fs.existsSync(fx)) return;
  const result = audit(fx, { mechanicalOnly: false, skillHost: false });
  for (const rr of result.ruleResults) {
    if (rr.rule === 'RULE-06') {
      assert.equal(rr.count, 0, 'RULE-06 fired on fenced-code fixture');
    }
  }
});

test('audit (no skill host) skips all semantic rules', () => {
  const fx = path.join(FIXTURES_DIR, 'mixed.md');
  if (!fs.existsSync(fx)) return;
  const result = audit(fx, { mechanicalOnly: false, skillHost: false });
  const leaks = result.ruleResults.filter(
    (rr) => rr.detector === 'semantic' && rr.status === 'violation'
  );
  assert.equal(leaks.length, 0, 'semantic detectors should be skipped without skill host');
});

test('--mechanical-only excludes structural and semantic', () => {
  const fx = path.join(FIXTURES_DIR, 'mixed.md');
  if (!fs.existsSync(fx)) return;
  const result = audit(fx, { mechanicalOnly: true, skillHost: false });
  const leaks = result.ruleResults.filter(
    (rr) => rr.detector !== 'mechanical' && rr.status === 'violation'
  );
  assert.equal(
    leaks.length,
    0,
    `mechanical-only leaked non-mechanical violations: ${leaks.map((l) => l.rule).join(', ')}`
  );
});

test('RULE-07 classification includes structural and semantic', () => {
  assert.deepEqual(
    [...CLASSIFICATION['RULE-07']].sort(),
    ['semantic', 'structural']
  );
});

function sortObj(obj) {
  return Object.fromEntries(Object.entries(obj).sort(([a], [b]) => a.localeCompare(b)));
}

// ---------------------------------------------------------------------------
// Exact-object boundary tests. Mirror of the Python cases in
// packages/pypi/tests/test_review_fixtures.py.
//
// The fixture tests above assert per-rule counts only, so a false positive and
// a false negative for the same rule cancel out and the suite still passes. The
// cases below build their own input and assert the complete violation location,
// which is what makes them a regression oracle rather than a tally.
// ---------------------------------------------------------------------------

const os = require('os');
const { lineSpans } = require('../lib/review/detectors_mech');

let caseSeq = 0;

// Audit `text` through the public file path; return complete violations.
// Comparing whole objects rather than [line, column] is the point: RULE-A's
// `detail` string is part of the canonical JSON, so a change to it is a
// behavior change that a coordinate-only assertion would not catch.
function auditText(text, rule) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'agent-style-case-'));
  const target = path.join(dir, `case-${caseSeq++}.md`);
  fs.writeFileSync(target, Buffer.from(text, 'utf8'));
  const result = audit(target, { skillHost: false });
  return result.ruleResults
    .filter((rr) => rr.rule === rule)
    .flatMap((rr) => (rr.violations || []).map((v) => ({
      line: v.line, column: v.column, excerpt: v.excerpt, detail: v.detail,
    })));
}

// Coordinate-only view of auditText, for the many-case tables.
function auditTextAt(text, rule) {
  return auditText(text, rule).map((v) => [v.line, v.column]);
}

for (const [label, newline] of [['lf', '\n'], ['crlf', '\r\n'], ['cr', '\r']]) {
  test(`RULE-05 locates a cliche under ${label} line endings`, () => {
    const text = `prefix${newline}paradigm shift${newline}tail${newline}`;
    assert.deepEqual(
      auditText(text, 'RULE-05'),
      [{ line: 2, column: 1, excerpt: 'paradigm shift', detail: "cliché phrase 'paradigm shift'" }],
      `RULE-05 mislocated the cliche under ${label} line endings`
    );
  });

  // Go through the detector, not just its helper. `audit` normalises line
  // endings on read, so a direct-text caller is the only path that exercises
  // RULE-05's own offset arithmetic; asserting on lineSpans alone would still
  // pass if RULE-05 stopped consuming it.
  test(`RULE-05 handles ${label} line endings in direct text`, () => {
    const { run: runMech } = require('../lib/review/detectors_mech');
    const result = runMech(
      { id: 'RULE-05', severity: 'medium' },
      `prefix${newline}paradigm shift`,
      'memory.md'
    );
    assert.deepEqual(
      result.violations.map((v) => [v.line, v.column, v.detail]),
      [[2, 1, "cliché phrase 'paradigm shift'"]]
    );
  });
}

test('line spans handle mixed line endings in direct text', () => {
  for (const newline of ['\n', '\r\n', '\r']) {
    assert.deepEqual(
      lineSpans(`prefix${newline}paradigm shift`),
      [[0, 6], [6 + newline.length, 6 + newline.length + 14]],
      `line spans wrong for ${JSON.stringify(newline)}`
    );
  }
});

// RULE-A's directive names checklist steps as a genuine list. Shortness is not
// evidence, and neither is a repeated opening word; both describe these lists
// as much as they describe fragmented prose.
for (const [label, body] of [
  ['imperative checklist', '1. Stop the service.\n2. Rotate the credentials.\n3. Restart the workers.\n'],
  ['repeated-opener checklist', '1. Run the migration.\n2. Run the tests.\n3. Run the service.\n'],
  ['preposition-led enumeration', '- For Linux, use apt.\n- For macOS, use brew.\n- For Windows, use winget.\n'],
  ['uniform per enumeration', '- Per minute limits\n- Per user limits\n- Per region limits\n'],
  ['short independent labels', '- Linux\n- macOS\n- Windows\n'],
]) {
  test(`RULE-A leaves a genuine enumeration alone: ${label}`, () => {
    assert.deepEqual(auditText(`Heading:\n\n${body}`, 'RULE-A'), []);
  });
}

// Each of RULE-A's own BAD shapes must fire, at the first item's line.
for (const [label, body] of [
  ['connective shards', '- Training a contrastive embedder\n- Because this improves recall\n- Which matters downstream\n'],
  ['emphasis-wrapped connective', '- Training an embedder\n- **Because** this improves recall\n- **Which** matters\n'],
  ['leading and', '- A misconfigured load balancer rule\n- An outdated auth-v1 service\n- And insufficient alerting\n'],
  ['mixed per fragments', '- Free tier\n- 100 requests\n- Per minute\n- Per user\n'],
  ['repeated subject and copula', '- It is fast\n- It is accurate\n- It is easy to use\n'],
  ['numbered causal chain', '1. Because retrieval is hard\n2. Therefore we add reranking\n3. And this improves recall\n'],
]) {
  test(`RULE-A flags prose shredded into bullets: ${label}`, () => {
    assert.deepEqual(auditTextAt(`Heading:\n\n${body}`, 'RULE-A'), [[3, 1]]);
  });
}

test('RULE-A strong signal survives a long item', () => {
  const body =
    '- Training a contrastive embedder on a very large corpus of documents\n' +
    '- Because this improves recall\n' +
    '- Which matters downstream\n';
  assert.deepEqual(auditTextAt(`Heading:\n\n${body}`, 'RULE-A'), [[3, 1]]);
});

// ---------------------------------------------------------------------------
// List-container and block-boundary cases. Mirror of the Python block.
//
// These were verified in a local matrix before they were committed, which is
// exactly the gap this block closes: an uncommitted matrix cannot stop the next
// edit from regressing them.
// ---------------------------------------------------------------------------

// A marker and an opening word are not evidence about list structure.
for (const [label, body] of [
  ['nested children not flattened into parent', '- Rate limits:\n  - Per minute\n  - Per user\n'],
  ['only one item is not a Per fragment', '- Global\n- Per user\n- Per project\n'],
  ['bare one-word connective labels', '- And\n- But\n- Or\n'],
]) {
  test(`RULE-A leaves a genuine list container alone: ${label}`, () => {
    assert.deepEqual(auditText(`Heading:\n\n${body}`, 'RULE-A'), []);
  });
}

// Breaking out of the group at the first deeper line turned this three-item
// parent list into groups of one and two, so its connective shards stopped
// being visible at all.
test('RULE-A parent list survives a nested block', () => {
  const body =
    '- Training a contrastive embedder\n' +
    '  - Local negatives\n' +
    '  - Hard negatives\n' +
    '- Because this improves recall\n' +
    '- Which matters downstream\n';
  assert.deepEqual(auditTextAt(`Heading:\n\n${body}`, 'RULE-A'), [[3, 1]]);
});

// Raw character length calls one space and one tab the same depth.
test('RULE-A treats one tab as deeper than one space', () => {
  const body =
    ' - Parent item\n' +
    '\t- Because nested reason\n' +
    '\t- Which nested consequence\n';
  assert.deepEqual(auditText(`Heading:\n\n${body}`, 'RULE-A'), []);
});

// Both land on column 4, so these are siblings and the shards are visible.
// Raw character length calls them depths 4 and 1, losing the positive.
test('RULE-A treats four spaces and one tab as the same depth', () => {
  const body =
    '    - Training a contrastive embedder\n' +
    '\t- Because this improves recall\n' +
    '\t- Which matters downstream\n';
  assert.deepEqual(auditTextAt(`Heading:\n\n${body}`, 'RULE-A'), [[3, 1]]);
});

// The one-transition allowance is per block, not per blank-line run.
for (const [label, body, expected] of [
  ['heading separates two prose blocks', 'Additionally, first.\n## Section\nMoreover, second.\n', []],
  ['adjacent list items are separate blocks', '- Additionally, first.\n- Moreover, second.\n', []],
  ['blockquoted heading separates blocks', '> Additionally, first.\n> ## Section\n> Moreover, second.\n', []],
  ['blockquoted list items are separate blocks', '> - Additionally, first.\n> - Moreover, second.\n', []],
  [
    'two openers in one real paragraph still fire',
    'The first passed. Additionally, the second passed. Furthermore, the third passed.\n',
    [[1, 52]],
  ],
]) {
  test(`RULE-D uses Markdown block boundaries: ${label}`, () => {
    assert.deepEqual(auditTextAt(body, 'RULE-D'), expected);
  });
}

// Two 20-word sentences are two sentences however the second one opens. The
// splitter required a capital, quote, `(` or `[`; prose opens sentences with an
// inline code span or with emphasis constantly, and none of those characters was
// in the class, so each pair scored as one 40-word violation that was not there.
// The capital case is the control: it always passed.
const TWENTY_A =
  'Alpha beta gamma delta epsilon zeta eta theta iota kappa ' +
  'lambda mu nu xi omicron pi rho sigma tau upsilon.';
const TWENTY_TAIL =
  'two three four five six seven eight nine ten ' +
  'eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty.';
const TWENTY_CAPITAL = `One ${TWENTY_TAIL}`;
for (const [label, second, expected] of [
  ['capital opener', TWENTY_CAPITAL, []],
  ['inline-code opener', `\`code\` ${TWENTY_TAIL}`, []],
  ['emphasis opener', `*Emphasized* ${TWENTY_TAIL}`, []],
  ['underscore opener', `_Emphasized_ ${TWENTY_TAIL}`, []],
]) {
  test(`RULE-12 splits a sentence whatever markup opens it: ${label}`, () => {
    assert.deepEqual(auditTextAt(`${TWENTY_A} ${second}`, 'RULE-12'), expected);
  });
}

// Markup after the final punctuation must not hide the boundary either. A
// sentence ending `.**` puts the closing delimiter between the period and the
// whitespace, so a lookbehind anchored on the punctuation never saw it, and
// every bolded CHANGELOG entry read as one sentence through the next one. Each
// case puts the punctuation INSIDE the delimiter, which is the broken shape; a
// period after a closing delimiter always split, so that proves nothing.
const TWENTY_LEAD = TWENTY_A.split(' ').slice(0, -1).join(' ').replace(/\.$/, '');
for (const closer of ['**', '__', '*', '_', '`']) {
  test(`RULE-12 splits when markup closes the first sentence: ${closer}`, () => {
    const text = `${closer}Strong ${TWENTY_LEAD}.${closer} Then ${TWENTY_CAPITAL}`;
    assert.deepEqual(auditTextAt(text, 'RULE-12'), []);
  });
}

// The looser split must not stop the rule from firing on a real violation.
test('RULE-12 still flags a genuinely long sentence', () => {
  const text = `${Array(35).fill('word').join(' ')}.`;
  assert.deepEqual(
    auditText(text, 'RULE-12').map((v) => v.detail),
    ['sentence length 35 words (>30)'],
  );
});

// An abbreviation before a formatted value is not a sentence boundary. Every
// markup opener lives in the guarded branch; putting them in the unguarded one
// looks equivalent and silently suppresses real violations after `e.g.` and
// friends. The matrix is what proves it: a guard applied to only one delimiter
// looks correct until another is tried. `etc.` is deliberately unguarded and so
// is absent, because at a sentence end it is a real boundary.
for (const [abbreviation, lead] of [
  ['e.g.', 'The command supports several output formats, e.g.'],
  ['vs.', 'The evaluation compares our primary system vs.'],
  ['Fig.', 'The evaluation trend appears in Fig.'],
  ['cf.', 'The report compares the alternate protocol, cf.'],
]) {
  for (const value of ['`json`', '*json*', '_json_', '**json**']) {
    test(`RULE-12 does not split ${abbreviation} before ${value}`, () => {
      const text =
        `${lead} ${value}, when automated consumers need stable fields for ` +
        'parsing, validation, archival, comparison, monitoring, and downstream ' +
        'reporting across multiple independent services during every nightly ' +
        'scheduled production run.';
      const words = (text.match(/\b[\w'-]+\b/g) || []).length;
      assert.ok(words > 30, 'fixture must exceed the threshold to be meaningful');
      assert.deepEqual(
        auditText(text, 'RULE-12').map((v) => v.detail),
        [`sentence length ${words} words (>30)`],
      );
    });
  }
}

// ---------------------------------------------------------------------------
// RULE-03 intervals in prose and stacked figures. Mirror of
// packages/pypi/tests/test_rule03_figures.py. Every text here is synthetic:
// invented sentences about caches, networks, compilers, batteries and crop
// yields, with made-up numbers; nothing is copied or paraphrased from a real
// document, and the abstracts the thresholds were calibrated on are not
// committed. A cross-engine diff over 1,300 files in 4,144 file-path cases
// found no difference in line, detail, or excerpt, with two known exceptions:
// a column on a line holding an astral character differs, because this engine
// counts UTF-16 units, and Python's case-insensitive match also accepts a
// dotless i in the word interval, which this engine's does not.
// ---------------------------------------------------------------------------

const { run: runMech03, rule03 } = require('../lib/review/detectors_mech');

const R03_STACKED =
  'We study eviction policies for web caches. ' +
  'Raising the cache from 2\\% to 100\\% of memory changes the hit rate by 3.7 points, ' +
  'from 41.6 to 45.3 on the shared trace. ' +
  'Prefetching lowers the miss rate by 8.9 points at full load and by 5.2 points ' +
  'at idle load, against 73.4 for the baseline policy. ' +
  'A second layout gives 0.57 and 0.43 with a 6\\% floor. ' +
  'Operators should expect little change.';

const R03_SPARSE =
  'We study eviction policies for web caches. ' +
  'Prefetching lowers the miss rate by 8.9 points at full load. ' +
  'Changing the block size or the associativity moves them by under one point. ' +
  'Operators that raise either should expect little change. ' +
  'Production kernels already enable the prefetch path.';

const r03Intervals = (vs) => vs.filter((v) => v.detail.includes('numeric interval'));
const r03Stacks = (vs) => vs.filter((v) => v.detail.includes('consecutive sentences'));
const r03Crowds = (vs) => vs.filter((v) => v.detail.startsWith('one sentence'));

for (const sentence of [
  'Heating lowers cell capacity by $-0.052$ [$-0.083$, $-0.031$] at full charge.',
  'Doubling the buffer lowers stall time by 0.63 (95\\% interval 0.48 to 0.81).',
  'The gap is 0.36 with a 95% CI 0.6-0.9 over eighteen sensors.',
  'Crop yield was 4.81 [4.52, 5.07] on the held-out plots.',
  'The difference is -0.06 (95\\% CI: -0.12 to 0.03).',
  'Germination reached 71.3\\% (68.2 to 74.9) against 69.8\\%.',
  'The median is 4 (95% CI 3 to 5).',
  'The median is 4 (95% bootstrap interval 3 to 5).',
  'The median is 4 (95% percentile bootstrap interval 3 to 5).',
  'The 95% CI, 0.57 to 0.68, is narrow.',
  'The 95% CI 0.57 and 0.68 is narrow.',
  'The interval between 0.57 and 0.68 is wide.',
  'The interval 0.57 to 0.68 is wide.',
  'The interval: 0.57-0.68 is wide.',
]) {
  test(`RULE-03 flags an interval sentence: ${sentence.slice(0, 40)}`, () => {
    const found = rule03(sentence);
    assert.equal(r03Intervals(found).length, 1, JSON.stringify(found.map((v) => v.detail)));
    assert.ok(found.every((v) => v.rule === 'RULE-03'));
  });
}

for (const sentence of [
  'Raising the pool size from 1 to 100 changes nothing.',
  'As shown by prior work [1, 2], the effect is small.',
  'Citations [12-15] agree.',
  'The score lies in [0, 1] and is normalised.',
  'Scores are scaled to [0.0, 1.0] before averaging.',
  'We set the damping ratio in $[0.15, 0.65]$ for every run.',
  'The analytic bounds reach $[0.08, 0.62]$ at 40 cycles.',
  'Polling every interval of 1.5 to 4 seconds keeps the load low.',
  'The two compilers scored 58 (0.91 and 0.86) respectively.',
  'Intervals are 90\\% percentile intervals of 4,000 bootstrap resamples.',
  'The build used a 5 to 10 slot window.',
  // A percentage that merely precedes the word "interval" is a result, not a level.
  'Throughput drops by 15% over an interval of 2 to 4 hours.',
  'Error drops by 5% when the retry interval is 1 to 3 seconds.',
  'Memory falls by 30% across an interval of 100 to 200 steps.',
  'Throughput drops by 15% across an interval of 2 to 4 retries.',
  'Latency drops by 15% over an interval of 1.5 to 4.5 hours.',
  // A clause around a bare "interval" is not an interval estimate.
  'In the second interval, 0.57 and 0.68 are the two rates.',
  'In the second interval, 0.57 to 0.68 of the requests fail.',
  'During this interval, 12.4% and 15.8% of requests fail.',
  'During this interval 12.4% and 15.8% of requests fail.',
  // A word that is not a statistical modifier means the percentage is no level.
  'The gain is 4 (95% in each interval 3 to 5).',
  // With an interval keyword the duration filter holds even for an explicit level.
  'The wait is 3 hours (95% confidence interval 2 to 4 hours).',
]) {
  test(`RULE-03 leaves a non-interval bracket alone: ${sentence.slice(0, 40)}`, () => {
    assert.deepEqual(r03Intervals(rule03(sentence)), []);
  });
}

test('RULE-03 reports one finding per sentence that carries intervals', () => {
  const found = r03Intervals(rule03('Compression gives 0.31 [0.22, 0.46] and caching gives 0.06 [-0.03, 0.15].'));
  assert.equal(found.length, 1);
  assert.match(found[0].detail, /2 numeric intervals/);
});

test('RULE-03 still counts a percentage that precedes the word interval as a figure', () => {
  // 14.6% would be read as a confidence level, and dropped from the count, if a
  // few arbitrary words could stand between it and the keyword.
  const middle = 'Accuracy rose by 14.6% in the second interval and by 9.3% overall. ';
  const text = `${middle}Latency fell by 21.6% and 17.8%. Energy fell by 11.2% and 6.7%.`;
  assert.deepEqual(r03Intervals(rule03(text, 'abstract.md')), []);
  const found = r03Stacks(rule03(text, 'abstract.md'));
  assert.equal(found.length, 1, JSON.stringify(rule03(text, 'abstract.md').map((v) => v.detail)));
  assert.match(found[0].detail, /6 precise figures/);
  // A real level, with or without a modifier, is still metadata and not a figure.
  const level =
    'Yield rose by 3.2% (95% bootstrap interval 3 to 5). Latency fell by 21.6% and 17.8%. ' +
    'Energy fell by 11.2% and 6.7%.';
  assert.deepEqual(r03Stacks(rule03(level, 'abstract.md')), []);
});

for (const modifier of [
  'confidence', 'credible', 'prediction', 'tolerance', 'bootstrap', 'bootstrapped', 'percentile', 'central',
  'posterior', 'highest-density', 'equal-tailed', 'simultaneous', 'two-sided', 'one-sided', 'Wald', 'Wilson',
  'asymptotic', 'exact', 'coverage', 'BOOTSTRAP',
]) {
  test(`RULE-03 keeps a level explicit through the modifier ${modifier}`, () => {
    const sentence = `The median is 4 (95% ${modifier} interval 3 to 5).`;
    assert.equal(r03Intervals(rule03(sentence)).length, 1, sentence);
  });
}

test('RULE-03 skips tables and code', () => {
  const tabular =
    'The table lists the estimates.\n\\begin{tabular}{lcc}\nA & 0.62 & [0.51, 0.83]\\\\\n' +
    'B & 0.52 & 0.4 to 0.6\\\\\n\\end{tabular}\n';
  assert.deepEqual(rule03(tabular), []);
  const mdTable = '| Model | CI |\n| --- | --- |\n| A | [0.51, 0.83] |\n| B | (95% CI 0.4 to 0.6) |\n';
  assert.deepEqual(rule03(mdTable), []);
  const code = 'Run `score --ci [0.51, 0.83]` first.\n\n```\nresult: 0.62 [0.51, 0.83]\n```\n';
  assert.deepEqual(rule03(code, 'notes.md'), []);
});

test('RULE-03 flags a stacked abstract, and only a stack', () => {
  const found = rule03(R03_STACKED, '00-abstract.tex');
  assert.equal(r03Stacks(found).length, 1);
  assert.match(r03Stacks(found)[0].detail, /in the abstract/);
  assert.deepEqual(rule03(R03_SPARSE, '00-abstract.tex'), []);
});

test('RULE-03 thresholds: five figures crowd a sentence, four do not, two sentences are no run', () => {
  const crowded =
    'We compare battery chemistries. Capacity fades from 18.4\\% to 7.3\\% and resistance ' +
    'from 52.6\\% to 31.8\\% at 85.2\\% charge. Cells still swell at the edges.';
  assert.equal(r03Crowds(rule03(crowded, 'abstract.md')).length, 1);
  const four = 'Capacity fades from 18.4\\% to 7.3\\% at 85.2\\% charge against 90.1\\%.';
  assert.deepEqual(rule03(four, 'abstract.md'), []);
  const two =
    'Prefetching lowers misses by 8.9 points and 5.2 points. Tuning moves them by 0.6 and 0.8 points. ' +
    'Operators should expect little change.';
  assert.deepEqual(rule03(two, '00-abstract.tex'), []);
});

test('RULE-03 check B stays quiet outside an abstract or introduction', () => {
  const text = `\\section{Results}\n${R03_STACKED}\n\\section{Discussion}\nThe gap is 0.15, 0.26, 0.48, 0.59, 0.67, 0.82.\n`;
  assert.deepEqual(rule03(text, 'main.tex'), []);
  for (const name of ['04-results.tex', 'notes.md', '']) {
    assert.deepEqual(rule03(R03_STACKED, name), [], name);
  }
});

test('RULE-03 ignores versions, dates, counts, references, identifiers and code', () => {
  const text =
    'Release v0.5.0 (2026-10-16) ships 38 tests and 2,417 fixtures. ' +
    'It follows 0.4.2 and 0.4.1, and runs on Python 3.9-3.13 with Node 20.11.1. ' +
    'The matrix is ubuntu x 3.9/3.10/3.11/3.12/3.13 and macos x 3.12/3.13. ' +
    'See Section 3.2, Tables 4 and 5, Figure 2.1, Appendix B.3, and Eq. 7.1. ' +
    'Evaluated on Claude Opus 4.5, Gemini 2.5 Pro, GPT-4.1 and Llama-3.3-70B with Qwen2.5-72B. ' +
    'The job started at 12:30:45.123 and cites arXiv:2310.12345 and doi 10.1145/3331184.3331185. ' +
    'Logs live at https://example.org/v1.2/run-0.5 and docs/v1.2/guide-0.5.md. ' +
    'The rule refs are \\cref{sec:3.2} and \\citep{smith2020.5}, with `0.62` in code. ' +
    '```\nscore = 0.62\nscore = 0.52\nscore = 0.63\n```\n';
  for (const name of ['CHANGELOG.md', '00-abstract.md', 'intro.md', 'notes.md']) {
    assert.deepEqual(rule03(text, name), [], name);
  }
});

test('RULE-03 finds the abstract and introduction by file name', () => {
  for (const name of ['00-abstract.tex', 'ABSTRACT.md', 'paper-Abstract-draft.txt', '01-introduction.tex',
    'INTRO.md', 'intro-draft.rst', '/tmp/x/sections/01-Introduction.tex']) {
    assert.equal(r03Stacks(rule03(R03_STACKED, name)).length, 1, name);
  }
  for (const name of ['', 'results.tex', 'main.tex', 'notes.md', 'README.md']) {
    assert.deepEqual(rule03(R03_STACKED, name), [], name);
  }
  assert.match(r03Stacks(rule03(R03_STACKED, '01-introduction.tex'))[0].detail, /in the introduction/);
});

test('RULE-03 finds the abstract and introduction by markup', () => {
  const env =
    `\\documentclass{article}\n\\begin{document}\n\\begin{abstract}\n${R03_STACKED}\n\\end{abstract}\n` +
    '\\section{Method}\nWe run it.\n\\end{document}\n';
  const found = r03Stacks(rule03(env, 'main.tex'));
  assert.equal(found.length, 1);
  assert.equal(found[0].line, 4);

  assert.equal(
    r03Stacks(rule03(`\\section{Introduction}\n${R03_STACKED}\n\\section{Method}\nWe run it.\n`, 'main.tex')).length,
    1
  );
  assert.deepEqual(
    rule03(`\\section{Introduction}\nWe study caches.\n\\section{Method}\n${R03_STACKED}\n`, 'main.tex'),
    []
  );
  assert.deepEqual(rule03(`% \\section{Introduction}\n${R03_STACKED}\n`, 'main.tex'), []);

  const md = `# Paper\n\n## Abstract\n\n${R03_STACKED}\n\n### Detail\n\nMore text.\n\n## Method\n\nWe run it.\n`;
  const mdFound = r03Stacks(rule03(md, 'paper.md'));
  assert.equal(mdFound.length, 1);
  assert.equal(mdFound[0].line, 5);
  assert.deepEqual(rule03(`## Abstract\n\nWe study caches.\n\n## Method\n\n${R03_STACKED}\n`, 'paper.md'), []);
  assert.equal(r03Stacks(rule03(`## 1. Introduction\n\n${R03_STACKED}\n`, 'paper.md')).length, 1);
  assert.deepEqual(rule03(`\`\`\`\n## Abstract\n\`\`\`\n\n${R03_STACKED}\n`, 'paper.md'), []);
});

// Masks and exemptions: tables with or without outer pipes, CommonMark fences,
// indented code in Markdown, sentences that end inside emphasis, appendix prose.
// IV is a prose sentence with one interval; each test asks which line it lands
// on, so the line tells where a mask ended.
const R03_IV = 'Gain is 0.62 [0.51, 0.83] here.';
const R03_TABLE_NO_PIPES =
  'Metric | Gain | CI\n--- | --- | ---\nLatency | 0.62 | 95% CI 0.51 to 0.83\n';
const r03Lines = (text, name = 'notes.md') => r03Intervals(rule03(text, name)).map((v) => v.line);

test('RULE-03 skips a Markdown table without outer pipes', () => {
  for (const name of ['', 'notes.md', 'results.txt']) {
    assert.deepEqual(rule03(R03_TABLE_NO_PIPES, name), [], name);
    assert.deepEqual(rule03(`${R03_TABLE_NO_PIPES}Energy | 0.12 | [0.04, 0.2]\n`, name), [], name);
    const aligned = 'Metric | Gain | CI\n:--- | :---: | ---:\nLatency | 0.62 | 95% CI 0.51 to 0.83\n';
    assert.deepEqual(rule03(aligned, name), [], name);
  }
  assert.deepEqual(rule03('| a | b |\n|---|---|\nx | 0.62 [0.51, 0.83]\n'), []);
  assert.deepEqual(rule03('a | b |\n--|--\nx | 0.62 [0.51, 0.83]\n'), []);
});

test('RULE-03 ends a table at a blank line or a line without a pipe', () => {
  assert.deepEqual(r03Lines(`${R03_TABLE_NO_PIPES}\n${R03_IV}\n`), [5]);
  assert.deepEqual(r03Lines(`${R03_TABLE_NO_PIPES}${R03_IV}\n`), [4]);
});

test('RULE-03 does not take pipes alone for a table', () => {
  for (const text of [
    'Metric | Gain | CI\nLatency | 0.62 | 95% CI 0.51 to 0.83\n', // no delimiter row
    'Metric | Gain | CI\n--- | ---\nLatency | 0.62 | 95% CI 0.51 to 0.83\n', // cell counts differ
    'Metric | Gain | CI\n---\nLatency | 0.62 | 95% CI 0.51 to 0.83\n', // a rule has no pipe
    'Metric | Gain | CI\n--- | x | ---\nLatency | 0.62 | 95% CI 0.51 to 0.83\n', // not a delimiter cell
  ]) {
    assert.equal(r03Intervals(rule03(text, 'notes.md')).length, 1, text);
  }
});

test('RULE-03 does not count a table without outer pipes in an abstract', () => {
  const text =
    '## Abstract\n\nWe study caches.\n\n' +
    'a | b | c\n- | - | -\n0.62 | 0.52 | 0.63\n0.46 | 0.85 | 0.96\n\n' +
    'Operators should expect little change.\n';
  assert.deepEqual(rule03(text, 'paper.md'), []);
});

test('RULE-03 fences follow CommonMark: character, length, no info string on the closer', () => {
  assert.deepEqual(
    r03Lines(`\`\`\`\`\n\`\`\`\nresult: 0.62 [0.51, 0.83]\n\`\`\`\nalso 0.5 [0.4, 0.6]\n\`\`\`\`\n\n${R03_IV}\n`),
    [8]
  );
  assert.deepEqual(
    r03Lines(`~~~\n\`\`\`\nx 0.62 [0.51, 0.83]\n\`\`\`\nmore 0.5 [0.4, 0.6]\n~~~\n\n${R03_IV}\n`),
    [8]
  );
  assert.deepEqual(r03Lines(`~~~\nx 0.62 [0.51, 0.83]\n~~~~\n\n${R03_IV}\n`), [5]);
  assert.deepEqual(r03Lines(`\`\`\`\nresult: 0.62 [0.51, 0.83]\n\`\`\`\`\`\n\n${R03_IV}\n`), [5]);
  assert.deepEqual(
    r03Lines(`\`\`\`\nx\n\`\`\`python\nresult: 0.62 [0.51, 0.83]\n\`\`\`\n\n${R03_IV}\n`),
    [7]
  );
  // A shorter run does not close, so the fence runs to the end of the text.
  assert.deepEqual(rule03('````\nresult: 0.62 [0.51, 0.83]\n```\nmore 0.5 [0.4, 0.6]\n', 'notes.md'), []);
  // A backtick run with a backtick in its info string is an inline code span.
  assert.deepEqual(r03Lines('```inline``` and 0.62 [0.51, 0.83] here.\n\nMore prose.\n'), [1]);
});

test('RULE-03 masks indented code in Markdown input only', () => {
  const spaced = 'Intro text.\n\n    result: 0.62 [0.51, 0.83]\n    other: 0.5 [0.4, 0.6]\n\nProse follows.\n';
  const tabbed = 'Intro text.\n\n\tresult: 0.62 [0.51, 0.83]\n\nProse follows.\n';
  for (const name of ['notes.md', 'README.markdown', 'DOC.MD', '']) {
    assert.deepEqual(rule03(spaced, name), [], name);
    assert.deepEqual(rule03(tabbed, name), [], name);
    assert.deepEqual(r03Lines(`${spaced}\n${R03_IV}\n`, name), [8], name);
  }
  for (const name of ['notes.txt', 'main.tex', 'results.rst', 'README']) {
    assert.deepEqual(r03Lines('Intro text.\n\n    result: 0.62 [0.51, 0.83]\n\nProse follows.\n', name), [3], name);
  }
  assert.deepEqual(r03Lines(`\\section{Results}\n\n    ${R03_IV}\n`, ''), [3]);
  assert.deepEqual(r03Lines(`\\begin{document}\n\n    ${R03_IV}\n`, ''), [3]);
});

test('RULE-03 keeps list continuations and paragraph continuations as prose', () => {
  for (const text of [
    `- Item one.\n\n    ${R03_IV}\n`,
    `1. Step one.\n\n    ${R03_IV}\n`,
    `- Item\ncontinues here.\n\n    ${R03_IV}\n`,
    `* Outer\n  - Inner\n\n      ${R03_IV}\n`, // nested item, two columns past its content
    'Gain is\n    0.62 [0.51, 0.83] here.\n',
  ]) {
    assert.equal(r03Intervals(rule03(text, 'notes.md')).length, 1, text);
  }
  assert.deepEqual(rule03('- Item.\n\nPlain paragraph.\n\n    result: 0.62 [0.51, 0.83]\n', 'notes.md'), []);
  assert.deepEqual(rule03('- Item.\n## Next\n\n    result: 0.62 [0.51, 0.83]\n', 'notes.md'), []);
});

// CommonMark 0.31.2: an indented code block may begin the document or follow a
// heading, an item's code is indented four columns past its content column, and a
// fence is indented at most three spaces.
const R03_CODE = 'result: 0.62 [0.51, 0.83]';

test('RULE-03 masks indented code at the start of the document', () => {
  for (const name of ['notes.md', 'README.markdown', '']) {
    assert.deepEqual(rule03(`    ${R03_CODE}\n`, name), [], name);
    assert.deepEqual(rule03(`\t${R03_CODE}\n`, name), [], name);
    assert.deepEqual(r03Lines(`    ${R03_CODE}\n\n${R03_IV}\n`, name), [3], name);
    // A paragraph that starts the document keeps its indented continuation as prose.
    assert.deepEqual(r03Lines('Gain is\n    0.62 [0.51, 0.83] here.\n', name), [2], name);
  }
  assert.deepEqual(r03Lines(`    ${R03_IV}\n`, 'notes.txt'), [1]);
  assert.deepEqual(r03Lines(`    ${R03_IV}\n`, 'main.tex'), [1]);
});

test('RULE-03 masks indented code right after a heading', () => {
  for (const gap of ['', '\n']) {
    assert.deepEqual(rule03(`## Results\n${gap}    ${R03_CODE}\n`, 'notes.md'), [], JSON.stringify(gap));
    assert.deepEqual(rule03(`# Results\n${gap}\t${R03_CODE}\n`, 'notes.md'), [], JSON.stringify(gap));
    assert.deepEqual(
      r03Lines(`## Results\n${gap}    ${R03_CODE}\n\n${R03_IV}\n`),
      [4 + gap.length],
      JSON.stringify(gap)
    );
  }
  // A paragraph between the heading and the indented line makes it a continuation.
  assert.deepEqual(r03Lines('## Results\nGain is\n    0.62 [0.51, 0.83] here.\n'), [3]);
});

test('RULE-03 masks indented code beneath a list item', () => {
  for (const text of [
    `- Example:\n\n      ${R03_CODE}\n`, // content column 2, indent 6
    `- Example:\n\n\t\t${R03_CODE}\n`, // tabs: columns 8
    `* Example:\n\n      ${R03_CODE}\n`,
    `+ Example:\n\n      ${R03_CODE}\n`,
    `1. Step one:\n\n       ${R03_CODE}\n`, // content column 3, indent 7
    `10. Step ten:\n\n        ${R03_CODE}\n`, // content column 4, indent 8
    `-   Wide marker gap.\n\n        ${R03_CODE}\n`, // content column 4, indent 8
    `* Outer\n  - Inner\n\n        ${R03_CODE}\n`, // inner content column 4, indent 8
    `- Item.\n\n      ${R03_CODE}\n      other 0.5 [0.4, 0.6]\n`,
    `- Item\ncontinues here.\n\n      ${R03_CODE}\n`, // lazy continuation keeps the item open
  ]) {
    assert.deepEqual(rule03(text, 'notes.md'), [], text);
    const lineCount = text.split('\n').length - 1;
    assert.deepEqual(r03Lines(`${text}\n${R03_IV}\n`), [lineCount + 2], text);
  }
});

test('RULE-03 keeps a list continuation paragraph below the code threshold as prose', () => {
  for (const text of [
    `- Example:\n\n  ${R03_IV}\n`, // at the content column
    `- Example:\n\n     ${R03_IV}\n`, // one column short of code
    `1. Step one:\n\n      ${R03_IV}\n`, // content column 3, indent 6
    `10. Step ten:\n\n       ${R03_IV}\n`, // content column 4, indent 7
    `* Outer\n  - Inner\n\n      ${R03_IV}\n`, // inner content column 4, indent 6
  ]) {
    assert.equal(r03Intervals(rule03(text, 'notes.md')).length, 1, text);
  }
});

test('RULE-03 closes a list item at a line indented less than its content column', () => {
  // One space is less than the content column of two, so the item is closed and
  // the line after the blank is a paragraph of the document, then code follows it.
  assert.deepEqual(rule03(`- Item.\n\n Para.\n\n    ${R03_CODE}\n`, 'notes.md'), []);
  // Indented to the content column, the paragraph stays in the item and four
  // further columns are code, while two are prose.
  assert.deepEqual(rule03(`- Item.\n\n  Para.\n\n      ${R03_CODE}\n`, 'notes.md'), []);
  assert.equal(r03Intervals(rule03(`- Item.\n\n  Para.\n\n    ${R03_IV}\n`, 'notes.md')).length, 1);
});

test('RULE-03 measures the code threshold from the innermost open list item', () => {
  // Under the outer item (content column 2) six spaces are code; under the inner
  // item (content column 4) the same six spaces are a continuation paragraph.
  assert.deepEqual(r03Lines(`* Outer\n\n      ${R03_CODE}\n\n  * Inner\n\n      ${R03_IV}\n`), [7]);
});

test('RULE-03 scans deep nesting with many lazy lines in linear time', () => {
  let nest = '';
  for (let i = 0; i < 400; i++) nest += `${' '.repeat(2 * i)}- item\n`;
  const start = Date.now();
  rule03(nest + 'lazy\n'.repeat(60000), 'notes.md');
  assert.ok(Date.now() - start < 3000);
});

test('RULE-03 does not close a fence on a line indented four spaces', () => {
  const text = `\`\`\`\n    \`\`\`\n${R03_CODE}\n\`\`\`\n\n${R03_IV}\n`;
  // Line 2 is code inside the block, so line 3 stays masked and line 6 is read.
  assert.deepEqual(r03Lines(text), [6]);
  assert.deepEqual(r03Lines(text, 'notes.txt'), [6]);
  assert.deepEqual(r03Lines(`~~~\n    ~~~\n${R03_CODE}\n~~~\n\n${R03_IV}\n`), [6]);
});

test('RULE-03 lets a fence be indented up to three spaces', () => {
  for (const indent of ['', ' ', '  ', '   ']) {
    assert.deepEqual(r03Lines(`${indent}\`\`\`\n${R03_CODE}\n${indent}\`\`\`\n\n${R03_IV}\n`), [5], indent);
  }
  // Three spaces still close a block that opened flush left.
  assert.deepEqual(r03Lines(`\`\`\`\n${R03_CODE}\n   \`\`\`\n\n${R03_IV}\n`), [5]);
});

test('RULE-03 does not open a fence on a line indented four spaces', () => {
  // After a blank line it is an indented code block; the block is masked either way.
  assert.deepEqual(rule03(`Intro.\n\n    \`\`\`\n    ${R03_CODE}\n    \`\`\`\n`, 'notes.md'), []);
  assert.deepEqual(r03Lines(`Intro.\n\n    \`\`\`\n    ${R03_CODE}\n    \`\`\`\n\n${R03_IV}\n`), [7]);
  // Directly after a paragraph the line is text, not a fence: nothing is masked.
  assert.deepEqual(r03Lines(`Intro.\n    \`\`\`\n${R03_IV}\n`), [3]);
  assert.deepEqual(r03Lines(`    \`\`\`\n${R03_IV}\n`, 'notes.txt'), [2]);
});

test('RULE-03 counts fence indentation inside a list item from its content column', () => {
  assert.deepEqual(r03Lines(`- Item.\n\n  \`\`\`\n  ${R03_CODE}\n  \`\`\`\n\n${R03_IV}\n`), [7]);
  // A closer six columns in is four past the content column: still code.
  const deeper = `- Item.\n\n  \`\`\`\n  ${R03_CODE}\n      \`\`\`\n  more 0.5 [0.4, 0.6]\n  \`\`\`\n\n${R03_IV}\n`;
  assert.deepEqual(r03Lines(deeper), [9]);
});

test('RULE-03 ends a fence inside a list item with the item', () => {
  assert.deepEqual(r03Lines(`- Item.\n\n  \`\`\`\n  ${R03_CODE}\n\n${R03_IV}\n`), [6]);
  // At the top level an unclosed fence still runs to the end of the text.
  assert.deepEqual(rule03(`\`\`\`\n${R03_CODE}\n\n${R03_IV}\n`, 'notes.md'), []);
});

test('RULE-03 opens no list for an item that cannot interrupt a paragraph', () => {
  // `10.` after a paragraph line is text, so four spaces after a blank line are
  // top-level code; `1.` and a bullet do open an item, and the same four spaces
  // are then a continuation paragraph.
  assert.deepEqual(rule03(`Notes.\n10. Step ten.\n\n    ${R03_CODE}\n`, 'notes.md'), []);
  assert.equal(r03Intervals(rule03(`Notes.\n1. Step one.\n\n    ${R03_IV}\n`, 'notes.md')).length, 1);
  assert.equal(r03Intervals(rule03(`Notes.\n- Step.\n\n    ${R03_IV}\n`, 'notes.md')).length, 1);
  // A text-less marker is not an item either.
  assert.deepEqual(rule03(`Notes.\n-\n\n    ${R03_CODE}\n`, 'notes.md'), []);
  // A sibling of an open list may carry any number.
  assert.equal(r03Intervals(rule03(`1. One.\n10. Ten.\n\n    ${R03_IV}\n`, 'notes.md')).length, 1);
  assert.deepEqual(rule03(`1. One.\n10. Ten.\n\n        ${R03_CODE}\n`, 'notes.md'), []);
});

test('RULE-03 masks a list item whose first content is indented code', () => {
  assert.deepEqual(rule03(`-     ${R03_CODE}\n`, 'notes.md'), []);
  // The next flush-left line follows code, not a paragraph, so it ends the item.
  assert.deepEqual(r03Lines(`-     ${R03_CODE}\n${R03_IV}\n`), [2]);
  assert.deepEqual(r03Lines(`-     ${R03_CODE}\n\n      more 0.5 [0.4, 0.6]\n\n${R03_IV}\n`), [5]);
});

// A fence may start on the line of a list item marker or after a blockquote marker.
// The fence lines are masked; the prose of the list or the quote stays visible.
const R03_CONTAINER_FENCES = [
  // [opening line, prefix of the lines inside the container, closing fence]
  ['- ```text', '  ', '```'],
  ['* ```', '  ', '```'],
  ['+ ~~~', '  ', '~~~'],
  ['1. ```', '   ', '```'], // content column 3
  ['10) ```', '    ', '```'], // content column 4
  ['-   ```', '    ', '```'], // content column 4
  ['> ```', '> ', '```'],
  ['> ```text', '> ', '```'],
  ['>```', '>', '```'],
  ['> > ```', '> > ', '```'],
  ['>> ```', '>> ', '```'],
  ['   > ```', '   > ', '```'], // a quote may be indented three spaces
  ['- - ```', '    ', '```'], // nested items
  ['- > ```', '  > ', '```'], // a quote inside an item
  ['> - ```', '>   ', '```'], // an item inside a quote
  ['1. > ```', '   > ', '```'],
];

test('RULE-03 masks a fence on a list item or blockquote line', () => {
  const listed = '- ```text\n  result: 0.62 [0.51, 0.83]\n  ```\n\n  Gain is 0.62 [0.51, 0.83] here.\n';
  assert.deepEqual(r03Lines(listed), [5]);
  const quoted = '> ```text\n> result: 0.62 [0.51, 0.83]\n> ```\n\nGain is 0.62 [0.51, 0.83] here.\n';
  assert.deepEqual(r03Lines(quoted), [5]);
});

test('RULE-03 masks each container fence and reads the prose after it', () => {
  for (const [first, prefix, closer] of R03_CONTAINER_FENCES) {
    const body = [first, prefix + R03_CODE, prefix + closer];
    assert.deepEqual(rule03(`${body.join('\n')}\n`, 'notes.md'), [], first);
    // Prose in the same container right after the fence, and flush left after a blank line.
    assert.deepEqual(r03Lines(`${[...body, prefix + R03_IV].join('\n')}\n`), [4], first);
    assert.deepEqual(r03Lines(`${[...body, '', R03_IV].join('\n')}\n`), [5], first);
  }
});

test('RULE-03 keeps container prose visible around a fence', () => {
  assert.deepEqual(r03Lines(`- ${R03_IV}\n- \`\`\`\n  ${R03_CODE}\n  \`\`\`\n- ${R03_IV}\n`), [1, 5]);
  assert.deepEqual(r03Lines(`> ${R03_IV}\n> \`\`\`\n> ${R03_CODE}\n> \`\`\`\n> ${R03_IV}\n`), [1, 5]);
  assert.deepEqual(r03Lines(`1. ${R03_IV}\n2. \`\`\`\n   ${R03_CODE}\n   \`\`\`\n3. ${R03_IV}\n`), [1, 5]);
});

test('RULE-03 ends a fence in a blockquote at a line without a marker', () => {
  // The blank line ends the quote, so the prose after it is read.
  assert.deepEqual(r03Lines(`> \`\`\`\n> ${R03_CODE}\n\n${R03_IV}\n`), [4]);
  // A flush-left line ends it too, with no blank line between.
  assert.deepEqual(r03Lines(`> \`\`\`\n> ${R03_CODE}\n${R03_IV}\n`), [3]);
  // A nested quote ends when one marker is missing.
  assert.deepEqual(r03Lines(`> > \`\`\`\n> > ${R03_CODE}\n> ${R03_IV}\n`), [3]);
});

test('RULE-03 ends a fence on a list item line with the item', () => {
  assert.deepEqual(r03Lines(`- \`\`\`\n  ${R03_CODE}\n\n${R03_IV}\n`), [4]);
  assert.deepEqual(r03Lines(`- \`\`\`\n  ${R03_CODE}\n${R03_IV}\n`), [3]);
  // A blank line alone does not end the item, so the fence goes on.
  assert.deepEqual(rule03(`- \`\`\`\n  ${R03_CODE}\n\n  more 0.5 [0.4, 0.6]\n`, 'notes.md'), []);
  // A quote inside the item ends the fence when its marker is missing.
  assert.deepEqual(r03Lines(`- > \`\`\`\n  > ${R03_CODE}\n  ${R03_IV}\n`), [3]);
});

test('RULE-03 closes a container fence only at its content position', () => {
  // Four columns past the content column is code, not a closing fence.
  const listed = `- \`\`\`\n  ${R03_CODE}\n      \`\`\`\n  more 0.5 [0.4, 0.6]\n  \`\`\`\n\n  ${R03_IV}\n`;
  assert.deepEqual(r03Lines(listed), [7]);
  const quoted = `> \`\`\`\n> ${R03_CODE}\n>     \`\`\`\n> more 0.5 [0.4, 0.6]\n> \`\`\`\n\n${R03_IV}\n`;
  assert.deepEqual(r03Lines(quoted), [7]);
  // Up to three columns past it still closes.
  assert.deepEqual(r03Lines(`> \`\`\`\n> ${R03_CODE}\n>    \`\`\`\n\n${R03_IV}\n`), [5]);
  assert.deepEqual(r03Lines(`- \`\`\`\n  ${R03_CODE}\n     \`\`\`\n\n  ${R03_IV}\n`), [5]);
  // A longer fence holds a shorter one, and a tilde fence is not closed by backticks.
  assert.deepEqual(r03Lines(`> \`\`\`\`\n> \`\`\`\n> ${R03_CODE}\n> \`\`\`\`\n\n${R03_IV}\n`), [6]);
  assert.deepEqual(r03Lines(`- ~~~\n  \`\`\`\n  ${R03_CODE}\n  ~~~\n\n  ${R03_IV}\n`), [6]);
});

test('RULE-03 ends a list item at a blockquote line it is not indented into', () => {
  assert.deepEqual(r03Lines(`- Item.\n> \`\`\`\n> ${R03_CODE}\n> \`\`\`\n\n${R03_IV}\n`), [6]);
  // Indented to the content column, the quote belongs to the item and stays inside it.
  assert.deepEqual(r03Lines(`- Item.\n  > \`\`\`\n  > ${R03_CODE}\n  > \`\`\`\n  ${R03_IV}\n`), [5]);
});

test('RULE-03 masks nothing for a marker line that opens no fence', () => {
  for (const text of [
    '- ```inline``` and 0.62 [0.51, 0.83] here.\n', // a backtick in the info string
    '> ```inline``` and 0.62 [0.51, 0.83] here.\n',
    `-\`\`\`\n${R03_IV}\n`, // no space after the marker: not an item
    `- Text\n  \`\`\`inline\`\`\` ${R03_IV}\n`,
    `- ${R03_IV}\n`, // a marker line with no fence
    `> ${R03_IV}\n`,
  ]) {
    assert.equal(r03Intervals(rule03(text, 'notes.md')).length, 1, text);
  }
});

test('RULE-03 recognizes a container fence in Markdown input only', () => {
  // Outside Markdown a marker line is text, as everywhere else in this mask.
  assert.deepEqual(r03Lines(`- \`\`\`\n  ${R03_IV}\n`, 'notes.txt'), [2]);
});

// A setext underline or a thematic break ends the paragraph, so an indented line
// after it is code, as it is after a heading (CommonMark example 115).
test('RULE-03 ends a paragraph at a setext underline', () => {
  for (const underline of ['-------', '=======', '---', '===', '-', '=', '   -----', '---   ', '-- ']) {
    assert.deepEqual(rule03(`Example\n${underline}\n    ${R03_CODE}\n`, 'notes.md'), [], underline);
    assert.deepEqual(r03Lines(`Example\n${underline}\n    ${R03_CODE}\n\n${R03_IV}\n`), [5], underline);
  }
  assert.deepEqual(r03Lines(`Example\n-------\n    ${R03_CODE}\n\n${R03_IV}\n`, ''), [5]);
  // Below a longer paragraph.
  assert.deepEqual(r03Lines(`Gain rose\nacross trials\n---\n    ${R03_CODE}\n\n${R03_IV}\n`), [6]);
});

test('RULE-03 ends a paragraph at a thematic break', () => {
  for (const rule of ['---', '***', '___', '* * *', '- - -', '_ _ _', '----------', ' ---', '   ***', '-  -  -', '--- ---']) {
    assert.deepEqual(r03Lines(`Before.\n\n${rule}\n    ${R03_CODE}\n\n${R03_IV}\n`), [6], rule);
    assert.deepEqual(r03Lines(`Before.\n${rule}\n    ${R03_CODE}\n\n${R03_IV}\n`), [5], rule);
  }
  // `- - -` is a break, not an item, so the line below sits four columns past the document.
  assert.deepEqual(r03Lines(`- - -\n    ${R03_CODE}\n\n${R03_IV}\n`), [4]);
  assert.deepEqual(r03Lines(`* * *\n    ${R03_CODE}\n\n${R03_IV}\n`), [4]);
});

test('RULE-03 leaves the paragraph open for a line that is no underline or break', () => {
  for (const text of [
    `Example\n    -------\n    ${R03_IV}\n`, // four spaces: continuation, not an underline
    `Example\n----- x\n    ${R03_IV}\n`, // text after the dashes
    `Example\n== ==\n    ${R03_IV}\n`, // a space inside an '=' underline
    `Example\n--x\n    ${R03_IV}\n`,
    'Gain is\n    0.62 [0.51, 0.83] here.\n', // plain paragraph continuation
    'Gain is\n  0.62 [0.51, 0.83] here.\n',
    `- Item\n===\n    ${R03_IV}\n`, // '===' is a lazy continuation of the item
  ]) {
    assert.equal(r03Intervals(rule03(text, 'notes.md')).length, 1, text);
  }
});

test('RULE-03 ends a list item at a break it is not indented into', () => {
  assert.deepEqual(r03Lines(`- Item\n---\n    ${R03_CODE}\n\n${R03_IV}\n`), [5]);
  // Indented to the content column, an underline stays inside the item and ends its paragraph.
  assert.deepEqual(r03Lines(`- Item\n  ---\n      ${R03_CODE}\n\n  ${R03_IV}\n`), [5]);
});

test('RULE-03 does not underline a blockquote or HTML paragraph', () => {
  // A paragraph that holds a quote or an HTML line is not underlined by '-'.
  assert.deepEqual(r03Lines(`<!-- note -->\n-\n    ${R03_IV}\n`), [3]);
  assert.deepEqual(r03Lines(`> Quote.\n-\n    ${R03_IV}\n`), [3]);
  // A thematic break ends a quote's paragraph, as it ends the quote.
  assert.deepEqual(r03Lines(`> Quote.\n---\n    ${R03_CODE}\n\n${R03_IV}\n`), [5]);
});

const R03_BOLD_THREE =
  '**Soil moisture rises by 11.3% and 13.8%.** **Yield rises by 22.3% and 26.5%.** **Cost falls by 2.5%.**';

test('RULE-03 splits sentences that end inside emphasis', () => {
  // 2 + 2 + 1 figures: no run of three, and no single crowded sentence.
  assert.deepEqual(rule03(R03_BOLD_THREE, 'abstract.md'), []);
  const found = rule03(R03_BOLD_THREE.replace('falls by 2.5%', 'falls by 2.5% and 3.5%'), 'abstract.md');
  assert.equal(r03Stacks(found).length, 1, JSON.stringify(found.map((v) => v.detail)));
  assert.deepEqual(r03Crowds(found), []);
  assert.match(r03Stacks(found)[0].detail, /3 consecutive sentences/);
  for (const wrap of ['**{}**', '__{}__', '*{}*', '_{}_', '(**{}**)', '**{}**)', '\u201c**{}**\u201d']) {
    const text = [
      'Soil moisture rises by 11.3% and 13.8%.',
      'Yield rises by 22.3% and 26.5%.',
      'Cost falls by 2.5%.',
    ].map((s) => wrap.replace('{}', s)).join(' ');
    assert.deepEqual(rule03(text, 'abstract.md'), [], wrap);
  }
});

test('RULE-03 scans a run of closers in linear time', () => {
  for (const text of ['*'.repeat(200000), `a.${'*'.repeat(100000)}b`, '._'.repeat(100000), 'x.**'.repeat(50000)]) {
    const start = Date.now();
    rule03(text, 'abstract.md');
    assert.ok(Date.now() - start < 3000);
  }
});

test('RULE-03 skips check A in a file named for an appendix or a supplement', () => {
  for (const name of ['appendix.tex', '02-Appendix.tex', 'A_appendices.md', 'supplement.md',
    'Supplementary-Materials.tex', 'paper supp results.tex', 'supp.tex', '/tmp/x/sections/appendix_b.tex',
    'C:\\x\\appendix.md', 'results.appendix.tex']) {
    assert.deepEqual(r03Intervals(rule03(R03_IV, name)), [], name);
  }
  for (const name of ['support.md', 'supportive-notes.md', 'results.tex', 'notes.md', '']) {
    assert.equal(r03Intervals(rule03(R03_IV, name)).length, 1, name);
  }
});

test('RULE-03 keeps check B in an appendix-named file', () => {
  assert.equal(r03Stacks(rule03(R03_STACKED, 'abstract-appendix.tex')).length, 1);
  const found = rule03(`${R03_STACKED} ${R03_IV}`, 'supp-abstract.md');
  assert.deepEqual(r03Intervals(found), []);
  assert.equal(r03Stacks(found).length, 1);
  assert.deepEqual(rule03(`\\appendix\n\\section{Details}\n${R03_STACKED}\n`, 'main.tex'), []);
});

test('RULE-03 skips check A after \\appendix and inside the appendices environment', () => {
  assert.deepEqual(
    r03Lines(`\\section{Results}\n${R03_IV}\n\\appendix\n\\section{Details}\n${R03_IV}\n`, 'main.tex'),
    [2]
  );
  assert.deepEqual(
    r03Lines(`${R03_IV}\n\\begin{appendices}\n${R03_IV}\n\\end{appendices}\n${R03_IV}\n`, 'main.tex'),
    [1, 5]
  );
  assert.deepEqual(r03Lines(`${R03_IV}\n\\begin{appendices}\n${R03_IV}\n`, 'main.tex'), [1]);
  assert.deepEqual(r03Lines(`% \\appendix\n${R03_IV}\n`, 'main.tex'), [2]);
  assert.deepEqual(r03Lines(`\\appendixname\n${R03_IV}\n`, 'main.tex'), [2]);
  assert.deepEqual(r03Lines(`\\verb|\\appendix| ${R03_IV}\n`, 'main.tex'), [1]);
});

test('RULE-03 skips check A under a Markdown heading that begins with Appendix', () => {
  const text =
    `# Paper\n\n## Results\n\n${R03_IV}\n\n` +
    `## Appendix A: Details\n\n${R03_IV}\n\n### Sub-detail\n\n${R03_IV}\n\n` +
    `## Appendix B\n\n${R03_IV}\n\n` +
    `## Discussion\n\n${R03_IV}\n`;
  assert.deepEqual(r03Lines(text, 'paper.md'), [5, 21]);
  assert.deepEqual(r03Lines(text.replace(/\n/g, '\r\n'), 'paper.md'), [5, 21]);
  const nested = `# Paper\n\n## Method\n\n### Appendix note\n\n${R03_IV}\n\n### Other\n\n${R03_IV}\n`;
  assert.deepEqual(r03Lines(nested, 'paper.md'), [11]);
  assert.deepEqual(r03Lines(`## Appendix\n\n${R03_IV}\n\n#### Deep\n\n${R03_IV}\n`, 'paper.md'), []);
  // The heading rule and the command rule each stay inside their own format.
  assert.deepEqual(r03Lines(`## See the appendix\n\n${R03_IV}\n`, 'paper.md'), [3]);
  assert.deepEqual(r03Lines(`Type \\appendix to start. ${R03_IV}\n`, 'notes.md'), [1]);
  assert.deepEqual(r03Lines(`# Appendix\n\n${R03_IV}\n`, 'main.tex'), [3]);
});

test('RULE-03 interval message keeps the claim and names the display', () => {
  const one = r03Intervals(rule03(R03_IV))[0].detail;
  assert.equal(
    one,
    'a numeric interval in prose; keep what the reader needs to judge the claim, ' +
      'in words where possible, and give the interval in a table or figure'
  );
  const two = r03Intervals(rule03('Compression gives 0.31 [0.22, 0.46] and caching gives 0.06 [-0.03, 0.15].'))[0].detail;
  assert.ok(two.startsWith('2 numeric intervals in prose; keep what the reader needs'));
  assert.ok(!one.includes('state the effect here'));
});

test('RULE-03 locates findings under comments and CRLF', () => {
  const text = '% a comment line\r\n% another 0.1 [0.0, 0.2]\r\n\r\nGain is 0.62 [0.51, 0.83] here.\r\n';
  const found = r03Intervals(rule03(text, 'x.tex'));
  assert.equal(found.length, 1);
  assert.equal(found[0].line, 4);
});

test('RULE-03 is dispatched with the file path', () => {
  const rule = { id: 'RULE-03', severity: 'high' };
  const quiet = runMech03(rule, R03_STACKED, 'results.tex');
  assert.equal(quiet.status, 'ok');
  const loud = runMech03(rule, R03_STACKED, '00-abstract.tex');
  assert.equal(loud.status, 'violation');
  assert.equal(loud.count, 1);
  assert.equal(loud.detector, 'mechanical');
});

test('RULE-03 never throws and stays fast on hostile input', () => {
  const odd = [
    '', ' ', '\n', '\r', '\u0000\u0001\u0002 0.5 [0.1, 0.2]\u0000',
    '{{{{ \\begin{abstract} 0.5, 0.6, 0.65, 0.8, 0.9, 1.1 }}}} ((((',
    '\\begin{abstract}\n0.1 0.2 0.3 0.4 0.5 0.6.', '\\begin{tabular}{ll} 0.1 & 0.2 \\\\',
    '\\begin{figure} 0.1 [0.0, 0.2]', '$$ 0.5 [0.1, 0.2] ', '\\[ 0.5 ',
    '\\cite{ \\cite{ \\ref{ [0.1, 0.2] (0.3 to 0.4)', '[[[[[[[[ 0.1, 0.2 ]]]]]]]] ((((( 0.1 - 0.2 )))))',
    '```\n0.5 [0.1, 0.2]', '<!-- 0.5 [0.1, 0.2]', '## \n#\n######## Abstract\n## Introduction',
    '\u2212\u2212 0.5\u2212 [\u22120.1, \u22120.2] 5\u00a0% \u00a7 3.2',
    '9'.repeat(5000), '.'.repeat(5000), '0.'.repeat(5000), '1,234,'.repeat(2000),
    '95% CI '.repeat(500), 'interval 0.5 to '.repeat(500),
    'a | b\n--- | ---\n0.5 [0.1, 0.2]\n', 'a | b\r\n--- | ---\r\n0.5\r\n', '|\n|-\n||\n| |\n-|-',
    '````\n```\n~~~\n`````\n', '    0.5 [0.1, 0.2]\n\n\t0.6 [0.2, 0.3]\n- a\n\n    0.85 [0.3, 0.4]',
    '- ```\n  0.5 [0.1, 0.2]', '> ```\n> 0.5 [0.1, 0.2]\n\n0.6', '> > - > ```\n> > - > 0.5\n>\n>>\n- - - ```\n',
    '-\t```\n\t0.5\n>\t```\n>\t0.5\n> \t\t```\n',
    'Foo\n---\n    0.5 [0.1, 0.2]\n===\n-\n= =\n***\n_ _ _\n- - -\n',
    '1. ```\n2. ```\n10) ~~~\n123456789. ```\n1234567890. ```\n',
    '\\appendix \\begin{appendices} 0.5 [0.1, 0.2]', '## Appendix\n#### Appendix\n# Results\n####### Appendix',
    '**0.5.** __0.6.__ *0.85.* _0.8._ `0.9.`',
  ];
  for (const text of odd) {
    for (const name of ['', '00-abstract.tex', 'main.tex', 'notes.md']) {
      assert.ok(Array.isArray(rule03(text, name)));
    }
  }
  assert.deepEqual(rule03(null), []);
  for (const text of [
    '0'.repeat(200000), '!'.repeat(200000), '\\begin{figure} 0.5 '.repeat(10000), 'a/'.repeat(100000),
    '|\n'.repeat(100000), 'a | b\n- | -\n'.repeat(50000), '|'.repeat(200000), `${'-|'.repeat(100000)}\n`,
    '## Appendix\n'.repeat(100000), '    x\n\n'.repeat(50000), '- a\n\n    b\n'.repeat(50000),
    '````\n```\n'.repeat(50000), '```x`\n'.repeat(50000), '\\appendix '.repeat(20000),
    '> ```\n> x\n'.repeat(50000), '- ```\n  x\n'.repeat(50000), `${'> '.repeat(150000)}\`\`\`\n${'x\n'.repeat(100000)}`,
    `${'- '.repeat(100000)}\`\`\`\n${'  x\n'.repeat(100000)}`, `${'> '.repeat(1000)}\`\`\`\n${`${'> '.repeat(1000)}x\n`.repeat(100)}`,
    `${'>'.repeat(200000)}\n${'> x\n'.repeat(50000)}`, 'Foo\n---\n'.repeat(50000), '***\n    x\n'.repeat(50000),
    '- - -\n'.repeat(100000), `${'- > '.repeat(50000)}\`\`\`\n${'  > x\n'.repeat(50000)}`,
  ]) {
    for (const name of ['00-abstract.tex', 'notes.md']) {
      const start = Date.now();
      rule03(text, name);
      assert.ok(Date.now() - start < 3000, name);
    }
  }
});
