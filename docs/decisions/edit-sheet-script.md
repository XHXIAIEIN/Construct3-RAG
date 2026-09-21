# Events Go into a Sheet through a Checked Plan

Date: 2026-09-22
Schema: Construct 3 r495.2

## Problem

An agent that changes an event sheet by hand edits JSON indented 7 to 17
tabs deep with its harness's exact-match edit tool. Putting an event in
means matching the lines around the place, several of them, tabs included.

Task: the agent writes the events it wants, says where by the numbers it
read off the printed sheet, and they land in the file as the editor would
have written them, or not at all.

The default path calls it: `SKILL.md` of `construct3-project` names it as
the way to change a sheet, ahead of a hand edit.

## Evidence

Transcripts of the eval runs of `project-tools-skill.md`, iterations 1 and 2
(Claude Haiku 4.5, read with `evals/trace.py`): 22 of the 60 Edit calls of
the eight runs that edited a sheet failed with "String to replace not
found", with and without the skill. Each was a match of several lines with
one tab too many or too few. The ones that went through at the first
attempt were single lines. A sentence in `SKILL.md` about tabs and anchoring
on a `sid` changed nothing: 8 of 19 failed with it, 14 of 41 without.

What the editor writes, over the 433 official examples that have an event
sheet and mergeGame, 46 000 events saved by 126 releases: a group always
carries `eventType, disabled, title, description, isActiveOnStart, children,
sid` in that order, a variable `eventType, name, type, initialValue, comment,
isStatic, isConstant, sid`, a block `eventType, conditions, actions, sid`
with `children` and `isOrBlock` after them when it has them, a condition or
action `id, objectClass, sid` and then `behaviorType`, `parameters`,
`isInverted`; `initialValue` is a string whatever the type. All 573 sheets
of the examples, mergeGame and WaterSort come back byte for byte from
`json.dumps(json.loads(text), indent="\t", ensure_ascii=False)`.

## Options

1. A sentence in `SKILL.md` on how to edit. Tried, no effect.
2. One command per change, `--after 8 events.json`. Simple to describe. The
   numbers move with every insert, an agent plans its changes from one print,
   and the second command then lands in a valid, wrong place without a word.
3. A plan: one JSON file of operations, every number meaning the sheet as it
   is on disk, applied together or not at all after the result has passed
   the checker.
4. JSON Patch (RFC 6902). A path such as `/events/3/children/0/actions/1` is
   not something the printed sheet gives, and it moves like the numbers do.
5. Leave it to the generator. It owns projects an agent wrote from the
   start; the sheets agents edit by hand are the ones made in the editor.

## Decision

Option 3, `scripts/edit_sheet.py SHEET PLAN.json`.

- Operations on events: `after`, `before`, `into` (0 is the sheet) and
  `replace` with `"events"`, `remove`, `move` to one of the three places.
  On what an event holds: `"event": N` with `"add-actions"` or
  `"add-conditions"` and an optional `"position"`; with `"condition": J` or
  `"action": J` and `"set"` or `"remove": true`, the place a finding of the
  checker names; with `"set"` alone for the event's own values. `set` takes
  a parameter at a time, `null` takes a key out, and a key the editor does
  not write for that kind of entry is refused. Targets are found before the
  first operation runs and followed through the ones after it; one that a
  plan has already removed is an error.
- The comments directly above an event are about it: `before` goes above
  them, `remove` and `move` take them along, `replace` leaves them.
- A new entry is completed from the table above: the keys the editor always
  writes, its defaults, its order. `sid` is given where it is missing, not a
  positive integer, or taken; a `replace` frees the sids it removes, so an
  event shown with `print_sheet.py --show`, changed and put back keeps its
  own, and one event put in the place of another without a sid takes the
  other's.
- Validation is `check_project.py`'s, in memory: the project is checked as
  it is and as the plan would make it, and the plan is refused if it adds an
  error. Findings are compared without their event numbers, which an insert
  shifts; the sid in them stays. An error that was there does not stop a
  plan, or a project with one broken event could not be repaired through it.
  There is no `--force`: a hand edit remains.
- Output: what each operation did, the changed events as the editor words
  them under their new numbers, new warnings, and the checker's last line.
  Refusals name the operation. `--dry-run` writes nothing.
- The file is written through a temporary one, in the layout above.
- `SKILL.md` makes the plan the way to change a sheet, all of it; other
  project files are edited as they are.

`check_project.py` gained `Checker.check()` and a `sheets` argument for a
sheet that is not on disk, and two of its findings, an inverted trigger and
*Trigger once* in a triggered branch, now name their condition as the others
do. Over the 1 618 runs of `evals/sweep_outputs.py` that is the whole
difference: three checks, 12 characters per finding, no exit code. The sweep
now also dry-runs a plan of a comment, a variable and an event on the first
sheet of every project: 440 of 440 take it, the 32 that fail the checker
among them.

## Evaluation

Claude Haiku 4.5 subagents, two runs per case and arm, the previous skill
(5f39cf7, from a worktree) as the baseline; runs in
`skills/construct3-project-workspace/iteration-3` to `iteration-5`, read
with `evals/trace.py`. Means of two runs:

| Case, version | Assertions | Tokens | Seconds | Tool calls | Lost calls |
|---------------|------------|--------|---------|------------|------------|
| add-countdown, previous skill | 7/7, 7/7 | 76 486 | 211 | 34.5 | 6 |
| add-countdown, first version | 5/7, 6/7 | 66 013 | 159 | 30.5 | 4.5 |
| add-countdown, second | 7/7, 7/7 | 64 672 | 160 | 24.5 | 4.5 |
| add-countdown, as committed | 7/7, 6/7 | 62 991 | 152 | 19 | 1 |
| fix-load-errors, previous skill | 8/8, 8/8 | 59 577 | 102 | 20 | 7 |
| fix-load-errors, first version | 8/8, 8/8 | 61 110 | 110 | 19 | 3.5 |
| fix-load-errors, second | 8/8, 8/8 | 56 301 | 75 | 15.5 | 1 |
| fix-load-errors, as committed | 8/8, 8/8 | 57 978 | 97 | 14.5 | 1 |

What the three versions were, and what the transcripts showed:

- First: events in, out and moved, conditions and actions added. The runs
  of add-countdown no longer touched the sheet with Edit at all. Two things
  cost them assertions: `replace` gave the event a new sid, and changing one
  action of an event meant printing it, rewriting it and putting it back,
  which one run skipped. The runs of fix-load-errors never used a plan:
  `SKILL.md` had left a change within one line to a plain edit, and that is
  what four of its five repairs are.
- Second: `set` and `remove` by the place a finding names, a sid kept on
  `replace`, `--show` moved to the printer, where a run had looked for it,
  and `SKILL.md` without the exception. Both runs of fix-load-errors wrote
  one plan of five operations from the five findings. Both also wrote
  `{"event": 2, "set": {"inverted": false}}`, which the script took: the
  key stayed in the sheet and meant nothing, and no assertion saw it. The
  finding had not said which condition.
- As committed: `set` takes only keys the editor writes for that kind of
  entry or the entry already has, and names the nearest; the finding names
  the condition. One run of fix-load-errors wrote its plan right the first
  time, the other after one refusal; neither sheet holds a stray key.
- In two of the six plan runs of add-countdown the text set in `AddScore`
  was left without the time, which no run of the previous skill did in
  five. The sheet as events shows that action as the JSON does; two of six
  against none of five is within what chance gives.
- A refused plan is a lost call by `trace.py`'s count, and most of those
  left were refusals that named a wrong id or parameter before it reached
  the file.

Not verified: that the editor opens what the script writes. The keys and the
layout are the editor's by the counts above, and the checker passes; nobody
has opened a sheet changed this way in Construct.

## Re-evaluate when

- A sheet changed by a plan does not open in the editor: the message, then
  the key or the order it points to, against the table under Evidence.
- A stray key turns up in a sheet from a hand edit: a checker warning for a
  key the editor never writes for that kind of event, after a run over the
  examples that adds no finding.
- Plans keep missing a second place that needs the same change: print the
  whole sheet after a plan, not only what changed, and measure it on
  add-countdown.
- An agent needs to address a variable, a comment or an include, which have
  no number: a place by sid.
