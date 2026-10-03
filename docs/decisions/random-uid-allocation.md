# New Projects Allocate Uids at Random

Date: 2026-10-03

## Problem

With `uidAllocationMode: increment`, the editor's default, a new instance
takes the next number, and so does an instance an agent or a script adds,
counted from what it read. The two meet: a single-global object keeps its
uid in `objectTypes/`, which a count over the layouts misses. The editor
opens two instances with one uid and gives all but one another uid, so a
hierarchy link or a *Pick by UID* written for one reaches another.

## Evidence

- Scirra's guide
  [Construct's project format](https://www.construct.net/en/tutorials/constructs-project-format-3275)
  states that a uid may be any value as long as every instance has its own,
  that large random numbers work better under source control, and that
  Construct then uses six-digit random numbers.
- Two instances sharing a uid opened in the editor on 2026-10-03, and the
  preview showed one of them under another uid
  (`checker-editor-load-rules.md`).
- A game project switched to random allocation in the editor keeps the
  uids it had and gives new instances numbers such as 681293.
- The empty project with random allocation opened and previewed in the
  editor on 2026-10-03.

## Options

1. Keep `increment` and rely on the checker, which reports two instances
   with one uid after they are written.
2. Random allocation as the default of the projects this repository starts.

## Decision

Option 2. `data/c3-new-project/project.c3proj`, which `scripts/bootstrap.py`
copies, has `uidAllocationMode: random`, set as **UID numbering** in the
editor's project properties before the project was saved; and so does the generator
template's default for a project that lacks the key. A project made in the
editor keeps its own setting.

## Re-evaluate when

A release refuses random allocation or changes how it numbers instances.
