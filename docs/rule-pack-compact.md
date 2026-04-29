<!-- SPDX-License-Identifier: CC-BY-4.0 -->

# The Elements of Agent Style — Rules

This is the compact render of the agent-style rule pack. Each rule shows the directive and one illustrative BAD → GOOD pair. The full reference (5+ BAD/GOOD pairs per rule, agent-instruction evidence, severity classification, and rationale) lives in [`rule-pack.md`](rule-pack.md) at the same release.

## Severity Rubric

Each rule has a severity from this four-level scale:

- **critical** — reader cannot understand or trust the prose if the rule is violated.
- **high** — externally visible AI-tell, or a recurring clarity failure that breaks skim-reading.
- **medium** — local readability cost, felt by the reader but not a trust issue.
- **low** — polish or preference; flagged for consistency rather than comprehension.

## Escape Hatch (Meta-Principle)

> *"Break any of these rules sooner than say anything outright barbarous."*
> — George Orwell, "Politics and the English Language" (1946), Rule 6

Rules are guides to clarity, not ends in themselves. When a rule fights the sentence, drop the rule.

## The 12 Rules

### Audience and Reader State

#### RULE-01: Do Not Assume the Reader Shares Your Tacit Knowledge (Resist the Curse of Knowledge)

##### Directive

Do not use technical terms or acronyms that have not been established for the reader's background level. Do not launch into mechanics before naming the purpose. Do not write a multi-paragraph argument without a one-sentence map first. Before writing, name the intended reader for this artifact: adjacent-field graduate student for research papers, junior engineer for API docs, on-call engineer for runbooks, cross-panel reviewer for proposals, release reader for changelogs, or another concrete reader. If that reader would pause to infer what a term means, define it or rewrite around it.

##### BAD → GOOD

- BAD: `We use contrastive learning with InfoNCE and a momentum encoder.`
- GOOD: `Our method trains a representation to separate similar from dissimilar image pairs (contrastive learning), with InfoNCE as the loss and a slowly-updating momentum encoder to stabilize training.`

### Voice and Directness

#### RULE-02: Do Not Use Passive Voice When the Agent Matters

##### Directive

Do not write "X was done by Y" when "Y did X" fits. Active voice names the agent, shortens the sentence, and makes the verb carry the action. When the agent is genuinely unknown or irrelevant (scientific attribution, observation of phenomena, general truths), passive is correct; use it deliberately, not by default. Before each passive construction, ask: is the agent known and worth naming? If yes, rewrite active.

##### BAD → GOOD

- BAD: `The experiments were conducted on eight NVIDIA A100 GPUs.`
- GOOD: `We ran the experiments on eight NVIDIA A100 GPUs.`

### Word Choice

#### RULE-03: Do Not Use Abstract or General Language When a Concrete, Specific Term Exists

##### Directive

Do not use abstract nouns when concrete ones exist. "The system has performance issues" says nothing; "the checkout endpoint p95 latency rose from 120ms to 450ms at 14:00 UTC" names what, when, and how much. Replace category words ("factors", "aspects", "considerations", "issues", "elements") with the specific items they refer to. If you reach for a category word, ask: what exactly? If the answer takes longer than one clause to give, the sentence was hiding the work.

##### BAD → GOOD

- BAD: `The model shows improvements across various metrics.`
- GOOD: `The model improves F1 by 3.2 points (0.812 to 0.844) on FEVER and cuts hallucination rate from 11.3% to 6.8% on TruthfulQA.`

#### RULE-04: Do Not Include Needless Words

##### Directive

Do not stretch phrases. "In order to" is "to"; "due to the fact that" is "because"; "at this point in time" is "now"; "it is important to note that" is (delete and state the fact); "may potentially" and "could possibly" are redundant hedges (use "may" or "could", not both). Every filler phrase signals to the reader that substance is about to arrive; delete the phrase and let the substance arrive directly.

##### BAD → GOOD

- BAD: `It is important to note that the learning rate was reduced in order to prevent divergence.`
- GOOD: `We reduced the learning rate to prevent divergence.`

#### RULE-05: Do Not Use Dying Metaphors or Prefabricated Phrases

##### Directive

Do not use metaphors, similes, or phrases you have seen often in print. When a phrase feels off-the-shelf — ready-made framing for work-in-general rather than for this work — either restate in plain technical terms with specific numbers or a specific mechanism, or delete the sentence. If the sentence is paraphrasing what other people write about work like yours rather than stating what is true about yours, it is a dying metaphor and should go.

##### BAD → GOOD

- BAD: `This work pushes the boundaries of what's possible in large language model alignment.`
- GOOD: `This work reduces harmful-completion rate on HarmBench from 14.1% to 3.2% without degrading MMLU accuracy.`

#### RULE-06: Do Not Use Avoidable Jargon Where an Everyday English Word Exists

##### Directive

Do not use "leverage" where "use" fits. Do not use "utilize" where "use" fits. Do not use "methodology" where "method" fits. Do not use "functionality" where "function" or "feature" fits. Reserve the longer word for when it carries information the shorter word does not. Technical jargon with distinct meaning ("backpropagation", "quantization", "deserialization") is fine and often necessary. Corporate-speak jargon ("leverage", "utilize", "operationalize") is substitutable by shorter everyday words without loss of meaning.

##### BAD → GOOD

- BAD: `We leverage transformer architectures to facilitate cross-lingual transfer.`
- GOOD: `We use transformers for cross-lingual transfer.`

### Claims and Calibration

#### RULE-07: Use Affirmative Form for Affirmative Claims ("Trivial" Instead of "Not Important")

##### Directive

Replace "not important" with "trivial"; "did not remember" with "forgot"; "did not pay attention to" with "ignored"; "is not often" with "rarely"; "is not large" with "small"; "does not succeed" with "fails". Prefer one affirmative word over two negating words. When the sentence genuinely negates something (the proposition is true only in the negative), a single "not" is fine and necessary. The rule targets two-word negations that have a one-word affirmative equivalent. The operational test: can I replace "not X" with a single positive word that names the state directly? If yes, do so.

##### BAD → GOOD

- BAD: `The variance was not large.`
- GOOD: `The variance was small.`

#### RULE-08: Do Not Linguistically Overstate or Understate Claims Relative to the Evidence

##### Directive

Do not overclaim (saying "proves X" when the evidence is "suggests X"). Do not underclaim via reflexive weasel (saying "it might be worth considering" when you mean "we should do X"). Calibrate verbs to evidence: experimental results "suggest" or "show"; theoretical derivations "imply" or "prove"; user reports "indicate" (pending verification); benchmarks "measure". Use "best" only when you have compared against the strongest alternative; use "only" only when you have ruled out alternatives. When the evidence is uncertain, say so in one clause; do not weaken the main verb beyond what the evidence supports.

##### BAD → GOOD

- BAD: `Our method revolutionizes language model alignment.`
- GOOD: `Our method reduces harmful-completion rate on HarmBench from 14.1% to 3.2% without degrading MMLU accuracy. (Generalization to other alignment benchmarks is future work.)`

### Sentence Structure

#### RULE-09: Express Coordinate Ideas in Similar Form (Parallel Structure)

##### Directive

Write coordinate ideas in the same grammatical form. In a list of three items, if item 1 is a noun phrase, items 2 and 3 are also noun phrases; if item 1 is a verb-initial clause, items 2 and 3 are also verb-initial clauses. The rule applies to bullet lists, parallel predicates ("we measure X, improve Y, and validate Z"), and compound sentences connected by "and" / "or" / "but". Mismatched forms force the reader to reparse each item against a new expected structure.

##### BAD → GOOD

- BAD: `The pipeline cleans the data, feature extraction, and then trains the model.`
- GOOD: `The pipeline cleans the data, extracts features, and trains the model.`

#### RULE-10: Keep Related Words Together

##### Directive

Keep subject close to verb, verb close to object, and modifier close to modified. When a long parenthetical or relative clause must appear between subject and verb, move the clause to the end of the sentence or split into two sentences. The operational test: count words between subject and verb; if the gap exceeds 8, split. Readers hold the subject in working memory until the verb arrives; every intervening clause costs memory slots and increases misparsing risk.

##### BAD → GOOD

- BAD: `The model, which was pre-trained on a mixed corpus of English Wikipedia, Common Crawl, and a 400-million-token curated scientific dataset assembled by the authors over eight months, achieves 87.2% accuracy.`
- GOOD: `The model achieves 87.2% accuracy. It was pre-trained on a mixed corpus of English Wikipedia, Common Crawl, and a 400-million-token scientific dataset the authors curated over eight months.`

#### RULE-11: Place New or Important Information in the Stress Position at the End of the Sentence

##### Directive

End sentences with the information you want the reader to remember. The beginning of a sentence (topic position) connects to what came before; the end (stress position) is where new or important information lands with maximum emphasis. If the key fact is in the middle, move it to the end or rebalance. The rule applies especially to result sentences in papers, conclusions in design docs, and root-cause lines in postmortems.

##### BAD → GOOD

- BAD: `A 3.2-point improvement in F1 over the previous best model was demonstrated by the new architecture on the SQuAD 2.0 test set.`
- GOOD: `On the SQuAD 2.0 test set, the new architecture improves F1 by 3.2 points over the previous best model.`

#### RULE-12: Break Long Sentences; Vary Length (Split Sentences over 30 Words)

##### Directive

Split any sentence over 30 words into two or more sentences. Vary sentence length across a paragraph: a paragraph of five 25-word sentences reads less well than the same content in sentences of 8, 18, 22, 14, 30 words. Short sentences land points; long sentences carry qualification and detail. A paragraph that does only one of these reads as monotone. When a long sentence is unavoidable (single logical unit that resists splitting), make the previous and following sentences short to balance.

##### BAD → GOOD

- BAD (43 words, single sentence): `We evaluate our model on five standard benchmarks covering natural-language inference, reading comprehension, and factual-recall tasks, reporting both in-distribution accuracy on held-out splits of the training corpora and out-of-distribution accuracy on benchmarks not seen during training or fine-tuning.`
- GOOD (three sentences, 15 + 12 + 11 words): `We evaluate our model on five standard benchmarks: NLI, reading comprehension, and factual-recall. In-distribution accuracy uses held-out splits of the training corpora. Out-of-distribution accuracy uses benchmarks not seen during training.`

## The 9 Field-Observed Rules

The following nine rules (RULE-A through RULE-I) come from my observation of LLM output across dozens of writing projects and code releases, 2022 to 2026. They are not drawn from cited writing authorities; each rule names a recurring pattern I saw frequently enough across distinct projects to warrant a named rule. They are treated as peer input to the 12 canonical rules in all adapter files; when an agent consumes the ruleset, both groups are binding.

### Observed LLM Patterns

#### RULE-A: Do Not Convert Prose into Bullet Points Unless the Content Is a Genuine List

##### Directive

Keep prose in paragraphs when ideas connect by cause-and-effect, argument, or narrative. Use bullets only when items are genuinely parallel enumerations (API endpoints, config options, checklist steps). The test: if a reader reads only the first few words of each bullet, does the shape recover meaning? For a genuine list, yes (each bullet names a thing); for fragmented prose, no (bullets are sentence shards with connective tissue stripped). Do not force 3-item lists when 2 items or a sentence fit; LLMs over-produce "first, second, third" triads where 2 items would be natural. Resist the pattern.

##### BAD → GOOD

- BAD (proposal, bullet-ified argument):

    ```text
    Our approach consists of:
    - Training a contrastive embedder
    - Because this improves retrieval recall
    - Which is important for RAG pipelines
    - And enables downstream applications
    ```

- GOOD (proposal): `Our approach trains a contrastive embedder, which improves retrieval recall for downstream RAG pipelines.`

#### RULE-B: Do Not Use Em or En Dashes as Casual Sentence Punctuation

##### Directive

Do not use em dashes or en dashes as casual sentence punctuation. Prefer commas for appositives, semicolons for linked independent clauses, colons for expansions, and parentheses for asides. En dashes remain correct in numeric ranges (`1-3`, `2020-2026`), paired names ("the Stein-Strömberg theorem"), and bibliographic page ranges. Normal hyphens in compound words and technical terms (`command-line`, `co-PI`, `zero-shot`) are not dashes and should not be flagged.

##### BAD → GOOD

- BAD: `The model converges quickly — typically within 5000 training steps — on most datasets.`
- GOOD: `The model converges quickly, typically within 5000 training steps, on most datasets.`

#### RULE-C: Do Not Start Consecutive Sentences with the Same Word or Phrase

##### Directive

Do not open two or more consecutive sentences with the same word. The pattern signals a drafting template that the generation process locked into (often `This ... This ... This ...`, `The ... The ... The ...`, or `We ... We ... We ...`). Vary the opener: topic-fronted versus subject-fronted versus connective. Pronoun subjects (`It`, `We`, `They`) are the most common offenders in LLM output because the model samples the next sentence conditional on the topic and re-picks the most fluent subject.

##### BAD → GOOD

- BAD (paper): `The method uses a contrastive loss. The method also applies dropout. The method converges in 5000 steps.`
- GOOD (paper): `The method uses a contrastive loss with 10% dropout, converging in 5000 steps.`

#### RULE-D: Do Not Overuse Transition Words ("Additionally", "Furthermore", "Moreover")

##### Directive

Do not open sentences with "Additionally", "Furthermore", "Moreover", "In addition", "What's more", or "Notably" unless the sentence genuinely builds on the preceding clause in a way that a period or `And` would not convey. In most cases, a period ends the prior sentence and the next sentence makes the connection by content alone. Reserve explicit transitions for the rare case where the logical move (addition, contrast, concession) needs to be flagged for the reader.

##### BAD → GOOD

- BAD (paper): `The model outperforms BM25 on MS MARCO. Additionally, it outperforms DPR on Natural Questions. Furthermore, it reaches state-of-the-art on BEIR.`
- GOOD (paper): `The model outperforms BM25 on MS MARCO and DPR on Natural Questions, and reaches state-of-the-art on BEIR.`

#### RULE-E: Do Not Close Every Paragraph with a Summary Sentence

##### Directive

Do not end every paragraph with a sentence that restates the paragraph's point ("In summary, ...", "Thus, the contribution is ...", "Overall, this means ...", "In conclusion, ..."). Summary closers are correct for the final paragraph of a piece, or for a long section that the reader will skim rather than read sequentially. For body paragraphs, trust the content to land its own point; a closer that restates the same claim in different words is noise. The test: if the closer sentence is deleted, does the paragraph still make its point? If yes, delete the closer.

##### BAD → GOOD

- BAD: `We trained the model on 50k query-passage pairs and evaluated on five benchmarks. The model reaches 0.79 recall@10 on our held-out set. Overall, these results demonstrate that our method is effective.`
- GOOD: `We trained the model on 50k query-passage pairs and evaluated on five benchmarks. The model reaches 0.79 recall@10 on our held-out set.`

#### RULE-F: Use Consistent Terms; Do Not Redefine Abbreviations Mid-Document

##### Directive

Once you introduce a term or abbreviation, keep using it. Do not alternate "large language model", "LLM", "language model", "LM", "neural language model", "foundation model" as synonyms for the same thing. Do not redefine an abbreviation: if `LLM` was defined as `large language model` in the introduction, do not expand it again in section 3. For the reader, a consistent term signals "this is the same concept I saw earlier"; varied terms signal "I should check whether this is something new."

##### BAD → GOOD

- BAD (paper, term drift): introduces "large language models (LLMs)" in §1, then writes in §3: "Neural language models achieve..."
- GOOD (paper): introduces "large language models (LLMs)" in §1, then writes in §3: "LLMs achieve..."

#### RULE-G: Use Title Case for Section and Subsection Headings

##### Directive

Capitalize the first word, the last word, and all major words (nouns, verbs, adjectives, adverbs, pronouns) in section and subsection headings. Lowercase articles (`a`, `an`, `the`), coordinating conjunctions (`and`, `but`, `or`, `nor`), and short prepositions (`of`, `in`, `on`, `to`, `for`, `by`, `at`, `with`). This applies in Markdown (H1 through H6), LaTeX (`\section`, `\subsection`, `\subsubsection`), reStructuredText, and similar structural-heading surfaces. Does not apply to sentence-style titles (question-form headings or full-sentence article titles where sentence case is intended).

##### BAD → GOOD

- BAD (Markdown): `## Experimental results and analysis`
- GOOD (Markdown): `## Experimental Results and Analysis`

#### RULE-H: Support Factual Claims with Citation or Concrete Evidence; Do Not Be Handwavy

##### Directive

When a sentence asserts a factual claim that warrants attribution (empirical result, published method, community consensus, comparative benchmark, historical fact), provide a verifiable citation, or name the specific source (a paper by author and year, a benchmark, a dataset, an observed experiment). Do not write handwavy attributions ("prior work shows", "it is well known that", "recent studies suggest", "many researchers believe") without naming the specific work. When the claim is the author's own observation, state the concrete evidence (number, dataset, experiment, condition). Never invent a citation; if the cited paper cannot be verified, remove the claim, soften it to the author's own observation, or mark `[UNVERIFIED]` and flag for review.

##### BAD → GOOD

- BAD (paper): `Prior work has shown that late-interaction retrieval improves over lexical retrieval.`
- GOOD (paper): `Khattab and Zaharia 2020 (ColBERT) report MS MARCO passage-ranking MRR@10 of 0.360 for ColBERT versus 0.187 for BM25-Anserini, using contextualized late interaction over BERT token embeddings.`

#### RULE-I: Prefer Full Forms over Contractions in Technical Prose

##### Directive

In formal technical prose (research papers, grant proposals, API specifications, technical documentation), prefer "it is" over "it's", "does not" over "doesn't", "cannot" over "can't", "will not" over "won't", "I am" over "I'm", "you are" over "you're". Contractions are acceptable in informal registers (blog posts, release notes, commit messages, casual documentation), but even there, be deliberate: a contraction sets a register, and if the surrounding prose is formal, the contraction reads as a tonal break. The operational test: if the surrounding sentences use full forms, the contraction stands out; if the surrounding sentences use contractions, the full form stands out. Pick the register and hold it within the document.

##### BAD → GOOD

- BAD (paper): `It's worth noting that the model doesn't converge when the learning rate is too high.`
- GOOD (paper): `The model does not converge when the learning rate is too high.` (The "it is worth noting that" phrase is itself filler and should also be cut per RULE-04.)
