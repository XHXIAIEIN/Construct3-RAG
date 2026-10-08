# Skill Evals Are Graded by Playing the Result

Date: 2026-10-08
Schema: Construct 3 r495.2 (stable)

## Problem

`evals/grade.py` judged a run by the files it left and by the checker. It
never played the game. A countdown that never reaches 0, a turn that passes
on every tick, a wall the player walks through or a HUD that sits inside the
screen's edge on a wider window all pass when the JSON looks right, and a
file assertion that reads one way of writing a mechanic fails a run that
wrote another way that works. The 20 cases also had no held-out part: every
one had steered an iteration of the skill, so a pass rate over them measures
the skill on the cases it was shaped on.

Task: a later change to the skill is judged by what the game does, on cases
that include the ones agents fail most, with a part kept out of the tuning
loop, and with the cost of each run beside its verdict.

## Evidence

Public benchmarks of agents that build games grade the same way at three
levels: the files, a static check, and deterministic assertions run in the
engine's own runtime, the last being the one that ranks. They repeat each
task, give the pass rate with a 95% interval, keep a set of tasks out of the
public ones, and report turns, output tokens and wall time per task as
usage, not as capability. Their results by category put agents weakest at
spatial layout, character control and physics, and near the ceiling on UI
and arcade logic.

`scripts/preview_project.py` already plays a JSON plan in the editor's
preview: input on the game's own instances, `until` on an expression, `js`
against the scripting runtime. A probe on the families fixture: W held for
0.5 s moved Player 0 px, the right arrow 69 px; a `tick` listener installed
by a `js` step read the player's box on every tick. One plan costs about
15 seconds.

## Options

1. More file assertions. Each reads one way of writing a mechanic, and a
   case grows a grader for every way a run finds; none of them says the
   mechanic works.
2. A screenshot judged by a model. Not deterministic, and it misses what
   happens between frames, such as a flip on every tick.
3. A plan per case played on the run's project, its checks `js` steps that
   read the running game and return pass or fail.

## Decision

Option 3, beside the file assertions, which stay.

- Levels. Each assertion result in `grading.json` has a `level`: `checker`,
  `files` or `runtime`. The summary gives the runtime checks apart and the
  highest level a run reached.
- Plans. `evals/play_cases.py` builds the plan of each case whose request
  changes what the game does. A check is a `js` step with a `check:` note
  returning `{ok, said}`; a setup step that fails leaves the checks after it
  not reached, and so failed. Every plan also fails on a runtime error the
  game logs. A plan finds what the run made by what it does, not by its name:
  the UI instance that widens when a coin is collected is the fill, the
  global that goes from 40 to 50 is hp. What moves between two samples is
  read by a `tick` listener, a restart by `afteranylayoutstart`.
- Requests a plan cannot play stay file assertions: an answer about events,
  a design, and a key held with another key, since a `key` step holds one.
- Cases. Four new ones where agents fail most: a double jump on the
  platformer template (character), a ship kept on a screen smaller than its
  layout (layout and movement), walls the player walks through
  (collision), and coins dealt evenly on a ring on the board (layout).
- Held out. A case marked `held_out` is laid out and graded only on request,
  printed and aggregated apart and without its evidence. A change is shaped
  on the other cases; the held-out ones run once the change is otherwise
  done, and what they show is not read while it is open. A held-out failure
  becomes a new tuning case first; the held-out case then joins the tuning
  set and a new one takes its place. Only new cases start held out, since
  every existing one has steered an iteration.
- Cost and spread. `trace.py` reads turns, output and input tokens and wall
  time from the transcript; `grade.py` puts them and the plan's seconds
  beside each verdict, and gives each case and arm its fully passed runs
  k of n with a Wilson 95% interval. With two to four runs per cell the
  interval spans most of 0 to 1, and the output says n.

## Re-evaluate when

- A Construct release changes how the preview opens or where the runtime
  runs, and the plans stop reaching the game.
- A plan's verdict disagrees with what a run visibly does: the check is
  wrong, and it is fixed before the run is scored again.
- A held-out case has run in more than one accepted change: rotate it into
  the tuning set.
