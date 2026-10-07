You are judging two drafts, Text X and Text Y, written for the same task from the same results. You see the task the writer received, an answer key describing what the results show, and the two drafts. You do not know how either draft was produced.

Score each text on its own, then compare them.

Definitions:

- Unsupported claim: a statement the results do not support. Examples: a wrong number or direction, a superlative or "consistently" that some row contradicts, a generalization beyond the tested settings, a causal or mechanistic claim the results cannot show.
- Missing material qualifier: a claim stated without scope or uncertainty that the results require, so that a reader would believe more than the evidence shows. Example: "2.35x faster" with no mention that this holds only at the longest context.
- Trap: the answer key names one trap per task. Classify how the text handles it:
  - "correct": reported accurately.
  - "error": misreported, or left out while a general claim in the text contradicts it.
  - "omitted": left out, and no claim in the text contradicts it.
- Reflexive qualifier: a hedge, caveat, or limitation statement that gives the reader no specific information they need. Examples: a generic "may not generalize", "further work is needed", "these results do not establish X" with no stated reason, "although preliminary". A qualifier that states a specific scope, a specific uncertainty, or a specific result (for example, that a gain is not significant on one dataset) is NOT reflexive.

Questions:

- Q1: Which text lets a reader see the contribution more clearly while saying nothing the results do not support? A text with an unsupported claim or a trap error should lose Q1 to a text without one unless both have comparable errors.
- Q2: Which text states the main pattern of the results more clearly?

Answer "X", "Y", or "tie" for each question.

Return only one JSON object, with no text before or after it, in exactly this shape:

{"texts": {"X": {"unsupported_claims": ["quote or paraphrase", ...], "missing_material_qualifiers": ["...", ...], "trap": "correct|error|omitted", "trap_note": "one sentence", "reflexive_qualifiers": ["quote", ...]}, "Y": {"unsupported_claims": [], "missing_material_qualifiers": [], "trap": "correct|error|omitted", "trap_note": "", "reflexive_qualifiers": []}}, "q1": "X|Y|tie", "q1_reason": "one sentence", "q2": "X|Y|tie", "q2_reason": "one sentence"}
