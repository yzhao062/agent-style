// SPDX-License-Identifier: MIT
'use strict';
/**
 * agent-style CLI entry point (Node). Mirrors agent_style.cli in Python.
 */

const { Registry, RegistryError } = require('./registry');
const { enable, disable, canonicalJson } = require('./installer');
const { audit: reviewAudit, compare: reviewCompare, RulesLoadError } = require('./review');
const { checkHostAndRaise, PolishNotAvailableError } = require('./review/polish');
const VERSION = require('../package.json').version;

const HELP = `agent-style: install and manage The Elements of Agent Style writing ruleset for AI agents.

Usage:
  agent-style <command> [options]

Commands:
  rules                          Print bundled RULES.md to stdout
  path                           Print bundled data directory path
  list-tools                     List supported tools and install modes
  enable <tool> [flags]          Enable agent-style for a tool (safe-append)
  disable <tool> [flags]         Remove agent-style for a tool
  review <file> [flags]          Review prose against agent-style rules
  --version                      Print version and exit
  --help                         Print this help

Flags (for enable/disable):
  --dry-run                      Print planned actions without writing
  --json                         Emit canonical JSON output (sorted keys, LF, POSIX paths)

Flags (for review):
  --audit-only                   Deterministic audit; semantic rules skipped. Emits JSON.
  --mechanical-only              Strictest deterministic subset (parity oracle)
  --compare A B                  A/B compare two files; per-rule delta, no polish
  --polish                       Produce FILE.reviewed.md (requires skill host; errors otherwise)
  --json                         Emit canonical JSON output
`;

function parseArgs(argv) {
  const out = {
    command: null,
    tool: null,
    dryRun: false,
    json: false,
    showHelp: false,
    showVersion: false,
    // review-specific
    files: [],
    auditOnly: false,
    mechanicalOnly: false,
    compare: null,  // [A, B] when --compare is given
    polish: false,
  };
  if (argv.length === 0) {
    out.showHelp = true;
    return out;
  }
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--version' || a === '-V') { out.showVersion = true; return out; }
    if (a === '--help' || a === '-h') { out.showHelp = true; return out; }
    if (a === '--dry-run') { out.dryRun = true; continue; }
    if (a === '--json') { out.json = true; continue; }
    if (a === '--audit-only') { out.auditOnly = true; continue; }
    if (a === '--mechanical-only') { out.mechanicalOnly = true; continue; }
    if (a === '--polish') { out.polish = true; continue; }
    if (a === '--compare') {
      const A = argv[i + 1];
      const B = argv[i + 2];
      if (!A || !B || A.startsWith('-') || B.startsWith('-')) {
        process.stderr.write("error: --compare requires two file arguments\n");
        out.showHelp = true;
        return out;
      }
      out.compare = [A, B];
      i += 2;
      continue;
    }
    if (!out.command) { out.command = a; continue; }
    if ((out.command === 'enable' || out.command === 'disable') && !out.tool) { out.tool = a; continue; }
    if (out.command === 'review') { out.files.push(a); continue; }
    // Unknown positional
    process.stderr.write(`error: unexpected argument '${a}'\n`);
    out.showHelp = true;
    return out;
  }
  return out;
}

function printJsonResult(result) {
  process.stdout.write(canonicalJson(result));
  process.stdout.write('\n');
}

function printHumanResult(result, subcommand) {
  const tool = result.tool || '?';
  const mode = result.install_mode || '?';
  const manual = result.manual_step_required === true;
  const actions = result.actions || [];
  if (manual) {
    process.stdout.write(`manual step required: ${tool} (${mode}) prepared, but needs a user action\n`);
  } else {
    process.stdout.write(`agent-style ${subcommand} ${tool} (${mode}): `);
    process.stdout.write(actions.length > 0 ? 'ok\n' : 'no changes\n');
  }
  for (const action of actions) {
    const op = action.op || '?';
    const p = action.path || '?';
    if (op === 'print-prompt') {
      process.stderr.write(`  action: ${op} ${p} (prompt body printed to stdout below)\n`);
    } else if (op === 'print-snippet') {
      const snippet = action.snippet || '';
      process.stderr.write(`  action: ${op} ${p}\n`);
      process.stderr.write('  add this to your config:\n');
      for (const line of snippet.split('\n')) process.stderr.write(`    ${line}\n`);
    } else {
      process.stderr.write(`  action: ${op} ${p}\n`);
    }
  }
}

function cmdRules(registry) {
  process.stdout.write(registry.readBundledRules());
  return 0;
}

function cmdPath(registry) {
  process.stdout.write(registry.dataDir + '\n');
  return 0;
}

function cmdListTools(registry) {
  for (const [name, spec] of Object.entries(registry.tools)) {
    const mode = spec.install_mode;
    let pathSummary;
    if (mode === 'skill-with-references') {
      pathSummary = (spec.target_groups || []).map((g) => g.target_path).join(' + ');
    } else {
      pathSummary = spec.target_path;
    }
    process.stdout.write(`${name.padEnd(18)}  ${mode.padEnd(22)}  ${pathSummary}\n`);
  }
  return 0;
}

function cmdEnable(args, registry) {
  let result;
  try {
    result = enable(args.tool, registry, '.', args.dryRun);
  } catch (exc) {
    if (exc instanceof RegistryError || exc.message) {
      process.stderr.write(`error: ${exc.message}\n`);
      return 2;
    }
    throw exc;
  }
  if (args.json) {
    printJsonResult(result);
  } else {
    printHumanResult(result, 'enable');
    if (result.install_mode === 'print-only') {
      const spec = registry.get(args.tool);
      const body = registry.readAdapter(spec.adapter_source);
      process.stdout.write(body);
    }
  }
  return 0;
}

function cmdReview(args, _registry) {
  if (args.polish) {
    try {
      checkHostAndRaise();
    } catch (exc) {
      if (exc instanceof PolishNotAvailableError) {
        process.stderr.write(`error: ${exc.message}\n`);
        return 2;
      }
      throw exc;
    }
  }

  if (args.compare) {
    const [fileA, fileB] = args.compare;
    let result;
    try {
      result = reviewCompare(fileA, fileB, { mechanicalOnly: args.mechanicalOnly, skillHost: false });
    } catch (exc) {
      process.stderr.write(`error: ${exc.message}\n`);
      return 2;
    }
    const payload = compareToPayload(result);
    process.stdout.write(canonicalReviewJson(payload));
    process.stdout.write('\n');
    return 0;
  }

  if (!args.files || args.files.length === 0) {
    process.stderr.write('error: review requires a FILE argument (or --compare A B)\n');
    return 2;
  }
  if (args.files.length > 1) {
    process.stderr.write(
      `error: review takes 1 file argument; got ${args.files.length}. ` +
      'For A/B compare, use --compare A B.\n'
    );
    return 2;
  }

  const filePath = args.files[0];
  let result;
  try {
    result = reviewAudit(filePath, {
      mechanicalOnly: args.mechanicalOnly,
      skillHost: false,
    });
  } catch (exc) {
    process.stderr.write(`error: ${exc.message}\n`);
    return 2;
  }
  const payload = auditToPayload(result);
  if (args.json || args.auditOnly || args.mechanicalOnly) {
    process.stdout.write(canonicalReviewJson(payload));
    process.stdout.write('\n');
  } else {
    printAuditHuman(payload);
  }
  return 0;
}

function auditToPayload(result) {
  // rules_path intentionally excluded from canonical JSON: it carries the
  // absolute filesystem path of the resolved RULES.md and differs between
  // pip and npm installs; including it would break --cli-parity byte identity.
  return {
    command: 'review',
    file: asPosix(result.file),
    rules_source: result.rulesSource,
    total_violations: result.totalViolations,
    rule_results: result.ruleResults.map((rr) => ({
      rule: rr.rule,
      severity: rr.severity,
      detector: rr.detector,
      status: rr.status,
      count: rr.count,
      note: rr.note || '',
      violations: (rr.violations || []).map((v) => ({
        line: v.line,
        column: v.column,
        excerpt: v.excerpt,
        detail: v.detail,
      })),
    })),
  };
}

function compareToPayload(result) {
  // rules_path intentionally excluded (see auditToPayload for rationale).
  return {
    command: 'review-compare',
    file_a: asPosix(result.fileA),
    file_b: asPosix(result.fileB),
    rules_source: result.rulesSource,
    total_a: result.totalA,
    total_b: result.totalB,
    per_rule_delta: Object.fromEntries(
      Object.entries(result.perRuleDelta).map(([k, v]) => [
        k,
        { a: v.a, b: v.b, delta: v.delta },
      ])
    ),
  };
}

function asPosix(p) {
  if (p === null || p === undefined) return null;
  let s = String(p).replace(/\\/g, '/');
  if (s.startsWith('./')) s = s.slice(2);
  return s;
}

// Stable-key JSON encoding with LF + 2-space indent (matches Python's canonical_json).
function canonicalReviewJson(obj) {
  return JSON.stringify(sortKeys(obj), null, 2);
}

function sortKeys(value) {
  if (Array.isArray(value)) return value.map(sortKeys);
  if (value && typeof value === 'object') {
    const out = {};
    for (const k of Object.keys(value).sort()) out[k] = sortKeys(value[k]);
    return out;
  }
  return value;
}

function printAuditHuman(payload) {
  process.stdout.write(`agent-style review ${payload.file}: ${payload.total_violations} violation(s)\n`);
  for (const rr of payload.rule_results) {
    if (rr.status === 'violation') {
      process.stdout.write(`  ${rr.rule} [${rr.severity}, ${rr.detector}]: ${rr.count}\n`);
      for (const v of rr.violations.slice(0, 5)) {
        process.stdout.write(`    L${v.line}:C${v.column}  ${v.detail}\n`);
      }
    }
  }
  const skipped = payload.rule_results.filter((rr) => rr.status === 'skipped').length;
  if (skipped > 0) {
    process.stdout.write(`  (${skipped} rule(s) skipped; run via a skill host for semantic coverage)\n`);
  }
}

function cmdDisable(args, registry) {
  let result;
  try {
    result = disable(args.tool, registry, '.', args.dryRun);
  } catch (exc) {
    if (exc instanceof RegistryError || exc.message) {
      process.stderr.write(`error: ${exc.message}\n`);
      return 2;
    }
    throw exc;
  }
  if (args.json) {
    printJsonResult(result);
  } else {
    printHumanResult(result, 'disable');
    if (result.message) {
      process.stderr.write(`error: ${result.message}\n`);
    }
  }
  // If the installer refused to disable (fail-closed on drift or missing-manifest-with-targets),
  // `enabled: true` remains in the result. Propagate that as a non-zero exit so shell callers
  // and CI pipelines see the partial state.
  if (result.enabled === true) {
    return 2;
  }
  return 0;
}

function main(argv) {
  const args = parseArgs(argv);
  if (args.showVersion) {
    process.stdout.write(`agent-style ${VERSION}\n`);
    return 0;
  }
  if (args.showHelp) {
    process.stdout.write(HELP);
    return 0;
  }
  if (!args.command) {
    process.stderr.write('error: no command specified\n\n' + HELP);
    return 2;
  }
  let registry;
  try {
    registry = new Registry();
  } catch (exc) {
    process.stderr.write(`registry error: ${exc.message}\n`);
    return 2;
  }
  if ((args.command === 'enable' || args.command === 'disable') && !args.tool) {
    process.stderr.write(`error: ${args.command} requires a <tool> argument\n`);
    return 2;
  }
  switch (args.command) {
    case 'rules': return cmdRules(registry);
    case 'path': return cmdPath(registry);
    case 'list-tools': return cmdListTools(registry);
    case 'enable': return cmdEnable(args, registry);
    case 'disable': return cmdDisable(args, registry);
    case 'review': return cmdReview(args, registry);
    default:
      process.stderr.write(`error: unknown command '${args.command}'\n\n` + HELP);
      return 2;
  }
}

module.exports = { main, parseArgs };
