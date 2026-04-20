// SPDX-License-Identifier: MIT
'use strict';
/**
 * Polish stub; raises outside a skill host. Mirrors agent_style.review.polish.
 */

class PolishNotAvailableError extends Error {
  constructor(msg) {
    super(msg);
    this.name = 'PolishNotAvailableError';
  }
}

function checkHostAndRaise() {
  throw new PolishNotAvailableError(
    'polish is only available inside a skill host (Claude Code or Anthropic Skills); ' +
    'run /style-review from one of those hosts. ' +
    'For a deterministic audit without polish, use ' +
    '`agent-style review --audit-only <file>`.'
  );
}

module.exports = { checkHostAndRaise, PolishNotAvailableError };
