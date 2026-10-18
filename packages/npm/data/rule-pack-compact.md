<!-- SPDX-License-Identifier: CC-BY-4.0 -->

# The Elements of Agent Style — Rules

Compact render: each rule shows its directive and one BAD → GOOD pair; `rule-pack.md` (an alias of `RULES.md`) holds the rest.

## Escape Hatch (Meta-Principle)

> *"Break any of these rules sooner than say anything outright barbarous."*
> — George Orwell, "Politics and the English Language" (1946), Rule 6

Most rules here are defaults to apply with judgment. Human writers depart from any single one now and then, and that variety is part of why their prose reads as written by a person. A few are firm: do not invent citations, evidence, or numbers, and do not leave placeholders in finished text. Judge a draft by its overall pattern: one that obeys every default in every sentence (every sentence under 30 words, every connective removed) reads as machine-made. When a rule fights the sentence, drop the rule.

## House Style

These habits, from Yue Zhao's pre-AI first-author ML papers, tune the classic rules to one author. A habit outranks a conflicting style rule below but never the facts: the firm rules and any needed scope or uncertainty come first, and a move the facts do not support is left out. Use each habit at its rate, not everywhere.

- **Abstract.** Open on the problem, never on the field's importance: about half open with a question naming the input and the constraint ("Given X, how can we ... without any labels?"), the rest with a concession ("There is no shortage of X, yet ...") or a task definition. Say what makes it hard, often as "(i) ... (ii) ..." reasons. Then "In this work, we" name the method and coin its acronym, give the mechanism, report evidence in words or one rounded figure ("Extensive experiments on more than 20 datasets show ..."), and close on code if released.
- **Introduction.** Concede, then turn ("Although X, they cannot Y"), naming the alternative and why it does not transfer; state limits of prior work flatly ("none of them"). A "first" the facts support takes "(to the best of our knowledge)"; add one scope remark ("We remark that X is strictly a Y technique, rather than a new Z"). No roadmap. End with "In summary, the key contributions of this work include:", three to five items with bold noun-phrase heads and full "We ..." sentences, effectiveness last, then a bold "Reproducibility." line if code is released.
- **Results.** Open a paragraph with a bold full-sentence finding, then the evidence and, where it shows them, a one-clause cause ("This is mainly because ...") and the exception.
- **Conclusion.** About 125 words in one paragraph: the claim in the abstract's words, the mechanism in a clause, one evidence sentence without numbers, at most one scoped limitation, and one future-work sentence.
- **Sentences.** About one in four runs past 30 words, carrying glosses ("(e.g., ...)", "(i.e., ...)") and inline "(i) ... (ii) ..." lists; short flat ones sit beside them ("Consider iForest as an example."). The method is the subject of plain active verbs (capitalizes on, carries over).
- **Signposts.** Most sentences start with their subject. Five abstracts hold two "Moreover" and one each of "Notably" and "In a nutshell"; an introduction has about one every two or three paragraphs, a conclusion one at most.
- **Words.** Keep the central claim and fixed terms in the same words across sections. Hedge a cause with one word ("possibly due to"). A plain colloquial word beside technical terms is fine ("juice out", "a black art").

## The 12 Rules

### Audience and Reader State

#### RULE-01: Do Not Assume the Reader Shares Your Tacit Knowledge (Resist the Curse of Knowledge)

##### Directive

Do not use technical terms or acronyms that have not been established for the reader's background level. Do not launch into mechanics before naming the purpose. Do not write a multi-paragraph argument without a one-sentence map first. Before writing, name the intended reader (an adjacent-field graduate student for a paper, a cross-panel reviewer for a proposal, an on-call engineer for a runbook). If that reader would pause to infer what a term means, define it or rewrite around it.

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

Do not use abstract nouns when concrete ones exist. "The system has performance issues" says nothing; "the checkout endpoint p95 latency rose from 120ms to 450ms at 14:00 UTC" names what, when, and how much. Replace category words ("factors", "aspects", "considerations", "issues", "elements") with the specific items they refer to.

Concrete means naming the specific finding, and a table transcribed into a sentence buries it. When a table or figure holds the results, state the pattern early, with the magnitude a reader needs to interpret it ("halves latency at batch size 1"). Point to the display for per-item scores, intervals, and p-values. Round each magnitude to the precision the claim needs ("about a third", "under one point"). Do not stack precise figures in consecutive sentences, and do not restate a figure in a second form. Give a kept figure its meaning for the reader (faster, cheaper, more accurate), in the same sentence when it fits, and only for the setting that produced it. An abstract, introduction, or conclusion carries the fewest numbers of any section: the few magnitudes behind the main findings, any tie or loss that bounds them with its size in words or one rounded figure, and no intervals or p-values. When uncertainty changes the interpretation, say so beside the estimate in plain words ("within noise", "consistent across seeds") rather than by citing standard deviations or confidence intervals. Do not call an inconclusive difference a gain, even with a caveat attached. Report a difference in points or percent ("6 points of AUC", "about 11% lower error"), not as a raw decimal, and keep one unit and sign convention across text, tables, and captions. Keep numbers that change the claim or that the reader acts on. When several figures matter and no display holds them, add a table (in an appendix if space is short) and point to it.

##### BAD → GOOD

- BAD: `The model shows improvements across various metrics.`
- GOOD: `The model improves FEVER F1 by 3.2 points and cuts the TruthfulQA hallucination rate by 4.5 points (Table 2).`

#### RULE-04: Do Not Include Needless Words

##### Directive

Do not stretch phrases. "In order to" is "to"; "due to the fact that" is "because"; "at this point in time" is "now"; "it is important to note that" is (delete and state the fact); "may potentially" and "could possibly" are redundant hedges (use "may" or "could", not both).

Cut needless sentences too: one that announces what the next sentence will do, restates the method or setup the reader already has, or repeats a finding already given. An abstract cites no table or figure, and a conclusion does not walk through the results again.

##### BAD → GOOD

- BAD: `It is important to note that the learning rate was reduced in order to prevent divergence.`
- GOOD: `We reduced the learning rate to prevent divergence.`

#### RULE-05: Do Not Use Dying Metaphors or Prefabricated Phrases

##### Directive

Do not use metaphors, similes, or phrases you have seen often in print. When a phrase feels off-the-shelf — ready-made framing for work-in-general rather than for this work — either restate in plain technical terms with specific numbers or a specific mechanism, or delete the sentence. If the sentence is paraphrasing what other people write about work like yours rather than stating what is true about yours, it is a dying metaphor and should go.

##### BAD → GOOD

- BAD (paper intro): `Outlier detection (OD) is no exception.`
- GOOD (author's paper): `The same problem applies to outlier detection (OD).`

#### RULE-06: Do Not Use Avoidable Jargon Where an Everyday English Word Exists

##### Directive

Do not use "leverage" where "use" fits. Do not use "utilize" where "use" fits. Do not use "methodology" where "method" fits. Do not use "functionality" where "function" or "feature" fits. Reserve the longer word for when it carries information the shorter word does not. Technical jargon with distinct meaning ("backpropagation", "quantization", "deserialization") is fine and often necessary.

##### BAD → GOOD

- BAD: `We leverage transformer architectures to facilitate cross-lingual transfer.`
- GOOD: `We use transformers for cross-lingual transfer.`

### Claims and Calibration

#### RULE-07: Put Statements in Positive Form (Affirmative Words; No "X, Not Y" Antithesis)

##### Directive

Prefer one affirmative word over two negating words: "trivial" for "not important", "forgot" for "did not remember", "rarely" for "is not often", "fails" for "does not succeed". A single "not" is right when the proposition is true only in the negative.

Do not stage a claim against a negated foil for emphasis: "X, not Y", "It is not X, it is Y", "Not just X, but Y". State the claim directly. Keep the negation only when the rejected alternative is specific and ruling it out informs the reader ("The bottleneck is disk I/O, not CPU"); drop a vague or strawman foil ("not just a tool").

##### BAD → GOOD

- BAD: `The variance was not large.`
- GOOD: `The variance was small.`

#### RULE-08: Do Not Linguistically Overstate or Understate Claims Relative to the Evidence

##### Directive

Do not overclaim (saying "proves X" when the evidence is "suggests X") or underclaim. Underclaiming takes two forms. One is reflexive weasel (saying "it might be worth considering" when you mean "we should do X"). The other is the caveat tail: a "however", a future-work aside, or a note on what the work does not establish, attached to a result by habit. Calibrate verbs to evidence: experimental results "suggest" or "show"; theoretical derivations "imply" or "prove"; user reports "indicate"; benchmarks "measure". Use "best" only when you have compared against the strongest alternative; use "only" only when you have ruled out alternatives.

Keep a qualifier when it changes what the evidence supports, and put it inside the claim. A tie, a loss, a difference within noise, or the weakest case is a finding: report it next to the claim it bounds, in the results and in any summary. Cut a qualifier that adds no information, and collect general limitations of the study design in the venue's Limitations section (Risks and Alternatives in a proposal).

##### BAD → GOOD

- BAD (paper intro): `We introduce MetaOD, a systematic meta-learning framework and the first method for UOMS.`
- GOOD (author's paper): `We propose MetaOD, (to our knowledge) the first effort on unsupervised model selection for OD tasks.`

### Sentence Structure

#### RULE-09: Express Coordinate Ideas in Similar Form (Parallel Structure)

##### Directive

Write coordinate ideas in the same grammatical form. In a list of three items, if item 1 is a noun phrase, items 2 and 3 are also noun phrases; if item 1 is a verb-initial clause, items 2 and 3 are also verb-initial clauses. The rule applies to bullet lists, parallel predicates ("we measure X, improve Y, and validate Z"), and compound sentences connected by "and" / "or" / "but". Mismatched forms force the reader to reparse each item against a new expected structure.

##### BAD → GOOD

- BAD: `The pipeline cleans the data, feature extraction, and then trains the model.`
- GOOD: `The pipeline cleans the data, extracts features, and trains the model.`

#### RULE-10: Keep Related Words Together

##### Directive

Keep subject close to verb, verb close to object, and modifier close to modified. When a long parenthetical or relative clause must appear between subject and verb, move the clause to the end of the sentence or split into two sentences. The operational test: count words between subject and verb; if the gap exceeds 8, split.

##### BAD → GOOD

- BAD (abstract, 15 words before the verb): `Choosing an outlier detection algorithm and its hyperparameters (together, a model) for a new dataset is difficult when labels are unavailable.`
- GOOD (author's paper): `Given an unsupervised outlier detection task on a new dataset, how can we automatically select a good outlier detection algorithm and its hyperparameter(s) (collectively called a model)?`

#### RULE-11: Place New or Important Information in the Stress Position at the End of the Sentence

##### Directive

End sentences with the information you want the reader to remember. The beginning of a sentence (topic position) connects to what came before; the end (stress position) is where new or important information lands with maximum emphasis. If the key fact is in the middle, move it to the end or rebalance. The rule applies especially to result sentences in papers, conclusions in design docs, and root-cause lines in postmortems.

##### BAD → GOOD

- BAD: `A 3.2-point improvement in F1 over the previous best model was demonstrated by the new architecture on the SQuAD 2.0 test set.`
- GOOD: `On the SQuAD 2.0 test set, the new architecture improves F1 by 3.2 points over the previous best model.`

#### RULE-12: Break Long Sentences; Vary Length

##### Directive

Vary sentence length: short sentences land points, and long ones carry a claim with its conditions. Split a sentence when the reader must hold more than one open clause to reach its point. A long sentence that carries one connected thought can stay, and a draft with no long sentences reads clipped. Paragraphs of only short or only long sentences read as monotone.

##### BAD → GOOD

- BAD (18 + 13 + 10 words): `MetaOD uses the performance records of a large collection of detection models on historical outlier detection benchmark datasets. It transfers this experience to select an effective model for a new dataset. Selection needs no ground-truth labels, model evaluations, or model comparisons.`
- GOOD (author's paper, 45 words, one thought): `MetaOD capitalizes on the performances of a large body of detection models on historical outlier detection benchmark datasets, and carries over this prior experience to automatically select an effective model to be employed on a new dataset without any labels, model evaluations or model comparisons.`

## The 9 Field-Observed Rules

RULE-A through RULE-I name patterns I saw recur in LLM output, 2022 to 2026. No writing authority supplies them, and they carry the same weight as the 12 canonical rules.

### Observed LLM Patterns

#### RULE-A: Do Not Convert Prose into Bullet Points Unless the Content Is a Genuine List

##### Directive

Keep prose in paragraphs when ideas connect by cause, argument, or narrative. Use bullets only for genuinely parallel items (endpoints, options, checklist steps): a reader who reads only the first words of each bullet should recover the shape. Do not force three items when two or a sentence fit. A table cell holds a number, a label, or a short phrase; content that needs a sentence belongs in the text.

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

Do not use em or en dashes as casual sentence punctuation. Use commas for appositives, colons for expansions, and parentheses for asides. Join independent clauses with a period, a comma and a conjunction, or a semicolon for two clauses too closely tied to stand apart; keep semicolons sparing, but do not split every one into a period. Dashes stay in numeric ranges, paired names, and page ranges; hyphens in compounds (`zero-shot`) are not dashes.

##### BAD → GOOD

- BAD: `The model converges quickly — typically within 5000 training steps — on most datasets.`
- GOOD: `The model converges quickly, typically within 5000 training steps, on most datasets.`

#### RULE-C: Do Not Start Consecutive Sentences with the Same Word or Phrase

##### Directive

Do not open two or more consecutive sentences with the same word (often `This ... This ... This ...`, `The ... The ... The ...`, or `We ... We ... We ...`). Vary the opener: topic-fronted versus subject-fronted versus connective. Pronoun subjects (`It`, `We`, `They`) are the most common offenders in LLM output.

##### BAD → GOOD

- BAD (paper): `The method uses a contrastive loss. The method also applies dropout. The method converges in 5000 steps.`
- GOOD (paper): `The method uses a contrastive loss with 10% dropout, converging in 5000 steps.`

#### RULE-D: Do Not Overuse Transition Words ("Additionally", "Furthermore", "Moreover")

##### Directive

Do not open sentences with "Additionally", "Furthermore", "In addition", or "What's more" when the word only announces another point. A period or `And` carries the same addition. "Moreover" and "Notably" may open one sentence in a paragraph, where they mark a second ingredient or a result that stands apart. Keep the words that mark a relation the text already establishes: contrast ("However", "Instead"), cause ("Thus", "Therefore"), sequence ("First", "Then"). A cause word is itself a claim. Do not add a reason, mechanism, or recommendation that the evidence does not show just to join two sentences.

##### BAD → GOOD

- BAD (paper, additive openers on a contrast): `Batching raises throughput on the large model. Additionally, it lowers throughput on the small model. Furthermore, it adds queueing delay on both.`
- GOOD (paper, the contrast word stays): `Batching raises throughput on the large model. However, it lowers throughput on the small model and adds queueing delay on both.`

#### RULE-E: Do Not Close Every Paragraph with a Summary Sentence

##### Directive

Do not end every paragraph with a sentence that restates its point ("Overall, this means ...", "Thus, the contribution is ..."). A summary closer fits the final paragraph of a piece or a long section that readers skim. The test: delete the closer, and if the paragraph still makes its point, leave it deleted.

##### BAD → GOOD

- BAD (design doc): `We chose two-tower retrieval because query embeddings cache across sessions. Thus, the architecture is well-suited to our caching strategy.`
- GOOD (design doc): `We chose two-tower retrieval because query embeddings cache across sessions.`

#### RULE-F: Use Consistent Terms; Do Not Redefine Abbreviations Mid-Document

##### Directive

Once you introduce a term or abbreviation, keep using it. Do not alternate "large language model", "LLM", "language model", "LM", "neural language model", "foundation model" as synonyms for the same thing. Do not redefine an abbreviation: if `LLM` was defined as `large language model` in the introduction, do not expand it again in section 3.

##### BAD → GOOD

- BAD (paper, term drift): introduces "large language models (LLMs)" in §1, then writes in §3: "Neural language models achieve..."
- GOOD (paper): introduces "large language models (LLMs)" in §1, then writes in §3: "LLMs achieve..."

#### RULE-G: Use Title Case for Section and Subsection Headings

##### Directive

Use title case in section and subsection headings: capitalize the first, last, and major words, and lowercase articles, coordinating conjunctions, and short prepositions (`of`, `in`, `on`, `to`, `for`, `by`, `at`, `with`). Question-form and full-sentence headings are exempt, and a full-sentence bold run-in lead takes sentence case.

##### BAD → GOOD

- BAD (Markdown): `## Experimental results and analysis`
- GOOD (Markdown): `## Experimental Results and Analysis`

#### RULE-H: Support Factual Claims with Citation or Concrete Evidence; Do Not Be Handwavy

##### Directive

When a sentence asserts a factual claim that warrants attribution (empirical result, published method, community consensus, comparative benchmark, historical fact), provide a verifiable citation, or name the specific source (a paper by author and year, a benchmark, a dataset, an observed experiment). Do not write handwavy attributions ("prior work shows", "it is well known that", "recent studies suggest", "many researchers believe") without naming the specific work. When the claim is the author's own observation, state the concrete evidence (dataset, experiment, condition, and the magnitude or a table pointer). Never invent a citation; if the cited paper cannot be verified, remove the claim, soften it to the author's own observation, or mark `[UNVERIFIED]` and flag for review.

##### BAD → GOOD

- BAD (paper): `Prior work has shown that late-interaction retrieval improves over lexical retrieval.`
- GOOD (paper): `Khattab and Zaharia 2020 (ColBERT) report that late interaction over BERT token embeddings nearly doubles the MRR@10 of BM25 (Anserini) on the MS MARCO passage-ranking Dev set.`

#### RULE-I: Prefer Full Forms over Contractions in Technical Prose

##### Directive

In formal technical prose (papers, proposals, specifications, documentation), write full forms: "it is", "does not", "cannot". Contractions suit informal registers such as blog posts and commit messages; hold one register per document.

##### BAD → GOOD

- BAD (technical spec): `The client shouldn't retry on 4xx errors.`
- GOOD (technical spec): `The client should not retry on 4xx errors.`
