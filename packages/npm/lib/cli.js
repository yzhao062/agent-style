// SPDX-License-Identifier: MIT
'use strict';
/**
 * agent-style CLI entry point (Node). Mirrors agent_style.cli in Python.
 */

const { Registry, RegistryError } = require('./registry');
const { enable, disable, canonicalJson } = require('./installer');
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
  --version                      Print version and exit
  --help                         Print this help

Flags (for enable/disable):
  --dry-run                      Print planned actions without writing
  --json                         Emit canonical JSON output (sorted keys, LF, POSIX paths)
`;

function parseArgs(argv) {
  const out = { command: null, tool: null, dryRun: false, json: false, showHelp: false, showVersion: false };
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
    if (!out.command) { out.command = a; continue; }
    if ((out.command === 'enable' || out.command === 'disable') && !out.tool) { out.tool = a; continue; }
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
    process.stdout.write(`${name.padEnd(18)}  ${spec.install_mode.padEnd(22)}  ${spec.target_path}\n`);
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
  if (args.json) printJsonResult(result);
  else printHumanResult(result, 'disable');
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
    default:
      process.stderr.write(`error: unknown command '${args.command}'\n\n` + HELP);
      return 2;
  }
}

module.exports = { main, parseArgs };
