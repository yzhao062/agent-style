// SPDX-License-Identifier: MIT
'use strict';
/**
 * Registry: loads and validates tools.json; exposes bundled data paths.
 * Mirrors agent_style.registry in the Python package.
 */

const fs = require('fs');
const path = require('path');

const REQUIRED_FIELDS = ['install_mode', 'target_path', 'adapter_source', 'load_class'];
const VALID_MODES = new Set([
  'import-marker',
  'append-block',
  'owned-file',
  'multi-file-required',
  'print-only',
]);

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
      for (const f of REQUIRED_FIELDS) {
        if (!(f in spec)) {
          throw new RegistryError(
            `tool '${name}' in tools.json is missing required field '${f}'`
          );
        }
      }
      if (!VALID_MODES.has(spec.install_mode)) {
        throw new RegistryError(
          `tool '${name}' has invalid install_mode '${spec.install_mode}'`
        );
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
