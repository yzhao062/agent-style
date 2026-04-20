// SPDX-License-Identifier: MIT
'use strict';
/**
 * 5-mode install dispatcher. Mirrors agent_style.installer in Python.
 */

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const { upsertBlock, removeBlock, MarkerParseError } = require('./markers');
const { sign, verify, extractSignature, computeHash, OwnedFileError } = require('./owned_file');

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

function realpathSafe(p) {
  // Resolve symlinks on existing ancestors; return path even if the leaf does not exist.
  try {
    return fs.realpathSync(p);
  } catch (e) {
    if (e.code === 'ENOENT') {
      const parent = path.dirname(p);
      if (parent === p) return p;
      return path.join(realpathSafe(parent), path.basename(p));
    }
    throw e;
  }
}

function safeResolve(projectRoot, relPath) {
  // Resolve a project-relative path, rejecting traversal outside projectRoot.
  if (!relPath || typeof relPath !== 'string') {
    throw new Error(`invalid path: empty or non-string (${JSON.stringify(relPath)})`);
  }
  if (path.isAbsolute(relPath)) {
    throw new Error(`invalid path: absolute paths not allowed (${JSON.stringify(relPath)})`);
  }
  // Windows drive-qualified paths ("C:foo") — path.isAbsolute misses these on POSIX hosts
  if (relPath.length >= 2 && relPath[1] === ':') {
    throw new Error(`invalid path: drive-qualified paths not allowed (${JSON.stringify(relPath)})`);
  }
  const parts = relPath.replace(/\\/g, '/').split('/');
  if (parts.some((p) => p === '..')) {
    throw new Error(`invalid path: '..' components not allowed (${JSON.stringify(relPath)})`);
  }
  const root = realpathSafe(path.resolve(projectRoot));
  const joined = realpathSafe(path.join(root, relPath));
  const norm = (s) => (process.platform === 'win32' ? s.toLowerCase() : s);
  const rootN = norm(root);
  const joinedN = norm(joined);
  if (joinedN !== rootN && !joinedN.startsWith(rootN + path.sep)) {
    throw new Error(`invalid path: resolves outside project root (${JSON.stringify(relPath)})`);
  }
  return joined;
}

function canonicalHash(content) {
  // Canonical-byte-stream sha256 for manifest entries (owned-file contract).
  if (content === null || content === undefined) return null;
  return computeHash(content);
}

const SHA256_HEX_RE = /^[0-9a-f]{64}$/;

function loadAndValidateManifest(manifestAbs) {
  // Load manifest.json and validate every entry.
  // Returns {priorManifest, error}:
  //   - {priorManifest: null, error: null}   -> manifest absent
  //   - {priorManifest: null, error: "..."}  -> manifest present but malformed
  //   - {priorManifest: {path: entry}, ...} -> well-formed
  //
  // A valid entry requires: non-empty string `path`, `kind === "file"`,
  // `sha256` matching /^[0-9a-f]{64}$/. Missing or malformed hashes fail closed
  // rather than proving ownership or permitting deletion (CodexReview Round 2, Finding 1).
  const text = readOrNull(manifestAbs);
  if (text === null) return { priorManifest: null, error: null };
  let doc;
  try {
    doc = JSON.parse(text);
  } catch (e) {
    return { priorManifest: null, error: `JSON parse error: ${e.message}` };
  }
  if (!doc || typeof doc !== 'object' || Array.isArray(doc)) {
    return { priorManifest: null, error: 'manifest root is not a JSON object' };
  }
  const entries = doc.entries;
  if (!Array.isArray(entries)) {
    return { priorManifest: null, error: "'entries' is not a list" };
  }
  const map = {};
  for (let i = 0; i < entries.length; i++) {
    const e = entries[i];
    if (!e || typeof e !== 'object' || Array.isArray(e)) {
      return { priorManifest: null, error: `entries[${i}] is not a JSON object` };
    }
    const p = e.path;
    if (typeof p !== 'string' || !p) {
      return { priorManifest: null, error: `entries[${i}] missing non-empty string 'path'` };
    }
    if (e.kind !== 'file') {
      return {
        priorManifest: null,
        error: `entries[${i}] ('${p}') has kind='${e.kind}'; expected 'file'`,
      };
    }
    const sha = e.sha256;
    if (typeof sha !== 'string' || !SHA256_HEX_RE.test(sha)) {
      return {
        priorManifest: null,
        error: `entries[${i}] ('${p}') has invalid or missing sha256`,
      };
    }
    map[p] = e;
  }
  return { priorManifest: map, error: null };
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

function detectActiveSurfaces(projectRoot, registry) {
  const active = new Set();
  for (const [toolName, toolSpec] of Object.entries(registry.tools)) {
    if (toolSpec.install_mode === 'skill-with-references') continue;
    const tp = toolSpec.target_path;
    if (!tp) continue;
    if (fs.existsSync(path.join(projectRoot, tp))) {
      active.add(toolName);
    }
  }
  return active;
}

function iterBundledReferences(registry, referencesSource) {
  const base = path.join(registry.dataDir, referencesSource);
  if (!fs.existsSync(base) || !fs.statSync(base).isDirectory()) return [];
  const out = [];
  function walk(dir) {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const full = path.join(dir, entry.name);
      if (entry.isDirectory()) walk(full);
      else if (entry.isFile()) {
        const rel = path.relative(base, full).split(path.sep).join('/');
        out.push(rel);
      }
    }
  }
  walk(base);
  return out.sort();
}

function enableSkillWithReferences(tool, spec, registry, projectRoot, dryRun) {
  const skillSource = spec.skill_source;
  const referencesSource = spec.references_source;
  const targetGroups = spec.target_groups || [];
  const manualMsg = spec.manual_step_message || '';

  const activeSurfaces = detectActiveSurfaces(projectRoot, registry);

  // Deduplicate by target path; collect covered surfaces per target.
  const toWrite = new Map();
  for (const group of targetGroups) {
    const covered = (group.surfaces || []).filter((s) => activeSurfaces.has(s));
    if (covered.length === 0) continue;
    const existing = toWrite.get(group.target_path) || new Set();
    for (const s of covered) existing.add(s);
    toWrite.set(group.target_path, existing);
  }

  const actions = [];
  const manifestEntries = [];

  // No active surface at all -> print-only
  if (toWrite.size === 0) {
    const msg =
      'no skill-capable surface detected in this project. ' +
      'Enable `claude-code` or `anthropic-skill` first, ' +
      'or run `agent-style review <file>` from the CLI directly.';
    return {
      tool,
      install_mode: spec.install_mode,
      enabled: false,
      manual_step_required: true,
      actions: [
        {
          order: 0,
          op: 'print-message',
          path: '',
          content_sha256_before: null,
          content_sha256_after: null,
          message: msg,
        },
      ],
    };
  }

  // Load and validate any prior-install manifest BEFORE we touch the filesystem.
  // A malformed manifest (bad JSON or entry missing sha256 etc.) must fail closed
  // rather than granting ownership of user-owned files.
  const manifestPath = path.join(AGENT_STYLE_DIR, 'skills', tool, 'manifest.json');
  const manifestAbs = safeResolve(projectRoot, manifestPath);
  const { priorManifest, error: manifestError } = loadAndValidateManifest(manifestAbs);
  if (manifestError) {
    throw new Error(
      `refusing to enable '${tool}': manifest at '${toPosix(manifestPath)}' is malformed (${manifestError}); move it aside manually, then rerun \`agent-style enable style-review\``
    );
  }

  // Validate every skill target path BEFORE touching the filesystem. A malformed
  // tools.json entry must fail closed, not write to `../outside.md`.
  for (const tp of [...toWrite.keys()]) {
    safeResolve(projectRoot, tp);
  }

  function proveOwnership(relPath, current) {
    if (current === null) return;
    if (priorManifest === null) {
      throw new Error(
        `refusing to overwrite existing file at '${relPath}': no manifest found at '${toPosix(manifestPath)}'; move or rename that file and rerun \`agent-style enable style-review\``
      );
    }
    const entry = priorManifest[toPosix(relPath)];
    if (!entry) {
      throw new Error(
        `refusing to overwrite existing file at '${relPath}': not listed in manifest '${toPosix(manifestPath)}'; it is owned by another source`
      );
    }
    // Post-validation, `sha256` is guaranteed present and well-formed. Defensive
    // recheck: an entry without a matching sha256 must never prove ownership.
    const expected = entry.sha256;
    if (!expected || canonicalHash(current) !== expected) {
      throw new Error(
        `refusing to overwrite '${relPath}': content has drifted since the prior install (canonical sha256 mismatch); move your edits aside, run \`agent-style disable style-review\`, then rerun \`agent-style enable style-review\``
      );
    }
  }

  // Atomicity: first pass proves ownership for every target (throws on any conflict
  // BEFORE any write). Only after every target clears do we write in the second pass.
  const pendingWrites = []; // {relPath, body, covered}
  for (const targetPath of [...toWrite.keys()].sort()) {
    const covered = [...toWrite.get(targetPath)].sort();
    const absTarget = safeResolve(projectRoot, targetPath);

    if (absTarget.endsWith('.md') || absTarget.endsWith('.mdc')) {
      const body = registry.readAdapter(skillSource);
      const before = readOrNull(absTarget);
      proveOwnership(targetPath, before);
      pendingWrites.push({ relPath: targetPath, body, covered });
    } else {
      for (const rel of iterBundledReferences(registry, referencesSource)) {
        const relParts = rel.split('/');
        if (relParts.some((p) => p === '..') || path.isAbsolute(rel)) {
          throw new Error(`invalid bundled reference path '${rel}'; package data is corrupt`);
        }
        const srcAbs = path.join(registry.dataDir, referencesSource, rel);
        const dstRel = (targetPath.replace(/\/$/, '') + '/' + rel).split(path.sep).join('/');
        const dstAbs = safeResolve(projectRoot, dstRel);
        const body = fs.readFileSync(srcAbs, 'utf8');
        const before = readOrNull(dstAbs);
        proveOwnership(dstRel, before);
        pendingWrites.push({ relPath: dstRel, body, covered });
      }
    }
  }

  // Ownership passed for every target. Only now do we touch the filesystem.
  // Creating `.agent-style/RULES.md` here (not earlier) preserves the promise
  // that a refused enable leaves no partial install footprint.
  for (const a of ensureAgentStyleDir(projectRoot, registry, dryRun)) actions.push(a);

  // Second pass: actually write everything (or compute dry-run actions).
  for (const { relPath, body, covered } of pendingWrites) {
    const absPath = safeResolve(projectRoot, relPath);
    const before = readOrNull(absPath);
    const beforeHash = canonicalHash(before);
    const afterHash = canonicalHash(body);
    if (beforeHash !== afterHash) {
      if (!dryRun) {
        fs.mkdirSync(path.dirname(absPath), { recursive: true });
        fs.writeFileSync(absPath, body, 'utf8');
      }
      actions.push({
        order: actions.length,
        op: 'owned-file-write',
        path: toPosix(relPath),
        content_sha256_before: beforeHash,
        content_sha256_after: afterHash,
        covered_surfaces: covered,
      });
    }
    manifestEntries.push({
      path: toPosix(relPath),
      kind: 'file',
      sha256: afterHash,
      covered_surfaces: covered,
    });
  }

  // Write the manifest.
  const manifestDoc = {
    schema_version: 1,
    tool,
    generated_by: `agent-style ${VERSION}`,
    entries: manifestEntries.slice().sort((a, b) => (a.path < b.path ? -1 : a.path > b.path ? 1 : 0)),
  };
  const manifestBody = JSON.stringify(sortKeysDeep(manifestDoc), null, 2) + '\n';
  const before = readOrNull(manifestAbs);
  const beforeHash = canonicalHash(before);
  const afterHash = canonicalHash(manifestBody);
  if (beforeHash !== afterHash) {
    if (!dryRun) {
      fs.mkdirSync(path.dirname(manifestAbs), { recursive: true });
      fs.writeFileSync(manifestAbs, manifestBody, 'utf8');
    }
    actions.push({
      order: actions.length,
      op: 'manifest-write',
      path: toPosix(manifestPath),
      content_sha256_before: beforeHash,
      content_sha256_after: afterHash,
    });
  }

  // Emit print-message actions for tools the user has enabled that are not
  // covered by any target_group (so they see the CLI fallback guidance).
  const coveredSurfacesAll = new Set();
  for (const s of toWrite.values()) for (const x of s) coveredSurfacesAll.add(x);
  const uncovered = [...activeSurfaces].filter((s) => !coveredSurfacesAll.has(s)).sort();
  if (uncovered.length > 0 && manualMsg) {
    for (const uncoveredTool of uncovered) {
      actions.push({
        order: actions.length,
        op: 'print-message',
        path: '',
        content_sha256_before: null,
        content_sha256_after: null,
        message: manualMsg.replace('{tool}', uncoveredTool),
      });
    }
  }

  return {
    tool,
    install_mode: spec.install_mode,
    enabled: true,
    manual_step_required: false,
    actions,
  };
}

function sortKeysDeep(value) {
  if (Array.isArray(value)) return value.map(sortKeysDeep);
  if (value && typeof value === 'object') {
    const out = {};
    for (const k of Object.keys(value).sort()) out[k] = sortKeysDeep(value[k]);
    return out;
  }
  return value;
}

const ENABLE_DISPATCH = {
  'import-marker': enableImportMarker,
  'append-block': enableAppendBlock,
  'owned-file': enableOwnedFile,
  'multi-file-required': enableMultiFileRequired,
  'print-only': enablePrintOnly,
  'skill-with-references': enableSkillWithReferences,
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

function disableSkillWithReferences(tool, spec, projectRoot, dryRun) {
  // Fail-closed disable driven by the manifest; validates every path; never
  // delegates deletion to raw relpaths from the manifest.
  const manifestPath = path.join(AGENT_STYLE_DIR, 'skills', tool, 'manifest.json');
  const manifestAbs = safeResolve(projectRoot, manifestPath);
  const actions = [];
  const drifted = [];
  const nonEmptyDirs = [];

  const targetGroups = spec.target_groups || [];
  // Validate every declared target path up-front (schema-level safety).
  for (const group of targetGroups) {
    safeResolve(projectRoot, group.target_path);
  }

  const { priorManifest, error: manifestError } = loadAndValidateManifest(manifestAbs);
  if (manifestError) {
    // Malformed manifest (bad JSON or malformed entry). Fail closed: leave the
    // manifest and every target in place; emit an actionable message.
    return {
      tool,
      install_mode: spec.install_mode,
      enabled: true,
      manual_step_required: true,
      actions: [],
      drifted: [],
      non_empty_directories: [],
      message:
        `refusing to disable '${tool}': manifest at '${toPosix(manifestPath)}' is malformed ` +
        `(${manifestError}); inspect and repair or remove manually`,
    };
  }
  if (priorManifest === null) {
    // No manifest. Scan declared targets; if any still exist, fail closed.
    const existingTargets = [];
    for (const group of targetGroups) {
      const abs = safeResolve(projectRoot, group.target_path);
      if (!fs.existsSync(abs)) continue;
      const st = fs.statSync(abs);
      if (st.isFile()) existingTargets.push(group.target_path);
      else if (st.isDirectory() && fs.readdirSync(abs).length > 0) existingTargets.push(group.target_path);
    }
    if (existingTargets.length > 0) {
      return {
        tool,
        install_mode: spec.install_mode,
        enabled: true,
        manual_step_required: true,
        actions: [],
        drifted: [],
        non_empty_directories: [],
        message:
          `refusing to disable '${tool}': manifest missing at '${toPosix(manifestPath)}' but target files still exist: ` +
          JSON.stringify(existingTargets.sort()) +
          '; inspect and remove manually, or restore the manifest and rerun',
      };
    }
    return {
      tool,
      install_mode: spec.install_mode,
      enabled: false,
      manual_step_required: false,
      actions: [],
      drifted: [],
      non_empty_directories: [],
    };
  }

  // Manifest is present and every entry's schema is already validated.
  // Re-check each path's safety containment.
  const entries = Object.values(priorManifest);
  for (const entry of entries) {
    try {
      safeResolve(projectRoot, entry.path);
    } catch (err) {
      throw new Error(
        `refusing to disable '${tool}': manifest contains an unsafe path ('${entry.path}'): ${err.message}`
      );
    }
  }

  // Coverage check: every declared target_group target that currently exists on
  // disk must be covered by at least one manifest entry. An uncovered active
  // target means the manifest doesn't match reality — disable would leave
  // orphan installed files behind while claiming success. Catches `entries: []`
  // and partial/stale manifests alike (CodexReview Round 3, Finding 1).
  const manifestPaths = new Set(Object.keys(priorManifest));
  const uncoveredTargets = [];
  for (const group of targetGroups) {
    const tp = group.target_path;
    const absTarget = safeResolve(projectRoot, tp);
    const tpPosix = toPosix(tp);
    if (!fs.existsSync(absTarget)) continue;
    const st = fs.statSync(absTarget);
    if (st.isFile()) {
      if (!manifestPaths.has(tpPosix)) uncoveredTargets.push(tp);
    } else if (st.isDirectory()) {
      const prefix = tpPosix.replace(/\/$/, '') + '/';
      const coveredAny = [...manifestPaths].some((p) => p.startsWith(prefix));
      if (!coveredAny && fs.readdirSync(absTarget).length > 0) uncoveredTargets.push(tp);
    }
  }
  if (uncoveredTargets.length > 0) {
    return {
      tool,
      install_mode: spec.install_mode,
      enabled: true,
      manual_step_required: true,
      actions: [],
      drifted: [],
      non_empty_directories: [],
      message:
        `refusing to disable '${tool}': declared target(s) ` +
        JSON.stringify(uncoveredTargets.slice().sort()) +
        ` exist on disk but are not listed in manifest '${toPosix(manifestPath)}'; ` +
        'inspect and remove manually, or restore a complete manifest and rerun',
    };
  }

  // Remove manifest-owned files whose canonical hash matches; record drift.
  const removalActions = []; // {_abs, action}
  for (const entry of entries) {
    const relPath = entry.path;
    const absPath = safeResolve(projectRoot, relPath);
    const expectedHash = entry.sha256; // validated as 64-hex above
    const current = readOrNull(absPath);
    if (current === null) {
      removalActions.push({
        _abs: absPath,
        action: {
          order: 0,
          op: 'owned-file-remove',
          path: toPosix(relPath),
          content_sha256_before: null,
          content_sha256_after: null,
          noop: true,
        },
      });
      continue;
    }
    if (canonicalHash(current) !== expectedHash) {
      drifted.push(relPath);
      continue;
    }
    removalActions.push({
      _abs: absPath,
      action: {
        order: 0,
        op: 'owned-file-remove',
        path: toPosix(relPath),
        content_sha256_before: canonicalHash(current),
        content_sha256_after: null,
      },
    });
  }

  // If any file drifted, fail closed: do NOT delete anything, keep manifest intact.
  if (drifted.length > 0) {
    return {
      tool,
      install_mode: spec.install_mode,
      enabled: true,
      manual_step_required: true,
      actions: [],
      drifted: drifted.sort(),
      non_empty_directories: [],
      message:
        `refusing to disable '${tool}': ${drifted.length} file(s) have been edited since install ` +
        '(canonical sha256 mismatch). Manifest and targets are left in place. ' +
        'Move your edits aside, then rerun `agent-style disable style-review`.',
    };
  }

  // No drift: apply removals.
  for (const { _abs, action } of removalActions) {
    if (!action.noop && !dryRun) fs.unlinkSync(_abs);
    action.order = actions.length;
    actions.push(action);
  }

  // Remove directory targets from target_groups if empty after file-by-file cleanup.
  for (const group of targetGroups) {
    const absTarget = safeResolve(projectRoot, group.target_path);
    if (absTarget.endsWith('.md') || absTarget.endsWith('.mdc') || absTarget.endsWith('.json')) continue;
    if (!fs.existsSync(absTarget)) continue;
    const st = fs.statSync(absTarget);
    if (!st.isDirectory()) continue;
    const stack = [];
    function walk(d) {
      // Containment guard: never walk outside project root
      safeResolve(projectRoot, path.relative(projectRoot, d));
      for (const entry of fs.readdirSync(d, { withFileTypes: true })) {
        if (entry.isDirectory()) walk(path.join(d, entry.name));
      }
      stack.push(d);
    }
    walk(absTarget);
    for (const d of stack) {
      const remaining = fs.readdirSync(d);
      if (remaining.length === 0) {
        if (!dryRun) fs.rmdirSync(d);
        actions.push({
          order: actions.length,
          op: 'owned-directory-remove',
          path: toPosix(path.relative(projectRoot, d)),
          content_sha256_before: null,
          content_sha256_after: null,
        });
      } else {
        nonEmptyDirs.push(toPosix(path.relative(projectRoot, d)));
      }
    }
  }

  // Remove manifest last. Re-read once more for the canonical hash before deletion;
  // safe because nothing else wrote to it during disable.
  const manifestTextForHash = readOrNull(manifestAbs);
  if (!dryRun) {
    try { fs.unlinkSync(manifestAbs); } catch (e) { if (e.code !== 'ENOENT') throw e; }
  }
  actions.push({
    order: actions.length,
    op: 'manifest-remove',
    path: toPosix(manifestPath),
    content_sha256_before: canonicalHash(manifestTextForHash),
    content_sha256_after: null,
  });

  // Cleanup containing skills dir if empty.
  const skillsRoot = path.dirname(manifestAbs);
  if (fs.existsSync(skillsRoot) && fs.statSync(skillsRoot).isDirectory()) {
    try {
      const remaining = fs.readdirSync(skillsRoot);
      if (remaining.length === 0) {
        if (!dryRun) fs.rmdirSync(skillsRoot);
        actions.push({
          order: actions.length,
          op: 'owned-directory-remove',
          path: toPosix(path.relative(projectRoot, skillsRoot)),
          content_sha256_before: null,
          content_sha256_after: null,
        });
      }
    } catch { /* ok */ }
  }

  return {
    tool,
    install_mode: spec.install_mode,
    enabled: false,
    manual_step_required: false,
    actions,
    drifted: [],
    non_empty_directories: [...new Set(nonEmptyDirs)].sort(),
  };
}

const DISABLE_DISPATCH = {
  'import-marker': disableMarkerBased,
  'append-block': disableMarkerBased,
  'owned-file': disableOwnedFile,
  'multi-file-required': disableMultiOrPrint,
  'print-only': disableMultiOrPrint,
  'skill-with-references': disableSkillWithReferences,
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
