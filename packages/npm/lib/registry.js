// SPDX-License-Identifier: MIT
'use strict';
/**
 * Registry: loads and validates tools.json; exposes bundled data paths.
 * Mirrors agent_style.registry in the Python package.
 */

const fs = require('fs');
const path = require('path');

// Schema-1 legacy 5-mode required fields.
const LEGACY_REQUIRED_FIELDS = ['install_mode', 'target_path', 'adapter_source', 'load_class'];

// Schema-1 skill-with-references required fields (mode-specific, backward-compatible).
const SKILL_REQUIRED_FIELDS = [
  'install_mode',
  'skill_source',
  'references_source',
  'target_groups',
  'manual_step_message',
];
// Fields forbidden in skill-with-references (they belong to the legacy 5-mode shape).
const SKILL_FORBIDDEN_FIELDS = ['target_path', 'adapter_source', 'load_class'];

const LEGACY_MODES = new Set([
  'import-marker',
  'append-block',
  'owned-file',
  'multi-file-required',
  'print-only',
]);
const SKILL_MODES = new Set(['skill-with-references']);
const VALID_MODES = new Set([...LEGACY_MODES, ...SKILL_MODES]);

class RegistryError extends Error {
  constructor(msg) {
    super(msg);
    this.name = 'RegistryError';
  }
}

class Registry {
  constructor() {
    this.dataDir = this._findDataDir();
    this.toolsJsonPath = path.join(this.dataDir, 'tools.json');
    this.rulesMdPath = path.join(this.dataDir, 'RULES.md');
    const raw = JSON.parse(fs.readFileSync(this.toolsJsonPath, 'utf8'));
    this.schemaVersion = Number(raw.schema_version || 0);
    this.agentStyleVersion = String(raw.agent_style_version || '');
    this.tools = raw.tools || {};
    this._validate();
  }

  _findDataDir() {
    // __dirname is packages/npm/lib; data lives at packages/npm/data
    const candidate = path.join(__dirname, '..', 'data');
    if (!fs.existsSync(candidate) || !fs.statSync(candidate).isDirectory()) {
      throw new RegistryError(
        `bundled data directory not found at ${candidate}; is the package installed correctly?`
      );
    }
    return candidate;
  }

  _validate() {
    if (this.schemaVersion !== 1) {
      throw new RegistryError(
        `tools.json schema_version ${this.schemaVersion} not supported; expected 1`
      );
    }
    for (const [name, spec] of Object.entries(this.tools)) {
      const mode = spec.install_mode;
      if (!mode) {
        throw new RegistryError(`tool '${name}' in tools.json is missing 'install_mode'`);
      }
      if (!VALID_MODES.has(mode)) {
        throw new RegistryError(
          `tool '${name}' has invalid install_mode '${mode}'`
        );
      }
      const keys = new Set(Object.keys(spec));
      if (LEGACY_MODES.has(mode)) {
        for (const f of LEGACY_REQUIRED_FIELDS) {
          if (!keys.has(f)) {
            throw new RegistryError(
              `tool '${name}' uses install_mode '${mode}' and is missing required field '${f}'`
            );
          }
        }
        const forbiddenPresent = SKILL_REQUIRED_FIELDS.filter(
          (f) => f !== 'install_mode' && keys.has(f)
        );
        if (forbiddenPresent.length > 0) {
          throw new RegistryError(
            `tool '${name}' uses install_mode '${mode}' but has skill-mode-only fields: ${forbiddenPresent.join(', ')}`
          );
        }
      } else if (SKILL_MODES.has(mode)) {
        for (const f of SKILL_REQUIRED_FIELDS) {
          if (!keys.has(f)) {
            throw new RegistryError(
              `tool '${name}' uses install_mode '${mode}' and is missing required field '${f}'`
            );
          }
        }
        const forbiddenPresent = SKILL_FORBIDDEN_FIELDS.filter((f) => keys.has(f));
        if (forbiddenPresent.length > 0) {
          throw new RegistryError(
            `tool '${name}' uses install_mode '${mode}' but has legacy-mode-only fields: ${forbiddenPresent.join(', ')} (these belong to the 5-mode shape)`
          );
        }
        const groups = spec.target_groups;
        if (!Array.isArray(groups) || groups.length === 0) {
          throw new RegistryError(
            `tool '${name}': target_groups must be a non-empty list`
          );
        }
        // Surface names must resolve to legacy-mode tools (skill-mode tools cannot
        // host other skills by construction).
        const knownSurfaceTools = new Set();
        for (const [tn, ts] of Object.entries(this.tools)) {
          if (LEGACY_MODES.has(ts.install_mode)) knownSurfaceTools.add(tn);
        }
        const seenNormalized = new Map(); // normalized path -> first index
        for (let i = 0; i < groups.length; i++) {
          const g = groups[i];
          if (!g || typeof g !== 'object' || !('target_path' in g) || !('surfaces' in g)) {
            throw new RegistryError(
              `tool '${name}': target_groups[${i}] must have 'target_path' and 'surfaces'`
            );
          }
          const tp = g.target_path;
          if (typeof tp !== 'string' || tp.length === 0) {
            throw new RegistryError(
              `tool '${name}': target_groups[${i}].target_path must be a non-empty string`
            );
          }
          if (path.isAbsolute(tp)) {
            throw new RegistryError(
              `tool '${name}': target_groups[${i}].target_path '${tp}' must be relative, not absolute`
            );
          }
          // Windows drive-qualified paths ("C:foo")
          if (tp.length >= 2 && tp[1] === ':') {
            throw new RegistryError(
              `tool '${name}': target_groups[${i}].target_path '${tp}' must not be drive-qualified`
            );
          }
          const tpParts = tp.replace(/\\/g, '/').split('/');
          if (tpParts.some((p) => p === '..')) {
            throw new RegistryError(
              `tool '${name}': target_groups[${i}].target_path '${tp}' must not contain '..'`
            );
          }
          const surfaces = g.surfaces;
          if (!Array.isArray(surfaces) || surfaces.length === 0) {
            throw new RegistryError(
              `tool '${name}': target_groups[${i}].surfaces must be a non-empty list`
            );
          }
          for (let j = 0; j < surfaces.length; j++) {
            const s = surfaces[j];
            if (typeof s !== 'string' || s.length === 0) {
              throw new RegistryError(
                `tool '${name}': target_groups[${i}].surfaces[${j}] must be a non-empty string`
              );
            }
            if (!knownSurfaceTools.has(s)) {
              const known = [...knownSurfaceTools].sort();
              throw new RegistryError(
                `tool '${name}': target_groups[${i}].surfaces[${j}]='${s}' does not match any ` +
                `known non-skill tool; known surfaces are ${JSON.stringify(known)}`
              );
            }
          }
          // Normalize for uniqueness: strip leading `./` and collapse `//`.
          const norm = tpParts.filter((p) => p !== '' && p !== '.').join('/');
          if (seenNormalized.has(norm)) {
            throw new RegistryError(
              `tool '${name}': target_groups[${i}].target_path '${tp}' collides with ` +
              `target_groups[${seenNormalized.get(norm)}] after normalization; ` +
              'combine them into a single entry and merge the surfaces lists'
            );
          }
          seenNormalized.set(norm, i);
        }
      }
    }
  }

  get(tool) {
    if (!(tool in this.tools)) {
      throw new RegistryError(
        `unknown tool '${tool}'; run \`agent-style list-tools\` to see supported tools`
      );
    }
    return this.tools[tool];
  }

  readBundledRules() {
    return fs.readFileSync(this.rulesMdPath, 'utf8');
  }

  readAdapter(adapterSource) {
    return fs.readFileSync(path.join(this.dataDir, adapterSource), 'utf8');
  }
}

module.exports = { Registry, RegistryError };
