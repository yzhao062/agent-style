# SPDX-License-Identifier: CC-BY-4.0

# style-review rule detector matrix

Reference for the `style-review` skill. Detection approach per rule; bucket determines which code path runs the check.

| Rule | Bucket | Detector approach | Threshold / heuristic |
| --- | --- | --- | --- |
| RULE-01 curse of knowledge | semantic | LLM judge: "are any terms undefined for the stated audience?" with rule directive + BAD/GOOD | host model judgment |
| RULE-02 passive voice when agent matters | structural + semantic | POS heuristic for passive; LLM judge to decide whether agent matters | deferred to v0.3.0; `status: skipped` in v0.2.0 |
| RULE-03 abstract vs concrete | semantic | LLM judge: "are any claims vague adjective/noun pairs without a metric/name/date?" | host model judgment |
| RULE-04 needless words | semantic | LLM judge with Orwell Rule 3 + S&W §II.17 examples | host model judgment |
| RULE-05 dying metaphors / clichés | mechanical + semantic | Regex over ~37 cliché phrases from Orwell 1946 + RULE-05 BAD examples; LLM judge for novel clichés | case-insensitive phrase match |
| RULE-06 avoidable jargon | mechanical + semantic | Regex over the 45-word banned AI-tell list + Orwell Rule 5 jargon words | word-boundary match, case-insensitive |
| RULE-07 positive form | structural | Detect `not <adj>` constructions with a positive equivalent | deferred to v0.3.0; `status: skipped` in v0.2.0 |
| RULE-08 calibrated claims | semantic | LLM judge: "which verbs overstate the evidence actually presented?" | host model judgment |
| RULE-09 parallel structure | structural | Heuristic on adjacent list items / coordinate clauses | deferred to v0.3.0; `status: skipped` in v0.2.0 |
| RULE-10 keep related words together | structural | Subject-verb distance heuristic | deferred to v0.3.0; `status: skipped` in v0.2.0 |
| RULE-11 stress position | semantic | LLM judge: "is new information at the end of each sentence?" | host model judgment |
| RULE-12 sentence length | mechanical | Count words per sentence; flag >30 | `>30` word threshold per RULES.md |
| RULE-A bullet overuse | structural | Flag bullet lists with ≤2 items OR all items ≤8 words | 2-item minimum; 8-word short-item threshold |
| RULE-B em/en-dash casual use | mechanical | Regex for `—` / `–` outside numeric ranges | excludes numeric-range en-dashes and inline code |
| RULE-C consecutive same-starts | structural | Window of 3 adjacent sentences; flag if ≥2 share first token | 3-sentence sliding window |
| RULE-D transition overuse | mechanical | Regex for sentence-initial `Additionally` / `Furthermore` / `Moreover` / `In addition` | line-start after list/blockquote markup |
| RULE-E paragraph-closing summaries | structural | Pattern set for closer starters and restatement phrases | last-sentence-in-paragraph check |
| RULE-F term drift | semantic | LLM judge: "is any defined term re-defined or replaced with a synonym?" | host model judgment |
| RULE-G title case headings | mechanical | Parse Markdown headings; apply RULE-G's title-case convention | lowercase articles, short prepositions, coord conjunctions |
| RULE-H citation discipline (critical) | semantic | LLM judge: "which claims sound authoritative but lack a named source / number / date / code artifact?" | host model judgment |
| RULE-I contractions | mechanical | Regex for contractions outside code spans | excludes inline backtick spans |

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
