<!-- SPDX-License-Identifier: CC-BY-4.0 -->

# House Style Bench: v0.9.0

The House Style section of `RULES.md` comes from this bench. It asks two questions: how close can an agent's paper prose come to one author's own writing, and does an agent apply that style when it is shipped as rules and a skill rather than pasted into a prompt? Habits written as rates, together with the author's own passages, moved drafts closer to the author on word use, sentence length, glosses, and parentheses, and brought back the abstract moves the general rules had dropped; relation words stayed below the author's rate, and abstracts opened with a question more often than the author's do. A four-pair blind test used drafts from an earlier form of the habits (condition F), and the author took three of them for their own originals. In a consumer setup with the full composed `AGENTS.md`, every agent loaded the `author-voice` skill for a paper section without being asked, also when asked only to polish an existing section, and never loaded it for a README or an email.

## 1. Corpus and Tasks

The reference is five first-author ML papers written before AI writing tools: MetaOD (NeurIPS 2021), SUOD (MLSys 2021), ELECT (ICDM 2022), HPOD (arXiv 2022), and ADMoE (AAAI 2023). Their LaTeX was reduced to prose by section.

Twelve tasks rewrite one section each: the five abstracts, three introductions (MetaOD, ELECT, ADMoE), and four conclusions (MetaOD, HPOD, SUOD, ELECT). An agent turned each original section into a fact sheet that keeps every claim, number, and scope but no wording, and the task asks for the section from that sheet at the original's length. Writers were Claude Opus 5.5 and Claude Sonnet 5.5 through `claude -p` and Codex `gpt-6.1-sol` through `codex exec`, one generation per task, 36 drafts per condition. The habit-bench judge from `scripts/bench/habit/` scored accuracy in blind A/B pairs.

Every condition that shows the author's passages uses leave-one-paper-out: a draft of a section never sees any section of its own paper.

## 2. Measures

Style is measured against the original sections in four ways:

- Burrows' Delta over the 120 most frequent words of the author's sections, from each draft to its original (lower is closer).
- Sentence shape and punctuation: share of sentences over 30 words, sentence-initial relation words, e.g. and i.e. glosses, parentheses, numbers, ", so" joins, and semicolons.
- Four abstract moves: a question, a "Given ..." or concession opening, "In this work", and "Extensive experiments".
- `voice_check.py` from the `author-voice` skill, which counts the measures that fall outside the author's range. On the author's own fifteen abstracts, introductions, and conclusions it reports about one measure outside range on average, not counting the flagged words the author uses and the pack keeps out; on drafts under the 0.8.0 rules it reports about three.

## 3. What Moves the Style

| Condition | Delta | Over 30 words | Relation words /1k | e.g./i.e. /1k | Parentheses /1k | Abstracts with a question |
| --- | --- | --- | --- | --- | --- | --- |
| Author's originals | | 25% | 3.8 | 4.7 | 27 | 60% |
| A: 0.8.0 rules | 0.626 | 4% | 0.8 | 0.0 | 9 | 13% |
| C: rules + passages | 0.545 | 6% | 1.7 | 1.1 | 12 | 80% |
| D: C + "the author comes first" | 0.525 | 8% | 4.8 | 1.7 | 15 | 80% |
| B: rules + habit card | 0.535 | 14% | 7.8 | 5.8 | 24 | 100% |
| E: rules + card + passages | 0.531 | 17% | 7.6 | 3.9 | 23 | 100% |
| F: card + passages, no general rules | 0.524 | 17% | 8.0 | 6.1 | 28 | 100% |
| G: card with rates + passages | 0.499 | 17% | 2.0 | 5.8 | 27 | 87% |

The passages carry the moves and the stock phrases ("In this work", "Extensive experiments show"); the habit card carries sentence shape, glosses, and parentheses. A card written as instructions overshot: drafts under B, E, and F used "Moreover", "Notably", and "In a nutshell" about twice as often as the author and opened every abstract with a question. Writing each habit as the rate the papers show (G) brought relation words down from about twice the author's rate to about half of it and kept the other gains. Dropping the general rules (F against E) changed little, so the House Style ranks above the rules instead of replacing them.

Judged accuracy did not worsen with the card. Against condition A in the same runs, unsupported claims were 4 against 9 for B, 4 against 7 for E, and 4 against 6 for G, with one trap error in all of B through G together. Reflexive qualifiers rose (6 to 11 per arm, against 1 to 4), which matches the author's own hedges such as "(to the best of our knowledge)". The judge preferred condition A on clarity in most pairs, so the judge is no stand-in for the author.

## 4. Blind Test

The author read four pairs (two abstracts and two conclusions), each holding an original section and a condition F draft from the same facts, and named which was theirs. The author named the AI draft as their own in three of the four pairs, confidently in one, and judged the two texts close in the last two pairs. Condition F is an earlier form of the released habits, without their rates.

## 5. Release Check: Does the Agent Apply It?

The released text ran in a consumer setup: the full composed `AGENTS.md` (shared baseline, this pack, and the `profile` and `paper-workflow` packs, about 57 KB with the bootstrap and banner sections removed), with the `author-voice` skill installed and its passages again leave-one-paper-out. Condition A is the same file with agent-style 0.8.0 and the earlier profile. Task prompts never named the skill.

| Condition | Delta | Over 30 words | Relation words /1k | e.g./i.e. /1k | Parentheses /1k | `voice_check` outside range |
| --- | --- | --- | --- | --- | --- | --- |
| Author's originals | | 25% | 3.8 | 4.7 | 27 | about 1, flagged words aside |
| 0.8.0 consumer | 0.578 | 3% | 1.6 | 0.4 | 9 | 3.2; no draft at 0 |
| 0.9.0 consumer with skill | 0.505 | 24% | 3.3 | 4.7 | 21 | 0.3; 29 of 36 at 0 |

Delta is computed over the drafts and originals that share one table, so it compares rows within a table, not across tables.

Judged accuracy held. Unsupported claims were 12 under 0.8.0 and 5 under 0.9.0, though the same 0.8.0 drafts drew 8 in an earlier judging, so these counts move by about four from one judging to the next. Neither condition missed a material qualifier or failed the trap. Reflexive qualifiers rose from 2 to 9, and the judge preferred the 0.8.0 drafts on clarity in 20 pairs and the 0.9.0 drafts in 9, with 7 ties.

A separate run recorded each agent's tool calls. For the abstract, introduction, and conclusion tasks, all 15 runs (Opus and Codex twice per task, Sonnet once) loaded the skill, read its template and passages, and ran `voice_check.py` before finishing; 14 of the 15 final drafts had no measure outside the author's range. For a README section and an email, none of 10 runs loaded the skill. The trigger is the `profile` line that names the skill for those sections, together with the skill's own description.

Polishing an existing section drew the skill as well. In 15 runs, `main.tex` held a 0.8.0 draft of an abstract, introduction, or conclusion, and the prompt asked only to polish it before submission. Every run loaded the skill and ran the script, and no run dropped or added a number. Under an earlier skill wording that let any departure stay if it read well, the agents left most rate measures alone: measures outside range fell from 4.0 to 1.9 on average, and the Codex runs barely moved. The released skill asks a polish to treat long sentences, glosses, and parentheses as targets, using only material already in the text and keeping the relation between joined claims. Measures outside range then fell to 0.5, with 8 of 15 polishes at 0. A judge from the other model family found a change of meaning in 3 of these 15 polishes and in 2 of 15 under the earlier wording; two of the three were joined sentences that made one claim read as the cause of another.

## 6. Where the Rules Fight the Author

A review of the author's own sections against each rule's directive found four rules the author breaks as a habit:

- RULE-05: "capitalizes on", "In a nutshell", "carries over", "a black art". The House Style names these as the author's own.
- RULE-06: "leverage" appears 37 times in the five papers, "facilitate" 13 times. Drafts under the rules never used them, even where a fact sheet did. The maintainer kept RULE-06, so the skill tells writers not to copy these words from the passages.
- RULE-B: 37 unspaced or spaced dashes for a trailing gloss. The maintainer kept the ban.
- RULE-F: abbreviations defined more than once and near-synonyms alternated. The rule stays; the House Style asks for fixed terms.

Two words from the banned list also appear in the papers, and the guard keeps blocking them. Smaller tensions were resolved in the text: RULE-D now lets "Moreover" or "Notably" open one sentence in a paragraph, RULE-04 no longer asks a conclusion to restate its limits, and the RULE-12 example keeps a 45-word sentence from the author that an AI draft had cut into three.

## 7. Limits

One author, five papers, and one field (outlier detection) set every range here. The fact sheets came from the papers themselves, so a draft that matches the original also matches the facts it was given. Three writers from two model families wrote the drafts, each judged by the other family, and the judges count unsupported claims well but prefer the generic rules on clarity. The blind test had four pairs. In the consumer bench the agent's reply is the draft, so 13 of the 36 condition B drafts ended with the `voice_check` report the skill asks for; those lines were cut before the style measures and the judging. In normal use the draft goes to a file and the report stays in the reply. The skill gained its polishing step after the 36-draft run and its clause on joined claims after the trigger run; the polishing figures use the released wording.
