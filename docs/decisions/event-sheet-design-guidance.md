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
block of `skills/construct3-agent-plugin/assets/game-project-block.md`.

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
form that passes the official examples stays prose. A pile of state globals
is one: no heuristic tells it from a legitimate global.

A global that a round starts from shows the same. *Restart layout* keeps
global variables, so a countdown that restarts the layout at 0 stays 0 on
the next run unless an event sets it back. The runs set their countdown
back the way the stand-in game sets `score` back, under *On start of
layout*. The reset goes before the text that shows the value, or the text
shows the last round's values at the start of the next.

The countdown itself shows the limit of a guide. `event-sheet-thinking.md`
names the Timer behavior for a countdown, and the runs do not open it: they
count a global down under *Every 1 seconds*. So the route to the Timer is
in what they read. `SKILL.md` has a section, "Built-ins before variables",
drawn from the Native first table and rule 2 of the thinking guide, and
`check_project.py --style` has a `countdown` kind, below. Runs still count
by hand: the warning shows under the plan, and they go on to
`check_project.py` without `--style`, which ends in `ok:`. The
`add-countdown` case grades either form, a Timer started for 30 seconds
under *On start of layout* with *On timer* restarting the layout, or a
variable set back on start. The plan example in `SKILL.md` and in
`edit_sheet.py --help` is a best score, a global kept across restarts on
purpose, because runs copy an example's form: while the example was a
countdown under *Every 1 seconds*, every run wrote that countdown.

A Timer is not faster. Timed per runtime tick in the preview, one countdown
costs the same either way. With ten thousand instances, a Timer each costs
more than subtracting `dt` in events, because *On timer* is tested every
tick for every instance (`.local/docs/evidence/timer-vs-dt-2026-10-01/`).
What the Timer gives one countdown is a value that starts over with the
layout, and a variable set back under *On start of layout* gives that too.
So the countdown stays a warning: a refusal would hold up a form that works,
for no gain in speed.

An edit to `event-sheet-thinking.md` moves Haiku's structure on tasks the
edit does not mention. After rules on counts, doors and project files went
in, Haiku put a tween's *On finished* inside the function that starts the
tween, and no single one of those rules carried the effect. So rule 6 says
that a function counts as the trigger of its branch, and an edit to that
file is run beside the file before it on a task that asks for one function
to tween an instance and act when the tween ends. The task, its rubric and
the runs are in `.local/docs/evidence/pitfalls-fix-lines-2026-09-30/` and
`prompt-verify-2026-10-04/`.

## The authoring style

The style file describes one cohort of the official examples: the demo
games and templates of the studios credited at the top of their sheets.
Scirra's feature examples, the rest, are mostly one or two events and have
no style to learn. The survey scripts are kept under
`.local/docs/evidence/example-style-survey/`.

One rule departs from the examples: a text built from two or more values
is a `StringSub` template. No example calls `StringSub`; they chain `&`.
`StringSub("X = {0}    Y = {1}", ...)` reads as the line on screen, where a
chain splits it into quoted fragments between values, which matters most in
the readouts of a small bug-report project.

## Style checks

`check_project.py --style` reports ten kinds, each with the event and the
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
| `choice` | `chooseindex(c, a, b)` whose first argument is a comparison, a logical operator or a boolean variable | it returns `b` when `c` is true, the reverse of `c ? b : a`; no example calls `chooseindex` |
| `dispatch` | 2 or more sibling events testing one text with `find(X, "<literal>")` | `find` matches any part and ignores case, so `"B"` runs for `"BU"`; no example dispatches so |
| `table` | `mid("<letters>", ...find("<letters>", X)...)` | a cycle or a table written as letters; no example calls `find` with a literal first |

A user's project is not held to the agent's style, so `--style` is off by
default. `edit_sheet.py` refuses a plan whose new events raise `comment`,
`run`, `cases` or `tick`, whose fix is one comment or one deleted condition.
`tree`, `ladder`, `countdown`, `choice`, `dispatch` and `table` stay
warnings: fixing them is a design change the plan's author must make. With
the refusal stated in `SKILL.md` and its plan example carrying a comment,
runs write the comment from the first draft.

A Pathfinding *Find path* in an event that runs every tick, with no trigger,
*Every X seconds* or *Trigger once* in it or above it, is a warning of
`check_project.py` from the manual (`behavior-reference/pathfinding.md`) and
fires on none of the official examples. Small models write it as *Every
tick* or *NOT Is moving along path* -> *Find path*, and keep it through the
warning, calling it intentional. So `edit_sheet.py` refuses it in an event
the plan creates, under
the kind `pathfinding`, and its line names the fix first: the trigger that
sets the target, or *Every 0.5 seconds* with the JSON of that condition. In
the user's own events it stays a warning.

The traps of the running game in the table below take the same path as
*Find path*. Small models write them in plans whatever the guides say, so
the rule goes into the line a script prints, with the fix as JSON:

| Kind | Finding | Passes |
|------|---------|--------|
| `timer` | Timer *Start timer* in an event that runs every tick, every condition of its branch a test of a variable or `Count`; the timer starts over each tick, so *On timer* never fires | a branch that tests *Is timer running* or what changes as the game plays (an overlap, a key, a position, a function), and one whose actions set the variable it tests, create or destroy the type it counts, call a function or leave the group or layout |
| `control` | *Simulate control* of a Platform's left or right, or of any 8 Direction or Car control, under a trigger: the control holds for the one tick the trigger fires (manual: `behavior-reference.md` "Custom controls") | a Platform jump and a Tile movement step, each a whole move in one tick |
| `count` | `X.Count = 0`, `≤ 0` or `< 1` in a condition that runs after a *Destroy* of X in the same top-level event: the destroyed instance counts until that event ends | a comparison with 1, as the official examples write it, and a test after a *Wait* |
| `picked` | `X.PickedCount = 0`, `≤ 0` or `< 1` below a condition of its branch that picks X: a pick of no X stops its event, and *Pick all* is false when no X exists | a test of `X.Count` in an event that does not pick X |
| `flip` | a variable flipped in an event that runs every tick, by *Toggle* or a *Set* to `N - x`, `-x`, `x * -1` or `x = a ? b : a` of the same variable: the event runs again on the next tick and flips it back | a branch whose actions, or the functions they call, change what a condition tests (they set a variable, create or destroy a type, or act on an object the condition names or reads; an *Else* also tests the event it answers), or leave the group or layout |

Each fires on none of the official examples. `edit_sheet.py` refuses each
in an event a plan creates, and its line names the fix: *Trigger once*, the
condition that holds while the input is held (*Key is down* with the
trigger's key), or the `Count` test in an event of its own. For `flip` it
names the event whose trigger causes the change, such as *On touched
object* for a tap. A flip that a value running out causes, such as the
time left of a turn, has no trigger to move into, so the line also names
the action that sets that value back in the same event. In the user's own events they stay warnings. A counter
kept beside an instance count, and a door left Solid, have no form a check
can tell from sound code: `SKILL.md` names `Count` among the built-ins and
the Solid among the gotchas.

`flip` comes from a generated board game that changed the turn in a
top-level *Else* after a test of the game state. The turn flipped on every
tick, so the value a tap read depended on the tick it landed in. A branch
that resets a flag its tap raised, or that tests the variable it flips,
runs once, so the rule leaves it alone. A fixed step without `dt`, *Add* 1
each tick, is not a flip: it counts ticks or sums an input axis.

With that shape seeded into the stand-in game, three of four Haiku runs
added *Trigger once* to the flipping event. The one run that read the
`flip` warning first moved the flip into the custom action the tap calls.
Under tests of values, *Trigger once* flips once each time the tests turn
true, which in the seeded game is once a round. So the checker names that form
too, as the kind `flip-once`, and the `flip` line says that *Trigger once*
is not the fix. `flip-once` is a warning that `edit_sheet.py` does not
refuse, since a flip once a round, such as the side that starts the next
round, is sound. In a second batch, with that line, all three runs moved
the flip under a trigger, two of them after reading the warning; two of
three runs of the previous skill did so, and the third kept a flip under
*Trigger once*, which the checker names. Evidence:
`.local/docs/evidence/skill-evals/construct3-agent-plugin/iteration-43/`.

A scan with `check_project.py` of the projects that small models wrote, in
eval runs and through a spec builder, finds no `flip`. It finds
`flip-once` only in runs of the seeded case that added *Trigger once* to
the flipping *Else*. There the turn passed once a round instead of once a
tap. Every hit is a fault, so `flip-once` stays as it is.

In skill runs the refusals rarely fire: given a project, Haiku tests a key
the way the project's own events do. A warning that names the fix gets a
seeded trap fixed at once. Evidence:
`.local/docs/evidence/skill-evals/construct3-agent-plugin/iteration-39/`.

Asked to make the stand-in game two-player, Haiku passed the turn in the
function the tap calls, with the rule and without it. Given a time limit
too, it passed the turn on a timeout in an event that also sets the time
back. That event runs once per timeout, so the refusal had nothing to
refuse.

The board game that `flip` comes from was built by a spec builder, which
writes a model's events through `edit_sheet.py`. Later plans of that
builder again changed the turn in a top-level event after the tests of a
win. `edit_sheet.py` refuses such a plan with the `flip` line. The
builder's own check refuses the same events first. The model then moves the
flip under the tap, the fix that the `flip` line names. Evidence:
`.local/docs/evidence/skill-evals/construct3-agent-plugin/iteration-45/`.

For `comment`, the events directly in a group are top-level events, and
small models do not read them so: refused, they put the comment above the
group, and the retry still leaves an event of the group without its
comment. So for an event directly in a group the finding names the group
and the event's entry in its `children`, the list the comment goes into,
and under `check_project.py --style` the `edit_sheet.py` operation that puts
it there. A refused plan gets no operation: its numbers are the ones the
sheet would have.

`countdown` is the one smell of `event-sheet-thinking.md` that small models
write and that has a mechanical form the official examples pass.
Subtracting `dt` from a variable is how the examples count cooldowns, so it
is not a finding. A variable named for a UID, and `Pick all` on the
trigger's object inside a triggered branch, appear in sound example code
and in no run; they stay prose in the smell table until a run writes them.
Where an example writes that `Pick all`, it reaches the rest of the type,
as when every ghost stops once one touches the player, or it is followed by
a pick from a stored link, a UID in a function parameter or a variable, the
only form rule 8 and the smell row of `event-sheet-thinking.md` call a
rebuilt pick.

`choice`, `dispatch` and `table` come from a generated card game that coded
enemy moves (`"A6x2"`, `"BU"`, `"SHIFT"`) and card effects as strings,
dispatched them with `find` in sibling events, chose between values with
`chooseindex(condition, ...)` and cycled its five elements through two
letter strings. The official examples do none of the three: they choose
with `c ? a : b` and cycle with `(n + 1) % N`, so the three fire on no
example. The design rows are in the Native first and smell tables of
`event-sheet-thinking.md`.

Comments, variable comments and function descriptions end without a period,
the style this repository writes; a second sentence keeps the period
between the two. The checker does not look at punctuation.

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
- A run that counts seconds by hand also leaves the global where the last
  round ended, the warning under its plan: the warning is not enough for
  the case where it matters; make `edit_sheet.py` refuse that pair.
- `flip-once` names a sheet that flips a value once a round on purpose,
  such as the side that starts the next round. Narrow it to an *Else* with
  *Trigger once*, the form the seeded case produces.
- The official examples change: rerun the survey scripts; the thresholds
  are constants at the top of `check_project.py`.
- A game needs real art at generation time: design a generator that writes
  frames from a CC0 archive into `images/`, with the tile size as the unit.
- Construct changes the picking model, `Else`, or family picking: re-read
  the manual pages the guide cites.
