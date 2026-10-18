<!-- SPDX-License-Identifier: CC-BY-4.0 -->

# Human-Baseline Harness

`measure.py` measures how human-written papers read, and how often each detector in `agent_style.review.detectors_mech` speaks about them. Run it before a detector is added or a threshold moves. A detector for a document-wide pattern that reports on human papers is measuring a habit people share, and its threshold has to change before it ships. Detectors that point at a single sentence are different: they may report on some human papers, as a prompt to look, and the harness shows how often they do.

No corpus is committed. The papers stay on your machine, and the repository carries only the harness and `manifest.tsv`, the list of public arXiv IDs behind the 0.8.0 thresholds.

## What It Reports

For each `.tex`, `.md` or `.txt` document:

- the words, the prose sentences, the sentence-length median and 90th percentile, and the share of sentences over 30 words.
- rates per 1,000 prose words of `, so` clause joins, semicolons, sentence-initial relation words (contrast, cause, sequence) and scope-negation sentences.
- the finding count and the rate per 1,000 words of every detector in `detectors_mech`, the CLI rules and the hook-only ones.
- for the hook-only RULE-12 profile, the findings split by check: the sentences over the extreme length (the profile reports them as one finding per document, and the harness counts the sentences), a share of long sentences that is too high or too low, and `, so` joins. The `share checked` flag says whether the share check ran at all, because it reads only a complete LaTeX document: `\begin{document}` and `\end{document}`, a paper class, no `\input`, `\include` or `\subfile` left in the body outside a table or a figure, and 40 sentences or more. Markdown and text are never checked. Read the flag before reading a column of zeros, because a paper that is not checked cannot report a share.
- the long-sentence tail: the sentences over 50, 60, 65, 70, 75, 80 and 100 words, pooled by group, with the words per hit. This table is the basis of the extreme-sentence threshold.

The output is Markdown, JSON, or both, with a summary per group (minimum, median and maximum) and the number of documents in each group that a detector reports on.

Prose is segmented by the detectors' own pipeline. A metric therefore counts the sentences a detector sees. In LaTeX that means the preamble, title page, tables, figures, captions, display math and bibliography are left out, and each inline math span counts as one word. Markdown footnote definitions and their markers are left out as well. PDF-extracted text also works, but it is approximate: it keeps table cells, captions and line breaks. An earlier pass over the PDF text of the same 12 papers put the share of sentences over 30 words at about 18% to 46%, against about 9% to 33% from their LaTeX sources. The two do not share a scale. Calibrate on LaTeX sources and treat PDF text as a rough check.

The package is imported from this repository (`packages/pypi`), never from site-packages. A measurement therefore describes the working tree, and the harness fails loudly if it cannot import from there.

## Assemble a Corpus From ArXiv E-Prints

1. Choose papers people wrote and record each in a `manifest.tsv` with the columns `id`, `group`, `first_author`, `year` and `title`. A line that starts with `#` is a comment. Use one group for the papers you trust as a baseline and a second group for anything you want to compare against it.
2. Download each source: `curl -L -o <id>.src https://arxiv.org/e-print/<id>`. Pause a few seconds between requests, as arXiv's access guidelines ask.
3. An e-print is a gzipped tar archive, or a single gzipped `.tex` file. Extract each into a new, empty directory. Treat the contents as untrusted data: read them, and never run anything they hold.
4. Find the main file, the one with `\begin{document}`, and inline its `\input` and `\include` files into a single `<id>.tex`. Keep `\documentclass`, `\begin{document}` and `\end{document}` in the file, and leave no `\input` or `\include` of a body file behind. The profile's share check reads only a complete document, and a main file that still pulls its sections in is read as a file with no prose of its own. Skip a paper whose sources are missing files, or delete the `\input` lines of the missing files and record the gap in your notes.
5. Place the flattened files under `corpus/<group>/<id>.tex`. The directory name becomes the group when the manifest has no entry.

The papers stay under their authors' licenses. Keep the corpus out of the repository.

## Run It

```
python -I scripts/human-baseline/measure.py corpus --manifest scripts/human-baseline/manifest.tsv --md human-baseline.md --json human-baseline.json
```

The harness inserts `packages/pypi` on its own path. Running it with `-I`, which ignores the environment and the working directory, is therefore safe and is recommended for untrusted input. Without `--md` and `--json` the Markdown report goes to standard output.

## Reading the Report

Start with the group summary and compare the human group against the group you are testing. Document-wide patterns and single sentences get different expectations.

A document-wide pattern is the share of long sentences, the `, so` joins or a repeated caveat. Its threshold should leave the human group at zero reports per document, with a margin over the highest human value.

A check on single sentences, such as the report of sentences over 80 words, is a prompt to look at each sentence and says little about the paper as a whole. Some human papers hold such a sentence. Expect part of the human group to receive that finding, and judge the threshold by its rate over the pooled words and by whether it keeps to the far tail of the length distribution.

Write the margin and the measured range next to the constant in the detector, in rounded figures, and rerun the harness after every change.

## The 0.8.0 Calibration

`manifest.tsv` lists 18 public arXiv papers. Twelve are human-written papers from 2017 to 2022 (group `human`), among them reports, benchmarks, method papers and a toolbox description. Six are 2023 and 2024 papers on LLM agents (group `era`), which check that a threshold does not flag current human writing about the same topic. The sources of two era papers (SWE-bench and AgentBench) had `\input` files missing from the e-print. Their measured text is partial.

The named constants in `detectors_mech.py` that start with `_R12_` and `_R08_` come from this corpus, and each carries its basis in a comment. None of the 18 papers triggers a share, a `, so` or a repeated-caveat finding. Eight trigger the collapsed finding for sentences over 80 words, 21 sentences in all over about 224,000 words. Two choices follow from how the profile reads a paper. Footnote bodies and acknowledgment sections are not prose for any check, because about half of the sentences over 70 words in a first measurement were a footnote merged into the sentence around it. The extreme-sentence threshold sits in the far tail: over both corpora a sentence over 80 words comes once per 10,700 words, and at 60 words 15 of the 18 papers would get a finding.

## Tests

`packages/pypi/tests/test_human_baseline_measure.py` pins the metric functions on synthetic text, the manifest, the repository import and the report output. No test needs a corpus.
