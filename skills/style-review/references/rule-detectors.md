# SPDX-License-Identifier: CC-BY-4.0

# style-review rule detector matrix

Reference for the `style-review` skill. Detection approach per rule; bucket determines which code path runs the check.

| Rule | Bucket | Detector approach | Threshold / heuristic |
| --- | --- | --- | --- |
| RULE-01 curse of knowledge | semantic | LLM judge: "are any terms undefined for the stated audience?" with rule directive + BAD/GOOD | host model judgment |
| RULE-02 passive voice when agent matters | structural + semantic | POS heuristic for passive; LLM judge to decide whether agent matters | no detector yet; `status: skipped` as of v0.5.0 |
| RULE-03 abstract vs concrete | semantic (audit) + hook-only mechanical | LLM judge: "does any sentence use a vague category word where a specific name, mechanism, or magnitude exists, or transcribe a table's numbers where the pattern should be stated?" `detectors_mech._rule_03` counts precise figures: decimals and percentages, not counts, versions, or references. It flags a numeric interval in body prose. In an abstract or introduction, it also flags three consecutive sentences with two or more figures each, or one sentence with five or more. | host model judgment. Both mechanical checks skip tables, code, and equations; only the interval check skips appendices and supplements. Hooks that import it run it, such as the anywhere-agents guard; `agent-style review` does not in either mode, so the published bench scope is unchanged. |
| RULE-04 needless words | semantic | LLM judge with Orwell Rule 3 + S&W §II.17 examples | host model judgment |
| RULE-05 dying metaphors / clichés | mechanical + semantic | Regex over 37 cliché phrases from Orwell 1946 + RULE-05 BAD examples; LLM judge for novel clichés | case-insensitive match bounded by `[A-Za-z0-9_]`; a hyphen does not suppress (`paradigm shift-based` fires), a word character does (`a novelty-detection` does not) |
| RULE-06 avoidable jargon | mechanical + semantic | Regex over 54 entries: the 45-word banned AI-tell list + 9 forms of 3 RULE-06 callouts | word-boundary match, case-insensitive |
| RULE-07 positive form + antithesis | structural + semantic | Detect `not <adj>` constructions with a positive equivalent; clause-level "X, not Y" / "not just X, but Y" antithesis via semantic judge | mechanical part deferred (`status: skipped`); antithesis via host model judgment |
| RULE-08 calibrated claims | semantic | LLM judge: "which claims are miscalibrated: a verb that overstates the evidence, a qualifier that adds no information, or a missing qualifier that would change what the evidence supports?" | host model judgment |
| RULE-09 parallel structure | structural | Heuristic on adjacent list items / coordinate clauses | no detector yet; `status: skipped` as of v0.5.0 |
| RULE-10 keep related words together | structural | Subject-verb distance heuristic | no detector yet; `status: skipped` as of v0.5.0 |
| RULE-11 stress position | semantic | LLM judge: "is new information at the end of each sentence?" | host model judgment |
| RULE-12 sentence length | mechanical | Count words per sentence; flag >30 | `>30` word threshold per RULES.md |
| RULE-A bullet overuse | structural | Flag lists of ≥3 items whose items read as sentence shards; the marker is not evidence, so ordered and unordered are treated alike, and neither is shortness on its own | 3-item minimum. **Strong** signal, fires at any item length: an item opens with a coordinator, subordinator or relative pronoun (`Because`, `Which`, `And`, `Rather`), or some but not all items lead with `Per`. **Weak** signal, needs every item ≤8 words: ≥2 items repeat a subject-and-copula opening (`It is` …). Imperative checklist steps, preposition-led enumerations (`For Linux, …`) and short independent labels stay clean; ambiguous triads whose second token varies are left to semantic review |
| RULE-B em/en-dash casual use | mechanical | Regex for `—` / `–` outside numeric ranges and paired names | excludes numeric-range and paired-name en-dashes and inline code |
| RULE-C consecutive same-starts | structural | Window of 3 adjacent sentences; flag if ≥2 share first token | 3-sentence sliding window |
| RULE-D transition overuse | mechanical | Sentence-initial match over all 6 directive openers, grouped by Markdown block | allow 1 per block; flag the second and later openers. A blank line, a fence, a markup-only line, an ATX heading, a table row, a thematic break, and each list item all end the block, so the allowance never leaks across a heading or between sibling bullets |
| RULE-E paragraph-closing summaries | structural | Pattern set for closer starters and restatement phrases | last-sentence-in-paragraph check |
| RULE-F term drift | semantic | LLM judge: "is any defined term re-defined or replaced with a synonym?" | host model judgment |
| RULE-G title case headings | mechanical | Parse Markdown headings; apply RULE-G's exact title-case convention | excludes question/full-sentence headings, code/link text, versions, digit-leading tokens, and paths |
| RULE-H citation discipline (critical) | semantic | LLM judge: "which claims sound authoritative but lack a named source or checkable evidence (citation, dataset, experiment, code artifact, or table pointer)?" | host model judgment |
| RULE-I contractions | mechanical | Closed host lists for ambiguous `'s` / `'d`; suffix regex for unambiguous endings outside code spans | excludes possessives and inline backtick spans |

## Source of truth

This matrix is in sync with:

- The `_CLASSIFICATION` dict in `packages/pypi/agent_style/review/primitive.py` and its Node mirror `packages/npm/lib/review/primitive.js`.
- The rule blocks in `RULES.md` (directive, BAD/GOOD examples, severity).

If the detectors diverge from the RULES.md text, update the detectors, not this matrix (the matrix documents intent).

## Judge prompt shape (semantic rules)

For each semantic rule, the host model is called with:

1. System: "You are a strict writing-rule auditor. Report only violations of the specific rule below. Output machine-readable JSON only."
2. User: the rule's directive + BAD/GOOD pairs + the source text, annotated with line numbers.
3. Expected response: JSON array of `{line, column, excerpt, detail}` objects, compatible with the deterministic Violation schema.

The skill parses the response and merges it into the full scorecard under the rule's `rule_results[...]` entry with `detector: "semantic"`.
