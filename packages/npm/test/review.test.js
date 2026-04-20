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

function sortObj(obj) {
  return Object.fromEntries(Object.entries(obj).sort(([a], [b]) => a.localeCompare(b)));
}
