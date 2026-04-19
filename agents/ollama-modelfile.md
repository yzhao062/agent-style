<!-- SPDX-License-Identifier: CC-BY-4.0 -->
<!-- Adapter: Ollama Modelfile SYSTEM section -->
<!-- Target path: paste into SYSTEM directive of an Ollama Modelfile, then `ollama create <name> -f Modelfile` -->

# Ollama Modelfile — Writing Style Rules

🚧 Phase 1a placeholder. Full adapter content added in Phase 2a.

Ollama models load a `SYSTEM` section from the Modelfile. Create a model that embeds these rules:

```
FROM llama3.2
SYSTEM """
<paste the content of RULES.md here, or a compact subset>
"""
```

Then `ollama create eoas-writer -f Modelfile`. The model instance bakes the rules into its system prompt.

## Writing style (summary)

See [`RULES.md`](../RULES.md) for the canonical full version. Phase 2a populates this file with a compact system-prompt-sized version.
