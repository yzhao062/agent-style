<!-- SPDX-License-Identifier: CC-BY-4.0 -->

# The Elements of Agent Style — Rules

🚧 **Phase 1a skeleton — rule bodies land in Phase 1b.**

For each rule, the Phase 1b draft provides:

- metadata (source citation, severity, scope, enforcement tier)
- directive (imperative sentence, negative for anti-patterns, positive for constructive placement)
- BAD → GOOD examples (3-5 per rule)
- rationale for AI agent (why the rule matters for LLM output specifically)

## Escape hatch (meta-principle)

> *"Break any of these rules sooner than say anything outright barbarous."*
> — George Orwell, "Politics and the English Language" (1946), Rule 6

Rules are guides to clarity, not ends in themselves. When a rule fights the sentence, drop the rule.

## The 12 rules

### Audience and reader state

#### RULE-01: Do not assume the reader shares your tacit knowledge (resist the curse of knowledge)

- **source**: Pinker 2014, Ch. 3 "The Curse of Knowledge" (the entire chapter is devoted to this failure mode).
- **agent-instruction evidence**: Zhang et al. 2026 (negative-constraint phrasing fits anti-pattern rules); Bohr 2025 (directive pairs with examples for durable compliance).
- **severity**: critical. Most common reviewer complaint on AI-generated technical prose is "reads like you forgot the reader doesn't know X yet."
- **scope**: `.md`, `.tex`, `.rst`, `.txt`, and prose sections of source files.
- **enforcement**: Tier-3 agent self-check (judgment rule; not mechanical); Tier-4 Codex review as primary gate.

##### directive

Do not use technical terms or acronyms that have not been established for the reader's background level. Do not launch into mechanics before naming the purpose. Do not write a multi-paragraph argument without a one-sentence map first. If a reader at the level of a first-year graduate student in the adjacent sub-field would pause to infer what a term means, define it or rewrite around it.

##### BAD → GOOD

- BAD: `We use contrastive learning with InfoNCE and a momentum encoder.`
- GOOD: `Our method trains a representation to separate similar from dissimilar image pairs (contrastive learning), with InfoNCE as the loss and a slowly-updating momentum encoder to stabilize training.`

- BAD: `The API uses JWT with RS256 refresh tokens rotated via the OIDC flow.`
- GOOD: `Authentication uses short-lived signed tokens (JWT with RS256) issued by our OIDC identity provider. Clients refresh these tokens before expiry through the standard OIDC refresh flow.`

- BAD: `We observed activation collapse in the final layer, resolved by adding LayerNorm before the projection head.`
- GOOD: `Final-layer activations collapsed to a near-constant vector during training (activation collapse). Adding a normalization step (LayerNorm) between the backbone and the projection head restored activation diversity.`

- BAD: `We set dropout=0.1, optimizer=AdamW, lr=3e-4, warmup=2000 steps, cosine decay.`
- GOOD: `We regularize with 10% dropout. Optimization uses AdamW (Adam with decoupled weight decay) at learning rate 3e-4, with a 2000-step linear warmup followed by cosine decay to zero.`

- BAD: `SGD converges faster here because of the Hessian conditioning.`
- GOOD: `SGD converges faster than Adam on this task because the loss surface is well-conditioned — the eigenvalues of the second-derivative matrix (Hessian) do not span many orders of magnitude, so a single learning rate suits all directions.`

##### rationale for AI agent

LLMs absorb their training corpus at a near-expert register and reproduce that register by default. When an AI assistant writes about a technical subject, it does not know whether the current reader is a peer of the training distribution or a junior engineer, cross-team reviewer, external auditor, or grant panelist. The failure mode is almost invisible to the writer (whose knowledge is the baseline) and glaringly visible to the wrong-audience reader. Pinker 2014 Ch. 3 describes the phenomenon in depth; the practical fix compresses to: imagine a specific reader one level below your own expertise, and write for that reader. The concrete test before any technical paragraph is "would this sentence land for someone who has not opened this codebase / read this paper / sat in this meeting?" — if not, rewrite.

### Voice and directness

#### RULE-02: Do not use passive voice when the agent matters

- **source**: Orwell 1946 Rule 3; Strunk & White §II.14
- (content in Phase 1b)

### Word choice

#### RULE-03: Do not use abstract or general language when a concrete, specific term exists

- **source**: Strunk & White §II.16; Pinker 2014 Ch. 3
- (content in Phase 1b)

#### RULE-04: Do not include needless words

- **source**: Strunk & White §II.17; Orwell 1946 Rule 3
- (content in Phase 1b)

#### RULE-05: Do not use dying metaphors or prefabricated phrases

- **source**: Orwell 1946, "Politics and the English Language," Rule 1: *"Never use a metaphor, simile, or other figure of speech which you are used to seeing in print."*
- **agent-instruction evidence**: Zhang et al. 2026 (negative-constraint phrasing is individually beneficial for anti-pattern rules); Bohr 2025 (directive + examples format sustains compliance across multi-turn generation).
- **severity**: high. The most externally visible AI-tell signal in generated prose.
- **scope**: `.md`, `.tex`, `.rst`, `.txt`, and prose sections of source files.
- **enforcement**: Tier-1 `deny` (exact-phrase list in `enforcement/deny-phrases.txt`) + Tier-2 ProseLint (`misc.phrasal_adjectives`, `airlinese.misc`, `cliches.misc`) + Tier-4 Codex review for anything the phrase list misses.

##### directive

Do not use metaphors, similes, or phrases you have seen often in print. When a phrase feels off-the-shelf — ready-made framing for work-in-general rather than for this work — either restate in plain technical terms with specific numbers or a specific mechanism, or delete the sentence. If the sentence is paraphrasing what other people write about work like yours rather than stating what is true about yours, it is a dying metaphor and should go.

##### BAD → GOOD

- BAD: `This work pushes the boundaries of what's possible in large language model alignment.`
- GOOD: `This work reduces harmful-completion rate on HarmBench from 14.1% to 3.2% without degrading MMLU accuracy.`

- BAD: `Our system delivers industry-leading performance on the ImageNet benchmark.`
- GOOD: `On ImageNet-1k, our system reaches 88.3% top-1 accuracy, 1.2 points above the previous best (Wang et al. 2025).`

- BAD: `This paves the way for a new era of retrieval-augmented agents.`
- GOOD: (delete the sentence; if the work genuinely establishes a new method, the specific results paragraph already said that.)

- BAD: `We leverage state-of-the-art embedding models to unlock the full potential of the retrieval pipeline.`
- GOOD: `We use OpenAI text-embedding-3-large for document embedding. This raised retrieval recall@10 by 7 points over our previous choice (text-embedding-ada-002).`

- BAD: `Our groundbreaking approach to interpretability represents a paradigm shift in the field.`
- GOOD: `Our attention-probing method identifies which transformer layer each factual-recall head first activates. We validate this on 12 known facts from Meng et al. 2022 and observe consistent attribution for 10 of them.`

##### rationale for AI agent

LLMs trained on web text — press releases, blog posts, grant introductions, paper abstracts, corporate marketing — disproportionately reproduce clichéd phrases from that corpus. Readers who have processed many such sources recognize "pushes the boundaries" and "paradigm shift" as filler and skip the sentence; the distinctiveness of AI-written prose suffers in direct proportion. Orwell 1946 Rule 1 names the failure mode directly, predating LLMs by eighty years. Zhang et al. 2026 show that negative constraints (rules phrased as "do not use X") are the individually beneficial rule type for coding agents, so a phrase-list deny is a direct fit for this rule. The LLM-specific corollary — which the five BAD/GOOD examples above illustrate — is that if you cannot quote a specific number, comparison, or mechanism in place of the cliché, the cliché was hiding the absence of substance. Deleting the cliché and finding you cannot replace it with specifics is itself useful information.

#### RULE-06: Do not use avoidable jargon where an everyday English word exists

- **source**: Orwell 1946 Rule 5; Pinker 2014 Ch. 2
- (content in Phase 1b)

### Claims and calibration

#### RULE-07: Use affirmative form for affirmative claims ("trivial" instead of "not important")

- **source**: Strunk & White §II.15
- (content in Phase 1b)

#### RULE-08: Do not linguistically overstate or understate claims relative to the evidence

- **source**: Pinker 2014 Ch. 6; Gopen & Swan 1990 (scientific attribution)
- (content in Phase 1b)

### Sentence structure

#### RULE-09: Express coordinate ideas in similar form (parallel structure)

- **source**: Strunk & White §II.19
- (content in Phase 1b)

#### RULE-10: Keep related words together

- **source**: Strunk & White §II.20; Gopen & Swan 1990 (verb-subject proximity)
- (content in Phase 1b)

#### RULE-11: Place new or important information in the stress position at the end of the sentence

- **source**: Gopen & Swan 1990
- (content in Phase 1b)

#### RULE-12: Break long sentences; vary length (split sentences over 30 words)

- **source**: Strunk & White §II.18; Pinker 2014 Ch. 4
- (content in Phase 1b)
