# Event Sheet Design Guidance

Date: 2026-09-07
Schema: Construct 3 r495.2

## Problem

An agent asked to rework a drag-and-drop interaction wrote a program
transcribed into events: UID instance variables linking slots and pieces in
both directions, globals for the dragged piece, `Pick all` in most
sub-events of the drop trigger, custom actions whose only job was to keep
two variables agreeing. It reached the native shape after three attempts
and the user's guidance: a family as the second pick of one object type,
collisions off during the drag, `Pick overlapping point`, then a trigger,
narrowing sub-events and `Else`.

The repository held a catalog of which ACEs exist and nothing on when to use
them. The failure was one of modelling, relations as pointers instead of
relations as conditions, which a catalog cannot correct. Nothing in the game
project pointed at the repository either.

## Decision

A design layer in prose, a design SOP, and a route to both from the game
project.

| File | Answers |
|------|---------|
| `prompts/event-sheet-thinking.md` | What the events are: the picking model, the native shape per interaction, the smell table |
| `prompts/event-sheet-pitfalls.md` | Runtime facts intuition gets wrong: every pitfall as a one-line conclusion, with its fix, under a when-to-read line |
| `prompts/pitfalls/` | One file per topic of the index, each pitfall with its cases and its source |
| `prompts/event-sheet-assistant.md` | Output format and name verification |
| `prompts/event-sheet-style.md` | How the official examples organise, name and comment a sheet |
| `prompts/references/` | Material needed only sometimes, each named by the task that needs it: a new project's sheets, layers, objects and look; feel; the slot case, native and as a program; hand-editing project JSON; bars and life counters |

`AGENTS.md` section 3 is the SOP; the game project reaches it through the
block of `skills/construct3-project/assets/game-project-block.md`.

How the prompts are kept:

- A line stays only if removing it would cause a mistake. Counts behind a
  rule and the story of how it was found stay out of the prompts.
- The block and `AGENTS.md` route to one file per task and do not repeat
  it: a rule written twice drifted twice.
- A pointer to a prompt is a when-clause ("before events go into a project,
  read ..."), not a description of the file.

## What small models read

Over the Haiku runs of the skill's evals, `SKILL.md` was opened in almost
every run and a design prompt in a handful, all on the one case that asks
for a mechanic. The checker's output reached every run that edited a sheet,
because `edit_sheet.py` runs it. What reaches a small model is a tool's
output; prose reaches the model that already knows it needs it.

So a habit with a mechanical form becomes a checker finding or a generator
helper that makes the good shape the default. A habit with no mechanical
form that passes the official examples stays prose. A pile of state globals,
the first habit the user named, is one: no heuristic tells it from a
legitimate global.

A global that a round starts from is the case in point. *Restart layout*
keeps global variables, so a countdown that restarts the layout at 0 is 0
on the next run unless something sets it back. In iterations 21 to 27 of
`add-countdown`, on the stand-in before it had rounds, 1 of 48 runs set it
back. In iteration 29, on the stand-in with rounds, 3 of 4 did with the
previous template and 4 of 4 with the stand-in that sets `score` back under
*On start of layout*; that difference is within chance, and the skill
changed between the iterations as well, so what moved the rate is not
isolated. The reset comes before the text that shows the score: one run
rewrote that text to read `score` and `timeLeft` above the resets, which
shows the last round's values at the start of the next.

Update 2026-09-28. A preview of an iteration-27 run with the countdown cut to
3 seconds: the first start reads 3, every later one 0, and the layout
restarted 144 times in 10 seconds. None of the 56 archived runs used a
Timer, although `prompts/event-sheet-thinking.md` names the Timer behavior
for a countdown, and the case graded only the variable: a Timer run would
have failed three assertions. The case now accepts a Timer started for 30
seconds under *On start of layout* with *On timer* restarting the layout; a
reference solution scores 8 of 8 and, cut to 3 seconds, counts 3, 2, 1, 0
and 3 again in preview. The verdicts of the 56 archived runs are unchanged.
The plan example in `SKILL.md` and in `edit_sheet.py --help` was this
countdown, a global under *Every 1 seconds* without a reset, the form every
run wrote: the case measured the copy of the example more than the skill's
guidance. The example is now a best score, a global kept across restarts
on purpose, raised to `max(best, score)` when a round ends, so how to count
down is left to `event-sheet-thinking.md` and the pitfalls.

Update 2026-10-01. Iteration 30 confirmed it: no run opened
`event-sheet-thinking.md`, 0 of 6 used a Timer. The route to the Timer is
now in what the runs read. `SKILL.md` has a section, "Built-ins before
variables", of five lines from the Native first table, and
`check_project.py --style` has a `countdown` kind, below. Over the 60
archived `add-countdown` runs of iterations 21 to 30 it fires on every one,
and on no official example or game project; nothing else the checker prints
changed. Whether runs then write a Timer is not measured yet.

## The authoring style

The style file describes one cohort of the official examples: the demo
games and templates of the studios credited at the top of their sheets.
Scirra's feature examples, the rest, are mostly one or two events and have
no style to learn. The survey scripts are kept under
`.local/docs/evidence/example-style-survey/`.

One rule departs from the examples: a text built from two or more values
is a `StringSub` template. No example calls `StringSub`; they chain `&`.
The user chose the template on 2026-09-30, reviewing the readouts of small
bug-report projects: `StringSub("X = {0}    Y = {1}", ...)` reads as the line
on screen, where a chain splits it into quoted fragments between values.

## Style checks

`check_project.py --style` reports seven kinds, each with the event and the
JSON to write. The thresholds come from the studio cohort, and each check
was run over the official examples before it was kept.

| Kind | Fires on | Why this threshold |
|------|----------|--------------------|
| `run` | 8 or more actions in a row without a comment action | the cohort's longest uncommented run is 3 at the median, 6 at the 90th percentile |
| `comment` | a top-level event, function or custom action without a comment above it | nearly every top-level event of the cohort has one |
| `cases` | an event with two or more case sub-events, none commented | most of the cohort's cases carry their own comment |
| `tick` | *Every tick* beside another condition outside an OR block | an event without a trigger is tested every tick anyway |
| `tree` | sub-events 3 levels deep whose leaves all call one function | a decision flattened into sub-events with one call at each leaf |
| `ladder` | 5 or more sibling events of one shape, values aside | input ladders and else-if chains legitimately reach it, so it stays a warning |
| `countdown` | *Every N seconds* taking N off a variable in the same event: *Subtract* N, *Add* -N or *Set* v to v - N | the variable counts seconds; no official example does it, the one that subtracts every N seconds counts coins |

A user's project is not held to the agent's style, so `--style` is off by
default. `edit_sheet.py` refuses a plan whose new events raise `comment`,
`run`, `cases` or `tick`, whose fix is one comment or one deleted condition.
`tree`, `ladder` and `countdown` stay warnings: fixing them is a design
change the plan's author must make. With the refusal stated in `SKILL.md` and its plan example
carrying a comment, runs wrote the comment from the first draft.

For `comment`, the events directly in a group are top-level events, and
small models do not read them so. In iteration 29 of `add-countdown`, two
Haiku runs put a comment above a new group and not above the events in it;
`edit_sheet.py` refused 10 and 8 of their plans, and every retry left an
event of the group without its comment. The finding called those events
top-level and named them by numbers the file did not have yet. For an event
directly in a group it now names the group and the event's entry in its
`children`, the list the comment goes into, and under
`check_project.py --style` the `edit_sheet.py` operation that puts it there.
A refused plan gets no operation: its numbers are the ones the sheet would
have.

`countdown` is the one smell of `event-sheet-thinking.md` that small models
were seen writing and that has a mechanical form the official examples pass.
Measured over the 524 examples and the 149 eval and small-model projects on
2026-10-01: subtracting `dt` from a variable appears in 33 examples, cooldowns
among them, so it is not a finding; a variable named for a UID appears in 20
examples; `Pick all` on the trigger's object inside a triggered branch
appears in 6 examples and in no run, nor does *Pick by unique ID* on it. Those
stay prose in the smell table until a run writes them.

Comments, variable comments and function descriptions end without a period,
by the user's choice; a second sentence keeps the period between the two.
The checker does not look at punctuation.

## Placement and HUD helpers

The examples lean on a grid without obeying one: a warning for an off-grid
instance would fire in most official projects, so the grid is the
generator's default, not a finding. `assets/build_project.py` holds it:

- `UNIT` (8 px for a viewport 360 high or less, else 32), `MARGIN` (one
  unit), `TOUCH` (48 dp at the viewport, rounded up to a unit), `units()`,
  `snap()`, `anchor()`. The touch size follows Android's 48 dp target;
  Apple and WCAG ask for 44.
- `hud_text()` sizes a label's box to its longest text and aligns it to the
  side it hangs on; `row()` spaces repeated items a unit apart.
- `no_overlap()` stops the generator naming two HUD boxes that meet or one
  past the viewport, and gives the `dy` that clears them. A box wholly inside
  another, a fill in its frame, passes.
- `hud_bar()`, `bar_width()`, `set_width()` and `tween_width()` build a bar
  the way the examples do: a Tiled Background fill at origin (0, 0.5) in a
  frame, `clamp(value / maximum, 0, 1) * length`, Tween *Width*; 9-patches
  with `caps=True`.

In the evals a small model placed boxes by the grid only once the grid was a
constant and a helper, and gave a bar its origin on the growing edge only
through `hud_bar()`; the prose in `references/progress-bars.md`, read or
not, did neither. The reference stays as the sourced answer for a reader who
asks.

Not taken: an index of the editor's bundled asset packs (the agent cannot
fetch them, and the editor's import creates new object types instead of
filling the agent's placeholders), and third-party UI skills (their content
is two lines of the style prompt).

## Re-evaluate when

- A fresh agent given the original drag-and-drop task still writes UID
  links or `Pick all` in the drop trigger: the guide is not enough; try a
  library of worked cases.
- A small model given the refusal abandons the task or loops on it: the
  refused kinds go back to warnings, with the run as evidence.
- A capable model's plans are refused more than once per run: the message
  does not say what to write.
- `add-countdown` runs still count seconds by hand with the `countdown`
  warning under their plan: a warning is not enough; make the generator's
  helper or the refusal carry the Timer.
- The official examples change: rerun the survey scripts; the thresholds
  are constants at the top of `check_project.py`.
- A game needs real art at generation time: design a generator that writes
  frames from a CC0 archive into `images/`, with the tile size as the unit.
- Construct changes the picking model, `Else`, or family picking: re-read
  the manual pages the guide cites.
