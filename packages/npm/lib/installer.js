// SPDX-License-Identifier: MIT
'use strict';
/**
 * 5-mode install dispatcher. Mirrors agent_style.installer in Python.
 */

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const { upsertBlock, removeBlock, MarkerParseError } = require('./markers');
const { sign, verify, extractSignature, OwnedFileError } = require('./owned_file');

const AGENT_STYLE_DIR = '.agent-style';
const RULES_FILENAME = 'RULES.md';

const VERSION = require('../package.json').version;

function toPosix(p) {
  return p.split(path.sep).join('/');
}

function readOrNull(p) {
  try {
    return fs.readFileSync(p, 'utf8');
  } catch (e) {
    if (e.code === 'ENOENT') return null;
    throw e;
  }
}

function contentHash(content) {
  if (content === null || content === undefined) return null;
  return crypto.createHash('sha256').update(content, 'utf8').digest('hex');
}

function ensureAgentStyleDir(projectRoot, registry, dryRun) {
  const actions = [];
  const agentDir = path.join(projectRoot, AGENT_STYLE_DIR);
  const rulesTarget = path.join(agentDir, RULES_FILENAME);
  const bundledRules = registry.readBundledRules();
  const before = readOrNull(rulesTarget);
  if (before !== bundledRules) {
    if (!dryRun) {
      fs.mkdirSync(agentDir, { recursive: true });
      fs.writeFileSync(rulesTarget, bundledRules, { encoding: 'utf8' });
    }
    actions.push({
      order: actions.length,
      op: before === null ? 'create' : 'owned-file-write',
      path: toPosix(path.relative(projectRoot, rulesTarget)),
      content_sha256_before: contentHash(before),
      content_sha256_after: contentHash(bundledRules),
    });
  }
  return actions;
}

function copyBundledAdapter(projectRoot, registry, adapterSource, destRel, dryRun) {
  const agentDir = path.join(projectRoot, AGENT_STYLE_DIR);
  const dest = path.join(agentDir, destRel);
  const body = registry.readAdapter(adapterSource);
  const before = readOrNull(dest);
  if (before === body) {
    return null; // no action needed
  }
  if (!dryRun) {
    fs.mkdirSync(path.dirname(dest), { recursive: true });
    fs.writeFileSync(dest, body, { encoding: 'utf8' });
  }
  return {
    order: 0,
    op: 'owned-file-write',
    path: toPosix(path.relative(projectRoot, dest)),
    content_sha256_before: contentHash(before),
    content_sha256_after: contentHash(body),
  };
}

function enableImportMarker(tool, spec, registry, projectRoot, dryRun) {
  const actions = ensureAgentStyleDir(projectRoot, registry, dryRun);
  const adapterFilename = path.basename(spec.adapter_source);
  const adapterAction = copyBundledAdapter(projectRoot, registry, spec.adapter_source, adapterFilename, dryRun);
  if (adapterAction) {
    adapterAction.order = actions.length;
    actions.push(adapterAction);
  }
  const target = path.join(projectRoot, spec.target_path);
  const beforeText = readOrNull(target) || '';
  const [newText, op] = upsertBlock(beforeText, VERSION, spec.import_line);
  const beforeHash = beforeText ? contentHash(beforeText) : null;
  const afterHash = contentHash(newText);
  if (beforeHash !== afterHash) {
    if (!dryRun) {
      fs.mkdirSync(path.dirname(target) || '.', { recursive: true });
      fs.writeFileSync(target, newText, { encoding: 'utf8' });
    }
    actions.push({
      order: actions.length,
      op,
      path: toPosix(path.relative(projectRoot, target)),
      content_sha256_before: beforeHash,
      content_sha256_after: afterHash,
    });
  }
  return {
    tool,
    install_mode: spec.install_mode,
    enabled: true,
    manual_step_required: false,
    actions,
  };
}

function enableAppendBlock(tool, spec, registry, projectRoot, dryRun) {
  const actions = ensureAgentStyleDir(projectRoot, registry, dryRun);
  const target = path.join(projectRoot, spec.target_path);
  const beforeText = readOrNull(target) || '';
  const body = registry.readAdapter(spec.adapter_source);
  const [newText, op] = upsertBlock(beforeText, VERSION, body);
  const beforeHash = beforeText ? contentHash(beforeText) : null;
  const afterHash = contentHash(newText);
  if (beforeHash !== afterHash) {
    if (!dryRun) {
      fs.mkdirSync(path.dirname(target) || '.', { recursive: true });
      fs.writeFileSync(target, newText, { encoding: 'utf8' });
    }
    actions.push({
      order: actions.length,
      op,
      path: toPosix(path.relative(projectRoot, target)),
      content_sha256_before: beforeHash,
      content_sha256_after: afterHash,
    });
  }
  return {
    tool,
    install_mode: spec.install_mode,
    enabled: true,
    manual_step_required: false,
    actions,
  };
}

function enableOwnedFile(tool, spec, registry, projectRoot, dryRun) {
  const actions = ensureAgentStyleDir(projectRoot, registry, dryRun);
  const target = path.join(projectRoot, spec.target_path);
  const beforeText = readOrNull(target);
  const body = registry.readAdapter(spec.adapter_source);
  const signed = sign(body, VERSION);
  if (beforeText !== null) {
    if (extractSignature(beforeText) === null) {
      throw new Error(
        `refusing to overwrite non-agent-style file at '${target}'; move or rename that file and rerun \`agent-style enable\``
      );
    }
    try {
      verify(beforeText);
    } catch (exc) {
      throw new Error(
        `agent-style owned file at '${target}' has been edited since it was written: ${exc.message}; move your edits into a separate file, then rerun`
      );
    }
  }
  const beforeHash = beforeText ? contentHash(beforeText) : null;
  const afterHash = contentHash(signed);
  if (beforeHash !== afterHash) {
    if (!dryRun) {
      fs.mkdirSync(path.dirname(target) || '.', { recursive: true });
      fs.writeFileSync(target, signed, { encoding: 'utf8' });
    }
    actions.push({
      order: actions.length,
      op: 'owned-file-write',
      path: toPosix(path.relative(projectRoot, target)),
      content_sha256_before: beforeHash,
      content_sha256_after: afterHash,
    });
  }
  return {
    tool,
    install_mode: spec.install_mode,
    enabled: true,
    manual_step_required: false,
    actions,
  };
}

function enableMultiFileRequired(tool, spec, registry, projectRoot, dryRun) {
  const actions = ensureAgentStyleDir(projectRoot, registry, dryRun);
  const target = path.join(projectRoot, spec.target_path);
  const body = registry.readAdapter(spec.adapter_source);
  const beforeText = readOrNull(target);
  const beforeHash = contentHash(beforeText);
  const afterHash = contentHash(body);
  if (beforeHash !== afterHash) {
    if (!dryRun) {
      fs.mkdirSync(path.dirname(target) || '.', { recursive: true });
      fs.writeFileSync(target, body, { encoding: 'utf8' });
    }
    actions.push({
      order: actions.length,
      op: 'owned-file-write',
      path: toPosix(path.relative(projectRoot, target)),
      content_sha256_before: beforeHash,
      content_sha256_after: afterHash,
    });
  }
  const snippet = spec.second_file_snippet || '';
  actions.push({
    order: actions.length,
    op: 'print-snippet',
    path: toPosix(path.relative(projectRoot, target)),
    content_sha256_before: null,
    content_sha256_after: contentHash(snippet),
    snippet,
  });
  return {
    tool,
    install_mode: spec.install_mode,
    enabled: false,
    manual_step_required: true,
    actions,
  };
}

function enablePrintOnly(tool, spec, registry, projectRoot, dryRun) {
  const actions = ensureAgentStyleDir(projectRoot, registry, dryRun);
  const target = path.join(projectRoot, spec.target_path);
  const body = registry.readAdapter(spec.adapter_source);
  const beforeText = readOrNull(target);
  const beforeHash = contentHash(beforeText);
  const afterHash = contentHash(body);
  if (beforeHash !== afterHash) {
    if (!dryRun) {
      fs.mkdirSync(path.dirname(target) || '.', { recursive: true });
      fs.writeFileSync(target, body, { encoding: 'utf8' });
    }
    actions.push({
      order: actions.length,
      op: 'owned-file-write',
      path: toPosix(path.relative(projectRoot, target)),
      content_sha256_before: beforeHash,
      content_sha256_after: afterHash,
    });
  }
  actions.push({
    order: actions.length,
    op: 'print-prompt',
    path: toPosix(path.relative(projectRoot, target)),
    content_sha256_before: null,
    content_sha256_after: contentHash(body),
  });
  return {
    tool,
    install_mode: spec.install_mode,
    enabled: false,
    manual_step_required: true,
    actions,
  };
}

const ENABLE_DISPATCH = {
  'import-marker': enableImportMarker,
  'append-block': enableAppendBlock,
  'owned-file': enableOwnedFile,
  'multi-file-required': enableMultiFileRequired,
  'print-only': enablePrintOnly,
};

function enable(tool, registry, projectRoot = '.', dryRun = false) {
  const spec = registry.get(tool);
  const fn = ENABLE_DISPATCH[spec.install_mode];
  return fn(tool, spec, registry, projectRoot, dryRun);
}

function disableMarkerBased(tool, spec, projectRoot, dryRun) {
  const actions = [];
  const target = path.join(projectRoot, spec.target_path);
  const beforeText = readOrNull(target);
  if (beforeText === null) {
    return { tool, install_mode: spec.install_mode, enabled: false, manual_step_required: false, actions: [] };
  }
  let newText, op;
  try {
    [newText, op] = removeBlock(beforeText);
  } catch (exc) {
    throw new Error(
      `refusing to modify '${target}': agent-style marker region is tampered or ambiguous: ${exc.message}; inspect the file and repair manually`
    );
  }
  if (op === 'noop') {
    return { tool, install_mode: spec.install_mode, enabled: false, manual_step_required: false, actions: [] };
  }
  if (!dryRun) {
    fs.writeFileSync(target, newText, { encoding: 'utf8' });
  }
  actions.push({
    order: 0,
    op: 'remove-marker',
    path: toPosix(path.relative(projectRoot, target)),
    content_sha256_before: contentHash(beforeText),
    content_sha256_after: contentHash(newText),
  });
  return { tool, install_mode: spec.install_mode, enabled: false, manual_step_required: false, actions };
}

function disableOwnedFile(tool, spec, projectRoot, dryRun) {
  const actions = [];
  const target = path.join(projectRoot, spec.target_path);
  const beforeText = readOrNull(target);
  if (beforeText === null) {
    return { tool, install_mode: spec.install_mode, enabled: false, manual_step_required: false, actions: [] };
  }
  if (extractSignature(beforeText) === null) {
    throw new Error(
      `refusing to delete '${target}': not agent-style-owned (no signature found); inspect the file and remove manually if intended`
    );
  }
  try {
    verify(beforeText);
  } catch (exc) {
    throw new Error(
      `refusing to delete '${target}': ${exc.message}; inspect the file and repair manually`
    );
  }
  if (!dryRun) fs.unlinkSync(target);
  actions.push({
    order: 0,
    op: 'owned-file-remove',
    path: toPosix(path.relative(projectRoot, target)),
    content_sha256_before: contentHash(beforeText),
    content_sha256_after: null,
  });
  return { tool, install_mode: spec.install_mode, enabled: false, manual_step_required: false, actions };
}

function disableMultiOrPrint(tool, spec, projectRoot, dryRun) {
  const actions = [];
  const target = path.join(projectRoot, spec.target_path);
  const beforeText = readOrNull(target);
  if (beforeText !== null) {
    if (!dryRun) fs.unlinkSync(target);
    actions.push({
      order: 0,
      op: 'owned-file-remove',
      path: toPosix(path.relative(projectRoot, target)),
      content_sha256_before: contentHash(beforeText),
      content_sha256_after: null,
    });
  }
  return { tool, install_mode: spec.install_mode, enabled: false, manual_step_required: false, actions };
}

const DISABLE_DISPATCH = {
  'import-marker': disableMarkerBased,
  'append-block': disableMarkerBased,
  'owned-file': disableOwnedFile,
  'multi-file-required': disableMultiOrPrint,
  'print-only': disableMultiOrPrint,
};

function disable(tool, registry, projectRoot = '.', dryRun = false) {
  const spec = registry.get(tool);
  const fn = DISABLE_DISPATCH[spec.install_mode];
  return fn(tool, spec, projectRoot, dryRun);
}

function canonicalJson(result) {
  const actions = [...(result.actions || [])];
  actions.sort((a, b) => {
    const pa = a.path || '';
    const pb = b.path || '';
    if (pa !== pb) return pa < pb ? -1 : 1;
    const oa = a.op || '';
    const ob = b.op || '';
    if (oa !== ob) return oa < ob ? -1 : 1;
    return (a.order || 0) - (b.order || 0);
  });
  // Sort keys lexicographically by rebuilding each action object with sorted keys.
  const sortedActions = actions.map((a) => {
    const out = {};
    for (const k of Object.keys(a).sort()) out[k] = a[k];
    return out;
  });
  const top = { ...result, actions: sortedActions };
  // Sort top-level keys too
  const sortedTop = {};
  for (const k of Object.keys(top).sort()) sortedTop[k] = top[k];
  return JSON.stringify(sortedTop, null, 2);
}

module.exports = { enable, disable, canonicalJson };
