# Skill Evals Are Graded by Playing the Result

Date: 2026-10-08
Schema: Construct 3 r495.2 (stable)

## Problem

The files a run leaves and the checker's verdict do not show what the game
does. A countdown that never reaches 0 can look right in the JSON. So can a
turn that passes on every tick, or a wall the player walks through. A file
assertion also reads one way of writing a mechanic, and fails a run that
wrote it another way that works. A pass rate over cases that have steered
the skill's iterations measures the skill on the cases it was shaped on,
not on new requests.

Task: a change to the skill is judged by what the game does. The cases
include the kinds of request agents fail most, a part of them stays out of
the tuning loop, and each run's cost is recorded beside its verdict.

## Evidence

A public benchmark of agents that build games grades at three levels: the
files, a static check, and deterministic assertions run in the engine's own
runtime. The runtime level ranks the agents. The benchmark repeats each
task and gives the pass rate with a 95% interval. It keeps a set of tasks
out of the public ones. It reports turns, output tokens and wall time per
task as usage, not as capability. By category, its agents fail most at
spatial layout, character control and physics, and least at UI and arcade
logic.

`scripts/preview_project.py` plays a JSON plan in the editor's preview: it
sends input to the game's own instances, waits on an expression, and runs
`js` against the scripting runtime. A `tick2` listener that a `js` step
installs reads what moves between two samples.

The plans were checked before they graded anything. Each plan fails its
unfixed fixture on what the case asks and passes the rest. Each passes a
project that does what the case asks. Replayed on runs of earlier
iterations, the plans failed runs that the file assertions had passed. Each
such run was read, and in each the defect was real:

- the editor refuses to open the project, or the preview refuses its script;
- the layout restarts on every tick from its first one;
- coin sizes are set in On created, before the value they read is assigned;
- a label counts the collected coin until that coin is destroyed;
- two tap events both fire on one touch, so the turn passes twice;
- a player clamped by its centre, or by its unrotated width, leaves the
  layout;
- the speed tests `isKeyDown("Shift")`, but `isKeyDown` matches a key's
  code (`ShiftLeft`, `ShiftRight`), never `Shift`, so holding Shift does
  not double it.

The file assertions failed one run that works: its countdown reads the
system expression `time`. The same replays found mistakes in the plans,
such as a value read in the tick that restarts the layout. A run that
writes something no plan foresaw can meet another such mistake, so a
disagreement between the levels is read before either side is trusted.

## Options

1. More file assertions. Each one reads one way of writing a mechanic, so a
   case needs a grader for every way a run finds, and none of them shows
   that the mechanic works.
2. A screenshot judged by a model. The verdict is not deterministic, and it
   misses what happens between frames, such as a flip on every tick.
3. A plan per case, played on the run's project. Its checks are `js` steps
   that read the running game and return pass or fail.

## Decision

Option 3, beside the file assertions, which stay.

- Levels. Each assertion in `grading.json` has a `level`: `checker`,
  `files` or `runtime`. The summary gives the runtime assertions separately
  and the highest level up to which every assertion passed.
- Plans. `evals/play_cases.py` builds the plan of each case whose request
  changes what the game does. A check is a `js` step with a `check:` note
  that returns `{ok, said}`. When a setup step fails, the checks after it
  fail as not reached. Every plan also fails on a runtime error the game
  logs. Where the run chooses the name of an object or a variable, the plan
  finds it by what it does: the UI instance that widens when a coin is
  collected is the fill. A `tick2` listener reads what moves between two
  samples, and `afteranylayoutstart` counts the restarts.
- Requests a plan cannot play stay file assertions: an answer about events
  and a design.
- Cases. Four cases cover the requests agents fail most: a double jump on
  the platformer template (character), a ship kept on a screen smaller than
  its layout (layout and movement), walls the player walks through
  (collision), and coins dealt evenly on a ring on the board (layout).
- Held out. A case marked `held_out` is laid out only with `--held-out`,
  reported apart from the others, and its failures are printed only with
  `--show-held-out`. A change is shaped on the other cases. The held-out
  cases run once the change is otherwise done, and what they show is not
  read while it is open. A held-out failure first becomes a new tuning
  case. The held-out case then joins the tuning set, and a new case takes
  its place. Only cases that have steered no iteration start held out.
- Cost and spread. `trace.py` reads turns, output and input tokens and wall
  time from the transcript. `grade.py` records them and the plan's seconds
  beside each verdict. For each case and arm it gives the runs that passed
  every assertion, k of n, with a Wilson 95% interval. With two to four runs
  per cell the interval spans most of 0 to 1, so the output gives n with
  it.

## Re-evaluate when

- A Construct release changes how the preview opens or where the runtime
  runs, and the plans stop reaching the game.
- Read disagreements keep showing the plan wrong and the run right: the
  plans then read the game too narrowly to stand above the files.
- The held-out cases pass whenever the tuning cases pass: they then measure
  nothing more, and harder cases replace them.
