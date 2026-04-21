# agent-style sanity benchmark: task list

Ten concrete prose-writing tasks. The v0.3.0 composition mixes short-form technical writing (PR descriptions, commit messages, design-doc sections) with long-form academic and formal writing (paper abstract / methods / experiments / related-work, grant-proposal specific aim, product description). Each task has the same prompt regardless of whether agent-style is loaded or not (baseline vs treatment).

The v0.2.0 task set (5 PR descriptions + 3 design-doc sections + 2 commit messages) showed ceiling effects on modern frontier models because modern CLI-coding-agent models already write clean short technical prose. The v0.3.0 set retains 4 short-form canaries to confirm that loading the ruleset does not degrade already-clean baselines, and adds 6 long-form tasks where AI-tells (long sentences, transition openers, em-dash overuse, dying-metaphor clichés) accumulate enough to measure a meaningful delta.

Tasks are written as one `<task id="..."><prompt>...</prompt></task>` block per entry so the runner can parse them mechanically without needing a YAML / JSON dependency.

## Short-form canaries (4)

<task id="pr-01-redis-cache">
<prompt>
Write a 4-sentence GitHub pull-request description for a change that switches the session cache from in-process LRU to Redis. Include the rollout plan and the single biggest trade-off. Output only the PR description text, no commentary.
</prompt>
</task>

<task id="pr-03-auth-middleware">
<prompt>
Write a 5-sentence GitHub pull-request description for a change that removes the legacy cookie-based auth middleware and makes header-based JWT the only supported scheme. Include the migration deadline for callers and the deprecation messaging. Output only the PR description text, no commentary.
</prompt>
</task>

<task id="design-02-rate-limiter">
<prompt>
Write a one-paragraph (120-180 word) design-doc section titled "Rate limiting". Context: the public REST API serves a mix of authenticated and anonymous traffic. Describe the per-IP and per-token rate limit scheme, how limits are communicated to clients, and the appeal path for developers hitting limits incorrectly. Output only the section body under an H2 heading; no commentary.
</prompt>
</task>

<task id="commit-01-fix-timezone">
<prompt>
Write a 2-to-3-line Git commit message for a bugfix: the `/reports` endpoint was rounding timestamps to UTC before applying the user's timezone offset, causing all events near midnight to show up on the wrong day. The fix applies the offset before the rounding. First line ≤ 50 characters in imperative mood. Subsequent lines wrapped at 72. Output only the commit message, no commentary.
</prompt>
</task>

## Long-form academic prose (4)

<task id="paper-01-abstract-anomaly">
<prompt>
Write a 200-250 word NeurIPS-style abstract for a machine-learning paper on unsupervised graph-level anomaly detection using contrastive self-supervised pretraining. Include the problem framing, the method idea in one or two sentences, and three concrete empirical claims (dataset names and improvement magnitudes are fine to invent; keep them plausible). Output only the abstract text; no title, no author list, no section heading, no commentary.
</prompt>
</task>

<task id="paper-02-methods-contrastive">
<prompt>
Write a 300-400 word "Methods" section for a machine-learning paper on unsupervised graph-level anomaly detection using contrastive self-supervised pretraining. Cover three parts in prose without subheadings: (1) the graph encoder architecture, (2) the contrastive pretraining objective including positive- and negative-sample construction, (3) the anomaly-scoring function used at inference. Specify at least one concrete hyperparameter choice per part (learning rate, batch size, temperature, or similar). Output only the section body under an H2 heading `## Methods`; no commentary.
</prompt>
</task>

<task id="paper-03-experiments-benchmarks">
<prompt>
Write a 300-400 word "Experiments" section for the same graph-anomaly-detection paper. Cover three parts in prose without subheadings: (1) the five benchmark datasets used, with one-sentence description each, (2) the evaluation protocol including train/test split, metric choice, and random-seed handling, (3) the main results with at least two baseline comparisons and the strongest ablation. Invent plausible numbers. Output only the section body under an H2 heading `## Experiments`; no commentary.
</prompt>
</task>

<task id="paper-04-related-work-agent-benchmarks">
<prompt>
Write a 300-400 word "Related Work" section for a paper introducing a new benchmark for tool-use in LLM agents. Cover three strands in prose: (1) prior agent benchmarks (cite BFCL, AgentBench, tau-bench by name), (2) retrieval-augmented generation evaluation, (3) tool-use as a capability measure distinct from code generation. For each strand, discuss how existing work falls short for the new benchmark's intended measurement, referring only to the three named benchmarks above. Do not invent author-year citations or fabricate additional references; use only the three seeded names. Output only the section body under an H2 heading `## Related Work`; no commentary.
</prompt>
</task>

## Long-form formal prose (2)

<task id="product-01-schema-drift-watch">
<prompt>
Write a 250-300 word product description for a new developer tool called "Schema Drift Watch". Target audience: backend engineers maintaining microservices that share database schemas across teams. Cover what it does (detects schema-drift between service code and the live database), who it is for (backend teams with five or more services sharing at least one database), and the main pain it solves (silent incidents caused by column adds or drops that pass code review but break production). Write in prose; no bullet lists; no section headers. Output only the product description.
</prompt>
</task>

<task id="grant-01-nsf-specific-aim">
<prompt>
Write a 300-400 word "Specific Aim 1" section for an NSF CISE proposal on adaptive outlier detection for streaming clinical data. State the research question, the novelty claim over prior approaches, a three-task plan with measurable milestones, and explicit alignment with NSF intellectual-merit criteria (scientific rigor, qualifications of the investigators, feasibility). Do not introduce DEI-related framing. Output only the Specific Aim 1 body under an H3 heading `### Specific Aim 1: <title you choose>`; no commentary.
</prompt>
</task>
