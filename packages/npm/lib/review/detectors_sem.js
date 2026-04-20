// SPDX-License-Identifier: MIT
'use strict';
/**
 * Semantic detector stubs. Return `status: "skipped"` outside a skill host.
 * Mirrors agent_style.review.detectors_sem in Python.
 */

function run(rule, _text, _filePath) {
  return {
    rule: rule.id,
    severity: rule.severity,
    detector: 'semantic',
    status: 'skipped',
    count: 0,
    note:
      'semantic detection not available from the plain CLI; ' +
      'run /style-review via Claude Code or Anthropic Skills ' +
      'to include this rule in the audit',
    violations: [],
  };
}

module.exports = { run };
