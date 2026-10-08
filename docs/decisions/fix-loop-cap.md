# The Fix Loop Stops After Two Changes Leave a Finding Standing

Date: 2026-10-08

## Problem

`SKILL.md` tells an agent to repeat three steps: run `check_project.py`, fix
what it prints, and run it again until the last line starts with `ok:`. A
checker with no memory between runs cannot end that loop. An agent that
misreads a finding changes the same place again, and each change can break
something next to it.

## Evidence

- A finding says what to write where it can: the nearest id, the owning
  behavior, the value the editor takes (`references/checker-rules.md`, "What
  a finding says"). When two changes at its place leave it standing, the
  agent read the fix wrongly, or the fix does not fit there.
- The checker's findings have no rule ids. The lowercase words of a message
  stay the same when a change alters the id, name or number it names: "system
  has no action add-to-x" and "system has no action add-to-y" are one
  finding at one place.

## Options

1. No cap: the loop ends only at `ok:`.
2. Count every run that still prints the finding. A rerun with nothing
   changed, or a run spent on another finding, then counts against it.
3. Count only the changes to the finding's own place after which the finding
   is still there, and stop at a cap of 2.
4. The same with a cap of 3 or 5, as other agent frameworks for making games
   use without giving a source.
5. Undo the changes when the cap is reached. A rollback of the whole project
   also undoes the fixes made elsewhere in the same runs.

## Decision

Option 3 (`CAP` in `check_project.py`).

- A finding is known by:
  - its file;
  - the event it names, by sid, or by its number when the sid changed, as it
    does when a generator writes the sheet again;
  - the rest of its place, such as `action 2`;
  - the lowercase words of its message, because a change alters the names,
    ids and numbers that the message names.
- Its place is the event without its sub-events, the layer without its
  sublayers, or else the whole file. A change counts when that place differs
  from the last run and the finding is still there.
- Each run writes its findings, place digests and counts to the project's
  `.tmp/check-project.json`, beside a `.gitignore` of `*`. A finding that is
  fixed leaves the record, so a new one starts from none.
- After two changes, the last line starts with `stop:`. It forbids a third
  change at the place, names the finding, says that `git diff` shows the
  changes, and gives the finding to the user. Nothing is undone, because
  which change to keep is the user's call.
- A run with nothing changed in the project counts no change and says so. In
  a generated project it adds that the generator must run after a change to
  it.
- `--review` keeps no record. The eval tools that run the checker over many
  projects at once (`sweep_outputs.py`, `scripts/output_diff.py`,
  `grade.py`) set `CONSTRUCT3_RAG_NO_RECORD=1`, so that their output does not
  depend on an earlier run.

The cap of 2 is a choice, not a measurement: a finding already names its
fix, so a third change rarely reads it better.

## Re-evaluate when

Eval traces show how many changes a fix that succeeds takes. If a third
change often succeeds, raise the cap. If agents stop on findings that they
could fix, change the message of those findings first.
