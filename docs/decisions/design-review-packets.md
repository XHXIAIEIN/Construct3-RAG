# Lightweight review and optional complete evidence

Date: 2026-10-10

## Problem

Design questions need called functions, shared state and schema facts.
Preparing complete evidence saves discovery steps, but that evidence can
cost more input than checking and printing the changed sheet.
Invocation counts alone cannot establish a lower task cost.

## Evidence

Characters each review path returns on one test project, scripted with the
same input, three repeats each with equal results; these are characters, not
model tokens or cost:

| Path | Characters |
|------|------------|
| Checker, plain review and printed sheet, before complete packets | 6,107 |
| First complete packet when it became the default | 46,223 |
| First complete packet, before and after scoping evidence by question | 49,161 and 38,995 |
| Same, reused judgements (cached) | 7,484 and 7,480 |
| Same, after a local change | 49,870 and 39,704 |
| `--check --limit 0`, the default now | 6,181 |

Coverage questions start from the selected sheet and follow shared symbols
and includes. Unrelated sheets stay outside their evidence. Relevant
layouts retain complete instance, initial-value and hierarchy data because
those fields can affect picking and behavior. Cached judgements avoid a
batch read, but their manifest carries accepted reasons and citations, and a
change in shared timing can invalidate every question.

The model comparison is one static review per arm (n = 1): from the packets
before and after scoping, both answered the seven questions alike (six pass,
one needs a change) with no supplemental project read, in 144 and 135
seconds. One run per arm gives no spread, and a static review is not a
repair task, so this shows that scoping lost no answer here, not that either
path costs less. When complete packets became the default, a clean model
comparison could not run at all: the CLI's OAuth session had expired and the
agent session's quota was spent. Model turns, tokens and cost of a full
repair task remain unmeasured for every path.

Scripted validation replays use synthetic answers and establish transport
size and invalidation only. Raw input, answers, commands and failure logs:
`.local/docs/evidence/skill-evals/rag-tool-flow/` for the first complete batch,
`.local/docs/evidence/skill-evals/rag-review-scope/` for the scoping.

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
Select changed sheets with `review_design.py --sheets NAME` when the task
supplies them. Read every design question and its required evidence with
`print_sheet.py`.

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
A reused judgement replaces none of the final runs: the full checker, the
editor, the target input and the visual review. Static reuse cannot
establish a runtime or visual result.

Before changing the review, read its row in the task table of
`skills/AGENTS.md`, "Change a project tool", which names its sources, tests
and contracts. The source decides what the tool does.

## Re-evaluate when

The skill's change to this default owes its eval iteration (`skills/AGENTS.md`,
"Evals"); its route counts and lost calls decide whether the default stays.
Measure complete repair tasks with repeated clean model runs before choosing
complete batches as the default. Record actual tokens and cost when exposed
by the model session. Extend relation parsing with a real project
representation and a regression case for each dependency it adds.
