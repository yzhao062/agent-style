# SPDX-License-Identifier: CC-BY-4.0

# style-review rule detector matrix

Reference for the `style-review` skill. Detection approach per rule; bucket determines which code path runs the check.

| Rule | Bucket | Detector approach | Threshold / heuristic |
| --- | --- | --- | --- |
| RULE-01 curse of knowledge | semantic | LLM judge: "are any terms undefined for the stated audience?" with rule directive + BAD/GOOD | host model judgment |
| RULE-02 passive voice when agent matters | structural + semantic | POS heuristic for passive; LLM judge to decide whether agent matters | no detector yet; `status: skipped` as of v0.8.0 |
| RULE-03 abstract vs concrete | semantic (audit) + hook-only mechanical | LLM judge: "does any sentence use a vague category word where a specific name, mechanism, or magnitude exists, or transcribe a table's numbers where the pattern should be stated?" `detectors_mech._rule_03` counts precise figures: decimals and percentages, not counts, versions, or references. It flags a numeric interval in body prose. In an abstract or introduction, it also flags three consecutive sentences with two or more figures each, or one sentence with five or more. LaTeX sources get three more checks: the three-sentence run anywhere in the body outside setup sections, a precision check, and a caption check. The precision check flags a paragraph with four or more numbers at four or more decimal places and three or more significant digits. Captions are flagged at three or more figures, legend values aside, or over 100 words. | host model judgment. Every mechanical check skips tables, code, and equations; all but the abstract and introduction check skip appendices and supplements. A hook that passes only an edited fragment loses the surrounding section and appendix context. Hooks that import it run it, such as the anywhere-agents guard; `agent-style review` does not in either mode, so the published bench scope is unchanged. |
| RULE-04 needless words | semantic | LLM judge with Orwell Rule 3 + S&W §II.17 examples | host model judgment |
| RULE-05 dying metaphors / clichés | mechanical + semantic | Regex over 37 cliché phrases from Orwell 1946 + RULE-05 BAD examples; LLM judge for novel clichés | case-insensitive match bounded by `[A-Za-z0-9_]`; a hyphen does not suppress (`paradigm shift-based` fires), a word character does (`a novelty-detection` does not) |
| RULE-06 avoidable jargon | mechanical + semantic | Regex over 54 entries: the 45-word banned AI-tell list + 9 forms of 3 RULE-06 callouts | word-boundary match, case-insensitive |
| RULE-07 positive form + antithesis | structural + semantic | Detect `not <adj>` constructions with a positive equivalent; clause-level "X, not Y" / "not just X, but Y" antithesis via semantic judge | mechanical part deferred (`status: skipped`); antithesis via host model judgment |
| RULE-08 calibrated claims | semantic (audit) + hook-only mechanical | LLM judge: "which claims are miscalibrated: a verb that overstates the evidence, a qualifier that adds no information, or a missing qualifier that would change what the evidence supports?" Hook-only: `detectors_mech._rule_08_repeats` reports one caveat framing stated three or more times outside a limitations section; see Hook-only detectors | host model judgment. The hook check needs three similar caveat sentences. A fragment with fewer never reports, and `agent-style review` does not run it |
| RULE-09 parallel structure | structural | Heuristic on adjacent list items / coordinate clauses | no detector yet; `status: skipped` as of v0.8.0 |
| RULE-10 keep related words together | structural | Subject-verb distance heuristic | no detector yet; `status: skipped` as of v0.8.0 |
| RULE-11 stress position | semantic | LLM judge: "is new information at the end of each sentence?" | host model judgment |
| RULE-12 sentence length | mechanical (audit) + hook-only profile | Count words per sentence; flag >30. Hook-only: `detectors_mech._rule_12_profile` replaces this per-sentence check in a hook with a document-level reading; see Hook-only detectors | `>30` word threshold for the audit, kept so that scores stay comparable with earlier releases (the directive no longer states a cap). The profile reports sentences over 80 words once per document, a share of long sentences outside 6% to 45% in a complete LaTeX paper, and `, so` clause joins in a paper; `agent-style review` keeps `_rule_12` |
| RULE-A bullet overuse | structural + hook-only mechanical | Flag lists of ≥3 items whose items read as sentence shards; the marker is not evidence, so ordered and unordered are treated alike, and neither is shortness on its own | 3-item minimum. **Strong** signal, fires at any item length: an item opens with a coordinator, subordinator or relative pronoun (`Because`, `Which`, `And`, `Rather`), or some but not all items lead with `Per`. **Weak** signal, needs every item ≤8 words: ≥2 items repeat a subject-and-copula opening (`It is` …). Imperative checklist steps, preposition-led enumerations (`For Linux, …`) and short independent labels stay clean; ambiguous triads whose second token varies are left to semantic review. Hook-only: `detectors_mech._rule_a` flags a LaTeX table with a cell over 15 words or of two sentences, outside appendices and supplements; `agent-style review` does not run it |
| RULE-B em/en-dash casual use | mechanical | Regex for `—` / `–` outside numeric ranges and paired names | excludes numeric-range and paired-name en-dashes and inline code |
| RULE-C consecutive same-starts | structural | Window of 3 adjacent sentences; flag if ≥2 share first token | 3-sentence sliding window |
| RULE-D transition overuse | mechanical | Sentence-initial match over all 6 directive openers, grouped by Markdown block | allow 1 per block; flag the second and later openers. A blank line, a fence, a markup-only line, an ATX heading, a table row, a thematic break, and each list item all end the block, so the allowance never leaks across a heading or between sibling bullets |
| RULE-E paragraph-closing summaries | structural | Pattern set for closer starters and restatement phrases | last-sentence-in-paragraph check |
| RULE-F term drift | semantic | LLM judge: "is any defined term re-defined or replaced with a synonym?" | host model judgment |
| RULE-G title case headings | mechanical | Parse Markdown headings; apply RULE-G's exact title-case convention | excludes question/full-sentence headings, code/link text, versions, digit-leading tokens, and paths |
| RULE-H citation discipline (critical) | semantic | LLM judge: "which claims sound authoritative but lack a named source or checkable evidence (citation, dataset, experiment, code artifact, or table pointer)?" | host model judgment |
| RULE-I contractions | mechanical | Closed host lists for ambiguous `'s` / `'d`; suffix regex for unambiguous endings outside code spans | excludes possessives and inline backtick spans |

## Hook-only detectors

A hook, such as the anywhere-agents guard, reaches these detectors by name and passes the file path along with the text. The npm package exports them as `rule12Profile`, `rule08Repeats`, `rule03` and `ruleA`, next to the Python `_rule_12_profile`, `_rule_08_repeats`, `_rule_03` and `_rule_a`. `agent-style review` never runs them. The audit classifies RULE-03 as semantic, RULE-A as structural and RULE-08 as semantic, and it keeps `_rule_12` for RULE-12. That leaves the published bench scope unchanged. Each detector reports a departure from the range of human-written papers and says what to consider. None of them calls a finding a violation.

The thresholds were measured with `scripts/human-baseline/measure.py` on the papers listed in `scripts/human-baseline/manifest.tsv`. Twelve are arXiv papers from 2017 to 2022, about 137,000 words (the human corpus), and six are 2023 and 2024 papers on LLM agents, about 87,000 words (the era corpus). Every figure below is rounded and comes from their LaTeX sources, each wrapped as a whole document, with footnote bodies and acknowledgments left out. Each threshold is a named constant in `detectors_mech.py`, with its basis in a comment beside it.

### RULE-12 profile

`_rule_12_profile` replaces `_rule_12` in a hook, under the same label. `_rule_12` flags every sentence over 30 words, which asks for a uniform length that human papers do not have. The profile reads the whole document and reports three patterns, in this order: the share, the `, so` joins, then the long sentences.

| Check | Reports when | Human corpus | Era corpus |
| --- | --- | --- | --- |
| Share of long sentences | a complete LaTeX paper has more than 45% or fewer than 6% of its prose sentences over 30 words; reported once | 9% to 33%, median 15% | 7% to 32% |
| `, so` clause joins | a paper context has at least 6 joins, at 1.5 or more per 1,000 words, in at least 1,000 words; reported once | 0 to 0.5 per 1,000 words | 0 to 0.5 |
| Long sentences | a document has a prose sentence over 80 words; one finding gives the count and the line of the first | 1 per 9,750 words; 4 of 12 papers have one | 1 per 12,500 words; 4 of 6 papers |

A finding about the document as a whole, which means the share, the `, so` joins and a repeated caveat, begins with `Across the document, `. The profile emits those first and the long-sentence finding last. A hook that shows only its first findings therefore keeps them, and a consumer that scopes findings to the changed lines can keep them when a revision touches other lines.

Reading rules:

- A share is read only in a complete LaTeX paper. That is a file with `\begin{document}` and a later `\end{document}`, whose class is not for slides, posters, letters or CVs (`beamer`, `powerdot`, `tikzposter`, `letter`, `scrlttr2`, `moderncv` and similar), with no `\input`, `\include` or `\subfile` left in the body outside a table or a figure, and with at least 40 prose sentences. A section file, a fragment, an edit that holds only the opening of a document, and a main file that pulls its sections in never get a share check, since one part of a paper has its own mix. Markdown and text never get one either. No heading or file name shows that such a file is whole or what genre it is, and a design note with an Introduction and a Conclusion looks like a paper. Agent notes and design documents are written under the 30-word rule on purpose and mostly sit at 0% to 8%.
- `, so` is read in a paper context: any LaTeX file that is not slides or a letter, a section file included. Markdown and text are never read. Changelogs and design notes carry the join at 2 to 11 per 1,000 words by design. An Abstract or Introduction heading opens design notes as often as papers and cannot carry the paper calibration. The check counts a join before a clause and skips so that, so far, so on, so forth, so as, so much, so many, so long, so few, so little, so often, so well and so-called.
- A fragment gets no share check. The `, so` check needs 1,000 words, which a section file or a long edit can reach. Long sentences need no document, and that check reads any prose. It compares with human-written papers in a paper context and with human-written prose elsewhere. A LaTeX section file without `\begin{document}` therefore receives only these two checks.
- Prose is segmented as RULE-03 segments it: code, comments, display environments, tables, headings and captions are left out. The LaTeX preamble and title page are left out too. So are the arguments of `\footnote`, `\footnotetext` and `\thanks`, which are no part of the sentence that carries them, Markdown footnote definitions (a line that opens with `[^label]:`, the lines that follow it, and each paragraph indented four columns after a blank line) with their markers in running text, acknowledgment sections (`\section*{Acknowledg...}`, `ack`, `acks` and `acknowledgments` environments, `\acks`, a Markdown heading that begins Acknowledg), and a leading YAML front-matter block. Each inline math span counts as one word, and a sentence under three words is not prose. Lines of one paragraph are joined. Hard-wrapped source therefore reads like unwrapped text.
- Document-wide patterns and single sentences are held to different expectations. The share, the `, so` joins and the repeated caveat describe a whole paper. None of the 18 papers triggers any of them. A sentence over 80 words describes one sentence. The finding is a prompt to check that the sentence carries one connected thought, and 8 of the 18 papers trigger it, with 21 such sentences in about 224,000 words. Most are enumerations such as "(i) ..., (ii) ..." and lists of names. About half of the sentences over 70 words in a first measurement were a footnote merged into the sentence around it, and footnote bodies are now set aside. The threshold sits in the far tail on purpose: at 60 words 15 of the 18 papers would get a finding, which would make it a note on nearly every paper.

### RULE-08 repeats

`_rule_08_repeats` reports a caveat framing stated three or more times outside a limitations section. The message asks for the copies that add nothing to go. A qualifier that bounds a claim, a limit of the study design included, stays with that claim and with every summary of it. Caveats that share one frame and differ in their subject, such as the same "does not establish whether it transfers to ..." with a new domain each time, are grouped as one framing.

1. A sentence is a caveat when it matches a scope or limitation cue: does not establish, show, test, imply or identify; we do not claim, test or measure; cannot rule out or distinguish; is limited to; remains untested, unknown or open; beyond the scope; we leave something to future work; it is unclear whether; should not be read as; one limitation or caveat.
2. Each caveat is reduced to content stems: lowercase, function words and the cue vocabulary dropped, plurals and `-ed`, `-ing` endings trimmed.
3. A caveat joins the first group it resembles. Two caveats resemble each other at 3 or more shared stems, when the shared stems are at least 60% of the smaller set and at least 30% of the union.
4. A group of three or more is reported once, at its first instance. The message quotes the first ten words of that sentence and lists the lines of the others.

Sentences under a limitations-style heading (limitations, caveats, threats to validity, and similar, up to the next heading of the same level), in a paragraph that opens with a bold run-in lead holding one of those words (`\textbf{Limitations.}`, `\noindent\textbf{Limitations}`, `**Limitations.**`, to the end of that paragraph), in a file named for one, in an appendix, or in a file named for an appendix are not counted. Footnote bodies (LaTeX arguments and Markdown definitions) and acknowledgments are not prose here either. A limitation stated once in the text and once under Limitations stays quiet. The finding begins with `Across the document, `.

Outside those sections, 17 of the 18 papers hold 0 to 6 caveat sentences each, and the 214-page report holds 34. No paper holds even a pair of similar caveats. The closest pair, two long sentences about different open problems, shares 45% of the smaller stem set and 20% of the union, which leaves a margin under the thresholds. Nothing in the corpus gives a reason to raise the floor of 3 shared stems.

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
