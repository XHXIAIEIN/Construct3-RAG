# Generating a Construct project from a script

Two scripts for a project an agent writes end to end: `build-project.py`
generates the object types, families, layouts, event sheets, images and the
index in `project.c3proj`; `check-project.py` checks the result against the
schemas in this repository before the editor opens it. They came out of the
Water Sort project (r502, September 2026), where the event sheet grew past
what hand-editing JSON can keep consistent: every rerun of the generator
produces the whole project from one Python file, and the checker catches the
mistakes the editor would otherwise report one at a time.

Generate when the agent owns the project and the user reviews it in the
editor: a prototype, a game built from a design conversation, a rewrite. Edit
JSON by hand ([../references/hand-editing-project-files.md](../references/hand-editing-project-files.md))
when the change is small and the project is the user's, made in the editor.
Do not generate over a project the user edits in parallel: the generator
overwrites the files it produces.

## Set up

1. In Construct, create the project (**Menu** > **Project** > **New**) and
   save it as a folder (**Menu** > **Project** > **Save As** > **Save as
   project folder**). `project.c3proj` now has the `uniqueId`, icons and
   scripts the generator keeps. The editor's `Layout 1` and `Event sheet 1`
   are left in place but no longer listed once the generator has run; delete
   the two files or give the generated ones those names.
2. Copy `build-project.py` and `check-project.py` into `tools/` in the
   project.
3. Put the block from [../game-project-AGENTS.md](../game-project-AGENTS.md)
   into the project's `CLAUDE.md` or `AGENTS.md`, whichever the agent's tool
   reads, with the real path. The checker reads the `Construct3-RAG:` line
   from either file to find the schemas, with `<path-to>` taken from a
   `path-to = <folder>` line when the block defines the folder that way;
   `--rag` and `CONSTRUCT3_RAG` override it.
4. Ignore what the editor and the scripts leave behind:

   ```gitignore
   *.uistate.json
   .trash/
   .tmp/
   __pycache__/
   ```

## Build, check, open

Design first, as [../event-sheet-thinking.md](../event-sheet-thinking.md)
says: relations, an official example with the same behaviors, the Native
first and Feel tables, the layout of the sheet. Then:

1. Write the design into the generator: the constants at the top, the
   objects and their variables and behaviors, the layouts, the groups of the
   event sheet in the order the guide gives (Setup, Input, ..., Restart).
2. Run the generator, then the checker, until the checker prints `ok`:

   ```bash
   python tools/build-project.py
   ```

   ```bash
   python tools/check-project.py
   ```

   Warnings do not fail the run; read them anyway, a generated project should
   have none.
3. Hand over. The agent cannot open the editor: ask the user to open the
   folder (**Menu** > **Project** > **Open**, the local project folder
   option) and to preview, and say what to look at. A load error names the event
   variable, object or parameter at fault; paste it back and fix the
   generator, not the JSON.
4. What the preview shows that the checker cannot (an instance picked twice,
   a tween and a timer ending a tick apart, a mask that leaves a corner
   uncovered) is a runtime fact. Fix the generator, and when the fact would
   trip the next agent, add it to
   [../event-sheet-pitfalls.md](../event-sheet-pitfalls.md) with its source.
5. Commit the generator with the files it produced; the diff of the
   generated JSON is the review of the change.

The project's README explains the objects, the groups, the constants and how
to regenerate. It is the second copy of the design, for the user, and it says
that running the generator discards edits made in the editor.

## What the checker sees

For every condition and action: the object or family exists, the behavior is
on it, the ACE id is in the plugin's, the behavior's or the shared world
object schema, the parameter keys are the schema's, a combo value is one of
its items, a comparison is an integer 0 to 5, a boolean is a JSON boolean.
Expressions are scanned for object, behavior, expression, instance variable,
function, global, local and parameter names, case-insensitively, as the
editor reads them. Layout instances must carry every instance variable and
behavior block of their type and only properties the schema has. Layers,
layouts, animations, groups, timelines, flowcharts, project files, images and
called functions and custom actions must exist, with the right parameter
count. Uids, and the sids of events, variables, object types and instances,
must be unique; a condition or action that shares a sid is a warning, since
the editor tolerates what its own paste leaves behind. A missing schema (a
third-party addon) is a warning, and its ACEs pass unchecked.

It also applies the rules the editor enforces when it opens or previews a
project, so that they surface here with an event number instead of one at a
time in a dialog
([decision record](../../docs/decisions/checker-editor-load-rules.md)):

| Rule | The editor's message |
|------|----------------------|
| One trigger per event and per branch of sub-events; a function or a custom action counts as one, so neither holds a trigger; an OR block may list several. *On collision* and *On timer* are triggers | `cannot add another trigger to event branch` |
| A trigger, a loop, *Else*, *Trigger once* and the conditions that only pick (*Pick all*, *Pick by comparison*, *Pick nearest/furthest*, *Pick children*) are never inverted | `condition not invertible` |
| *Else* is the first condition of an event that directly follows a plain event: not a trigger, not a loop, not a group or a variable, only comments between | `An Else condition cannot be placed here`, before preview and export |
| A plugin or behavior id is spelled as the editor spells it: `Arr`, `Json`, `TiledBg`, `EightDir`, `Sin`, `solid` | `missing plugin id` |
| An object or family name is not `self`, `true`, `false`, `system` or a system expression (`Floor`, `Time`, `Random`, `Max`) | `name is reserved` |
| A name has no spaces or punctuation; an instance variable name starts with a letter | the editor renames it silently, and the events that use it fail with `cannot find object` |
| An instance variable, behavior or effect is not named like another one on the object or its families, nor like an expression of the object (`Angle`, `Width`, `Count`, `Text`) | `name already in object class namespace` |
| A key is a key code, a JSON number | `expected finite number` |
| An action does not write a constant | `event variable X is constant` |
| An ease is a built-in id such as `easeoutback`, unless the project has custom eases | the tween keeps no ease and fails later |

*Trigger once* or *Every X seconds* in a triggered branch is a warning: the
editor no longer offers them there, and official examples that do it still
open.

A finding says what to write where it can: the nearest id, the behavior that
owns an ACE written without `behaviorType`, the editor's id for a display
name (`Array` is `Arr`), the project's object behind a plugin name in an
expression (`JSON.Get` is `Levels.Get`), a combo value written with inner
quotes, a text value written without them. A file that lacks a key the editor
always writes stops the run with the key and the place, exit code 2.

A finding in an event sheet is placed as `sheet Game event 15 action 2`. The
event number is the editor's: the one in the margin of the event sheet and
in the **Where** column of Find results. Blocks, groups and function blocks
are counted per sheet in document order, sub-events included. A variable,
comment or include has no number of its own: the margin leaves it blank and
Find files it under the next numbered event, so the nine locals above event
15 of the Water Sort sheet are `Event 15` too. Conditions and actions count
from 1. Talk to the user in these numbers, not in JSON line numbers, and read
a screenshot or a Find result back the same way. `check-project.py --outline
Game` prints the numbering of a sheet with each event's sid, which is what to
search the JSON for, unnumbered rows in parentheses; `--outline` alone prints
every sheet.

It does not see what happens at runtime: which instances a condition picks,
what order triggers fire in, whether an expression means what the comment
says. The editor and the preview judge those; the Water Sort observations in
the pitfalls came from previewing, not from the checker.

Run over the official example projects (saved r184 to r502) with the r495.2
schemas on 2026-09-21, it passed 493 of 524. The rest fail on ACEs and
parameters that a later release renamed, on layers and animations the
examples name but no longer have, and on duplicate sids in r184 projects;
each is a real finding, not a false one. None of them breaks an editor rule
of the table above, which is how each rule was confirmed before it became an
error. `tests/test_project_tools.py` generates the stand-in game, breaks it
one rule at a time and reads the finding.

## Writing the generator

The stand-in game in `build-project.py` shows the shape. Keep these habits;
they are what made rerunning safe in Water Sort.

- Constants once, at the top, and a global constant in the sheet for every
  number an event reads; a tunable value has one place to change. What a
  behavior owns (a Sine period, a particle rate) is an instance property set
  in `build_layouts()`, not an event.
- `random.seed(...)` before the first `sid()`: a rerun then produces the same
  ids and the diff shows only what changed.
- One helper per ACE, named for what it does, its parameters in the
  schema's order, with a docstring only where the schema does not say enough
  (which pick it leaves, what a tick later looks like). A helper is added
  when the design needs the ACE; read its entry in
  `data/c3-schemas/{locale}/` first and copy the parameter keys from there.
- Behaviors are referred to by the name given on the object, not the
  behavior id: `beh_def("Sin", "Shake")` and `beh_def("Sin", "Rock")` are
  two behaviors, and a helper takes `beh="Shake"`. The id is the editor's
  spelling from `data/c3-schemas/_index.json` (`originalId`): `Sin`, not
  `Sine`; `EightDir`, `TiledBg`, `Arr`, `Json`, `solid`.
- A `block()` has one trigger, as its first condition, and `func()` and
  `custom_action()` hold none. A function that starts a tween and must react
  to its end ends there; the reaction is a top-level `on_tween_finished`
  block that calls the next function.
- Names are plain words: no spaces or hyphens, an instance variable starts
  with a letter, an object is not named like a system expression (`Floor`,
  `Time`, `Random`), an instance variable not like an expression of its
  object (`Angle`, `Width`, `Count`).
- Every runtime-created type has a template instance in a layout that never
  runs (`Objects` in the stand-in).
- Family variables and behaviors are declared on the family and set on every
  member instance; the checker reports the instance that lacks one.
- A custom action on the object or family for logic that runs on the caller's
  picked instances; a function only for a return value or for logic that
  picks its own instances. Inside a family's block, write the family's name.
- Locals declared as children of a function block are not in scope for the
  block's own actions; put the actions that read them in a child block.
- Comments in the sheet (`comment(...)`) say what a group is for and which
  fact a block relies on; they are what the user reads in the editor.

## Keeping the editor's changes

The generator overwrites what it produces, so a change made in the editor is
either moved into the generator or lost. Before regenerating over files the
editor has touched, copy them to `.trash/<date>/<relative path>` (untracked
projects) or commit (tracked projects). `json.dumps(obj, indent="\t",
ensure_ascii=False)` written with `newline="\n"` and no trailing newline is
the editor's own file layout, so what the editor saves over a generated
project differs only where it changed something (roundtrip checked on
mergeGame, r502).
