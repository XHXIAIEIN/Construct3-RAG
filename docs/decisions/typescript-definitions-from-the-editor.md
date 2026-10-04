# A project's TypeScript definitions come from the editor

Date: 2026-10-04

## Problem

An agent that writes TypeScript for a project checks it against
definitions. `data/c3-ts-defs/` holds the runtime API of a release, the same
files the editor exports under `ts-defs/runtime/`. The project's own types
are not there: `InstanceType.Coin` with its behaviors and instance
variables, the objects, global variables, layouts and layers. The editor
writes them into `scripts/ts-defs/` of a folder project when the user
chooses *Set up TypeScript for external editor* or *Update TypeScript
definitions* on the Scripts folder, and only then. Three game projects on
disk held a `ts-defs/` written while they were empty and declared none of
their 10 to 12 object types.

## Options

- Generate the project's files from `objectTypes/` and the rest: no
  browser, but the editor's generator copied by hand, and every change to
  it in a release missed.
- Ask the user to run the menu command whenever an object is added: the
  definitions are right, but every new object stops the agent on the user.
- Have the editor write them: open the project as `open_in_editor.py`
  does, save it as a project folder into the page's origin-private file
  system, run *Set up TypeScript for external editor* from the Scripts
  folder's context menu, and copy what it wrote into the project.

## Decision

The editor writes them, through `open_in_editor.py --typescript`. The files
are the editor's own, from its model of the project, and a run takes about
10 seconds more than opening the project. It overwrites the files under
`scripts/ts-defs/`, which the editor's `.gitignore` leaves out of Git, and
writes `scripts/tsconfig.json` only when the project has none. It does not
write the `.ts` copies of `.js` files that the menu command also makes.

`check_project.py` warns when `scripts/ts-defs/instanceTypes.d.ts` exists
and does not name an object type or family of the project, and prints the
command. It does not warn when there is no `ts-defs/`: a project that
compiles its TypeScript in Construct needs none, and no official example has
one.

## Evidence

- A game project of 12 object types, r495-2, 2026-10-04: the run wrote 57 files, among them
  `plugins/` and `behaviors/` for the addons the project uses, and an
  `instanceTypes.d.ts` with a class per object type
  (`class Coin extends ISpriteInstance`, its behaviors typed); the checker's
  warning went away. On a copy, with `--preview` after it, the preview ran
  without errors, and `tsc --noEmit` with the written `tsconfig.json`
  accepted the project's scripts and a behavior property of an object type,
  and refused an object type and a behavior the project does not have.
- Menu items carry no id, only a label and a tooltip in the editor's
  language. The script reads each label by its key from the language file
  the editor loaded for the page's language, the keys `data/c3-lang` holds.
  An editor set to Chinese wrote the same 57 files as one in English.

## Not verified

- A project with families and instance variables.
