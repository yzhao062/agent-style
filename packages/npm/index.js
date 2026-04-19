// SPDX-License-Identifier: MIT
'use strict';
/**
 * agent-style programmatic API for Node consumers.
 *
 *   const agentStyle = require('agent-style');
 *   agentStyle.rules();
 *   agentStyle.listTools();
 *   agentStyle.enable('claude-code', { projectRoot: '.', dryRun: false });
 */

const { Registry } = require('./lib/registry');
const installer = require('./lib/installer');
const VERSION = require('./package.json').version;

function rules() {
  return new Registry().readBundledRules();
}

function path() {
  return new Registry().dataDir;
}

function listTools() {
  const r = new Registry();
  return Object.entries(r.tools).map(([name, spec]) => ({
    name,
    install_mode: spec.install_mode,
    target_path: spec.target_path,
  }));
}

function enable(tool, options = {}) {
  const { projectRoot = '.', dryRun = false } = options;
  return installer.enable(tool, new Registry(), projectRoot, dryRun);
}

function disable(tool, options = {}) {
  const { projectRoot = '.', dryRun = false } = options;
  return installer.disable(tool, new Registry(), projectRoot, dryRun);
}

module.exports = { version: VERSION, rules, path, listTools, enable, disable };
