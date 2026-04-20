// SPDX-License-Identifier: MIT
'use strict';
/**
 * RULES.md loader with the PLAN-documented 5-level resolution order.
 *
 * 1. Project-local: .agent-style/RULES.md in cwd or any parent.
 * 2. Package bundle: node_modules/agent-style/data/RULES.md (or ../data/RULES.md
 *    from this file when running from the source tree).
 * 3. `agent-style rules` subcommand output (child process).
 * 4. Pinned raw URL fallback at the current package version (10s timeout).
 * 5. Hard fail with an actionable error.
 *
 * Both Python and Node emit rules_source "package-bundle" when loading from
 * their own bundle, so the parity oracle never sees ecosystem-specific strings.
 */

const fs = require('fs');
const path = require('path');
const https = require('https');
const { execFileSync } = require('child_process');

const { version: PACKAGE_VERSION } = require('../../package.json');

const RAW_URL_TEMPLATE =
  'https://raw.githubusercontent.com/yzhao062/agent-style/v{version}/RULES.md';

class RulesLoadError extends Error {
  constructor(msg) {
    super(msg);
    this.name = 'RulesLoadError';
  }
}

/**
 * Load and parse RULES.md via the documented resolution order.
 * @param {object} [opts]
 * @param {string} [opts.projectRoot=process.cwd()] Starting dir for project-local search.
 * @param {boolean} [opts.preferProjectLocal=true] Try project-local first.
 * @param {string} [opts.packageVersion] Override the version used in the raw URL.
 * @returns {{text: string, rules: Rule[], rulesSource: string, sourcePath: string | null}}
 */
function loadRules(opts = {}) {
  const projectRoot = opts.projectRoot || process.cwd();
  const preferProjectLocal = opts.preferProjectLocal !== false;
  const packageVersion = opts.packageVersion || PACKAGE_VERSION;
  const attempts = [];

  if (preferProjectLocal) {
    const local = _findProjectLocal(projectRoot);
    if (local) {
      const text = fs.readFileSync(local, 'utf8');
      return {
        text,
        rules: parseRules(text),
        rulesSource: 'project-local',
        sourcePath: local,
      };
    }
    attempts.push(['project-local', 'not found']);
  }

  // Step 2: package bundle
  try {
    const bundlePath = path.resolve(__dirname, '..', '..', 'data', 'RULES.md');
    if (fs.existsSync(bundlePath)) {
      const text = fs.readFileSync(bundlePath, 'utf8');
      return {
        text,
        rules: parseRules(text),
        rulesSource: 'package-bundle',
        sourcePath: bundlePath,
      };
    }
    attempts.push(['package-bundle', `not found at ${bundlePath}`]);
  } catch (err) {
    attempts.push(['package-bundle', err.message]);
  }

  // Step 3: agent-style rules subcommand
  try {
    const stdout = execFileSync('agent-style', ['rules'], {
      encoding: 'utf8',
      timeout: 15000,
    });
    if (stdout && stdout.includes('RULE-')) {
      return {
        text: stdout,
        rules: parseRules(stdout),
        rulesSource: 'subcommand',
        sourcePath: null,
      };
    }
  } catch (_err) {
    attempts.push(['subcommand', 'agent-style rules not on PATH or failed']);
  }

  // Step 4: pinned raw URL fallback
  if (packageVersion) {
    const url = RAW_URL_TEMPLATE.replace('{version}', packageVersion);
    try {
      const text = _fetchSync(url, 10000);
      if (text && text.includes('RULE-')) {
        return {
          text,
          rules: parseRules(text),
          rulesSource: 'raw-url',
          sourcePath: url,
        };
      }
    } catch (err) {
      attempts.push([`raw-url (${url})`, err.message]);
    }
  }

  // Step 5: hard fail
  const summary = attempts.map(([step, detail]) => `${step}: ${detail}`).join('; ');
  throw new RulesLoadError(
    'RULES.md not found via any resolution step. ' +
    'Install agent-style via `pip install agent-style` or `npm install -g agent-style`, ' +
    'or place RULES.md at .agent-style/RULES.md in this project. ' +
    `Tried: ${summary}`
  );
}

function _findProjectLocal(projectRoot) {
  let here = path.resolve(projectRoot);
  let prev = null;
  while (here && here !== prev) {
    const candidate = path.join(here, '.agent-style', 'RULES.md');
    if (fs.existsSync(candidate)) return candidate;
    prev = here;
    here = path.dirname(here);
  }
  return null;
}

// Synchronous HTTP GET with timeout. Uses an atomic spawnSync call via a small
// child-process helper so the main loader stays sync-returning.
function _fetchSync(url, timeoutMs) {
  const result = execFileSync(
    process.execPath,
    [
      '-e',
      `const https = require('https');
       const req = https.get(${JSON.stringify(url)}, { timeout: ${timeoutMs} }, (res) => {
         if (res.statusCode !== 200) { process.exit(1); }
         let data = '';
         res.setEncoding('utf8');
         res.on('data', (c) => { data += c; });
         res.on('end', () => { process.stdout.write(data); });
       });
       req.on('error', () => process.exit(2));
       req.on('timeout', () => { req.destroy(); process.exit(3); });`
    ],
    { encoding: 'utf8', timeout: timeoutMs + 5000 }
  );
  return result;
}

// ---------- Rule parsing ---------------------------------------------------

const RULE_HEADING_RE = /^####\s+(RULE-[0-9A-I]+):\s*(.+?)\s*$/gm;

function parseRules(text) {
  const headings = [];
  let m;
  while ((m = RULE_HEADING_RE.exec(text)) !== null) {
    headings.push({ index: m.index, length: m[0].length, id: m[1], title: m[2].trim() });
  }
  RULE_HEADING_RE.lastIndex = 0;
  if (headings.length === 0) return [];

  const rules = [];
  for (let i = 0; i < headings.length; i++) {
    const h = headings[i];
    const end = i + 1 < headings.length ? headings[i + 1].index : text.length;
    const block = text.slice(h.index, end);
    const severity = _firstMatch(block, /^-\s*\*\*severity\*\*:\s*([a-z]+)/im, '').toLowerCase();
    const scope = _firstMatch(block, /^-\s*\*\*scope\*\*:\s*(.+)$/im, '');
    const source = _firstMatch(block, /^-\s*\*\*source\*\*:\s*(.+)$/im, '');
    const directive = _firstMatch(
      block,
      /^#####\s+Directive\s*$([\s\S]*?)^#####/m,
      ''
    ).trim();
    const rationale = _firstMatch(
      block,
      /^#####\s+Rationale for AI Agent\s*$([\s\S]*?)(?=^####|$)/m,
      ''
    ).trim();
    rules.push({
      id: h.id,
      title: h.title,
      severity,
      scope: scope.trim(),
      source: source.trim(),
      directive,
      bad_good_pairs: [],
      rationale,
    });
  }
  return rules;
}

function _firstMatch(block, re, fallback) {
  const m = block.match(re);
  return m ? m[1] : fallback;
}

module.exports = { loadRules, parseRules, RulesLoadError };
