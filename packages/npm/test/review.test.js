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
  // Only Markdown, plain text and unnamed non-LaTeX text: a LaTeX file reads its
  // body prose too since 0.7.0 (the 0.7.0 tests further down).
  const text = `## Results\n\n${R03_STACKED}\n\n## Discussion\n\nThe gap is 0.15, 0.26, 0.48, 0.59, 0.67, 0.82.\n`;
  assert.deepEqual(rule03(text, 'paper.md'), []);
  for (const name of ['notes.md', 'notes.txt', '']) {
    assert.deepEqual(rule03(R03_STACKED, name), [], name);
  }
});

test('RULE-03 ignores versions, dates, counts, references, identifiers and code', () => {
  const text =
    'Release v0.7.0 (2026-10-16) ships 38 tests and 2,417 fixtures. ' +
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
  for (const name of ['', 'notes.md', 'README.md', 'results.txt', 'results.rst']) {
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
  // The stack after the introduction is body prose, reported as such.
  const after = rule03(`\\section{Introduction}\nWe study caches.\n\\section{Results}\n${R03_STACKED}\n`, 'main.tex');
  assert.equal(r03Stacks(after).length, 1);
  assert.match(r03Stacks(after)[0].detail, /in the body text/);
  assert.equal(r03Stacks(after)[0].line, 4);
  assert.deepEqual(after.filter((v) => v.detail.includes('introduction')), []);
  const commented = rule03(`% \\section{Introduction}\n${R03_STACKED}\n`, 'main.tex');
  assert.equal(r03Stacks(commented).length, 1);
  assert.match(r03Stacks(commented)[0].detail, /in the body text/);
  assert.deepEqual(commented.filter((v) => v.detail.includes('introduction')), []);

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
    'C:\\x\\appendix.md', 'results.appendix.tex', 'app-prereg.tex', 'app_results.tex', 'appx.tex', 'apx-b.tex']) {
    assert.deepEqual(r03Intervals(rule03(R03_IV, name)), [], name);
  }
  for (const name of ['support.md', 'supportive-notes.md', 'results.tex', 'notes.md', '',
    'application.tex', 'apps.tex', 'mapping.tex']) {
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
  const quiet = runMech03(rule, R03_STACKED, 'results.md');
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

// ---------------------------------------------------------------------------
// 0.7.0: RULE-03 on LaTeX (body-prose stacks, captions, excess precision) and the
// hook-only RULE-A table-cell detector. Mirror of
// packages/pypi/tests/test_rule03_displays.py and test_rule_a_tables.py.
// Every text here is synthetic: invented sentences about caches, networks,
// batteries and crop yields, with made-up numbers. The corpora the limits were
// measured on are not committed.
//
// Cross-engine check, run by the maintainer and not committed: every input the
// Python suite passes to these scans, 9,000 random LaTeX documents with their
// Edit-sized fragments, and the three measurement corpora went through both
// engines. Findings agree in rule, line, detail, column and excerpt, with two
// exceptions that predate 0.7.0 and sit in checks A and B: a column on a line
// holding an astral character differs (this engine counts UTF-16 units), and
// U+001C-U+001F, U+0085, U+FEFF and non-ASCII digits are read differently by the
// pre-existing sentence splitter and figure patterns. Check C counts its figures
// with those same patterns, so a caption written with non-ASCII digits is read
// differently too; check D and RULE-A agree on those inputs.
// ---------------------------------------------------------------------------

const { rule03Scan, ruleA, ruleAScan, r03Tuning, r03Significant } = require('../lib/review/detectors_mech');

const bodyRuns = (vs) => vs.filter((v) => v.detail.includes('consecutive sentences in the body text'));
const bodyCrowds = (vs) => vs.filter((v) => v.detail.startsWith('one sentence in the body text'));
const frontHits = (vs) => vs.filter((v) => v.detail.includes('in the abstract') || v.detail.includes('in the introduction'));
const captionHits = (vs) => vs.filter((v) => v.detail.startsWith('a caption'));
const precisionHits = (vs) => vs.filter((v) => v.detail.includes('decimal places'));
const lineList = (vs) => vs.map((v) => v.line);

// Set fields of r03Tuning the way a Python test monkeypatches the _R03_* constants.
function withTuning(overrides, fn) {
  const saved = Object.assign({}, r03Tuning);
  Object.assign(r03Tuning, overrides);
  try {
    fn();
  } finally {
    Object.assign(r03Tuning, saved);
  }
}

// Three consecutive sentences with 5, 3 and 3 precise figures: a stack.
const D03_STACK =
  'Raising the cache from 2\\% to 100\\% of memory changes the hit rate by 3.7 points, ' +
  'from 41.6 to 45.3 on the shared trace. ' +
  'Prefetching lowers the miss rate by 8.9 points at full load and by 5.2 points ' +
  'at idle load, against 73.4 for the baseline policy. ' +
  'A second layout gives 0.57 and 0.43 with a 6\\% floor.';

// One sentence with six figures, and two with one each.
const D03_CROWD =
  'The gap is 0.15, 0.26, 0.48, 0.59, 0.67, and 0.82 across the six sensors. ' +
  'Operators should expect little change. Nothing else moved.';

// ---------- check B in body prose ----------

for (const name of ['main.tex', '04-results.tex', 'sections/related-work.tex', 'C:\\x\\paper.tex', 'x.TEX']) {
  test(`RULE-03 flags a stack in LaTeX body prose: ${name}`, () => {
    const text = `\\section{Results}\n${D03_STACK}\n`;
    const found = bodyRuns(rule03(text, name));
    assert.equal(found.length, 1, JSON.stringify(rule03(text, name).map((v) => v.detail)));
    assert.equal(found[0].line, 2);
    assert.equal(found[0].column, 1);
    assert.match(found[0].detail, /3 consecutive sentences in the body text carry 11 precise figures/);
  });
}

test('RULE-03 flags a stack in unnamed text with LaTeX markup', () => {
  const text = `\\section{Results}\n${D03_STACK}\n`;
  assert.equal(bodyRuns(rule03(text, '')).length, 1);
  assert.equal(bodyRuns(rule03(text)).length, 1);
});

for (const name of ['notes.md', 'README.markdown', 'results.txt', 'results.rst', 'NOTES.MD']) {
  test(`RULE-03 does not read other formats as body prose: ${name}`, () => {
    assert.deepEqual(rule03(`\\section{Results}\n${D03_STACK}\n`, name), [], name);
    assert.deepEqual(rule03(`## Results\n\n${D03_STACK}\n`, name), [], name);
  });
}

test('RULE-03 does not read unnamed text without LaTeX markup as body prose', () => {
  assert.deepEqual(rule03(D03_STACK), []);
  assert.deepEqual(rule03(D03_STACK, ''), []);
});

test('RULE-03 body: a sparse body, two stacked sentences, and a run that is not adjacent stay quiet', () => {
  const sparse =
    '\\section{Results}\nPrefetching lowers the miss rate by 8.9 points at full load. ' +
    'Changing the block size or the associativity moves them by under one point. ' +
    'Operators that raise either should expect little change. ' +
    'Production kernels already enable the prefetch path.\n';
  assert.deepEqual(rule03(sparse, 'main.tex'), []);
  const two =
    '\\section{Results}\nPrefetching lowers misses by 8.9 points and 5.2 points. ' +
    'Tuning moves them by 0.6 and 0.8 points. Operators should expect little change.\n';
  assert.deepEqual(rule03(two, 'main.tex'), []);
  const apart =
    '\\section{Results}\nPrefetching lowers misses by 8.9 points and 5.2 points. ' +
    'Tuning moves them by 0.6 and 0.8 points. Operators should expect little change. ' +
    'The block size moves them by 0.3 and 0.2 points. A second layout agrees at 0.5 and 0.4 points.\n';
  assert.deepEqual(rule03(apart, 'main.tex'), []);
});

test('RULE-03 body: a crowded sentence is not flagged, and stays an abstract and introduction criterion', () => {
  assert.deepEqual(rule03(`\\section{Results}\n${D03_CROWD}\n`, 'main.tex'), []);
  assert.equal(r03Tuning.bodyCrowded, null);
  const abstract = `\\begin{abstract}\n${D03_CROWD}\n\\end{abstract}\n`;
  assert.equal(frontHits(rule03(abstract, 'main.tex')).length, 1);
  const found = rule03(`\\section{Introduction}\n${D03_CROWD}\n`, 'main.tex');
  assert.equal(frontHits(found).length, 1);
  assert.deepEqual(bodyCrowds(found), []);
});

test('RULE-03 body: the crowded limit applies when it is set', () => {
  withTuning({ bodyCrowded: 5 }, () => {
    const found = bodyCrowds(rule03(`\\section{Results}\n${D03_CROWD}\n`, 'main.tex'));
    assert.equal(found.length, 1);
    assert.match(found[0].detail, /6 precise figures/);
    assert.ok(found[0].detail.startsWith('one sentence in the body text carries'));
  });
  assert.deepEqual(rule03(`\\section{Results}\n${D03_CROWD}\n`, 'main.tex'), []);
});

test('RULE-03 keeps the abstract and introduction messages and names the body case apart', () => {
  const abstract = `\\begin{abstract}\n${D03_STACK}\n\\end{abstract}\n`;
  const one = frontHits(rule03(abstract, 'main.tex'))[0].detail;
  assert.equal(
    one,
    '3 consecutive sentences in the abstract carry 11 precise figures; ' +
      'keep the few magnitudes behind the main findings and move the rest to a table'
  );
  const two = frontHits(rule03(`\\section{Introduction}\n${D03_STACK}\n`, 'main.tex'))[0].detail;
  assert.ok(two.startsWith('3 consecutive sentences in the introduction carry 11 precise figures'));
  assert.ok(!one.includes('body') && !two.includes('body'));
  const body = bodyRuns(rule03(`\\section{Results}\n${D03_STACK}`, 'main.tex'))[0].detail;
  assert.ok(!body.includes('abstract') && !body.includes('introduction'));
  assert.ok(body.endsWith('move the rest to a table or an appendix'));
  assert.equal(
    body,
    '3 consecutive sentences in the body text carry 11 precise figures. ' +
      'Keep the few magnitudes behind the main findings, round them, and move the rest to a table or an appendix'
  );
});

test('RULE-03 reports an abstract stack once and not also as a body finding', () => {
  const text = `\\begin{abstract}\n${D03_STACK}\n\\end{abstract}\n\\section{Method}\nWe run it.\n`;
  const found = rule03(text, 'main.tex');
  assert.equal(frontHits(found).length, 1);
  assert.deepEqual(bodyRuns(found), []);
  for (const name of ['00-abstract.tex', '01-introduction.tex']) {
    const named = rule03(D03_STACK, name);
    assert.equal(frontHits(named).length, 1, name);
    assert.deepEqual(bodyRuns(named), [], name);
  }
});

test('RULE-03 reads a stack before and after an introduction as body prose', () => {
  const text =
    `\\section{Related Work}\n${D03_STACK}\n\\section{Introduction}\nWe study caches.\n\\section{Results}\n${D03_STACK}\n`;
  assert.deepEqual(lineList(bodyRuns(rule03(text, 'main.tex'))), [2, 6]);
});

test('RULE-03 reads a body stack in an Edit-sized fragment', () => {
  assert.equal(bodyRuns(rule03(D03_STACK, 'main.tex')).length, 1);
  assert.equal(bodyRuns(rule03(`\\emph{Sizes.} ${D03_STACK}`, '')).length, 1);
  assert.deepEqual(bodyRuns(rule03(D03_STACK, 'main.md')), []);
});

for (const env of [
  'table', 'figure', 'tabular', 'tabulary', 'tblr', 'equation', 'align', 'verbatim', 'lstlisting',
  'algorithm', 'comment',
]) {
  test(`RULE-03 skips a stack inside ${env}`, () => {
    const text = `\\section{Results}\n\\begin{${env}}\n${D03_STACK}\n\\end{${env}}\n`;
    assert.deepEqual(rule03(text, 'main.tex'), [], env);
  });
}

test('RULE-03 skips a stack in a comment', () => {
  const commented = D03_STACK.split('. ').map((line) => `% ${line}\n`).join('');
  assert.deepEqual(rule03(`\\section{Results}\n${commented}`, 'main.tex'), []);
});

test('RULE-03 reads the stack around a display between sentences', () => {
  const text =
    '\\section{Results}\nRaising the cache from 2\\% to 100\\% changes the hit rate by 3.7 points and 4.1 points. ' +
    'Prefetching lowers misses by 8.9 points and 5.2 points.\n' +
    '\\begin{equation}\nx = 0.51 + 0.62 + 0.73\n\\end{equation}\n' +
    'A second layout gives 0.57 and 0.43 at idle load.\n';
  assert.equal(bodyRuns(rule03(text, 'main.tex')).length, 1);
});

for (const name of ['appendix.tex', '02-Appendix.tex', 'supp.tex', 'supplement.tex', 'supplementary-results.tex', 'A_appendices.tex']) {
  test(`RULE-03 skips body prose in the appendix-named file ${name}`, () => {
    assert.deepEqual(rule03(`\\section{Details}\n${D03_STACK}\n`, name), [], name);
  });
}

test('RULE-03 skips body prose after \\appendix and inside the appendices environment', () => {
  const after = `\\section{Results}\n${D03_STACK}\n\\appendix\n\\section{Details}\n${D03_STACK}\n`;
  assert.deepEqual(lineList(bodyRuns(rule03(after, 'main.tex'))), [2]);
  assert.deepEqual(rule03(`\\appendix\n${D03_STACK}\n`, 'main.tex'), []);
  const env =
    `\\section{Results}\n${D03_STACK}\n\\begin{appendices}\n${D03_STACK}\n\\end{appendices}\n` +
    `\\section{Discussion}\n${D03_STACK}\n`;
  assert.deepEqual(lineList(bodyRuns(rule03(env, 'main.tex'))), [2, 7]);
  const unclosed = `\\section{Results}\n${D03_STACK}\n\\begin{appendices}\n${D03_STACK}\n`;
  assert.deepEqual(lineList(bodyRuns(rule03(unclosed, 'main.tex'))), [2]);
});

test('RULE-03 does not read the preamble or the text after the document as body prose', () => {
  const preamble = `\\documentclass{article}\n${D03_STACK}\n\\begin{document}\nWe study caches.\n\\end{document}\n`;
  assert.deepEqual(rule03(preamble, 'main.tex'), []);
  const after = `\\begin{document}\n\\section{Results}\nWe study caches.\n\\end{document}\n${D03_STACK}\n`;
  assert.deepEqual(rule03(after, 'main.tex'), []);
  const inside = `\\begin{document}\n\\section{Results}\n${D03_STACK}\n\\end{document}\n`;
  assert.deepEqual(lineList(bodyRuns(rule03(inside, 'main.tex'))), [3]);
});

test('RULE-03 body stack does not hide an interval beside it', () => {
  const text = `\\section{Results}\nGain is 0.62 [0.51, 0.83] here. ${D03_STACK}\n`;
  const found = rule03(text, 'main.tex');
  assert.equal(r03Intervals(found).length, 1);
  assert.equal(bodyRuns(found).length, 1);
});

test('RULE-03 orders body findings by position with the other checks', () => {
  const text =
    `\\section{Results}\nGain is 0.62 [0.51, 0.83] here.\n\n${D03_STACK}\n\n` +
    '\\begin{figure}\n\\caption{Hit rate was 41.6, 45.3 and 47.1 on three traces.}\n\\end{figure}\n';
  const found = rule03(text, 'main.tex');
  assert.equal(found.length, 3);
  assert.deepEqual(lineList(found), lineList(found).slice().sort((x, y) => x - y));
});

// ---------- check C: captions ----------

const fig = (caption) => `\\begin{figure}\n\\centering\n\\includegraphics{a.pdf}\n${caption}\n\\end{figure}\n`;
const THREE = 'Hit rate was 41.6, 45.3 and 47.1 on three traces.';
const numberedWords = (n, stem = 'word') =>
  Array.from({ length: n }, (_, i) => stem + String.fromCharCode(97 + (i % 26))).join(' ');

for (const caption of [
  `\\caption{${THREE}}`,
  `\\caption[Hit rate]{${THREE}}`,
  `\\caption*{${THREE}}`,
  `\\captionof{figure}{${THREE}}`,
  `\\captionof*{table}{${THREE}}`,
  `\\caption {${THREE}}`,
  `\\caption\n{${THREE}}`,
  `\\caption{\\textbf{Hit rate.} ${THREE} \\label{fig:hit}}`,
  '\\caption{Hit rate was 41.6\\%, 45.3\\% and 47\\% on three traces.}',
  '\\caption{Hit rate was $0.416$, $0.453$ and $0.471$ on three traces.}',
]) {
  test(`RULE-03 flags a caption with three precise figures: ${caption.slice(0, 36).replace(/\n/g, ' ')}`, () => {
    const found = captionHits(rule03(fig(caption), 'main.tex'));
    assert.equal(found.length, 1, JSON.stringify(rule03(fig(caption), 'main.tex').map((v) => v.detail)));
    if (caption.startsWith('\\caption')) assert.equal(found[0].line, 4);
    else assert.ok(found[0].line >= 4);
    assert.ok(found[0].detail.includes('precise figures'));
  });
}

for (const caption of [
  '\\caption{Hit rate was 41.6 and 45.3 on two traces.}',
  '\\caption{Hit rate on 3 traces of 1200 requests and 45 clients.}',
  '\\caption{Hit rate by trace.}',
  '\\caption{Hit rate was 41.6 and 45.3 on Trace~2 (Section 3.2, Table 4, Figure 5.1).}',
  '\\caption{Hit rate on the traces of \\citet{lee2020.123}, run at 0.9\\textwidth.}',
  '\\caption{Hit rate was 41.6 and 45.3 (95\\% CI).}',
  '\\caption{Hit rate was 41.6 and 45.3, with 95\\% bootstrap intervals.}',
  '\\caption{Hit rate was 41.6 and 45.3 (CI 95\\%).}',
  '\\caption{Hit rate was 41.6 and 45.3 on v0.7.0 of the tool, run 2026-10-16.}',
]) {
  test(`RULE-03 leaves a caption below the limits quiet: ${caption.slice(0, 40)}`, () => {
    assert.deepEqual(captionHits(rule03(fig(caption), 'main.tex')), [], caption);
  });
}

test('RULE-03 treats a confidence level as metadata and not a figure in a caption', () => {
  assert.deepEqual(
    captionHits(rule03(fig('\\caption{Gain was 4.1 and 5.2 with a 95\\% confidence interval.}'), 'main.tex')),
    []
  );
  const flagged = fig('\\caption{Gain was 4.1, 5.2 and 6.3 with a 95\\% confidence interval.}');
  assert.equal(captionHits(rule03(flagged, 'main.tex')).length, 1);
});

test('RULE-03 flags a caption over one hundred words', () => {
  assert.deepEqual(captionHits(rule03(fig(`\\caption{${numberedWords(100)}}`), 'main.tex')), []);
  const found = captionHits(rule03(fig(`\\caption{${numberedWords(101)}}`), 'main.tex'));
  assert.equal(found.length, 1);
  assert.match(found[0].detail, /101 words/);
});

test('RULE-03 skips citations, references, math and numbers when it counts caption words', () => {
  const base = numberedWords(100, 'token');
  const padding = ' \\citep{a,b} \\ref{fig:x} $x_i + y_j$ 12 3 45 \\label{fig:y} 6.5 ';
  assert.deepEqual(captionHits(rule03(fig(`\\caption{${base}${padding}}`), 'main.tex')), []);
  // A command is dropped and the text in its argument is kept.
  const bold = `\\textbf{${numberedWords(101, 'token')}}`;
  assert.equal(captionHits(rule03(fig(`\\caption{${bold}}`), 'main.tex')).length, 1);
});

test('RULE-03 reports a caption once even when it breaks both limits', () => {
  const caption = `\\caption{${THREE} ${numberedWords(120)}}`;
  assert.equal(captionHits(rule03(fig(caption), 'main.tex')).length, 1);
});

test('RULE-03 checks each caption on its own line', () => {
  const text =
    `${fig(`\\caption{${THREE}}`)}\nText between the figures.\n\n` +
    `${fig('\\caption{A short caption.}')}${fig(`\\caption{${THREE}}`)}`;
  assert.deepEqual(lineList(captionHits(rule03(text, 'main.tex'))), [4, 17]);
});

test('RULE-03 reports a multi-line caption at the command line', () => {
  const caption = '\\caption{Hit rate\nwas 41.6,\n45.3 and 47.1\non three traces.}';
  const found = captionHits(rule03(fig(caption), 'main.tex'));
  assert.equal(found.length, 1);
  assert.equal(found[0].line, 4);
  assert.equal(found[0].column, 1);
});

test('RULE-03 checks a caption fragment alone', () => {
  assert.equal(captionHits(rule03(`\\caption{${THREE}}\n`, 'main.tex')).length, 1);
  assert.equal(captionHits(rule03(`\\emph{Hit rate.} \\caption{${THREE}}\n`, '')).length, 1);
  // A bare caption with no file name has no LaTeX marker the detector knows.
  assert.deepEqual(captionHits(rule03(`\\caption{${THREE}}\n`, '')), []);
});

test('RULE-03 reads a caption inside and outside an abstract or introduction', () => {
  const text = `\\section{Introduction}\n${fig(`\\caption{${THREE}}`)}`;
  assert.equal(captionHits(rule03(text, 'main.tex')).length, 1);
  assert.equal(captionHits(rule03(fig(`\\caption{${THREE}}`), '04-results.tex')).length, 1);
});

test('RULE-03 skips a caption in an appendix or a supplement', () => {
  const caption = fig(`\\caption{${THREE}}`);
  for (const name of ['appendix.tex', 'supp.tex', 'supplement-figures.tex', '02-Appendices.tex']) {
    assert.deepEqual(captionHits(rule03(caption, name)), [], name);
  }
  const after = `\\section{Results}\n${caption}\\appendix\n\\section{Details}\n${caption}`;
  assert.deepEqual(lineList(captionHits(rule03(after, 'main.tex'))), [5]);
  const environment = `${caption}\\begin{appendices}\n${caption}\\end{appendices}\n`;
  assert.deepEqual(lineList(captionHits(rule03(environment, 'main.tex'))), [4]);
});

test('RULE-03 does not read a caption in a Markdown or plain text file', () => {
  const text = fig(`\\caption{${THREE}}`);
  for (const name of ['notes.md', 'notes.markdown', 'notes.txt', 'notes.rst']) {
    assert.deepEqual(rule03(text, name), [], name);
  }
  assert.deepEqual(rule03(`Caption: ${THREE}`, ''), []);
});

for (const text of [
  `% \\caption{${THREE}}\n`,
  `\\begin{verbatim}\n\\caption{${THREE}}\n\\end{verbatim}\n`,
  `\\begin{lstlisting}\n\\caption{${THREE}}\n\\end{lstlisting}\n`,
  `\\begin{comment}\n\\caption{${THREE}}\n\\end{comment}\n`,
  `\\verb|\\caption{${THREE}}|\n`,
  '\\captionsetup{font=small, skip=0.5em, width=0.95\\textwidth, labelsep=0.1em}\n',
  `\\caption{${THREE}\n`,
  '\\caption\n\n',
  `\\caption[${THREE}\n`,
  `\\captionof{figure}[${THREE}]\n`,
  `\\caption}${THREE}{\n`,
  `\\mycaption{${THREE}}\n`,
]) {
  test(`RULE-03 does not read text that is no caption: ${text.slice(0, 34).replace(/\n/g, ' ')}`, () => {
    assert.deepEqual(captionHits(rule03(`\\begin{document}\n${text}`, 'main.tex')), [], text);
  });
}

test('RULE-03 does not let a caption feed checks A and B', () => {
  const stacked = `\\captionof{table}{${D03_STACK}}\n`;
  const found = rule03(`\\section{Results}\n${stacked}`, 'main.tex');
  assert.deepEqual(bodyRuns(found), []);
  assert.deepEqual(frontHits(found), []);
  const interval = '\\section{Results}\n\\captionof{figure}{Gain is 0.4 (95\\% CI 0.2 to 0.6) at idle load.}\n';
  assert.deepEqual(r03Intervals(rule03(interval, 'main.tex')), []);
  const inside = fig('\\caption{Gain is 0.4 [0.2, 0.6] at idle load.}');
  assert.deepEqual(r03Intervals(rule03(`\\section{Results}\n${inside}`, 'main.tex')), []);
  const abstract = `\\begin{abstract}\n\\captionof{table}{${D03_STACK}}\n\\end{abstract}\n`;
  assert.deepEqual(frontHits(rule03(abstract, 'main.tex')), []);
});

test('RULE-03 still reaches the caption check in a file of figures only', () => {
  const text = `\\begin{figure}\n\\caption{${THREE}}\n\\end{figure}\n`;
  assert.equal(captionHits(rule03(text, 'figs.tex')).length, 1);
});

test('RULE-03 caption message names the pattern and where the rest goes', () => {
  const figures = captionHits(rule03(fig(`\\caption{${THREE}}`), 'main.tex'))[0].detail;
  assert.equal(
    figures,
    'a caption carries 3 precise figures. A caption names the display, its pattern, and ' +
      'what the marks mean. Keep decoding values such as error-bar definitions; move ' +
      'repeated results, setup narration, and caveats to the text or an appendix'
  );
  const long = captionHits(rule03(fig(`\\caption{${Array(101).fill('word').join(' ')}}`), 'main.tex'))[0].detail;
  assert.ok(long.startsWith('a caption runs 101 words. A caption names the display, its pattern'));
});

test('RULE-03 caption limits follow the tuning', () => {
  const four = fig('\\caption{Hit rate was 41.6, 45.3, 47.1 and 48.2 on four traces.}');
  const three = fig(`\\caption{${THREE}}`);
  withTuning({ captionFigures: 4 }, () => {
    assert.deepEqual(captionHits(rule03(three, 'main.tex')), []);
    assert.equal(captionHits(rule03(four, 'main.tex')).length, 1);
  });
  withTuning({ captionWords: 50 }, () => {
    assert.equal(captionHits(rule03(fig(`\\caption{${numberedWords(60)}}`), 'main.tex')).length, 1);
  });
});

// Legend and decoding metadata. The numbers that name a line, a threshold or a symbol
// are keys to the display, so the figure count skips them; a result written beside
// them still counts. Mirror of the Python tests.

const LEGENDS = [
  '\\caption{Coverage by model. Lines mark the 25\\%, 50\\% and 75\\% quantiles.}',
  '\\caption{Coverage by model. Significance thresholds are 0.05, 0.01 and 0.001.}',
  '\\caption{Coverage by model. Stars mark significance at 0.05, 0.01, and 0.001.}',
  '\\caption{Stars: * $p<0.05$, ** $p<0.01$, *** $p<0.001$.}',
  '\\caption{Stars: * p < 0.05, ** p < 0.01, *** p < 0.001.}',
  '\\caption{Dashed lines at 0.25, 0.50 and 0.75.}',
  '\\caption{Shaded bands span the 5th and 95th percentiles; quantiles 0.05, 0.50 and 0.95.}',
  '\\caption{Curves for quantile levels 0.1, 0.5 and 0.9.}',
  '\\caption{Significant at $\\alpha = 0.05$, 0.01 and 0.001.}',
  '\\caption{Cells shaded at 0.05, 0.01 and 0.001 significance levels.}',
  '\\caption{Dotted line: random baseline at 0.5; dashed lines at 0.25 and 0.75.}',
  '\\caption{Markers denote the 0.1, 0.5 and 0.9 settings.}',
  '\\caption{Bands show the 10--90\\% and 25--75\\% percentile ranges, with p-values below 0.05 and 0.01.}',
  '\\caption{Solid, dashed, and dotted lines correspond to dropout rates of 0.1, 0.2, and 0.5, respectively.}',
  '\\caption{Shaded bands show the $68\\%$, $95\\%$, and $99.7\\%$ confidence intervals.}',
  '\\caption{Shaded bands (plain) show the 68\\%, 95\\%, and 99.7\\% confidence intervals.}',
  '\\caption{Ellipses give confidence levels of 68\\%, 95\\%, and 99.7\\%.}',
  '\\caption{Stars mark p-value thresholds of 0.05, 0.01, and 0.001.}',
  '\\caption{Stars: $p \\le 0.05$, 0.01, and 0.001.}',
  // A level list beside one result: every level is a key, so one figure remains.
  '\\caption{Mean latency is 12.4 ms. Shaded bands show the 68\\%, 95\\%, and 99.7\\% confidence intervals.}',
  '\\caption{Mean latency is 12.4 ms; bands give the 50\\%, 90\\%, and 95\\% CIs.}',
  '\\caption{Accuracy reaches 0.84. Shaded bands show the 68\\%, 95\\%, and 99.7\\% confidence intervals.}',
  '\\caption{Accuracy reaches 0.84 and 0.86. Bands show the 68\\%, 95\\%, and 99.7\\% confidence intervals.}',
  '\\caption{Shaded bands show the 50\\%, 68\\%, 95\\%, and 99.7\\% confidence intervals.}',
  // Wrapped and indented in the source, as captions often are.
  '\\caption{Shaded bands show the 50\\%,\n    68\\%,\n    95\\%,\n    99.7\\% confidence intervals.}',
  '\\caption{Accuracy reaches 0.84 and 0.86.\n    Shaded bands show the 68\\%,\n    95\\%, and 99.7\\% confidence intervals.}',
];

for (const caption of LEGENDS) {
  test(`RULE-03 takes legend numbers for keys and not results in a caption: ${caption.slice(0, 50)}`, () => {
    assert.deepEqual(captionHits(rule03(fig(caption), 'main.tex')), [], caption);
  });
}

for (const caption of [
  '\\caption{Hit rate was $0.416$, $0.453$ and $0.471$ on three traces.}',
  '\\caption{LRU reaches 41.2 ms (95\\% CI 39.8 to 42.7), LFU 38.9 ms, and prefetching 27.4 ms.}',
  '\\caption{Hit rate was 0.416, 0.453 and 0.471 at the 25th and 75th percentiles.}',
  '\\caption{Hit rate was 41.6, 45.3 and 47.1 (p < 0.05).}',
  '\\caption{A decision threshold of 0.5 gives 41.6, 45.3 and 47.1.}',
  '\\caption{LRU 41.6, LFU 45.3 and ARC 47.1; dashed lines mark the 25\\% and 75\\% quantiles.}',
  '\\caption{Lines show hit rates of 0.416, 0.453 and 0.471 on three traces.}',
  '\\caption{Markers show 41.6, 45.3 and 47.1.}',
  '\\caption{Stars mark p < 0.05. Hit rate was 41.6, 45.3 and 47.1.}',
  // A reported p-value is a result; only an inequality or a threshold word makes it a key.
  '\\caption{The three tests returned p-values of 0.041, 0.023, and 0.012.}',
  '\\caption{The three tests gave p = 0.041, 0.023, and 0.012.}',
  // A style mapped to values needs "respectively" to read as a legend.
  '\\caption{Lines represent accuracies of 0.812, 0.834, and 0.851.}',
  '\\caption{Confidence in the three runs was 0.812, 0.834, and 0.851.}',
  // A confidence level is a percentage; interval endpoints are results.
  '\\caption{Latency was 41.2 ms, with a confidence interval of 39.8 to 42.7.}',
  '\\caption{Accuracy was 81.2\\%, with a confidence interval of 79.4\\% to 83.0\\%.}',
  '\\caption{Accuracy reaches 0.84,\n    0.86, and 0.88.\n    Shaded bands show the 68\\%,\n    95\\%, and 99.7\\% confidence intervals.}',
  '\\caption{Accuracy reaches 0.84, 0.86, and 0.88. Bands show the 68\\% and 95\\% confidence intervals.}',
]) {
  test(`RULE-03 still flags results beside a legend phrase: ${caption.slice(0, 50)}`, () => {
    const found = captionHits(rule03(fig(caption), 'main.tex'));
    assert.equal(found.length, 1, JSON.stringify(found.map((v) => v.detail)));
    assert.ok(found[0].detail.includes('precise figures'));
  });
}

test('RULE-03 hides only the numbers of a legend', () => {
  const legend = ' Lines mark the 25\\%, 50\\% and 75\\% quantiles.';
  const two = fig(`\\caption{Hit rate was 41.6 and 45.3 on two traces.${legend}}`);
  assert.deepEqual(captionHits(rule03(two, 'main.tex')), []);
  const found = captionHits(rule03(fig(`\\caption{${THREE}${legend}}`), 'main.tex'));
  assert.equal(found.length, 1);
  assert.ok(found[0].detail.includes('3 precise figures'));
});

test('RULE-03 does not let a legend lift the word limit', () => {
  const caption = `\\caption{${numberedWords(101)} Lines mark the 25\\%, 50\\% and 75\\% quantiles.}`;
  const found = captionHits(rule03(fig(caption), 'main.tex'));
  assert.equal(found.length, 1);
  assert.ok(found[0].detail.includes('words'));
});

test('RULE-03 applies the legend rule to captions only', () => {
  // Three sentences of three figures each are a stack in an abstract, quantile list or not.
  const sentence = 'Lines mark the 25\\%, 50\\% and 75\\% quantiles. ';
  const abstract = `\\begin{abstract}\n${sentence.repeat(3)}\n\\end{abstract}\n`;
  assert.equal(frontHits(rule03(abstract, 'main.tex')).length, 1);
});

test('RULE-03 reads a legend in a caption fragment alone', () => {
  assert.deepEqual(captionHits(rule03('\\caption{Lines mark the 25\\%, 50\\% and 75\\% quantiles.}\n', 'main.tex')), []);
  assert.equal(captionHits(rule03(`\\caption{${THREE}}\n`, 'main.tex')).length, 1);
});

// ---------- check D: excess precision ----------

const FOUR = 'We obtain 0.81234, 0.82345, 0.83456 and 0.84567 on the four splits.';

test('RULE-03 ends a paragraph at a run-in heading', () => {
  // \paragraph{} runs its body on in the same source line; each heading still
  // starts a new paragraph, so two short ones do not add up to four numbers.
  const two =
    '\\section{Results}\n\\paragraph{Accuracy.} Scores are 0.8123 and 0.8234.\n' +
    '\\paragraph{Calibration.} Errors are 0.0143 and 0.0256.\n';
  assert.deepEqual(precisionHits(rule03(two, 'main.tex')), []);
  const one = `\\section{Results}\n\\paragraph{Accuracy.} ${FOUR}\n`;
  assert.equal(precisionHits(rule03(one, 'main.tex')).length, 1);
  const joined = '\\section{Results}\nScores are 0.8123 and 0.8234.\nErrors are 0.0143 and 0.0256.\n';
  assert.equal(precisionHits(rule03(joined, 'main.tex')).length, 1);
});

test('RULE-03 flags four long numbers in a paragraph once, at the first', () => {
  const found = precisionHits(rule03(`\\section{Results}\n${FOUR}\n`, 'main.tex'));
  assert.equal(found.length, 1);
  assert.equal(found[0].line, 2);
  assert.equal(found[0].column, FOUR.indexOf('0.81234') + 1);
  assert.ok(found[0].detail.includes('4 numbers written to 4 or more decimal places in one paragraph'));
});

for (const name of ['main.tex', '04-results.tex', '00-abstract.tex', '01-introduction.tex', 'x.TEX']) {
  test(`RULE-03 reads excess precision everywhere outside the appendix: ${name}`, () => {
    assert.equal(precisionHits(rule03(FOUR, name)).length, 1, name);
  });
}

test('RULE-03 reads excess precision in an abstract and an introduction', () => {
  assert.equal(precisionHits(rule03(`\\begin{abstract}\n${FOUR}\n\\end{abstract}\n`, 'main.tex')).length, 1);
  assert.equal(precisionHits(rule03(`\\section{Introduction}\n${FOUR}\n`, 'main.tex')).length, 1);
});

for (const name of ['notes.md', 'README.markdown', 'notes.txt', 'notes.rst', 'NOTES.MD']) {
  test(`RULE-03 reads excess precision in LaTeX only: ${name}`, () => {
    assert.deepEqual(rule03(`\\section{Results}\n${FOUR}\n`, name), [], name);
    assert.deepEqual(rule03(FOUR, name), [], name);
  });
}

test('RULE-03 reads unnamed text for excess precision only when it is LaTeX', () => {
  assert.equal(precisionHits(rule03(`\\section{Results}\n${FOUR}\n`, '')).length, 1);
  assert.deepEqual(rule03(FOUR, ''), []);
});

for (const text of [
  'We obtain 0.81234, 0.82345 and 0.83456 on three splits.',
  'We obtain 0.812, 0.823, 0.834, 0.845 and 0.856 on the five splits.',
  'We obtain 0.81, 0.82, 0.83, 0.84 and 0.85 on the five splits.',
  'We obtain 0.81234, 0.82345 and 0.83456 on three splits.\n\nOn a fourth, 0.84567.',
  '\\begin{itemize}\n\\item A: 0.81234.\n\\item B: 0.82345.\n\\item C: 0.83456.\n\\item D: 0.84567.\n\\end{itemize}',
  'We obtain 81234, 82345, 83456 and 84567 requests on the four splits.',
  'We obtain 1.2.3.4567, 1.2.3.4568, 1.2.3.4569 and 1.2.3.4570 as versions.',
  'Releases v0.12345, v0.12346, v0.12347 and v0.12348 shipped.',
  'See arXiv:2310.12345, arXiv:2310.12346, arXiv:2310.12347 and arXiv:2310.12348.',
  'See https://example.org/0.12345 https://example.org/0.12346 https://example.org/0.12347 https://example.org/0.12348.',
  'Cited as \\citep{lee2020.12345} \\citep{lee2020.12346} \\citep{lee2020.12347} \\citep{lee2020.12348}.',
  'Widths of 0.12345\\textwidth, 0.12346\\textwidth, 0.12347\\textwidth and 0.12348\\textwidth.',
  'Version 3.12345 of Python, Section 3.12346, Table 4.12347 and Figure 5.12348.',
]) {
  test(`RULE-03 leaves text below the precision limit or not a result quiet: ${text.slice(0, 40).replace(/\n/g, ' ')}`, () => {
    assert.deepEqual(precisionHits(rule03(`\\section{Results}\n${text}\n`, 'main.tex')), [], text);
  });
}

for (const env of ['table', 'tabular', 'tabulary', 'tblr', 'figure', 'equation', 'align', 'verbatim', 'lstlisting', 'comment']) {
  test(`RULE-03 skips long numbers inside ${env}`, () => {
    const text = `\\section{Results}\n\\begin{${env}}\n${FOUR}\n\\end{${env}}\n`;
    assert.deepEqual(precisionHits(rule03(text, 'main.tex')), [], env);
  });
}

test('RULE-03 skips long numbers in a comment', () => {
  const commented = FOUR.split(', ').map((piece) => `% ${piece}\n`).join('');
  assert.deepEqual(precisionHits(rule03(`\\section{Results}\n${commented}`, 'main.tex')), []);
});

test('RULE-03 skips long numbers in an appendix or a supplement', () => {
  for (const name of ['appendix.tex', 'supp.tex', 'supplement.tex', 'supplementary-tables.tex']) {
    assert.deepEqual(precisionHits(rule03(FOUR, name)), [], name);
  }
  const text = `\\section{Results}\n${FOUR}\n\n\\appendix\n\\section{Details}\n${FOUR}\n`;
  assert.deepEqual(lineList(precisionHits(rule03(text, 'main.tex'))), [2]);
  const environment = `${FOUR}\n\n\\begin{appendices}\n${FOUR}\n\\end{appendices}\n\n${FOUR}\n`;
  assert.deepEqual(lineList(precisionHits(rule03(environment, 'main.tex'))), [1, 7]);
});

test('RULE-03 does not read the preamble for excess precision', () => {
  const text = `\\documentclass{article}\n${FOUR}\n\\begin{document}\nHello.\n\\end{document}\n`;
  assert.deepEqual(precisionHits(rule03(text, 'main.tex')), []);
});

test('RULE-03 flags two paragraphs that each hold four long numbers twice', () => {
  const text = `\\section{Results}\n${FOUR}\n\n${FOUR.replace(/0\.8/g, '0.7')}\n`;
  assert.deepEqual(lineList(precisionHits(rule03(text, 'main.tex'))), [2, 4]);
});

for (const first of ['-0.81234', '+0.81234', '\u22120.81234', '$-0.81234$', '$-$0.81234', '$+0.81234$']) {
  test(`RULE-03 takes a leading sign as part of the number: ${first}`, () => {
    const sentence = `The shifts are ${first}, 0.82345, 0.83456 and 0.84567 on the splits.`;
    const found = precisionHits(rule03(`\\section{Results}\n${sentence}\n`, 'main.tex'));
    assert.equal(found.length, 1, sentence);
    assert.equal(found[0].column, sentence.indexOf(first) + 1, sentence);
  });
}

test('RULE-03 counts signed and unsigned long numbers alike', () => {
  const signed = 'Shifts of -0.1234, +0.2345, \u22120.3456 and $-0.4567$ appeared.';
  assert.equal(precisionHits(rule03(signed, 'main.tex')).length, 1);
  const short = 'Shifts of -0.1234, +0.2345 and \u22120.3456 appeared.';
  assert.deepEqual(precisionHits(rule03(short, 'main.tex')), []);
});

test('RULE-03 does not take a hyphen inside a name for a sign, and still counts the number', () => {
  const text = 'Layers layer-0.1234 and layer-0.2345 beat run-0.3456 and run-0.4567 on the splits.';
  const found = precisionHits(rule03(text, 'main.tex'));
  assert.equal(found.length, 1);
  assert.equal(found[0].column, text.indexOf('0.1234') + 1);
});

test('RULE-03 counts a number at the end of a sentence and thousands separators', () => {
  assert.equal(
    precisionHits(rule03('Scores were 0.1234, 0.2345, 0.3456 and 0.4567. Nothing else moved.', 'main.tex')).length,
    1
  );
  assert.equal(
    precisionHits(rule03('Costs were 1,234.5678, 2,345.6789, 3,456.7890 and 4,567.8901 dollars.', 'main.tex')).length,
    1
  );
});

test('RULE-03 does not take a confidence level for a long number', () => {
  const text = 'Gains were 0.1234, 0.2345 and 0.3456 (95.0000\\% CI) on the splits.';
  assert.deepEqual(precisionHits(rule03(text, 'main.tex')), []);
});

for (const [number, digits] of [
  ['0.0143', 3], ['-0.0143', 3], ['$-0.0143$', 3], ['\u22120.0143', 3], ['0.00143', 3], ['0.81234', 5],
  ['0.0001', 1], ['0.00025', 2], ['0.0010', 2], ['0.1000', 4], ['1.0000', 5], ['.0000', 0], ['0.0000', 0],
  ['1,234.5678', 8], ['12.3456', 6],
]) {
  test(`RULE-03 counts significant digits without the leading zeros: ${number}`, () => {
    assert.equal(r03Significant(number), digits, number);
  });
}

for (const text of [
  'We search learning rates 0.0001, 0.0002, 0.0005 and 0.0008.',
  'We search rates 0.00025, 0.00035, 0.00045 and 0.00055 on the splits.',
  'We search steps 0.0010, 0.0020, 0.0030 and 0.0040 on the splits.',
  'We search rates $0.0001$, $0.0002$, $0.0005$ and $0.0008$ on the splits.',
  'We search rates -0.0001, -0.0002, -0.0005 and -0.0008 on the splits.',
  'We search rates 0.0001, 0.0002, 0.0005, 0.0008, 0.0009 and 0.00012 on the splits.',
  'Shifts of 0.0143, 0.0256 and 0.0371 came with steps 0.0001, 0.0002 and 0.0003.',
]) {
  test(`RULE-03 takes leading fractional zeros for scale and not precision: ${text.slice(0, 40)}`, () => {
    // A learning rate of 0.0001 has one significant digit, so a paragraph of them reports no
    // excess precision; the paragraph stays quiet in a results section as well as a method one.
    assert.deepEqual(precisionHits(rule03(`\\section{Results}\n${text}\n`, 'main.tex')), [], text);
  });
}

for (const text of [
  'We obtain -0.0143, 0.0256, -0.0371 and 0.0482 on the four splits.',
  'We obtain 0.00143, 0.00256, 0.00371 and 0.00482 on the four splits.',
  'We obtain 0.1000, 0.2000, 0.3000 and 0.4000 on the four splits.',
  'We obtain $-0.0143$, $0.0256$, $-0.0371$ and $0.0482$ on the four splits.',
]) {
  test(`RULE-03 counts four places with three significant digits: ${text.slice(0, 40)}`, () => {
    const found = precisionHits(rule03(`\\section{Results}\n${text}\n`, 'main.tex'));
    assert.equal(found.length, 1, text);
    assert.ok(found[0].detail.includes('4 numbers written to 4 or more decimal places'));
  });
}

test('RULE-03 does not count small numbers toward the four', () => {
  const qualifying = 'Shifts of 0.0143, 0.0256, 0.0371 and 0.0482 came with steps 0.0001, 0.0002 and 0.0003.\n';
  const found = precisionHits(rule03(`\\section{Results}\n${qualifying}`, 'main.tex'));
  assert.equal(found.length, 1);
  assert.ok(found[0].detail.includes('4 numbers'));
  const three = 'Shifts of 0.0143, 0.0256 and 0.0371 came with steps 0.0001, 0.0002, 0.0003 and 0.0004.\n';
  assert.deepEqual(precisionHits(rule03(`\\section{Results}\n${three}`, 'main.tex')), []);
});

test('RULE-03 significant digit limit follows the tuning', () => {
  const text = '\\section{Results}\nWe search learning rates 0.0001, 0.0002, 0.0005 and 0.0008.\n';
  assert.deepEqual(precisionHits(rule03(text, 'main.tex')), []);
  withTuning({ decimalSignificant: 1 }, () => {
    assert.equal(precisionHits(rule03(text, 'main.tex')).length, 1);
  });
});

test('RULE-03 takes a thousands group for part of the number and of its significant digits', () => {
  const text = 'Costs were 1,000.0001, 2,000.0002, 3,000.0003 and 4,000.0004 dollars.';
  const found = precisionHits(rule03(text, 'main.tex'));
  assert.equal(found.length, 1);
  assert.equal(found[0].column, text.indexOf('1,000.0001') + 1);
});

test('RULE-03 reads excess precision in an Edit-sized fragment', () => {
  assert.equal(precisionHits(rule03(FOUR, 'main.tex')).length, 1);
  assert.equal(precisionHits(rule03(`\\emph{Splits.} ${FOUR}`, '')).length, 1);
});

test('RULE-03 excess precision limits follow the tuning', () => {
  const text = 'We obtain 0.812, 0.823, 0.834 and 0.845 on the four splits.\n';
  assert.deepEqual(precisionHits(rule03(text, 'main.tex')), []);
  withTuning({ decimalPlaces: 3 }, () => {
    assert.equal(precisionHits(rule03(text, 'main.tex')).length, 1);
    withTuning({ decimalCount: 5 }, () => {
      assert.deepEqual(precisionHits(rule03(text, 'main.tex')), []);
    });
  });
});

test('RULE-03 counts per sentence when the unit is a sentence', () => {
  withTuning({ decimalUnit: 'sentence', decimalCount: 2 }, () => {
    const text = 'We obtain 0.81234 and 0.82345 on two splits. A third gives 0.83456. A fourth gives 0.84567.\n';
    const found = precisionHits(rule03(text, 'main.tex'));
    assert.equal(found.length, 1);
    assert.ok(found[0].detail.includes('2 numbers') && found[0].detail.includes('in one sentence'));
    assert.equal(found[0].column, text.indexOf('0.81234') + 1);
  });
});

test('RULE-03 excess precision message says what to report', () => {
  assert.equal(
    precisionHits(rule03(FOUR, 'main.tex'))[0].detail,
    '4 numbers written to 4 or more decimal places in one paragraph. Report the precision ' +
      'the measurement supports, usually two or three significant digits, and keep the full ' +
      'values in a table or an appendix'
  );
});

test('RULE-03 locates body, caption and precision findings under comments and CRLF', () => {
  const text =
    `% a comment line\r\n\\section{Results}\r\n${FOUR}\r\n\r\n` +
    `\\begin{figure}\r\n\\caption{${THREE}}\r\n\\end{figure}\r\n`;
  assert.deepEqual(lineList(precisionHits(rule03(text, 'x.tex'))), [3]);
  assert.deepEqual(lineList(captionHits(rule03(text, 'x.tex'))), [6]);
});

// ---------- method and setup sections: exact settings are not findings ----------

// The exact settings of a method (optimizer constants, dropout, splits) are what a
// reader needs to repeat the work. A heading that names a method or a setup exempts
// the body run of check B and check D up to the next heading of the same or a higher
// level. Check A (intervals), check C (captions), the abstract and the introduction
// are read as before.

const D03_SETTINGS =
  'Adam uses beta values 0.9 and 0.999. Dropout is 0.1 and label smoothing is 0.2. ' +
  'Training and validation use fractions 0.8 and 0.2.';

test('RULE-03 does not read exact settings in a methods section as a body run', () => {
  assert.deepEqual(rule03(`\\section{Methods}\n${D03_SETTINGS}\n`, 'main.tex'), []);
  assert.equal(bodyRuns(rule03(`\\section{Results}\n${D03_SETTINGS}\n`, 'main.tex')).length, 1);
});

for (const title of [
  'Method', 'Methods', 'Methodology', 'Our Approach', 'Proposed Method', 'Setup', 'Experimental Setup',
  'Experimental Settings', 'Implementation', 'Implementation Details', 'Hyperparameters', 'Hyper-parameters',
  'Training Details', 'Configuration', 'Datasets', 'Datasets and Metrics', 'Set-up', 'METHODS',
  '1. Method', '2.1 Experimental Setup', 'Evaluation Setup', 'Evaluation Protocol',
]) {
  test(`RULE-03 exempts a section that names a method or a setup: ${title}`, () => {
    for (const command of ['section', 'section*', 'subsection', 'subsubsection', 'section[Short]']) {
      const text = `\\${command}{${title}}\n${D03_SETTINGS}\n${FOUR}\n`;
      assert.deepEqual(rule03(text, 'main.tex'), [], `${command} ${title}`);
    }
  });
}

for (const title of [
  'Results', 'Experiments', 'Evaluation', 'Analysis', 'Discussion', 'Related Work', 'Ablation Study', 'Conclusion',
  'Setup and Results', 'Methods and Results', 'Methodology and Analysis', 'Settings and Findings',
  'Main Results', 'Introduction to Caches',
]) {
  test(`RULE-03 reads a section that names no setup or names an outcome: ${title}`, () => {
    assert.equal(bodyRuns(rule03(`\\section{${title}}\n${D03_SETTINGS}\n`, 'main.tex')).length, 1, title);
  });
}

test('RULE-03 check D skips a setup section and reads the rest', () => {
  const text = `\\section{Experimental Setup}\n${FOUR}\n\n\\section{Results}\n${FOUR}\n`;
  assert.deepEqual(lineList(precisionHits(rule03(text, 'main.tex'))), [5]);
});

test('RULE-03 ends a setup section at the next section', () => {
  const text =
    `\\section{Methods}\n${D03_STACK}\n\\section{Results}\n${D03_STACK}\n` +
    `\\section{Implementation Details}\n${D03_STACK}\n\\chapter{Discussion}\n${D03_STACK}\n`;
  assert.deepEqual(lineList(bodyRuns(rule03(text, 'main.tex'))), [4, 8]);
});

test('RULE-03 exempts a subsection until the next subsection or section', () => {
  const quiet = 'Nothing else moved.\n';
  const text =
    `\\section{Experiments}\n${D03_STACK}\n${quiet}` +
    `\\subsection{Implementation details}\n${D03_STACK}\n` +
    `\\subsubsection{Optimizer}\n${D03_STACK}\n` +
    `\\subsection{Main results}\n${D03_STACK}\n${quiet}` +
    `\\section{Discussion}\n${D03_STACK}\n`;
  assert.deepEqual(lineList(bodyRuns(rule03(text, 'main.tex'))), [2, 9, 12]);
});

test('RULE-03 keeps a deeper heading inside the setup section', () => {
  const text =
    `\\subsection{Setup}\n${D03_STACK}\n\\subsubsection{Results of a pilot}\n${D03_STACK}\n` +
    `\\paragraph{Results}\n${D03_STACK}\n\\subsection{Results}\n${D03_STACK}\n`;
  assert.deepEqual(lineList(bodyRuns(rule03(text, 'main.tex'))), [8]);
});

test('RULE-03 opens a setup span at a paragraph header, to the next paragraph header or section', () => {
  const text =
    '\\section{Experiments}\n' +
    `\\paragraph{Implementation details.} ${D03_SETTINGS}\n` +
    `\\subparagraph{Optimizer} ${D03_STACK}\n` +
    `\\paragraph{Results.} ${D03_STACK}\n` +
    `\\paragraph{Implementation details} ${D03_STACK}\n` +
    `\\subsection{Analysis}\n${D03_STACK}\n`;
  assert.deepEqual(lineList(bodyRuns(rule03(text, 'main.tex'))), [4, 7]);
});

test('RULE-03 opens no setup span at a commented-out heading', () => {
  const text = `% \\section{Methods}\n\\section{Results}\n${D03_STACK}\n`;
  assert.equal(bodyRuns(rule03(text, 'main.tex')).length, 1);
  const verbatim = `\\begin{verbatim}\n\\section{Methods}\n\\end{verbatim}\n\\section{Results}\n${D03_STACK}\n`;
  assert.equal(bodyRuns(rule03(verbatim, 'main.tex')).length, 1);
});

test('RULE-03 runs a setup section to the end when no heading follows', () => {
  const text = `\\section{Results}\n${D03_STACK}\n\n\\section{Methods}\n${D03_STACK}\n\n${D03_STACK}\n`;
  assert.deepEqual(lineList(bodyRuns(rule03(text, 'main.tex'))), [2]);
});

test('RULE-03 leaves the other checks alone in a setup section', () => {
  const interval = '\\section{Methods}\nGain is 0.62 [0.51, 0.83] here.\n';
  assert.equal(r03Intervals(rule03(interval, 'main.tex')).length, 1);
  const caption = `\\section{Methods}\n${fig(`\\caption{${THREE}}`)}`;
  assert.equal(captionHits(rule03(caption, 'main.tex')).length, 1);
  const abstract = `\\begin{abstract}\n${D03_STACK}\n\\end{abstract}\n\\section{Methods}\n${D03_SETTINGS}\n`;
  assert.equal(frontHits(rule03(abstract, 'main.tex')).length, 1);
  const intro = `\\section{Introduction}\n\\subsection{Setup}\n${D03_STACK}\n`;
  assert.equal(frontHits(rule03(intro, 'main.tex')).length, 1);
  const named = rule03(`\\subsection{Setup}\n${D03_STACK}\n`, '01-introduction.tex');
  assert.equal(frontHits(named).length, 1);
});

test('RULE-03 does not let a sentence straddle the edge of a setup section', () => {
  // The setup text has no full stop before the next heading. The first sentence of the
  // results is still its own sentence, so three results sentences make a run.
  const text =
    '\\section{Methods}\nDropout is 0.1 and label smoothing is 0.2\n' +
    '\\section{Results}\nThe gap is 0.41 and 0.52. The next is 0.63 and 0.74. The last is 0.85 and 0.96.\n';
  const found = bodyRuns(rule03(text, 'main.tex'));
  assert.equal(found.length, 1);
  assert.equal(found[0].line, 4);
});

test('RULE-03 reads a fragment with no heading as body prose', () => {
  // The detector reads the text it is handed; it does not guess the section around an Edit.
  assert.equal(bodyRuns(rule03(D03_SETTINGS, 'main.tex')).length, 1);
});

test('RULE-03 leaves a section in scope when the detector cannot read its title', () => {
  // A heading with a nested command or a non-ASCII spelling is not matched as a setup title.
  for (const title of ['M\u00e9thode', '\\textsc{Method}', 'Method~\\label{sec:m}']) {
    assert.equal(bodyRuns(rule03(`\\section{${title}}\n${D03_SETTINGS}\n`, 'main.tex')).length, 1, title);
  }
});

// ---------- tblr and tabulary are display environments ----------

for (const env of ['tabulary', 'tblr']) {
  test(`RULE-03 skips a stack and long numbers inside ${env}`, () => {
    for (const body of [D03_STACK, FOUR]) {
      assert.deepEqual(rule03(`\\section{Results}\n\\begin{${env}}\n${body}\n\\end{${env}}\n`, 'main.tex'), [], env);
    }
  });
}

// ---------- robustness and performance of the new LaTeX checks ----------

const range = (n) => Array.from({ length: n }, (_, i) => i);
const D03_ODD = [
  '', ' ', '\n', '\\caption', '\\caption{', '\\caption{{{{{', '\\caption}}}}}', '\\captionof{', '\\captionof{figure}',
  '\\captionof*{figure}{', '\\caption[', '\\caption[]{}', '\\caption{}',
  '\\begin{figure}\\caption{ 0.1 0.2 0.3 0.4 }', '\\begin{verbatim}\\caption{0.1 0.2 0.3}',
  '\\begin{document}\\begin{document}\\end{document}\\end{document}0.1234 0.1234 0.1234 0.1234',
  '\\end{document}\\begin{document}', '0.1234 0.2345 0.3456 0.4567 0.5678', '.0000 .0000 .0000 .0000',
  '-0.1234 +.1234 \u22120.1234 $-$0.1234 $-0.1234$ $+$', '$-$ $-$ $-$ $-$ 0.1234 0.1234',
  '\\appendix \\caption{0.1 0.2 0.3} 0.1234 0.1234 0.1234 0.1234', '\\begin{appendices}\\caption{0.1 0.2 0.3}',
  '\u0000\u0001\u0002 \\caption{0.1\u0000 0.2 0.3}\u0000',
  '\\caption{\\href{x}{0.1} \\url{0.2} \\cite{0.3} 0.4 0.5 \\label{0.6}}', '\\caption{$ $ $ $ $ 0.1 0.2 0.3 0.4}',
  '\\caption{\\( 0.1 0.2 0.3 0.4 \\) \\(}', '\\caption{\\\\ \\\\\\ \\{ \\} \\% 0.1 0.2 0.3}',
  `\\caption{a}\\caption{b}\\caption{${'w '.repeat(150)}}`,
  range(0x300).map((i) => String.fromCharCode(i)).join(''),
  '9'.repeat(5000), '.'.repeat(5000), '0.'.repeat(5000), `${'{'.repeat(2000)}${'}'.repeat(2000)}`,
  `\\caption{${'{'.repeat(2000)}0.1 0.2 0.3 0.4${'}'.repeat(2000)}}`,
];
const RA_WORDS = (n) => Array(n).fill('alpha').join(' ');
const RA_ODD = [
  '', ' ', '\n', '\\begin{tabular}', '\\begin{tabular}{', '\\begin{tabular}{ll}', '\\begin{tabular}{ll} A & B',
  '\\end{tabular}', '\\end{tabular}\\begin{tabular}', '\\begin{tabular}{ll}\\end{tblr}',
  '\\begin{tblr}{ll}\\begin{tabular}{l}\\end{tblr}\\end{tabular}', '\\begin{tabular}[', '\\begin{tabular}[t',
  '\\begin{tabular*}{\\textwidth}', '\\begin{tabularx}{', '\\begin{tabular}{ll}\\end{tabular}',
  '\\begin{tabular}{ll}{}{}{}\\end{tabular}', '\\begin{tabular}{ll}}}}} & {{{{\\end{tabular}',
  '\\begin{tabular}{ll}\\\\ & \\\\ & \\\\\\end{tabular}', '\\begin{tabular}{ll}\\multicolumn{2}{c}{\\end{tabular}',
  `\\begin{tabular}{ll}\\multirow{2}{*}{${RA_WORDS(30)}\\end{tabular}`, '\\begin{tabular}{ll}\\cmidrule(lr){ \\end{tabular}',
  '\\begin{tabular}{ll}$ $ $ & \\( \\end{tabular}', `\\begin{tabular}{ll}${RA_WORDS(30)}\\end{tabular}\\appendix`,
  `\\begin{tabular}{ll}\\caption{${RA_WORDS(30)}\\end{tabular}`, `\\begin{tabular}{ll}${'\\\\['.repeat(50)}\\end{tabular}`,
  `\\begin{tabular}{ll}${'x. Y. '.repeat(200)}\\end{tabular}`, `\\begin{tabular}{ll}${'.'.repeat(500)}${RA_WORDS(10)}\\end{tabular}`,
  `\u0000\u0001 \\begin{tabular}{ll}\u0000 A \u0000 & \u0000 ${RA_WORDS(30)}\\end{tabular}`,
  range(0x300).map((i) => String.fromCharCode(i)).join(''), `${'{'.repeat(2000)}${'}'.repeat(2000)}`,
  `\\begin{tabular}{ll}${'{'.repeat(2000)}${RA_WORDS(30)}${'}'.repeat(2000)}\\end{tabular}`,
];

D03_ODD.concat(RA_ODD).forEach((text, i) => {
  test(`the 0.7.0 scans never throw on odd input ${i}`, () => {
    for (const name of ['', 'main.tex', 'appendix.tex', 'notes.md']) {
      // The scans themselves, not the public wrappers, so a bug cannot hide behind a catch-all.
      assert.ok(Array.isArray(rule03Scan(text, name)));
      assert.ok(Array.isArray(rule03(text, name)));
      assert.ok(Array.isArray(ruleAScan(text, name)));
      assert.ok(Array.isArray(ruleA(text, name)));
    }
  });
});

const D03_HOSTILE = [
  '\\caption{'.repeat(100000), '\\caption['.repeat(50000), '\\captionof{'.repeat(50000), '\\caption{a}'.repeat(50000),
  `\\caption{${'x '.repeat(100000)}}`, `\\caption{${'$'.repeat(200000)}}`, `\\caption{${'\\a['.repeat(60000)}}`,
  `\\caption{${'\\href{'.repeat(30000)}}`, `\\caption{${'\\citep{a} '.repeat(20000)}}`, `\\caption{${'0.1 '.repeat(60000)}}`,
  '\\caption  '.repeat(50000), `\\caption${' '.repeat(200000)}{x}`, '\\begin{figure}\\caption{x}'.repeat(20000),
  `${'\\appendix '.repeat(50000)}\\caption{x}`, '\\begin{verbatim}'.repeat(20000), '\\begin{document}'.repeat(20000),
  '0.12345 '.repeat(30000), '0.'.repeat(100000), '.0000'.repeat(40000), '-0.12345 '.repeat(25000),
  '$-$0.1234 '.repeat(20000), '1,234.5678 '.repeat(18000), '0.1234\n\n'.repeat(30000),
  `\\begin{abstract}${'0.1234 0.2345. '.repeat(14000)}`, `\\section{Results}\n${'0.12. 0.34. '.repeat(30000)}`,
  // Legend patterns in a caption: lists that almost match, runs of one keyword.
  `\\caption{${'quantile 1,1,1,1,'.repeat(12000)}}`, `\\caption{${'1 - '.repeat(60000)}quantile}`,
  `\\caption{${'p < 0.05, '.repeat(20000)}}`, `\\caption{${'lines at 0.5, '.repeat(15000)}}`,
  `\\caption{${'0.5 and '.repeat(40000)}quantiles}`, `\\caption{${'1,'.repeat(100000)}}`,
  `\\caption{${'0.5, '.repeat(60000)}percentile}`, `\\caption{${'stars mark '.repeat(20000)}}`,
  `\\caption{${'0.5 '.repeat(50000)}significance}`, `\\caption{${'9'.repeat(200000)} quantile}`,
  // Setup headings, thousands groups.
  '\\section['.repeat(50000), '\\paragraph{Method}'.repeat(20000), '\\subsection{Setup}\n\\section{Results}\n'.repeat(15000),
  '\\section{'.repeat(100000), `\\paragraph{${'x'.repeat(150000)}`, '\\section{Setup} 0.9 and 0.999. '.repeat(10000),
  `\\section{Results}\n${'123,'.repeat(50000)}`, `\\section{Results}\n${'1,234,567.8901 '.repeat(15000)}`,
];
const RA_HOSTILE = [
  '\\begin{tabular}{l}'.repeat(50000), '\\begin{tabular}{l}'.repeat(30000) + '\\end{tabular}'.repeat(30000),
  `${'\\begin{tabular}{l} a & b \\\\ '.repeat(20000)}\\end{tabular}`, `\\begin{tabular}{l}${'a & '.repeat(100000)}\\end{tabular}`,
  `\\begin{tabular}{l}${'x. '.repeat(60000)}\\end{tabular}`, `\\begin{tabular}{l}${'.'.repeat(200000)} a b c d e f \\end{tabular}`,
  `${'\\begin{tabular}['.repeat(50000)}\\end{tabular}`, `\\begin{tabular}${'{'.repeat(100000)}\\end{tabular}`,
  `\\begin{tabular}{l}${'\\multicolumn{2}{c}{'.repeat(20000)}\\end{tabular}`,
  `\\begin{tabular}{l}${'\\cmidrule(lr){2-3} '.repeat(20000)}\\end{tabular}`, `\\begin{tabular}{l}${'\\\\['.repeat(60000)}\\end{tabular}`,
  `\\begin{tabular}{l}${'\\a['.repeat(60000)}${RA_WORDS(20)}\\end{tabular}`, `\\begin{tabular}{l}${'$'.repeat(200000)}${RA_WORDS(20)}\\end{tabular}`,
  `\\begin{tabular}{l}${'\\href{'.repeat(30000)}${RA_WORDS(20)}\\end{tabular}`, `\\begin{tabular}{l}${'\\caption{x}'.repeat(30000)}\\end{tabular}`,
  `\\begin{tabular}{l}${' '.repeat(200000)}\\end{tabular}`, `\\begin{tabular}{l}${'\\\\'.repeat(100000)}\\end{tabular}`,
  `\\begin{tabular}{l}${'&'.repeat(200000)}\\end{tabular}`, `\\begin{tabular}{l}${'x '.repeat(100000)}\\end{tabular}`,
  `\\begin{tabular}{l}${'\\textbf{'.repeat(30000)}${'}'.repeat(30000)}\\end{tabular}`,
  `\\begin{tabular}{l}\\begin{tabular}{l}${RA_WORDS(3)}\\end{tabular}\\end{tabular}`.repeat(10000),
  `\\begin{tabular}{l}${RA_WORDS(20)}\\end{tabular}`.repeat(10000),
  '\\begin{tblr}\\begin{tabular}'.repeat(40000) + '\\end{tabular}\\end{tblr}'.repeat(5000), '\\end{tabular}'.repeat(50000),
  '\\begin{verbatim}\\begin{tabular}'.repeat(20000), '\\appendix \\begin{tabular}{l}'.repeat(20000),
  `${'\\caption{'.repeat(50000)}\\begin{tabular}{l}${RA_WORDS(20)}\\end{tabular}`,
];

D03_HOSTILE.concat(RA_HOSTILE).forEach((text, i) => {
  test(`the 0.7.0 scans are fast on hostile input ${i}`, () => {
    for (const name of ['main.tex', '00-abstract.tex', '']) {
      for (const scan of [rule03, ruleA]) {
        const start = Date.now();
        scan(text, name);
        assert.ok(Date.now() - start < 3000, `${scan.name} ${name}`);
      }
    }
  });
});

test('the 0.7.0 scans are fast on 200 KB of LaTeX with captions and tables', () => {
  const paragraph =
    '\\begin{figure}\n\\caption{Hit rate was 41.6, 45.3 and 47.1 on three traces, ' +
    'with Section 3.2 and Table 4 as context.}\n\\end{figure}\n' +
    'The build gave 0.62 on the first split and 0.52 on the second, with 0.8123 and 0.8234. ' +
    'Prefetching lowers the miss rate by 8.9 points at full load. v0.7.0 shipped on 2026-10-16.\n\n';
  const block =
    '\\begin{table}\n\\begin{tabular}{p{3cm}p{6cm}}\n\\toprule\nName & Note\\\\\n\\midrule\n' +
    `A & short\\\\\nB & ${RA_WORDS(20)} \\citep{lee2020}\\\\\n\\bottomrule\n\\end{tabular}\n\\end{table}\n\n`;
  const text = paragraph.repeat(Math.floor(200000 / paragraph.length) + 1);
  assert.ok(text.length >= 200000);
  for (const name of ['main.tex', '']) {
    const start = Date.now();
    const found = rule03(text, name);
    assert.ok(Date.now() - start < 3000, name);
    assert.ok(captionHits(found).length > 100);
  }
  const tables = block.repeat(Math.floor(200000 / block.length) + 1);
  const start = Date.now();
  const found = ruleA(tables, 'main.tex');
  assert.ok(Date.now() - start < 3000);
  assert.ok(found.length > 100);
});

function boom() {
  return {
    toString() {
      throw new Error('boom');
    },
  };
}

test('a broken scan is swallowed by the wrapper and raised by the scan', () => {
  // A path whose conversion to a string throws stands in for a bug inside the scan.
  assert.throws(() => rule03Scan(`\\caption{${THREE}}`, boom()));
  assert.deepEqual(rule03(`\\caption{${THREE}}`, boom()), []);
  assert.throws(() => ruleAScan(`\\begin{tabular}{ll}A & ${RA_WORDS(16)}\\\\\n\\end{tabular}`, boom()));
  assert.deepEqual(ruleA(`\\begin{tabular}{ll}A & ${RA_WORDS(16)}\\\\\n\\end{tabular}`, boom()), []);
});

// ---------- RULE-A: prose in a LaTeX table cell (hook-only) ----------

function raTable(rows, { env = 'tabular', spec = 'll', head = null } = {}) {
  const begin = head !== null ? head : `\\begin{${env}}{${spec}}`;
  return `${begin}\n${rows.join('\\\\\n')}\\\\\n\\end{${env}}\n`;
}

const RA_ENVS = [
  ['tabular', '\\begin{tabular}{ll}'],
  ['tabular*', '\\begin{tabular*}{\\textwidth}{ll}'],
  ['tabularx', '\\begin{tabularx}{\\textwidth}{lX}'],
  ['tabulary', '\\begin{tabulary}{\\textwidth}{LL}'],
  ['longtable', '\\begin{longtable}{p{3cm}p{6cm}}'],
  ['tblr', '\\begin{tblr}{colspec={ll}, hlines}'],
];

for (const [env, head] of RA_ENVS) {
  test(`RULE-A flags a cell over fifteen words in ${env}`, () => {
    const found = ruleA(raTable(['Name & Note', `A & ${RA_WORDS(16)}`], { env, head }), 'main.tex');
    assert.equal(found.length, 1, JSON.stringify(found.map((v) => v.detail)));
    assert.equal(found[0].rule, 'RULE-A');
    assert.equal(found[0].line, 3);
    assert.ok(found[0].detail.includes('a table cell of 16 words'));
  });

  test(`RULE-A leaves fifteen words and the layout arguments quiet in ${env}`, () => {
    // The width and the column specification open the table; they are no words.
    assert.deepEqual(ruleA(raTable([`${RA_WORDS(15)} & x`, 'A & B'], { env, head }), 'main.tex'), [], env);
  });
}

test('RULE-A reads the first cell after the arguments', () => {
  const text = `\\begin{tabular}[t]{@{}p{3cm}p{6cm}@{}}\n${RA_WORDS(16)} & x\\\\\n\\end{tabular}\n`;
  const found = ruleA(text, 'main.tex');
  assert.equal(found.length, 1);
  assert.equal(found[0].line, 2);
  assert.equal(found[0].column, 1);
});

test('RULE-A flags two sentences in a short cell', () => {
  const found = ruleA(raTable(['Metric & Note', 'A & Lower is better. Averaged over five seeds.']), 'main.tex');
  assert.equal(found.length, 1);
  assert.ok(found[0].detail.includes('a table cell of 2 sentences'));
});

for (const cell of [
  'Lower is better.',
  'Lower is better',
  'Lower is better, averaged over five seeds.',
  'Lee and Kim ran Prof. Park and Dr. Chen over five seeds',
  'Lee and Kim ran J. Smith and K. Lee over five seeds',
  'Gain over the baseline, e.g. Five seeds, i.e. Averaged over runs',
  'See Fig. Three for the setup and Tab. Four for the other splits',
  'Compared vs. Baseline models on the full test set',
  'Study of 3.5 points. 4.2 points. 1.1 points',
  'Yes. No.',
  'Mean (std.) over five seeds',
]) {
  test(`RULE-A takes one sentence for one: ${cell}`, () => {
    assert.deepEqual(ruleA(raTable(['Metric & Note', `A & ${cell}`]), 'main.tex'), [], cell);
  });
}

test('RULE-A flags a table once, at the first offending cell', () => {
  const found = ruleA(raTable(['Name & Note', 'A & short', `B & ${RA_WORDS(20)}`, `C & ${RA_WORDS(30)}`]), 'main.tex');
  assert.equal(found.length, 1);
  assert.equal(found[0].line, 4);
  assert.ok(found[0].detail.includes('20 words'));
});

test('RULE-A flags two tables on their own lines', () => {
  const text =
    `${raTable([`A & ${RA_WORDS(16)}`])}\nText between the tables.\n\n` +
    `${raTable(['A & short'])}${raTable([`A & ${RA_WORDS(17)}`])}`;
  assert.deepEqual(lineList(ruleA(text, 'main.tex')), [2, 11]);
});

test('RULE-A reports the offending cell line of a multi-line table', () => {
  const text =
    '\\begin{table}\n\\begin{tabular}{lll}\n\\toprule\nA & B & C\\\\\n\\midrule\n' +
    `x & y & z\\\\\nx & ${RA_WORDS(16)} & z\\\\\n\\bottomrule\n\\end{tabular}\n\\end{table}\n`;
  const found = ruleA(text, 'main.tex');
  assert.equal(found.length, 1);
  assert.equal(found[0].line, 7);
  assert.equal(found[0].column, 5);
});

test('RULE-A does not move the finding for a rule command before a cell', () => {
  const text =
    `\\begin{tabular}{ll}\n\\toprule\nA & B\\\\\n\\midrule\n${RA_WORDS(16)} & x\\\\\n\\cmidrule(lr){1-2}\n` +
    'y & z\\\\\n\\bottomrule\n\\end{tabular}\n';
  const found = ruleA(text, 'main.tex');
  assert.equal(found.length, 1);
  assert.equal(found[0].line, 5);
  const afterRule = `\\begin{tabular}{ll}\nA & B\\\\\n\\midrule\nx & ${RA_WORDS(16)}\\\\\n\\end{tabular}\n`;
  assert.equal(ruleA(afterRule, 'main.tex')[0].line, 4);
  const ruleLine = `\\begin{tabular}{ll}\nA & B\\\\\n\\midrule\n${RA_WORDS(16)} & x\\\\\n\\end{tabular}\n`;
  assert.equal(ruleA(ruleLine, 'main.tex')[0].line, 4);
});

test('RULE-A reads a cell that spans lines as one cell', () => {
  const text = `\\begin{tabular}{ll}\nA & ${RA_WORDS(8)}\n${RA_WORDS(8)}\\\\\n\\end{tabular}\n`;
  const found = ruleA(text, 'main.tex');
  assert.equal(found.length, 1);
  assert.equal(found[0].line, 2);
  assert.ok(found[0].detail.includes('16 words'));
});

test('RULE-A counts no word for numbers, single letters, math, citations and references', () => {
  const cell =
    `${RA_WORDS(15)} 12 3.45 6\\% a b c $x_i + y_j$ \\citep{lee2020,kim2021} ` +
    '\\ref{tab:x} \\cref{sec:y} \\label{z} 99.5 x y';
  assert.deepEqual(ruleA(raTable([`A & ${cell}`]), 'main.tex'), []);
  assert.equal(ruleA(raTable([`A & ${cell} beta`]), 'main.tex').length, 1);
});

test('RULE-A drops a command and keeps its text', () => {
  const bold = `\\textbf{${RA_WORDS(8)}} \\emph{${RA_WORDS(8)}}`;
  const found = ruleA(raTable([`A & ${bold}`]), 'main.tex');
  assert.equal(found.length, 1);
  assert.ok(found[0].detail.includes('16 words'));
});

test('RULE-A counts no word for layout commands', () => {
  const cell =
    `\\cellcolor{lightgray} \\textcolor{red}{${RA_WORDS(15)}} \\parbox[t]{5cm}{} \\hspace{2cm} \\rule{1cm}{1pt}`;
  assert.deepEqual(ruleA(raTable([`A & ${cell}`]), 'main.tex'), []);
});

for (const cell of [
  `\\multicolumn{2}{c}{${RA_WORDS(15)}}`,
  `\\multirow{2}{*}{${RA_WORDS(15)}}`,
  `\\multicolumn{2}{|c|}{${RA_WORDS(15)}}`,
  `\\cmidrule(lr){2-3} ${RA_WORDS(15)}`,
  `\\midrule ${RA_WORDS(15)}`,
  `\\cline{1-2} ${RA_WORDS(15)}`,
  `\\addlinespace[2pt] ${RA_WORDS(15)}`,
]) {
  test(`RULE-A keeps the text and adds no words for ${cell.slice(0, 24)}`, () => {
    assert.deepEqual(ruleA(raTable(['A & B', `${cell} & x`]), 'main.tex'), [], cell);
  });
}

test('RULE-A flags a long cell inside multicolumn', () => {
  const found = ruleA(raTable(['A & B', `\\multicolumn{2}{c}{${RA_WORDS(16)}}`]), 'main.tex');
  assert.equal(found.length, 1);
  assert.ok(found[0].detail.includes('16 words'));
});

test('RULE-A does not split a cell at a separator inside braces', () => {
  // `\\` inside \makecell is a line break in the cell, not a row end.
  const cell = `\\makecell{${RA_WORDS(8)}\\\\${RA_WORDS(8)}}`;
  const found = ruleA(raTable([`A & ${cell}`]), 'main.tex');
  assert.equal(found.length, 1);
  assert.ok(found[0].detail.includes('16 words'));
  assert.deepEqual(ruleA(raTable([`A & ${RA_WORDS(8)}\\\\${RA_WORDS(8)}`]), 'main.tex'), []);
});

test('RULE-A does not split a cell at an escaped ampersand', () => {
  const cell = Array(8).fill('alpha').join(' \\& ');
  assert.equal(ruleA(raTable([`A & ${cell} \\& ${RA_WORDS(8)}`]), 'main.tex').length, 1);
});

test('RULE-A does not read a short nested table as prose in the outer cell', () => {
  const inner = `\\begin{tabular}{@{}l@{}}${RA_WORDS(9)}\\\\${RA_WORDS(9)}\\end{tabular}`;
  assert.deepEqual(ruleA(raTable([`A & ${inner} & x`]), 'main.tex'), []);
});

test('RULE-A reports a nested table on its own and keeps its words out of the outer cell', () => {
  const inner = `\\begin{tabular}{@{}l@{}}${RA_WORDS(20)}\\end{tabular}`;
  const found = ruleA(raTable([`A & ${RA_WORDS(10)} ${inner}`]), 'main.tex');
  assert.equal(found.length, 1);
  assert.ok(found[0].detail.includes('20 words'));
  assert.equal(ruleA(raTable([`A & ${RA_WORDS(20)} ${inner}`]), 'main.tex').length, 2);
});

test('RULE-A leaves tables nested deeper than the limit inside their parent', () => {
  let text = '';
  for (let i = 0; i < 8; i++) text += `\\begin{tabular}{l}\n${RA_WORDS(2)} &\n`;
  text += RA_WORDS(20);
  for (let i = 0; i < 8; i++) text += '\n\\end{tabular}';
  const found = ruleA(`${text}\n`, 'main.tex');
  assert.ok(Array.isArray(found));
  assert.ok(found.length <= 4);
});

test('RULE-A does not read a caption in a longtable as a cell', () => {
  const text = `\\begin{longtable}{ll}\n\\caption{${RA_WORDS(40)}}\\\\\nA & B\\\\\n\\end{longtable}\n`;
  assert.deepEqual(ruleA(text, 'main.tex'), []);
  const found = ruleA(text.replace('A & B', `A & ${RA_WORDS(16)}`), 'main.tex');
  assert.equal(found.length, 1);
  assert.equal(found[0].line, 3);
});

test('RULE-A does not take a table environment wrapper for a table', () => {
  const text = `\\begin{table}\n\\caption{${RA_WORDS(40)}}\n${RA_WORDS(40)}\n\\end{table}\n`;
  assert.deepEqual(ruleA(text, 'main.tex'), []);
});

for (const wrap of [
  '% {}',
  '\\begin{verbatim}\n{}\n\\end{verbatim}',
  '\\begin{lstlisting}\n{}\n\\end{lstlisting}',
  '\\begin{comment}\n{}\n\\end{comment}',
]) {
  test(`RULE-A does not read a table in a comment or code: ${wrap.split('\n')[0]}`, () => {
    const inner = raTable([`A & ${RA_WORDS(20)}`]);
    const text = wrap.startsWith('\\')
      ? wrap.replace('{}', () => inner.trim())
      : inner.split('\n').filter((l, i, all) => i < all.length - 1).map((l) => `% ${l}\n`).join('');
    assert.deepEqual(ruleA(`\\begin{document}\n${text}\n`, 'main.tex'), [], wrap);
  });
}

test('RULE-A does not read a commented cell', () => {
  const text = `\\begin{tabular}{ll}\nA & B\\\\\n% C & ${RA_WORDS(30)}\\\\\nD & E\\\\\n\\end{tabular}\n`;
  assert.deepEqual(ruleA(text, 'main.tex'), []);
  const tail = `\\begin{tabular}{ll}\nA & B % ${RA_WORDS(30)}\\\\\n\\end{tabular}\n`;
  assert.deepEqual(ruleA(tail, 'main.tex'), []);
});

for (const name of [
  'appendix.tex', '02-Appendix.tex', 'supp.tex', 'supplement.tex', 'supplementary-tables.tex',
  'A_appendices.tex', 'C:\\x\\appendix.tex', '/tmp/x/sections/supp_b.tex',
]) {
  test(`RULE-A exempts an appendix or supplement file name: ${name}`, () => {
    assert.deepEqual(ruleA(raTable([`A & ${RA_WORDS(20)}`]), name), [], name);
  });
}

for (const name of ['support.tex', 'tables.tex', 'main.tex', 'application.tex', 'results.tex', '']) {
  test(`RULE-A reads other file names: ${name || '(none)'}`, () => {
    assert.equal(ruleA(raTable([`A & ${RA_WORDS(20)}`]), name).length, 1, name);
  });
}

test('RULE-A exempts a table after the appendix command', () => {
  const text = `${raTable([`A & ${RA_WORDS(20)}`])}\\appendix\n\\section{Details}\n${raTable([`A & ${RA_WORDS(20)}`])}`;
  assert.deepEqual(lineList(ruleA(text, 'main.tex')), [2]);
});

test('RULE-A exempts a table in the appendices environment', () => {
  const t = () => raTable([`A & ${RA_WORDS(20)}`]);
  const text = `${t()}\\begin{appendices}\n${t()}\\end{appendices}\n${t()}`;
  assert.deepEqual(lineList(ruleA(text, 'main.tex')), [2, 10]);
  assert.deepEqual(lineList(ruleA(`${t()}\\begin{appendices}\n${t()}`, 'main.tex')), [2]);
});

for (const name of ['notes.md', 'README.markdown', 'NOTES.MD', 'notes.txt', 'notes.rst']) {
  test(`RULE-A never reads Markdown, plain text or reStructuredText: ${name}`, () => {
    assert.deepEqual(ruleA(raTable([`A & ${RA_WORDS(20)}`]), name), [], name);
    const markdown =
      `| Name | Note |\n| --- | --- |\n| A | ${RA_WORDS(40)} |\n| B | Lower is better. Averaged over seeds. |\n`;
    assert.deepEqual(ruleA(markdown, name), [], name);
  });
}

test('RULE-A reads unnamed text only when it is LaTeX', () => {
  assert.equal(ruleA(raTable([`A & ${RA_WORDS(20)}`]), '').length, 1);
  assert.notDeepEqual(ruleA(raTable([`A & ${RA_WORDS(20)}`])), []);
  const markdown = `| Name | Note |\n| --- | --- |\n| A | ${RA_WORDS(40)} |\n`;
  assert.deepEqual(ruleA(markdown, ''), []);
  assert.deepEqual(ruleA(`A & ${RA_WORDS(40)}\\\\`, ''), []);
});

test('RULE-A reads an Edit-sized fragment alone', () => {
  // The guard hands an Edit's new fragment to the detector, not the file.
  const fragment = raTable([`A & ${RA_WORDS(16)}`]);
  assert.equal(ruleA(fragment, 'main.tex').length, 1);
  assert.equal(ruleA(fragment, '').length, 1);
  // Rows alone have no table to belong to, so nothing is read.
  assert.deepEqual(ruleA(`A & ${RA_WORDS(16)}\\\\\n`, 'main.tex'), []);
});

test('RULE-A orders findings by position', () => {
  const text = `${raTable([`A & ${RA_WORDS(16)}`])}\n${raTable([`B & ${RA_WORDS(17)}`])}`;
  const lines = lineList(ruleA(text, 'main.tex'));
  assert.equal(lines.length, 2);
  assert.deepEqual(lines, lines.slice().sort((x, y) => x - y));
});

test('RULE-A message says what a cell holds', () => {
  const found = ruleA(raTable([`A & ${RA_WORDS(16)}`]), 'main.tex')[0];
  assert.equal(
    found.detail,
    'a table cell of 16 words; a table cell holds a number, a label, or a short phrase, ' +
      'so move content that needs a sentence into the text'
  );
  const two = ruleA(raTable(['A & Lower is better. Averaged over five seeds.']), 'main.tex')[0];
  assert.ok(two.detail.startsWith('a table cell of 2 sentences; a table cell holds a number'));
});

test('RULE-A locates a finding under CRLF', () => {
  const text = `\\begin{tabular}{ll}\r\nA & B\\\\\r\nx & ${RA_WORDS(16)}\\\\\r\n\\end{tabular}\r\n`;
  const found = ruleA(text, 'main.tex');
  assert.equal(found.length, 1);
  assert.equal(found[0].line, 3);
});

test('RULE-A is registered for hooks with the file path', () => {
  const rule = { id: 'RULE-A', severity: 'low' };
  const text = raTable([`A & ${RA_WORDS(16)}`]);
  const loud = runMech03(rule, text, 'main.tex');
  assert.equal(loud.count, 1);
  assert.equal(loud.detector, 'mechanical');
  assert.equal(runMech03(rule, text, 'appendix.tex').count, 0);
  assert.equal(runMech03(rule, text, 'notes.md').count, 0);
});

test('RULE-A takes an empty file path by default', () => {
  const text = raTable([`A & ${RA_WORDS(16)}`]);
  assert.deepEqual(ruleA(text), ruleA(text, ''));
});

test('the audit never runs the hook-only detectors', () => {
  // `agent-style review` classifies RULE-A as structural and RULE-03 as semantic;
  // the benchmark pins its mechanical scope on that.
  assert.deepEqual([...CLASSIFICATION['RULE-A']], ['structural']);
  assert.deepEqual([...CLASSIFICATION['RULE-03']], ['semantic']);
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'agent-style-hookonly-'));
  const source = path.join(dir, 'paper.tex');
  fs.writeFileSync(
    source,
    '\\section{Results}\n' +
      'Raising the cache changes the hit rate by 3.7, 41.6 and 45.3 points. ' +
      'Prefetching lowers the miss rate by 8.9 and 5.2 points. A second layout gives 0.57 and 0.43.\n' +
      raTable([`A & ${RA_WORDS(40)}`, 'B & Lower is better. Averaged over five seeds.']) +
      '\\begin{figure}\n\\caption{Hit rate was 41.6, 45.3 and 47.1 on three traces.}\n\\end{figure}\n',
    'utf8'
  );
  for (const only of [true, false]) {
    const result = audit(source, { mechanicalOnly: only, skillHost: false });
    for (const rr of result.ruleResults) {
      if (rr.rule === 'RULE-A' || rr.rule === 'RULE-03') {
        assert.notEqual(rr.detector, 'mechanical', `${rr.rule} ran as a mechanical detector`);
        assert.ok(rr.violations.every((v) => v.rule === rr.rule));
        assert.ok(!rr.violations.some((v) => v.detail.includes('table cell') || v.detail.includes('caption')));
      }
    }
  }
});

// ---------- cross-rule: tblr and tabulary cells under RULE-03 ----------
// A numeric table cell is a table cell. RULE-03 reads prose, so every table environment
// RULE-A reads is a display for RULE-03 too; the numbers in tblr and tabulary cells feed
// none of checks A, B and D, while a long prose cell still belongs to RULE-A.

const CROSS_ENVS = [
  ['tblr', '\\begin{tblr}{cccc}'],
  ['tabulary', '\\begin{tabulary}{\\textwidth}{CCCC}'],
];
const CROSS_ROWS = [
  '0.81234 & 0.82345 & 0.83456 & 0.84567',
  '0.71234 & 0.72345 & 0.73456 & 0.74567',
  '0.62 [0.51, 0.83] & 41.6\\% & 45.3\\% & 47.1\\%',
  '0.41 & 0.52 & 0.63 & 0.74',
  '0.85 & 0.96 & 0.17 & 0.28',
];

for (const [env, head] of CROSS_ENVS) {
  for (const name of ['main.tex', '04-results.tex', '00-abstract.tex', '01-introduction.tex', '']) {
    test(`RULE-03 and RULE-A leave numeric ${env} cells in a table fragment quiet: ${name || '(none)'}`, () => {
      const fragment = raTable(CROSS_ROWS, { env, head });
      assert.deepEqual(rule03(fragment, name), [], `${env} ${name}`);
      assert.deepEqual(ruleA(fragment, name), [], `${env} ${name}`);
    });
  }

  test(`RULE-03 leaves numeric ${env} cells quiet in a float and among prose`, () => {
    const fragment = raTable(CROSS_ROWS, { env, head });
    const floated = `\\begin{table}\n\\caption{Scores by split.}\n${fragment}\\end{table}\n`;
    assert.deepEqual(rule03(floated, 'main.tex'), []);
    const among = `\\section{Results}\nThe scores are in the table.\n\n${fragment}\nNothing else moved.\n`;
    assert.deepEqual(rule03(among, 'main.tex'), []);
    assert.deepEqual(rule03(`\\begin{abstract}\n${fragment}\\end{abstract}\n`, 'main.tex'), []);
  });

  test(`RULE-A still flags a long prose cell in ${env} and RULE-03 does not`, () => {
    const rows = ['Name & Note & x & y', `A & ${RA_WORDS(20)} & 0.81234 & 0.82345`].concat(CROSS_ROWS);
    const text = raTable(rows, { env, head });
    const found = ruleA(text, 'main.tex');
    assert.equal(found.length, 1, JSON.stringify(found.map((v) => v.detail)));
    assert.equal(found[0].line, 3);
    assert.ok(found[0].detail.includes('a table cell of 20 words'));
    assert.deepEqual(rule03(text, 'main.tex'), []);
    const two = raTable(['A & Lower is better. Averaged over five seeds. & 0.81234 & 0.82345'], { env, head });
    assert.equal(ruleA(two, 'main.tex').length, 1);
    assert.deepEqual(rule03(two, 'main.tex'), []);
  });
}

test('RULE-03 treats every table environment RULE-A reads as a display', () => {
  // One list of environments: a table RULE-A reads must not feed RULE-03's prose checks.
  for (const [env, head] of [
    ['tabular', '\\begin{tabular}{ll}'],
    ['tabular*', '\\begin{tabular*}{\\textwidth}{ll}'],
    ['tabularx', '\\begin{tabularx}{\\textwidth}{lX}'],
    ['tabulary', '\\begin{tabulary}{\\textwidth}{LL}'],
    ['longtable', '\\begin{longtable}{p{3cm}p{6cm}}'],
    ['tblr', '\\begin{tblr}{colspec={ll}, hlines}'],
  ]) {
    assert.deepEqual(rule03(raTable(CROSS_ROWS, { env, head }), 'main.tex'), [], env);
  }
});

test('the 0.7.0 scans take odd argument types', () => {
  assert.deepEqual(ruleA(null), []);
  assert.deepEqual(ruleA(42), []);
  assert.deepEqual(rule03(undefined), []);
  assert.notEqual(ruleA(raTable([`A & ${RA_WORDS(16)}`]), null), null);
  assert.equal(ruleA(raTable([`A & ${RA_WORDS(16)}`]), { toString: () => 'main.tex' }).length, 1);
});
