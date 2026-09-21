---
name: construct3-project
description: Check, read, look up and generate the JSON of a Construct 3 folder project (project.c3proj, eventSheets, layouts, objectTypes, families) against the Construct3-RAG schemas and the rules the Construct 3 editor applies when it opens a project. Use this skill whenever you write or edit an event sheet or any other project file of a Construct 3 game, need the exact id, parameters and JSON of a condition, action or expression, want to read an event sheet or an official example as events instead of JSON, generate a whole project from a script, or the editor refuses to open or preview a project, even if the user only says "add a mechanic", "fix this event" or pastes an editor error.
compatibility: Requires Python 3.10+ and a local clone of Construct3-RAG, whose data/c3-schemas the scripts read. Pillow is optional and only compares image sizes.
metadata:
  source: https://github.com/XHXIAIEIN/Construct3-RAG
---

# Construct 3 project files

Scripts for the JSON of a Construct 3 project saved as a folder: look an ACE
up with the JSON to write, read a sheet as the editor words it, check the
project before the editor opens it, generate a whole project from Python.
They read the schemas of the Construct3-RAG clone, so a name they accept
exists and a name they reject does not.

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

## Scripts

| Script | Use |
|--------|-----|
| `scripts/lookup_ace.py OBJECT [WORD ...]` | Conditions, actions and expressions of an object of the project, of `System`, or of a plugin or behavior, each with its parameters and the JSON to write |
| `scripts/print_sheet.py [SHEET ...]` | A sheet as the editor words it, under the editor's event numbers; `--outline` for numbers and sids only |
| `scripts/check_project.py` | Every project file against the schemas and the editor's load rules; exit 0 when the last line starts with `ok:` |
| `scripts/install.py` | Install this skill in a game project, or refresh a copy from the clone |
| `assets/build_project.py` | Template of a generator, copied to the project's `tools/` and rewritten for the game |

Each prints its options and examples with `--help`. `--locale zh-CN` switches
names and wording to Chinese; ids are the same in every locale.

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
Add a word to narrow a long list; `condition`, `action` and `expression` are
words too. Copy the `write:` line and replace the values; an expression
prints the way it is reached, `Coin.Tween.Progress(tags)`.

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

Read a sheet this way before and after an edit: a wrong pick or a missing
branch shows in ten lines of events and hides in three hundred lines of JSON.
Read an official example the same way, `--project
<Construct-Example-Projects>/example-projects/template-snake`.

The numbers are the editor's: the margin of the event sheet and the
**Where** column of its Find results. Talk to the user in these numbers, not
in JSON line numbers, and read a screenshot or a pasted Find result back the
same way. `--outline` adds each event's sid, the string to search the JSON
for.

## Check after every change

1. Edit the project files, or rerun the generator.
2. Run `python scripts/check_project.py`.
3. Fix every line it prints: each names its place, `sheet Game event 15
   action 2`, and says what to write where it can. Warnings do not fail the
   run; a project an agent wrote should have none.
4. Repeat until the last line starts with `ok:`. Only then ask the user to
   open the project.

Exit code 2 and `stopped at`: a file lacks a key the editor always writes.
Compare it with a file `assets/build_project.py` generates or with an
official example. Read [references/checker-rules.md](references/checker-rules.md)
when a finding needs explaining or the editor reports an error the checker
let through.

## Generate a whole project

When the agent owns the project and the user reviews it in the editor, write
it as one Python generator instead of JSON by hand. Read
[references/generating-a-project.md](references/generating-a-project.md)
before writing it: set-up in the editor, the build and check loop, the habits
that keep a rerun safe.

## Gotchas

- A parameter is written by its type. An expression parameter is a string
  holding an expression: a number is `"100"`, a text carries inner quotes,
  `"\"hello\""`. A combo item, an object, a layout, a variable and an ease
  are bare: `"start"`, never `"\"start\""`. A comparison is a JSON number 0
  to 5 (=, !=, <, <=, >, >=), a boolean a JSON boolean, a key a key code (32,
  not `"Space"`).
- `behaviorType` is the name the behavior has on the object, not the
  behavior id, and a behavior's expression is reached through that name:
  `Player.Platform.Speed`.
- Addon ids are the editor's spelling, case-sensitive: `Arr`, `Json`,
  `TiledBg`, `EightDir`, `Sin`, `solid`. An expression goes through the
  project's object, not the plugin: `Levels.Get`, not `JSON.Get`.
- One trigger per event and per branch of sub-events. A function or a custom
  action counts as one and holds none: react to *On tween finished* in a
  top-level event of its own that calls the next function.
- *Else* is the first condition of an event that directly follows a plain
  event. A trigger, a loop, *Else* and *Trigger once* are never inverted.
- Names are plain words: no spaces or punctuation, an instance variable
  starts with a letter, an object is not named like a system expression
  (`Floor`, `Time`, `Random`), an instance variable not like an expression
  of its object (`Angle`, `Width`, `Count`).
- Every instance in a layout carries every instance variable of its type and
  a properties block per behavior, those of its families included. Every
  type created at runtime has a template instance in some layout.
- The checker cannot run the events: which instances a condition picks, what
  order triggers fire in and what a tick later looks like are the preview's
  to judge. Design with `Construct3-RAG/prompts/event-sheet-thinking.md`
  first; a runtime fact the preview teaches goes into
  `Construct3-RAG/prompts/event-sheet-pitfalls.md` with its source.
