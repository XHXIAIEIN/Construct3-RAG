# Events Go into a Sheet through a Checked Plan

Date: 2026-09-22
Schema: Construct 3 r495.2

## Problem

An agent that changes an event sheet by hand edits JSON indented 7 to 17
tabs deep with its harness's exact-match edit tool. In the skill's eval runs
about a third of those edits failed with "String to replace not found": a
match of several lines with one tab too many or too few. A sentence in
`SKILL.md` about tabs changed nothing.

Task: the agent writes the events it wants, says where by the numbers it
read off the printed sheet, and they land in the file as the editor would
have written them, or not at all. `SKILL.md` makes this the way to change a
sheet.

## Options

1. A sentence in `SKILL.md` on how to edit. Tried; no effect.
2. One command per change. The numbers move with every insert, and the
   second command lands in a valid, wrong place without a word.
3. A plan: one JSON file of operations, every number meaning the sheet as it
   is on disk, applied together or not at all after the result has passed
   the checker.
4. JSON Patch. Its paths are not something the printed sheet gives, and
   they move like the numbers do.
5. Leave it to the generator. The sheets agents edit by hand are the ones
   made in the editor.

## Decision

Option 3, `scripts/edit_sheet.py SHEET PLAN.json`.

- Operations on events: `after`, `before`, `into` (0 is the sheet) and
  `replace` with `"events"`, `remove`, `move`. On what an event holds:
  `"event": N` with `"add-actions"` or `"add-conditions"`; with
  `"condition": J` or `"action": J` and `"set"` or `"remove": true`, the
  place a finding of the checker names; `"set"` alone for the event's own
  values. `set` takes a parameter at a time, `null` takes a key out, and a
  key the editor does not write for that kind of entry is refused with the
  nearest one: an accepted stray key stayed in the sheet and meant nothing.
- Targets are found before the first operation and followed through the
  ones after it. An event replaced by one event keeps its number for the
  operations below it; replaced by several, or removed, it is gone, and a
  later operation on it is refused with the operation that removed it.
- The comments directly above an event belong to it: `before` goes above
  them, `remove` and `move` take them along, `replace` leaves them.
- A new entry gets the keys the editor always writes, in its order, with
  its defaults, as counted over the official examples. `sid` is given where
  it is missing, invalid or taken; `replace` frees the sids it removes, so an
  event shown with `print_sheet.py --show`, changed and put back keeps its
  own.
- The project is checked as it is and as the plan would make it, in memory,
  and the plan is refused if it adds an error. Findings are compared without
  their event numbers, which an insert shifts. An existing error does not
  stop a plan, so a broken event can be repaired through one. There is no
  `--force`.
- The file is written whole through a temporary one, in the editor's layout.
  `--dry-run` writes nothing.
- A plan's numbers come from a print. `print_sheet.py` keeps the hash of each
  sheet it prints in the system's temporary folder, not in the project, and
  a plan is refused when the sheet no longer matches it: a save in the
  editor in between can move the events the numbers name. A written plan
  keeps the new hash.
- Output: what each operation did, the changed events as the editor words
  them under their new numbers, new warnings, and the checker's last line.
  A `note:` names each action the plan did not touch that still writes an
  older form of a text the plan writes elsewhere: runs changed the score
  text in one place and left the other showing the old one. After a write,
  a `note:` says to reopen the project in an editor that has it open, whose
  next save would write back the sheet it had loaded.

## Re-evaluate when

- A sheet changed by a plan does not open in the editor: its message, then
  the key or order it points to.
- A stray key turns up in a hand-edited sheet: a checker warning for a key
  the editor never writes for that kind of event, after a run over the
  examples that adds no finding.
- Runs that read the note still leave the second place: print the whole
  sheet after a plan, not only what changed.
- An agent needs to address a variable, a comment or an include, which have
  no number: a place by sid.
