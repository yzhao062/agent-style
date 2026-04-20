// SPDX-License-Identifier: MIT
'use strict';
/**
 * agent-style review module: deterministic primitive for the style-review skill.
 *
 * Mirrors agent_style.review in the Python package. Mechanical + structural
 * detection is deterministic. Semantic detection returns status "skipped"
 * outside a skill host; polish errors outside a skill host.
 */

const { loadRules, RulesLoadError } = require('./loader');
const { audit, compare } = require('./primitive');

module.exports = {
  audit,
  compare,
  loadRules,
  RulesLoadError,
};
