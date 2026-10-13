# Complete design questions and conservative reuse

Date: 2026-10-10

## Problem

The design reviewer located candidates and printed fixed questions, then
asked the agent to print events separately. That handoff did not carry
called functions, shared definitions or the schema facts needed to judge
the question. A repeated review started that reading again.

## Evidence

A scripted comparison on the same project combined the full checker and
question preparation in one script invocation. Reading the batch supplied
the printed events and dependencies without another sheet lookup. The
first review returned more characters than the old checker, reviewer and
sheet print together: it also carried object, layout and schema evidence.
This supports fewer handoffs, not a claim of lower token use or cost.

The session answered a complete batch from that evidence. Repeated runs
reused its static judgements and left runtime checks pending. Regression
cases reject stale or unsupported answers and invalidate judgements after
shared definitions, objects, families, layouts, schemas or rules change.
Real preview plans drove collection, a delayed restart and alternating
turns, with state readback and runtime error checks.

Raw comparisons and failure logs are in
`.local/docs/evidence/skill-evals/rag-tool-flow/`. Clean model comparisons
could not finish because the CLI session could not authenticate and the
available agent session exhausted its quota. Model turns, tokens and cost
remain unmeasured.

## Options

- Keep separate review and print calls. This keeps the first response small
  but leaves dependency discovery and repeated reading to the agent.
- Prepare complete questions with evidence and validate saved judgements.
  This adds first-run input and code for dependency tracking, but makes
  the scope and the reason for invalidation inspectable.
- Add a repository graph or an external index. The existing event parser
  exposes explicit project relations; repository search already locates
  the maintenance entry points. No measured result justifies another index.

## Decision

Use `review_design.py --check --prepare .tmp/design-review --resume` in the
skill's repair loop. Select the changed sheets when the task supplies them.
Prepare relations on each invocation from current event and project fields.
Each relation carries direction and source evidence. Lexical closure is
conservative context selection, and unresolved scripts or mapped calls
widen the scope and prevent a passing judgement.

Keep the plain reviewer compatible. Batch whole questions and share their
evidence within a batch. Validate answer identity, version, citations and
suggestion scope; semantic correctness remains the reader's responsibility.
Accepted suggestions do not edit a project. `edit_sheet.py` still checks
event numbers against copied printed lines and validates its complete plan.
The final full checker, editor, input plan and visual review remain required.
Static reuse does not establish a runtime or visual result.

Keep the maintenance change to a task table in `skills/AGENTS.md`, pointing
to sources, tests and existing constraints. The current source determines
behavior. Do not add AST queries, a stale-summary checker or generated
module descriptions without a comparison that shows a benefit.

## Re-evaluate when

Complete clean model comparisons when authenticated sessions are available.
Reduce or revise the default packet flow if its added evidence increases
total task cost without improving completion or reducing supplemental reads.
Extend relation parsing only with a real project representation and a
regression case; an absent relation cannot establish that there is no effect.
