---
name: construct3-project
description: Check, read, look up and generate the JSON of a Construct 3 folder project (project.c3proj, eventSheets, layouts, objectTypes, families) against the Construct3-RAG schemas and the rules the Construct 3 editor applies when it opens a project. Use this skill whenever you write or edit an event sheet or any other project file of a Construct 3 game, need the exact id, parameters and JSON of a condition, action or expression, want to read an event sheet or an official example as events instead of JSON, generate a whole project from a script, or the editor refuses to open or preview a project, even if the user only says "add a mechanic", "fix this event" or pastes an editor error.
compatibility: Requires Python 3.10+ and a local clone of Construct3-RAG, whose data/c3-schemas the scripts read. Pillow is optional and only compares image sizes.
metadata:
  source: https://github.com/XHXIAIEIN/Construct3-RAG
---

# Construct 3 project files

Scripts for the JSON of a Construct 3 project saved as a folder: look an ACE
up with the JSON to write, read a sheet as the editor words it, change it
from a plan, check the project before the editor opens it, generate a whole
project from Python.
They read the schemas of the Construct3-RAG clone, so a name they accept
exists and a name they reject does not. None of it needs the editor open: a
project the checker passes is ready for it.

## Before the first command

- Commands here are written from this skill's folder. From the project root,
  put the folder this file is in before them, for example
  `python .agents/skills/construct3-project/scripts/check_project.py`. The
  scripts find the project from the current directory upward, so both work;
  `--project <folder>` names another one.
- The scripts find the clone through `--rag`, the `CONSTRUCT3_RAG`
  environment variable, or the `Construct3-RAG: <folder>` line in the
  project's `AGENTS.md` or `CLAUDE.md`. `Construct3-RAG not found`: fill that
  line in; ask the user for the folder instead of guessing it.
- Reading this inside the clone while the work is in a game project: install
  the skill there first, `python scripts/install.py --project <game folder>`.
  It copies this folder to the project's `.agents/skills/` and adds the
  Construct 3 block to its `AGENTS.md` with the clone's path filled in
  (`--into .claude/skills` for Claude Code, `.trae/skills` for TRAE). Tell
  the user in one sentence what was installed.
- A line `this copy of the construct3-project skill differs from the clone's`:
  run the command it prints, then repeat yours.
- The project has no `.git`: `git init` in it before the first edit, so that
  every change can be seen and undone. Commit when the user asks.

## Scripts

| Script | Use |
|--------|-----|
| `scripts/lookup_ace.py OBJECT [WORD ...]` | Conditions, actions and expressions of an object of the project, of `System`, or of a plugin or behavior, each with its parameters and the JSON to write |
| `scripts/print_sheet.py [SHEET ...] [--events A-B]` | A sheet, or a range of its events, as the editor words it, under the editor's event numbers; `--outline` for numbers and sids only, `--show N` for one event as JSON |
| `scripts/edit_sheet.py SHEET PLAN.json` | Events put into a sheet, moved, replaced or removed by their numbers, conditions and actions added, changed or removed; checked before anything is written |
| `scripts/check_project.py` | Every project file against the schemas and the editor's load rules; exit 0 when the last line starts with `ok:`. `--style` adds three readability warnings from the official examples' style, for a project the agent wrote |
| `scripts/install.py` | Install this skill in a game project, or refresh a copy from the clone |
| `assets/build_project.py` | Template of a generator, copied to the project's `tools/` and rewritten for the game |

Each prints its options and examples with `--help`. `--locale zh-CN` switches
names and wording to Chinese; ids are the same in every locale. A harness cuts
long tool output without saying where, so each script stops at about 10 000
characters and its last line says how to get the rest; `--limit 0` prints
everything, for a file or a pipe.

## Look an ACE up before writing it

An ACE missing from the schema does not exist. `plugins/system.json` and
`plugins/_common.json` run to thousands of lines, more than most file tools
return at once, and an ACE below the cut looks missing. Ask for the part:

```bash
python scripts/lookup_ace.py Coin tween two
```

```
action tween-two-properties - Tween (two properties) [behavior Tween, tween]  <isAsync>
  Tween two properties of the object.
  write: {"id": "tween-two-properties", "objectClass": "Coin", "behaviorType": "Tween", "sid": <new sid>, "parameters": {"tags": "\"\"", "property": "position", ...}}
    tags                   string     expression string, text in inner quotes: "\"hello\""
    property               combo      position | size | scale
    ease                   ease       bare id of a built-in ease: noease, easeinoutsine, easeoutback ...
```

An object of the project searches its plugin, the ACEs every world object
shares and its behaviors under the names they have on the object. A plugin
or behavior by id or display name (`"8 Direction" speed`) needs no project.
A word is matched as written, not by meaning, against the id and the names
and against where the ACE lives: the behavior, the category, `condition`,
`action`, `expression`. `System timer` finds nothing and lists the
categories; `System time` lists *Every X seconds*, *Wait* and `dt`.

Copy the `write:` line and replace the values. Leave `"sid": <new sid>` out
of a plan for `edit_sheet.py`, which gives every new entry one; in a hand
edit it is a 15-digit number the project does not use yet. An expression
prints the way it is reached, `Coin.Tween.Progress(tags)`. What
the line does not show is in
`Construct3-RAG/prompts/references/hand-editing-project-files.md`: read it
before writing a function or custom action block or a call of one, a
`projectfile` parameter, or a family's behavior through a member type.

## Read a sheet as events

```bash
python scripts/print_sheet.py Game
```

```
   5   Touch: On touched Coin (start)
           -> Coin: Collect()
   9   System: Coin.Count = 0
       System: Trigger once
           -> System: Wait 1 seconds (use time scale: True)
```

Read a sheet this way before an edit, and read what a plan prints after it:
a wrong pick or a missing branch shows in ten lines of events and hides in
three hundred lines of JSON. Read an official example the same way, `--project
<Construct-Example-Projects>/example-projects/template-snake`. A long sheet
prints in parts: run the command its last line gives, or ask for a range,
`--events 40-80`, which starts with the events the range sits in.

The numbers are the editor's: the margin of the event sheet and the
**Where** column of its Find results. Talk to the user in these numbers, not
in JSON line numbers, and read a screenshot or a pasted Find result back the
same way. `--outline` adds each event's sid, the string to search the JSON
for.

## Change a sheet with a plan

Every change to an event sheet goes through a plan: what changes, as JSON in
a file of its own, which the script puts into the sheet. The sheet's JSON is
indented seven to seventeen tabs deep, and an exact-match edit of several
lines there fails one time in three. Other project files are edited as they
are.

```json
[
  {"before": 1, "events": [{"eventType": "variable", "name": "timeLeft", "initialValue": "30"}]},
  {"event": 2, "add-actions": [{"id": "set-text", "objectClass": "ScoreText", "parameters": {"text": "\"Time: \" & timeLeft"}}]},
  {"event": 7, "action": 2, "set": {"parameters": {"text": "\"Score: \" & score & \"  Time: \" & timeLeft"}}},
  {"after": 8, "events": [{"eventType": "group", "title": "Timer", "children": [
    {"eventType": "comment", "text": "Count the time down each second."},
    {"eventType": "block",
     "conditions": [{"id": "every-x-seconds", "objectClass": "System", "parameters": {"interval-seconds": "1"}}],
     "actions": [{"id": "subtract-from-eventvar", "objectClass": "System", "parameters": {"variable": "timeLeft", "value": "1"}}]}]}]}
]
```

```bash
python scripts/edit_sheet.py Game plan.json
```

Every number is an event number of the sheet as it prints now, whatever the
operations above it do, so one print serves a whole plan. An event replaced
by one event keeps its number for the operations below. Its sub-events go
with it: write the ones to keep into the `"events"` that replace it, or
`move` them out in an operation above.

- New events: `"before": N` goes above event N and the comments about it,
  `"after": N` below it and its sub-events, `"into": N` among its
  sub-events, last, and `"into": 0` to the end of the sheet. An event is
  written as the sheet holds it, without `sid` and whatever the editor
  always writes the same way: a group needs its `title`, a variable its
  `name`, a block its conditions and actions.
- What is there: `"add-actions"` and `"add-conditions"`, with
  `"position": 1` for the front; `"set"` on a condition or an action, a
  parameter at a time, or on the event itself, with `null` to take a key
  out; `{"event": 6, "action": 3, "remove": true}`; `{"remove": N}`,
  `{"move": N, "after": M}` and `{"replace": N, "events": [...]}` for whole
  events. `python scripts/print_sheet.py Game --show N` prints event N as
  JSON, to put back changed.
- A finding of the checker names its place the same way: `sheet Game event 5
  condition 1` is `{"event": 5, "condition": 1, "set": {...}}`, and a
  trigger where none may be moves out with `{"move": 7, "after": 6}`.

Nothing is written unless the whole plan holds. The sheet it makes is checked
as `check_project.py` checks, and a problem the plan would add is printed
under its operation, with the file left as it was; a problem that was there
before does not stop it. It ends with the changed events as the editor words
them, under their new numbers, and the checker's last line. A new
top-level event, function or custom action needs a one-sentence comment
above it, `{"eventType": "comment", "text": "..."}` in the same `events`
list, and a run of eight actions needs a comment action, `{"type":
"comment", "text": "..."}`, among them: a plan that adds one without is
refused like a problem, with the place and the JSON to write. A decision
written as sub-events three levels deep is a `warning:` under the output;
write the cases as sibling sub-events instead. The user's older events are
not held to this. `--dry-run` does all of that and writes nothing.

## Check after every change

1. Change a sheet with `edit_sheet.py`, edit another project file, or rerun
   the generator.
2. Run `python scripts/check_project.py`; a plan that ended with `ok:` has
   done it.
3. Fix every line it prints, all of them in one plan: each names its place,
   `sheet Game event 15 action 2`, and says what to write where it can.
   Warnings do not fail the run; a project an agent wrote should have none.
4. Repeat until the last line starts with `ok:`. Only then ask the user to
   open the project.

`ok:` is about the files, not the game. The checker cannot run the events:
which instances a condition picks, what order triggers fire in and what a
tick later looks like are the preview's to judge. Design with
`Construct3-RAG/prompts/event-sheet-thinking.md` first, and before events go
into a sheet read `Construct3-RAG/prompts/event-sheet-style.md`, the shape
the official examples give a sheet, which the style warnings enforce only in
part; a runtime fact the preview teaches goes into
`Construct3-RAG/prompts/event-sheet-pitfalls.md` with its source.

Exit code 2 and `stopped at`: a file lacks a key the editor always writes.
Compare it with a file `assets/build_project.py` generates or with an
official example. Read [references/checker-rules.md](references/checker-rules.md)
when a finding needs explaining or the editor reports an error the checker
let through.

## Generate a whole project

When the agent owns the project and the user reviews it in the editor, write
it as one Python generator instead of JSON by hand. Read
[references/generating-a-project.md](references/generating-a-project.md)
before writing it: set-up in the editor, the build and check loop, one
function per group of the sheet, the habits that keep a rerun safe. The
generator checks what it wrote with `--style`, so every event is held to the
style of the official examples.

## Gotchas

- A parameter is written by its type, which `lookup_ace.py` prints beside
  it. An expression parameter is a string holding an expression: a number is
  `"100"`, a text carries inner quotes, `"\"hello\""`. Every other type is
  bare, or a JSON number or boolean: `"start"`, never `"\"start\""`.
- A variable's `initialValue` is text: `"0"`, and `"true"` or `"false"` for
  a boolean, which the editor reads by comparing to `"true"`. A layout
  instance writes its instance variables as JSON values (`1`, `true`) and
  its `world.angle` in radians. Angles in events are degrees, 0 faces right
  and they grow clockwise; the origin is the top-left and Y grows downwards.
- One trigger per event and per branch of sub-events. A function or a custom
  action counts as one and holds none: react to *On tween finished* in a
  top-level event of its own that calls the next function.
- A name is chosen once: every event that uses it changes with it. Names are
  plain words without spaces or punctuation, an instance variable starts
  with a letter, an object is not named like a system expression (`Floor`,
  `Time`, `Random`), an instance variable not like an expression of its
  object (`Angle`, `Width`, `Count`).
- An instance variable or a behavior added to a type or a family goes into
  every instance of it in every layout. A type created at runtime has a
  template instance in some layout.
