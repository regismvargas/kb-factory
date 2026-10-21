# Measured value: counterfactual experiments (October 2026)

Does a project knowledge base make a coding agent better, and does the gain come from the curated content or from the machinery that serves it? We ran two pre-registered counterfactual experiments on two real projects to find out. This page reports the method and the numbers. The projects are anonymized as project 1 (446 records) and project 2 (216 records); no project content is published.

## Bottom line

- **The value is the curated content, and it is large.** With the knowledge base, the agent recalled every core fact of the lookup tasks; with only its native memory it recalled half of them, and 9% of the facts that exist only in the knowledge base. False claims dropped from 0.63 to 0 per run, cost fell by about 40% and wall time by about 25%.
- **The read-side machinery adds no recall over the same content.** In both experiments the same records exported to plain Markdown, read with the agent's ordinary file tools, matched the knowledge base: 0.99 against 1.00 on lookup tasks, and equivalent within a 10-point margin on cross-record synthesis tasks.
- **What this means for the product:** curation, governance and getting content to the agent matter; search sophistication does not, at these sizes. The runtime is still what keeps the content correct: governed writes, status and supersession, exports and hygiene.

## Design

Each experiment copies one project three times and runs the same headless coding agent (Claude Code, Opus) on the same questions:

| Condition | What the agent gets |
|---|---|
| A, knowledge base | the project with `.kb/` and `.kb-next/`, the runtime commands and the session hooks |
| B, native memory only | the project without the knowledge base |
| C, Markdown export | the project without the knowledge base, plus every record exported to Markdown with all fields and a verbatim copy of the rest of the memory |

Instructions are equalized sentence by sentence between A and C. Answers are graded blind by a model of a different family (Codex, gpt-6-astra), and a 20% sample is checked by hand. Every run is audited for tool calls outside its own folder; such runs are excluded. Decision rules were fixed before any scored run.

## Experiment 1: lookup tasks (project 1)

10 tasks in the style of a project owner's questions, 44 gold facts, 3 runs per task and condition (90 runs, 2 excluded by the isolation audit). Manual check agreement: about 99%.

| Per-task mean | A, knowledge base | B, native only | C, Markdown |
|---|---|---|---|
| Recall of core facts | 1.00 | 0.51 | 0.99 |
| Facts that exist only in the knowledge base (14) | 1.00 | 0.09 | 1.00 |
| Facts also stated in the repository (12) | 1.00 | 1.00 | 1.00 |
| False claims per run | 0.00 | 0.63 | 0.03 |
| Cost | USD 0.33 | USD 0.57 | USD 0.34 |
| Wall time | 63 s | 86 s | 50 s |

The whole gain sits in the facts only the knowledge base holds: where a fact is also in the repository, all three conditions find it. Without the knowledge base the agent does not just forget; it rebuilds the project state from stale documents and states it as current.

## Experiment 2: synthesis tasks (project 2)

15 tasks with 115 gold items: 10 retrieval controls and 5 cross-record tasks (dependency chains, reversals over time, exceptions to a rule, status reconciliation, quantities across records), the latter written blind by the grading model from the export. 105 runs: 3 per task for A and C, 1 for B as a reference. Writes and reads outside each condition folder were blocked by permissions and verified by probes before the scored runs. Manual check agreement: 92.3% of 182 item verdicts; the grader was the stricter side in almost every disagreement, equally for all conditions.

Pre-registered rule on recall, A minus C, 90% bootstrap interval over tasks: a machinery gain needs a mean of at least 10 points with the interval above zero; equivalence needs the whole interval inside plus or minus 10 points.

| Per-task mean | A, knowledge base | C, Markdown | B, native only |
|---|---|---|---|
| Recall | 0.904 | 0.937 | 0.598 |
| Precision on closed tasks | 0.966 | 0.956 | 0.771 |
| Items only in the memory (16) | 0.81 | 0.85 | 0.00 |
| False claims per run | 0.067 | 0.067 | 0.222 |
| Tokens | 627 k | 438 k | 767 k |
| Cost | USD 0.54 | USD 0.47 | USD 0.80 |

**Verdict: equivalent within the margin.** A minus C is -3.3 points, 90% interval [-5.4, -1.4]: Markdown came out slightly ahead and used about 30% fewer tokens. In the experiment's permission setup, 23% of A's runtime commands were denied because agents prefixed them with `cd <absolute path> &&`; restricting A to the runs that used the runtime gives -2.8 points [-4.6, -1.1], the same verdict.

## Search

The same work measured the search layer on LongMemEval. The [usage guide](../products/kb-wiki-vnext/docs/en/usage-guide.md#dense-index) explains how to turn on the optional dense list.

| Route | Extra cost per cold command-line lookup | Measured gain |
|---|---|---|
| Words only (BM25, default) | none (0.5 s total) | ranked results instead of an unranked substring match |
| Optional dense list, `potion-base-32M` | about 3 s | LongMemEval M session recall at the paper's dense retriever (0.764 and 0.864 against 0.762 and 0.862), no margin |
| Optional dense list, `potion-multilingual-128M` | about 11 s | synonyms in Portuguese; not recommended for routine use |
| Agent-side query expansion (skill instruction) | none | on LongMemEval M, words plus expansion pass the same target without the dense list |

## Limits

- Two projects, one agent model, read-only tasks. The write side (governance, curation, the cost of keeping the content correct) was not measured.
- The gold sets come from the records that exist today; without a knowledge base, part of that knowledge might have been written elsewhere in the repository.
- Blinding is partial: the style of an answer's citations can hint at its condition.
- The grading model also wrote the five cross-record tasks of experiment 2.
