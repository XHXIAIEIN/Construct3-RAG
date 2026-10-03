# New and Generated Projects Allocate Uids at Random

Date: 2026-10-03

## Problem

A uid names one instance across a project. Agents add instances by editing
layout files and by rerunning a generator. With `uidAllocationMode:
increment`, the editor's default, the editor gives a new instance the next
number, and a script or an agent picks "the next" number from what it read:
a single-global object keeps its uid in `objectTypes/`, which a count over
the layouts misses, and the generator template numbers from 1. Two instances
that meet are not refused. The editor opens the project and gives all but
one of them another uid, so a hierarchy link or a *Pick by UID* written for
one reaches another.

## Evidence

- Two instances sharing a uid opened in the editor on 2026-10-03, and the
  preview showed one of them under another uid
  (`checker-editor-load-rules.md`).
- A game project switched to random allocation in the editor keeps the
  uids it had and gives new instances numbers such as 681293.
- A project copied by `scripts/bootstrap.py` with random allocation opened
  and previewed in the editor on 2026-10-03.
- Of the 524 official examples, 231 write `increment` and the rest, saved
  by older releases, omit the key.

## Options

1. Keep `increment` and rely on the checker, which reports two instances
   with one uid. The repeat is found after it is written, and every hand
   edit that numbers from what it read can write one.
2. Random allocation in the projects this repository creates: the copy
   `scripts/bootstrap.py` makes and every project the generator template
   builds. `data/c3-new-project/` stays the bytes the editor saved.
3. Option 2, with the value also edited into `data/c3-new-project/`. That
   folder is replaced by hand with a project saved from the editor, so the
   value would be lost at the next refresh.

## Decision

Option 2. `scripts/bootstrap.py` writes `uidAllocationMode: random` into
the project it copies. The generator template writes it into every project
it builds, as it writes the orientation, so a rerun restores it. A project
made in the editor keeps its own setting until a generator runs on it. The
checker still reports two instances with one uid as an error.

## Re-evaluate when

A release refuses random allocation or changes how it numbers instances, or
random uids are seen to collide in a project.
