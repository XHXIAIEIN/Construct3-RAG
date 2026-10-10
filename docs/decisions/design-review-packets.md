# Lightweight review and optional complete evidence

Date: 2026-10-10

## Problem

Design questions need called functions, shared state and schema facts.
Preparing complete evidence saves discovery steps, but that evidence can
cost more input than checking and printing the changed sheet.
Invocation counts alone cannot establish a lower task cost.

## Evidence

Same-input scripted first, cached and local-change reviews show that
sharing constraints and compact JSON reduce complete packet input.
Coverage questions start from the selected sheet and follow shared symbols
and includes. Unrelated sheets stay outside their evidence. Relevant
layouts retain complete instance, initial-value and hierarchy data because
those fields can affect picking and behavior.

The first complete packet still supplies substantially more characters
than checking and printing the sheet. Cached judgements avoid a batch read,
but their manifest carries accepted reasons and citations. A change in
shared timing can invalidate every question. These results support an
optional reuse path, not a default claim of lower task cost.

Clean static model reviews answer the same questions from each packet.
This comparison measures static judgement and supplemental reading.
It does not measure a full repair task, model token cost or repeated-run
variation. Scripted validation replays use synthetic answers and establish
transport size and invalidation only. Raw input, answers, commands and
failure logs are retained in
`.local/docs/evidence/skill-evals/rag-review-scope/`.

## Options

- Check and print questions, then read the changed sheet and dependencies.
  This keeps the first response small and requires explicit discovery.
- Prepare complete questions with evidence and validate saved judgements.
  This makes dependency scope and invalidation inspectable but adds input.
- Add a repository graph or external index. The existing parser already
  exposes project relations; no measured benefit supports another index.

## Decision

Use `review_design.py --check --limit 0` in the skill's repair loop.
It runs the full checker, records its complete result and stops on failure.
Read every design question and its required evidence with `print_sheet.py`.
Select changed sheets with `--sheets` when the task supplies them.

Use optional `--prepare .tmp/design-review --resume` for shared dependency
evidence or saved judgements. Prepare relations from current project files
on each invocation. Preserve each complete question, its citations, input
version and stable suggestion targets. Batch constraints are shared under
`review`; compact whitespace changes presentation only.

Calls and shared state extend scope to definitions and other uses.
Explicit includes follow their referenced sheets. Family and container
members retain their object data and picking relationships. Lexical
closure remains conservative. Scripts and unresolved dynamic dispatch
widen scope and prevent a passing judgement. Each explicit relation carries
direction and source evidence; an absent relation cannot prove no effect.

Keep the plain reviewer compatible. Validate answer identity, version,
citations and suggestion scope; semantic correctness belongs to the reader.
Saved suggestions do not edit a project. `edit_sheet.py` checks copied
printed lines and event numbers before applying a complete plan.
The final full checker, editor, target input and visual review still run.
Static reuse cannot establish a runtime or visual result.

The maintenance task table points to sources, tests and existing contracts.
The current source determines behavior.

## Re-evaluate when

Measure complete repair tasks with repeated clean model runs before choosing
complete packets as the default. Record actual tokens and cost when exposed
by the model session. Extend relation parsing with a real project
representation and a regression case for each dependency it adds.
