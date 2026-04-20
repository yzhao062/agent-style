// SPDX-License-Identifier: MIT
'use strict';
/**
 * High-level primitive for audit and compare.
 * Mirrors agent_style.review.primitive in the Python package.
 */

const fs = require('fs');
const { loadRules } = require('./loader');

// Per-rule bucket classification (same as Python).
const CLASSIFICATION = {
  'RULE-01': new Set(['semantic']),
  'RULE-02': new Set(['structural', 'semantic']),
  'RULE-03': new Set(['semantic']),
  'RULE-04': new Set(['semantic']),
  'RULE-05': new Set(['mechanical', 'semantic']),
  'RULE-06': new Set(['mechanical', 'semantic']),
  'RULE-07': new Set(['structural']),
  'RULE-08': new Set(['semantic']),
  'RULE-09': new Set(['structural']),
  'RULE-10': new Set(['structural']),
  'RULE-11': new Set(['semantic']),
  'RULE-12': new Set(['mechanical']),
  'RULE-A': new Set(['structural']),
  'RULE-B': new Set(['mechanical']),
  'RULE-C': new Set(['structural']),
  'RULE-D': new Set(['mechanical']),
  'RULE-E': new Set(['structural']),
  'RULE-F': new Set(['semantic']),
  'RULE-G': new Set(['mechanical']),
  'RULE-H': new Set(['semantic']),
  'RULE-I': new Set(['mechanical']),
};

function audit(filePath, opts = {}) {
  const projectRoot = opts.projectRoot || '.';
  const mechanicalOnly = opts.mechanicalOnly || false;
  const skillHost = opts.skillHost || false;

  const rules = loadRules({ projectRoot });
  const text = fs.readFileSync(filePath, 'utf8');
  const ruleResults = [];
  let total = 0;

  // Lazy-require detectors (avoids circular requires and keeps loader-only callers cheap)
  const detectorsMech = require('./detectors_mech');
  const detectorsStruct = require('./detectors_struct');
  const detectorsSem = require('./detectors_sem');

  for (const rule of rules.rules) {
    const bucket = CLASSIFICATION[rule.id] || new Set();
    if (bucket.has('mechanical')) {
      const result = detectorsMech.run(rule, text, filePath);
      ruleResults.push(result);
      total += result.count;
    }
    if (bucket.has('structural')) {
      if (mechanicalOnly) {
        ruleResults.push({
          rule: rule.id,
          severity: rule.severity,
          detector: 'structural',
          status: 'skipped',
          count: 0,
          note: 'structural detectors disabled (--mechanical-only)',
          violations: [],
        });
      } else {
        const result = detectorsStruct.run(rule, text, filePath);
        ruleResults.push(result);
        total += result.count;
      }
    }
    if (bucket.has('semantic')) {
      if (mechanicalOnly || !skillHost) {
        ruleResults.push({
          rule: rule.id,
          severity: rule.severity,
          detector: 'semantic',
          status: 'skipped',
          count: 0,
          note:
            'semantic detectors require a skill host (Claude Code or Anthropic Skills); ' +
            'run /style-review via one of those hosts to include semantic rules',
          violations: [],
        });
      } else {
        const result = detectorsSem.run(rule, text, filePath);
        ruleResults.push(result);
        total += result.count;
      }
    }
  }

  return {
    file: filePath,
    rulesSource: rules.rulesSource,
    rulesPath: rules.sourcePath,
    totalViolations: total,
    ruleResults,
  };
}

function compare(fileA, fileB, opts = {}) {
  const projectRoot = opts.projectRoot || '.';
  const mechanicalOnly = opts.mechanicalOnly !== undefined ? opts.mechanicalOnly : true;
  const skillHost = opts.skillHost || false;

  const a = audit(fileA, { projectRoot, mechanicalOnly, skillHost });
  const b = audit(fileB, { projectRoot, mechanicalOnly, skillHost });
  const perRule = {};

  for (const ra of a.ruleResults) {
    const row = perRule[ra.rule] || { a: 0, b: 0, delta: 0 };
    row.a += ra.count;
    perRule[ra.rule] = row;
  }
  for (const rb of b.ruleResults) {
    const row = perRule[rb.rule] || { a: 0, b: 0, delta: 0 };
    row.b += rb.count;
    perRule[rb.rule] = row;
  }
  for (const row of Object.values(perRule)) {
    row.delta = row.b - row.a;
  }

  return {
    fileA,
    fileB,
    rulesSource: a.rulesSource,
    rulesPath: a.rulesPath,
    totalA: a.totalViolations,
    totalB: b.totalViolations,
    perRuleDelta: perRule,
  };
}

module.exports = { audit, compare, CLASSIFICATION };
