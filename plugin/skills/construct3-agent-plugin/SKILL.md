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
project from Python, and open it in the editor to see that it opens.
They read the schemas of the Construct3-RAG clone, so a name they accept
exists and a name they reject does not. The checker reads the files alone;
the editor also reads the expressions, so a project the checker passes is
opened once before it is handed over.

## Before the first command

- Commands here are written from this skill's folder. From the project root,
  put the folder this file is in before them, for example
  `python .agents/skills/construct3-agent-plugin/scripts/check_project.py`. The
  scripts find the project from the current directory upward, so both work;
  `--project <folder>` names another one.
- The scripts find the clone through `--rag` where their `--help` lists it,
  the `CONSTRUCT3_RAG` environment variable, or the `Construct3-RAG: <folder>`
  line in the project's `AGENTS.md` or `CLAUDE.md`. `Construct3-RAG not found`:
  fill that line in; ask the user for the folder instead of guessing it.
- `check_project.py` fetches the clone at most once an hour to say when it
  is behind its upstream. `CONSTRUCT3_RAG_OFFLINE=1` turns the fetch and the
  comparison off.
- Loaded as the Claude Code plugin (the skill is named
  `construct3:construct3-agent-plugin`): the game project needs no copy; run
  the scripts from this folder. In the files of this skill, `Construct3-RAG/`
  before `data/` or `prompts/` stands for `${CLAUDE_PLUGIN_ROOT}/`. Other
  `Construct3-RAG/` paths, such as `docs/`, are not in the plugin; skip them.
  To hand a sheet change or a lookup to a sub-agent, start it as
  `construct3:project-worker`, which has only the tools these scripts need.
- Otherwise, reading this inside the clone while the work is in a game
  project: install the skill there first,
  `python scripts/install.py --project <game folder>`.
  It copies this folder to the project's `.agents/skills/` and adds the
  Construct 3 block to its `AGENTS.md` with the clone's path filled in
  (`--into .claude/skills` for Claude Code, `.trae/skills` for TRAE). Tell
  the user in one sentence what was installed.
- A line `this copy of the construct3-agent-plugin skill differs from the clone's`:
  run the command it prints, then repeat yours.
- The project has no `.git`: `git init` in it before the first edit, so that
  every change can be seen and undone.
- Commit on the branch `agents`, never on the user's own branch: `git switch
  agents`, or `git switch -c agents` the first time. Commit after each
  finished change, one commit per fix or review item, the message naming it;
  the user reviews `agents` and merges it. Edit `tools/build_project.py` in
  place: git keeps its history, so no scripts that patch it. At the
  hand-over, give the user the events that changed, not the JSON diff:
  `python scripts/print_sheet.py --since <the user's branch>`.
- The user has the project open in the Construct 3 editor: ask them to
  save and close it before you change its files, and to open it again
  after. The editor keeps the files as it loaded them, so a save there
  writes each file edited in the editor over your change, with no warning.

## Scripts

| Script | Use |
|--------|-----|
| `scripts/lookup_ace.py OBJECT [WORD ...]` | Conditions, actions and expressions of an object of the project, of `System`, or of a plugin or behavior, each with its parameters, the JSON to write and the commands that print the official examples using it; or an effect by id or name, with its parameters |
| `scripts/lookup_script_api.py NAME ...` | The scripting API: an interface with its members (`IRuntime`, `Sprite`, `Timer`), or a member with its declaration, its interface and its file and line (`callFunction`, `ISpriteInstance.x`, inherited members included) |
| `scripts/search_guides.py WORD ...` | The pitfall entries that hold the words, in full, and the official examples that do, with the command that prints their events; for an interaction, a timing, a pick or a movement before writing its events, and for events that do not behave as expected |
| `scripts/print_sheet.py [SHEET ...] [--events A-B]` | A sheet, or a range of its events, as the editor words it, under the editor's event numbers; `--map` for one line per sheet with the layouts that run it, the sheets that include it, what it defines and the objects it touches most, `--find NAME` for the events that use a variable, function or object, `--outline` for numbers and sids only, `--show N` for one event as JSON, `--since COMMIT` for the events added, changed, moved and removed since a commit |
| `scripts/print_layout.py [LAYOUT ...] [--layer NAME]` | Layers bottom to top and each instance in Z order with its box, size, opacity and text, and the object a text lies on; read it to say where things are, and after generating a layout, where `on no object` marks a label off its button |
| `scripts/edit_sheet.py SHEET PLAN.json` | Events put into a sheet, moved, replaced or removed by their numbers, conditions and actions added, changed or removed, variables and comments by name; checked before anything is written; `--new` creates the sheet first |
| `scripts/check_project.py` | Every project file against the schemas and the editor's load rules, and a warning for a string shaped like a key, which a web export ships to every player; exit 0 when the last line starts with `ok:`. `--style` adds the warnings of the official examples' style, for a project the agent wrote. For a project someone asks about, pass `--review` to this and to `print_sheet.py`: they then end with what a review reports |
| `scripts/review_design.py` | `--check` runs the full checker, then design findings and questions. Optional `--prepare FOLDER --resume` supplies complete evidence batches and validates saved judgements with `--answers FILE`. Read [references/design-review.md](references/design-review.md) before preparing or resuming a review |
| `scripts/open_in_editor.py` | Open the project in the Construct 3 editor and print `opened`, or `failed` with the editor's message; exit 0 when it opened. `--preview` then runs the game for a few seconds and prints its errors, each with its event, and `--state [TYPE ...]` what it holds at the end. `--install-addon FILE.c3addon` first installs a custom addon the project uses. A refusal of a project the checker passes ends with a report for the user to send, which goes out only at the user's word. It drives the Edge, Chrome or Chromium of the machine headless, 4 to 7 seconds a run once its profile holds the editor and 7 to 40 the first time; without one, or with `--steps`, it prints the same check as steps for a browser tool of the agent's |
| `scripts/preview_project.py PLAN.json` | Preview the project and play it from a plan: tap, hold and drag the game's instances by name, press keys, wait `until` an expression holds, read the state, take screenshots and record the window; one line per step with the runtime errors it caused. Each run starts from a first launch, with no save. `--keep NAME` keeps a plan that passes in `tools/plans/`, and `--all` replays every kept plan. `--help` describes the plan |
| `scripts/check_design.py DESIGN.json` | A new game's design before any project file: refuses a gap by its path (no request in the user's words or an empty `later` list, state nobody writes or reads, an input without feedback or that changes nothing the player sees, no restart of a game that ends, a win without input), then plays its acceptance tests on the rules as a prototype, without the editor, and names the failed step with the values the state held |
| `scripts/play_design.py DESIGN.json` | The same tests played in the editor on the game built from the design, one preview each, after the names and start values the design gives are checked against the project files; then the first screen, its texts, frames and counts of instances shown against the prototype and its layout faults. Each failure names the test, the step and the rules to compare |
| `scripts/review_look.py` | Preview the project, visit every layout and print a screenshot of each, the faults the runtime shows on it, and fixed yes/no questions to answer from the screenshots |
| `scripts/check_look.py` | The strict rules of `assets/look-manifest.json` on a project built from `assets/build_project.py`, after the generator's check ends with `ok:`: alpha, the grid, hit and squash, the screen fill; `--painted FILE ...` names a picture that keeps its soft edges |
| `scripts/screenshot_sheet.py [SHEET] [--group TITLE]` | A picture of an event sheet or one group of it as the editor shows it, in English, cropped to the sheet with each column as wide as its longest line, for a forum post, a bug report or a doc; into `.build/sheets/` |
| `scripts/advanced_random.py SEED` | The numbers an Advanced Random object gives after *Update seed* SEED, computed offline as the plugin computes them, for odds and for replaying a run from its seeds; it also imports as a module. `--check` compares them with the plugin's own code run in node: run it after a Construct update before trusting the numbers |
| `scripts/export_project.py` | Export the project to Web (HTML5) in the editor into `--to`, `--bump` raising its version; a string shaped like a key stops it first. The editor exports for a subscribed account, which the user logs in to: read [references/export-project.md](references/export-project.md) before the first export of a project, when the script stops, or before passing `--attach` |
| `scripts/pack_project.py` | Save the project as a .c3p or .zip, or a .c3p or .zip as a project folder, with project.c3proj at the root of the archive as the editor needs it and only the files the editor saves; what it leaves out it names. Any project handed over as a file, a bug report's attachment among them, is packed with it, `--open` opens the result once in the editor |
| `scripts/prepare_art.py` | The art from the image tool of this session: `--list` prints the next step toward the pictures the generator's `art()` asks for, ending in a prompt for each; without it, each picture saved in `art/raw/` is cut out of its background and fitted to its box, for the generator to take in place of the stand-in. Needs Pillow |
| `scripts/new_project.py FOLDER` | A new game project in an empty FOLDER, copied from the empty project the editor saves for Project > New under the folder's name and its own uniqueId; for a game that has no project yet |
| `scripts/install.py` | Install this skill in a game project, or refresh a copy from the clone and with it the Construct 3 block of the project's `AGENTS.md` and the helpers of its `tools/build_project.py`; `--block-only` and `--helpers-only` refresh one of those alone, for a project that holds no copy |
| `assets/build_project.py` | Template of a generator, copied to the project's `tools/` and rewritten for the game above and below its helpers, which stay the skill's between two markers |
| `assets/runtime-probe.js` | Evaluated in a running preview by a script of the agent's, reads the game's state: positions, variables, animations, behaviors. Read [references/reading-the-runtime.md](references/reading-the-runtime.md) before checking what an event did in the preview |

Each prints its options and examples with `--help`. A script that prints
the editor's wording prints it in Chinese with `--locale zh-CN`; ids are the
same in every locale. A harness cuts long tool output without saying where,
so a script whose output can run long stops at about 10 000 characters and
its last line says how to get the rest; `--limit 0` prints everything, for a
file or a pipe.

## Look an ACE up before writing it

An ACE missing from the schema does not exist, unless the lookup says it is
deprecated: the editor still opens a project that uses it, and a new event
should not. `plugins/system.json` and
`plugins/_common.json` run to thousands of lines, more than most file tools
return at once, and an ACE below the cut looks missing. Ask for the part:

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
world object, not to System or the plugin. Look them up on an object of the
project, `Coin nearest`, which prints them with the object's name written in.

Copy the `write:` line and replace the values. Leave `"sid": <new sid>` out
of a plan for `edit_sheet.py`, which gives every new entry one; in a hand
edit it is a 15-digit number the project does not use yet. A combo item
whose name in the locale differs from its id prints both, `id: name`:
write the id, and give the user the name. An expression
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

In a project of several sheets, find where a feature lives before printing a
sheet: `--map` for the sheets, `--find NAME` for the events that use a name.
A trigger fires only in a sheet the running layout runs, by its own sheet or
an include. So a sheet that no layout runs needs an include before its
triggers work.

## Change a sheet with a plan

Every change to an event sheet goes through a plan: what changes, as JSON in
a file of its own, which the script puts into the sheet. The sheet's JSON is
indented seven to seventeen tabs deep, and an exact-match edit of several
lines there fails one time in three. Other project files are edited as they
are.

```json
[
  {"before": 1, "line": "group Setup", "events": [{"eventType": "variable", "name": "best", "initialValue": "0"}]},
  {"event": 2, "line": "On start of layout", "action": 2, "set": {"parameters": {"text": "\"Score: 0  Best: \" & best"}}},
  {"event": 7, "line": "function AddScore", "action": 2, "set": {"parameters": {"text": "\"Score: \" & score & \"  Best: \" & best"}}},
  {"event": 9, "line": "Coin.Count = 0", "position": 1, "add-actions": [
    {"id": "set-eventvar-value", "objectClass": "System", "parameters": {"variable": "best", "value": "max(best, score)"}}]}
]
```

```bash
python scripts/edit_sheet.py Game plan.json
```

Every number is an event number of the sheet as it prints now, whatever the
operations above it do, so one print serves a whole plan. An operation
that names an event by its number also carries `"line"`: the line the print
shows for that event, or a part of it. If the event does not print that
line, the plan is refused, which catches a number from an older print or a
miscounted one. An event replaced
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
- A variable or a comment has no number, so a plan names a variable by its
  name and a comment by words of its text, as a line at the end of the
  print shows. A value kept in a constant is tuned there, not in the formulas
  that read it.
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
refused like a problem, with the place and the JSON to write, and so are
the traps of the running game that `references/checker-rules.md` marks as
refused, such as a *Find path* that runs every tick. A decision
written as sub-events three levels deep is a `warning:` under the output;
write the cases as sibling sub-events instead. The user's older events are
not held to this. `--dry-run` does all of that and writes nothing.

## Check after every change

1. Change a sheet with `edit_sheet.py`, edit another project file, or rerun
   the generator.
2. Run `python scripts/review_design.py --check --limit 0`, after a plan
   that ended with `ok:` too. It runs the full checker and stops on failure.
   Select changed sheets with `--sheets NAME`. For saved judgements or
   shared dependency evidence, use `--prepare .tmp/design-review --resume`
   as described in [references/design-review.md](references/design-review.md).
3. Fix every line it prints, all of them in one plan: each names its place,
   `sheet Game event 15 action 2`, and says what to write where it can.
   Warnings do not fail the run; a project an agent wrote should have none.
4. Repeat until the checker prints `ok:`. If it prints `stop:`
   instead, it names a finding that two changes left standing: do not change
   that place again, fix the other findings, and give that finding to the
   user as the line says before you go on. After `ok:`, answer every design
   question from `print_sheet.py` and its required dependencies, or from
   the optional complete batches. Validate batch answers with
   `python scripts/review_design.py --prepare .tmp/design-review --answers FILE`.
   Use `edit_sheet.py` for changes, then repeat step 2.
5. Open and preview it in the editor: run `python scripts/check_project.py`
   as the final complete file check, then
   `python scripts/open_in_editor.py --preview`.
   The browser runs headless, so the user sees no window and may think
   the editor never opened: show them the saved screenshot,
   `.tmp/shots/000-<project>.png`, with the result, attached or read with
   the image tool of this session, every time the script runs.
   `--headed` shows the window instead, when the user asks to watch.
   `opened` with `preview: ... no errors` passes, and step 6 follows.
   `failed` prints the editor's dialog, which names the place as
   `Game, event 12, condition 1`, event 12 of sheet Game as `print_sheet.py`
   numbers it; a `runtime:` line names it as `Event sheet 1, event 3,
   action 1`. Fix either as a finding and go back to step 2. The preview
   runs the layout the editor opens on without input, for the seconds its
   `preview:` line gives: it catches what breaks on start, not what a
   player does later. Add `--state Player Enemy` to see whether the events
   that run on start left the variables and instances they should. What a
   player does, a drag, a merge, a jump, is checked by playing it:
   `python scripts/preview_project.py PLAN.json`, with a plan that does it
   and waits `until` the result holds. When `tools/plans/` holds kept
   plans, replay them after every change with
   `python scripts/preview_project.py --all`. Read
   [references/verifying-a-change.md](references/verifying-a-change.md)
   before writing the plan, and
   [references/editor-and-preview.md](references/editor-and-preview.md)
   before previewing a game that starts on another layout, or before
   driving the preview with input from a script.
   Exit code 3: the machine has no browser the script can drive; follow the
   steps it printed instead.
6. Once the preview passes, run `python scripts/review_look.py` and do what
   it prints: fix every finding line, have its questions answered from the
   screenshots as its last line says, then fix each yes
   and run it again; a run with no finding and every answer no is the
   hand-over. A scene the game reaches only in play is read the same way
   from a `shot` of a plan.

In the hand-over, name the last of these steps that passed: checked,
reviewed, opened, previewed, played or looked. Then say what that step
leaves untested. The passing lines from opened on say it; after a check or
a review, the game has not run.

`ok:` is about the files, not the game. The checker cannot run the events:
which instances a condition picks, what order triggers fire in and what a
tick later looks like are the preview's to judge. Design with
`Construct3-RAG/prompts/event-sheet-thinking.md` and the pitfalls
`scripts/search_guides.py` prints for the interaction's words first. The
design guide also names the built-in to write before a variable or an
*Every tick* (its Native first table) and what a new project takes instead
of a superseded feature (a Tween on Opacity for Fade, a hierarchy for Pin,
instance tags for the Solid behavior's own), and before events go
into a sheet read `Construct3-RAG/prompts/event-sheet-style.md`, the shape
the official examples give a sheet, which the style warnings enforce only in
part. What the preview teaches goes, with its source, where "Adding an
entry" of `Construct3-RAG/prompts/event-sheet-pitfalls.md` says.

Exit code 2 and `stopped at`: the line says the cause and what to do.
Compare a file that lacks a key with a file `assets/build_project.py`
generates or with an official example. Read [references/checker-rules.md](references/checker-rules.md)
when a finding needs explaining or the editor reports an error the checker
let through.

## Generate a whole project

A new game starts as a design, checked and played as a prototype before
any file is written: read
[references/designing-a-game.md](references/designing-a-game.md) before
its first project file. When the agent owns the project and the user
reviews it in the editor, write it as one Python generator instead of JSON
by hand. Read
[references/generating-a-project.md](references/generating-a-project.md)
before writing it. The
generator checks what it wrote with `--style`, so every event is held to the
style of the official examples. Its helpers lie between two markers, and
`scripts/install.py` brings them up to date: write the game's settings above
them and the game below them, and a helper the game changes again below the
end marker, where it replaces the skill's.

Every sprite of the game is an `art()` in the generator: it shows a stand-in
shape until its picture is in `art/`. When this session has an image
generation tool, the art comes from that tool, not from code: run
`python scripts/prepare_art.py --list` and follow its output. Without an
image tool, keep the stand-ins: art drawn in code with Pillow looks worse
than they do and mixes styles.

When another model writes the generator, give it the `deliver` steps of
`assets/look-manifest.json`, then run its `confirm` steps on the result,
`scripts/check_look.py` among them. A rule whose status is `open` is the
user's to decide.
