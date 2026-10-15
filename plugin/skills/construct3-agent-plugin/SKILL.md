---
name: construct3-agent-plugin
description: Check, read, look up and generate the JSON of a Construct 3 folder project (project.c3proj, eventSheets, layouts, objectTypes, families) against the Construct3-RAG schemas and the rules the Construct 3 editor applies when it opens a project. Use this skill whenever you write or edit an event sheet or any other project file of a Construct 3 game, need the exact id, parameters and JSON of a condition, action or expression, want to read an event sheet or an official example as events instead of JSON, generate a whole project from a script, or the editor refuses to open or preview a project, even if the user only says "add a mechanic", "fix this event" or pastes an editor error.
compatibility: Requires Python 3.10+ and a local clone of Construct3-RAG or its Claude Code plugin, whose data/c3-schemas the scripts read. prepare_art.py needs Pillow to cut out the pictures of an image tool; elsewhere Pillow is optional, numbering the frames of a preview recording's contact sheet and joining the recording into a GIF where ffmpeg is missing. Opening the project in the editor takes a network connection and Edge, Chrome or Chromium, or a browser tool of the agent.
metadata:
  source: https://github.com/XHXIAIEIN/Construct3-RAG
---

# Construct 3 project files

Scripts for the JSON of a Construct 3 project saved as a folder: look an ACE
up with the JSON to write, read a sheet as the editor words it, change it
from a plan, check the project before the editor opens it, generate a whole
project from Python, and open it in the editor to see that it opens. They
read the schemas of the Construct3-RAG clone, so a name they accept exists
and a name they reject does not. The checker reads the files alone; the
editor also reads the expressions, so a project the checker passes is opened
once before it is handed over.

## Before the first command

- Commands here are written from this skill's folder. From the project root,
  put the folder this file is in before them, for example
  `python .agents/skills/construct3-agent-plugin/scripts/check_project.py`.
  The scripts find the project from the current directory upward;
  `--project <folder>` names another one.
- The scripts find the clone through `--rag`, the `CONSTRUCT3_RAG`
  environment variable, or the `Construct3-RAG: <folder>` line in the
  project's `AGENTS.md` or `CLAUDE.md`. `Construct3-RAG not found`: fill
  that line in; ask the user for the folder instead of guessing it.
  `check_project.py` fetches the clone at most once an hour to say when it
  is behind its upstream; `CONSTRUCT3_RAG_OFFLINE=1` turns the fetch and
  the comparison off.
- Loaded as the Claude Code plugin (the skill is named
  `construct3:construct3-agent-plugin`): the game project needs no copy; run
  the scripts from this folder. In the files of this skill, `Construct3-RAG/`
  before `data/` or `prompts/` stands for `${CLAUDE_PLUGIN_ROOT}/`; other
  `Construct3-RAG/` paths, such as `docs/`, are not in the plugin, so skip
  them. To hand a sheet change or a lookup to a sub-agent, start it as
  `construct3:project-worker`, which has only the tools these scripts need.
- Otherwise, reading this inside the clone while the work is in a game
  project: install the skill there first,
  `python scripts/install.py --project <game folder>`. It copies this folder
  to the project's `.agents/skills/` and adds the Construct 3 block to its
  `AGENTS.md` with the clone's path filled in (`--into .claude/skills` for
  Claude Code, `.trae/skills` for TRAE). Tell the user in one sentence what
  was installed. A line
  `this copy of the construct3-agent-plugin skill differs from the clone's`:
  run the command it prints, then repeat yours.
- The project has no `.git`: `git init` in it before the first edit, so that
  every change can be seen and undone.
- Commit on the branch `agents`, never on the user's own branch: `git switch
  agents`, or `git switch -c agents` the first time. Commit after each
  finished change, one commit per fix or review item, the message naming it;
  the user reviews `agents` and merges it. At the hand-over, give the user
  the events that changed, not the JSON diff:
  `python scripts/print_sheet.py --since <the user's branch>`.
- The user has the project open in the Construct 3 editor: ask them to save
  and close it before you change its files, and to open it again after. The
  editor keeps the files as it loaded them, so a save there writes each file
  edited in the editor over your change, with no warning.

## Scripts

| Script | Use |
|--------|-----|
| `scripts/lookup_ace.py OBJECT [WORD ...]` | Conditions, actions and expressions of an object of the project, of `System`, or of a plugin or behavior, each with its parameters, the JSON to write and the official examples that use it; or an effect, with its parameters |
| `scripts/lookup_script_api.py NAME ...` | The scripting API: an interface with its members, or a member with its declaration and its file and line |
| `scripts/search_guides.py WORD ...` | The pitfall entries and the official examples that hold the words, with the command that prints their events: before writing an interaction, and for events that do not behave as expected |
| `scripts/print_sheet.py [SHEET ...] [--events A-B]` | A sheet, or a range of its events, as the editor words it, under the editor's event numbers; `--map` one line per sheet with the layouts that run it, `--find NAME` the events that use a name, `--outline` numbers and sids, `--show N` one event as JSON, `--since COMMIT` what changed since a commit |
| `scripts/print_layout.py [LAYOUT ...] [--layer NAME]` | Layers bottom to top and each instance in Z order with its box, size, opacity and text, and the object a text lies on, `on no object` for a label off its button |
| `scripts/edit_sheet.py SHEET PLAN.json` | Events put into a sheet, moved, replaced or removed by their numbers, conditions and actions added, changed or removed, variables and comments by name; checked before anything is written; `--new` creates the sheet first |
| `scripts/check_project.py` | Every project file against the schemas and the editor's load rules, and a warning for a string shaped like a key; exit 0 when the last line starts with `ok:`. `--style` adds the warnings of the official examples' style, for a project the agent wrote; `--review`, here and in `print_sheet.py`, for a project someone asks about |
| `scripts/review_design.py` | `--check` runs the full checker, then design findings and questions; `--prepare FOLDER --resume` for saved judgements, after reading [references/design-review.md](references/design-review.md) |
| `scripts/open_in_editor.py` | Open the project in the Construct 3 editor and print `opened`, or `failed` with the editor's message. `--preview` then runs the game for a few seconds and prints its errors, each with its event, `--state [TYPE ...]` what it holds at the end, and `--install-addon FILE.c3addon` installs a custom addon first. A refusal the checker passed ends with a report, which goes out only at the user's word. It drives the machine's Edge, Chrome or Chromium headless, 4 to 7 seconds a run after the first, which takes 7 to 40; without one, or with `--steps`, it prints the same check as steps for a browser tool of the agent's |
| `scripts/preview_project.py PLAN.json` | Preview the project and play it from a plan: tap, hold and drag instances by name, press keys, wait `until` an expression holds, read the state, take screenshots and record, one line per step with the runtime errors. `--keep NAME` keeps a plan that passes in `tools/plans/`, `--all` replays every kept plan |
| `scripts/check_design.py DESIGN.json` | A new game's design before any project file: refuses a gap by its path, then plays its acceptance tests on the rules as a prototype, without the editor |
| `scripts/play_design.py DESIGN.json` | The same tests played in the editor on the game built from the design, then the first screen against the prototype; each failure names the test, the step and the rules to compare |
| `scripts/review_look.py` | Preview the project, visit every layout and print a screenshot of each, the faults the runtime shows on it, and fixed yes/no questions to answer from the screenshots |
| `scripts/check_look.py` | The strict rules of `assets/look-manifest.json` on a project built from `assets/build_project.py`, after the generator's check ends with `ok:` |
| `scripts/screenshot_sheet.py [SHEET] [--group TITLE]` | A picture of an event sheet or one group of it as the editor shows it, for a forum post, a bug report or a doc |
| `scripts/advanced_random.py SEED` | The numbers an Advanced Random object gives after *Update seed* SEED, computed offline as the plugin does |
| `scripts/export_project.py` | Export the project to Web (HTML5) in the editor into `--to`; a string shaped like a key stops it first. The editor exports for a subscribed account the user logs in to: read [references/export-project.md](references/export-project.md) before the first export, when the script stops, or before `--attach` |
| `scripts/pack_project.py` | Save the project as a .c3p or .zip, or a .c3p or .zip as a project folder, with project.c3proj at the archive's root as the editor needs it; a project handed over as a file is packed with it, only after the checker passed its files as they are (`--unchecked` packs them anyway), and `--open` opens the result once in the editor |
| `scripts/prepare_art.py` | The art from the image tool of this session: `--list` prints the next step toward the pictures the generator's `art()` asks for; without it, each picture saved in `art/raw/` is cut out and fitted to its box. Needs Pillow |
| `scripts/new_project.py FOLDER` | A new game project in an empty FOLDER, copied from the empty project the editor saves for Project > New; for a game that has no project yet |
| `scripts/install.py` | Install this skill in a game project, or refresh a copy, the Construct 3 block of the project's `AGENTS.md` and the helpers of its `tools/build_project.py` from the clone |
| `assets/build_project.py` | Template of a generator, copied to the project's `tools/` and rewritten for the game above and below its helpers, which stay the skill's between two markers |
| `assets/runtime-probe.js` | Evaluated in a running preview by a script of the agent's, reads the game's state. Read [references/reading-the-runtime.md](references/reading-the-runtime.md) before checking what an event did in the preview |

Each prints its options and examples with `--help`. A script that prints
the editor's wording prints it in Chinese with `--locale zh-CN`; ids are the
same in every locale. A harness cuts long tool output without saying where,
so a script whose output can run long stops at about 10 000 characters and
its last line says how to get the rest; `--limit 0` prints everything.

## Check after every change

1. Change a sheet with `edit_sheet.py`, edit another project file, or rerun
   the generator.
2. Run `python scripts/review_design.py --check --limit 0`, after a plan
   that ended with `ok:` too. It runs the full checker and stops on failure;
   `--sheets NAME` selects changed sheets.
3. Fix every line it prints, all of them in one plan: each names its place,
   `sheet Game event 15 action 2`, and says what to write where it can.
   Warnings do not fail the run; a project an agent wrote should have none.
4. Repeat until the checker prints `ok:`. If it prints `stop:` instead, it
   names a finding that two changes left standing: do not change that place
   again, fix the other findings, and give that finding to the user as the
   line says before you go on. After `ok:`, answer every design question
   from `print_sheet.py`, change with `edit_sheet.py`, then repeat step 2.
5. Open and preview it in the editor: `python scripts/check_project.py` as
   the final complete file check, then
   `python scripts/open_in_editor.py --preview`. The browser runs headless,
   so the user sees no window and may think the editor never opened. Show
   them the saved screenshot, `.tmp/shots/000-<project>.png`, with the
   result every time the script runs. `opened` with `preview: ... no errors` passes, and step
   6 follows. `failed` prints the editor's dialog, which names the place as
   `Game, event 12, condition 1`: event 12 of sheet Game as `print_sheet.py`
   numbers it. A `runtime:` line names it as `Event sheet 1, event 3, action
   1`. Fix either as a finding and go back to step 2. The preview runs the
   layout the editor opens on without input, so it catches what breaks on
   start, not what a player does later. Check what a player does, a drag, a
   merge, a jump, by playing it: `python scripts/preview_project.py
   PLAN.json` with a plan that does it and waits `until` the result holds.
   If `tools/plans/` holds kept plans, run
   `python scripts/preview_project.py --all` after every change. Read
   [references/verifying-a-change.md](references/verifying-a-change.md)
   before writing the plan, and
   [references/editor-and-preview.md](references/editor-and-preview.md)
   before a preview that starts on another layout or takes input from a
   script.
6. Once the preview passes, run `python scripts/review_look.py` and do what
   it prints: fix every finding line, have its questions answered from the
   screenshots as its last line says, then fix each yes and run it again. A
   run with no finding and every answer no is the hand-over. A scene the
   game reaches only in play is read the same way from a `shot` of a plan.

In the hand-over, name the last of these steps that passed: checked,
reviewed, opened, previewed, played or looked. Then say what that step
leaves untested. After a check or a review, the game has not run: `ok:` is
about the files, not the game, because the checker cannot run the events.
A project handed over as a file is packed after the last check, because
`pack_project.py` refuses files that the check has not passed.

Before you design an interaction, read
`Construct3-RAG/prompts/event-sheet-thinking.md` and run
`scripts/search_guides.py` with the interaction's words. The design guide
names the built-in to write before a variable or an *Every tick* (its
Native first table), and what a new project takes instead of a superseded
feature. Before events go into a sheet, read
`Construct3-RAG/prompts/event-sheet-style.md`, the shape the official
examples give a sheet.

Exit code 2 and `stopped at`: the line says the cause and what to do. Read
[references/checker-rules.md](references/checker-rules.md) when a finding
needs explaining or the editor reports an error the checker let through.

## Look an ACE up before writing it

An ACE missing from the schema does not exist, unless the lookup says it is
deprecated: the editor still opens a project that uses it, and a new event
should not. `plugins/system.json` and `plugins/_common.json` run to
thousands of lines, more than most file tools return at once, and an ACE
below the cut looks missing. Ask for the part:

```bash
python scripts/lookup_ace.py Coin tween two
```

```
action tween-two-properties - Tween (two properties) [behavior Tween, tween]  <isAsync>
  Tween two properties, such as the position (consisting of an X and Y co-ordinate).
  write: {"id": "tween-two-properties", "objectClass": "Coin", "behaviorType": "Tween", "sid": <new sid>, "parameters": {"tags": "\"\"", "property": "position", ...}}
    tags                   string     Optional space-separated list of many tags to identify a tween.
                                      (expression string, text in inner quotes: "\"hello\"")
    property               combo      The properties to tween.  (position | size | scale)
    ease                   ease       The easing function to use.  (bare id of a built-in ease: noease, easeinoutsine, easeoutback ...)
```

*Pick nearest/furthest*, *Is overlapping* and *Set color* belong to every
world object, not to System or the plugin: look them up on an object of the
project, `Coin nearest`. Copy the `write:` line and replace the values.
Leave `"sid": <new sid>` out of a plan for `edit_sheet.py`, which gives
every new entry one; in a hand edit it is a 15-digit number the project
does not use yet. A combo item whose name differs from its id prints both,
`id: name`: write the id, and give the user the name. An expression prints
the way it is reached, `Coin.Tween.Progress(tags)`. What the line does not
show is in `Construct3-RAG/prompts/references/hand-editing-project-files.md`:
read it before writing a function or custom action block or a call of one,
a `projectfile` parameter, or a family's behavior through a member type.

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
three hundred lines of JSON. Read an official example the same way,
`--project <Construct-Example-Projects>/example-projects/template-snake`. A
long sheet prints in parts: run the command its last line gives, or ask for
a range, `--events 40-80`, which starts with the events the range sits in.

The numbers are the editor's: the margin of the event sheet and the
**Where** column of its Find results. Talk to the user in these numbers, not
in JSON line numbers, and read a screenshot or a pasted Find result back the
same way.

In a project of several sheets, find where a feature lives first: `--map`
for the sheets, `--find NAME` for the events that use a name. A trigger
fires only in a sheet the running layout runs, by its own sheet or an
include, so a sheet that no layout runs needs an include before its
triggers work.

## Change a sheet with a plan

Every change to an event sheet goes through a plan: the operations as JSON
in a file of their own, which `edit_sheet.py` puts into the sheet. The
sheet's JSON is indented seven to seventeen tabs deep, and an exact-match
edit of several lines there fails one time in three; other project files
are edited as they are. `python scripts/edit_sheet.py --help` gives every
operation with its JSON: read it before the first plan.

```json
[
  {"before": 1, "line": "group Setup", "events": [{"eventType": "variable", "name": "best", "initialValue": "0"}]},
  {"event": 9, "line": "Coin.Count = 0", "position": 1, "add-actions": [
    {"id": "set-eventvar-value", "objectClass": "System", "parameters": {"variable": "best", "value": "max(best, score)"}}]}
]
```

```bash
python scripts/edit_sheet.py Game plan.json
```

Every number is an event number of the sheet as it prints now, whatever the
operations above it do, so one print serves a whole plan. `"line"` is the
line the print shows for that event, so a number from an older print is
refused. Nothing is written unless the whole plan holds: the sheet it makes
is checked as `check_project.py` checks, and a problem the plan would add is
printed under its operation with the file left as it was. A pass ends with
the changed events under their new numbers and the checker's last line.
`--dry-run` does all of that and writes nothing.

## Generate a whole project

A new game starts as a design, checked and played as a prototype before any
file is written: read
[references/designing-a-game.md](references/designing-a-game.md) before its
first project file. When the agent owns the project and the user reviews it
in the editor, write it as one Python generator instead of JSON by hand,
after reading
[references/generating-a-project.md](references/generating-a-project.md).
The generator checks what it wrote with `--style`, so every event is held
to the style of the official examples. Its helpers lie between two markers,
and `scripts/install.py` brings them up to date: write the game's settings
above them and the game below them, and a helper the game changes again
below the end marker, where it replaces the skill's. Edit
`tools/build_project.py` in place: git keeps its history, so no scripts
that patch it.

Every sprite of the game is an `art()` in the generator: it shows a
stand-in shape until its picture is in `art/`. When this session has an
image generation tool, the art comes from that tool, not from code: run
`python scripts/prepare_art.py --list` and follow its output. Without an
image tool, keep the stand-ins: art drawn in code with Pillow looks worse
than they do and mixes styles. When another model writes the generator,
give it the `deliver` steps of `assets/look-manifest.json`, then run its
`confirm` steps on the result, `scripts/check_look.py` among them. A rule
whose status is `open` is the user's to decide.
