# What `check_project.py` checks

Read this when a finding needs explaining, when the editor reports an error
the checker let through, or before adding a rule.

## Against the schemas and the project

For every condition and action: the object or family exists, the behavior is
on it, the ACE id is in the plugin's, the behavior's or the part of the
shared world object schema the plugin's `commonAces` lists, the parameter
keys are the schema's, a combo value is one of
its items, a comparison is an integer 0 to 5, a boolean is a JSON boolean.
Expressions are scanned for object, behavior, expression, instance variable,
function, global, local and parameter names, case-insensitively, as the
editor reads them. Layout instances must carry every instance variable and
behavior block of their type and only properties the schema has. Layers,
layouts, animations, groups, timelines, flowcharts, project files, images and
called functions and custom actions must exist, with the right parameter
count. An image is `images/<object type>-<animation>-<frame, three
digits>.png`, or `images/<object type>.png` for a single image, in lower
case; one imported in a lossy format and not edited since keeps that format,
which the entry's `fileType` names. Its size is not compared with the
entry's `width` and `height`: the editor takes the size from the file. Two object types or families with one sid are an error: the editor
stops with `object class sid already in use`. Any other repeated sid is a
warning: a project whose events, instances, layers or animations repeat
one opens and previews. Two instances with one uid are an error: the
editor opens them but gives all but one another uid, so a hierarchy link
or a *Pick by UID* written for one may reach the other. A missing schema (a
third-party addon) is a warning, and its ACEs pass unchecked. So is what the
editor has deprecated, from `Construct3-RAG/data/c3-schemas/{locale}/_deprecated.json`:
an addon, and an ACE or expression, once each at its first use with the count
of the others, and the current ACE of the same name when there is one. The
editor opens a project that uses them, and a new event should not.

Three findings about files are warnings, since the editor opens the project:

- a file in a folder of the project that `project.c3proj` does not list,
  which the editor ignores; `scripts/` is not searched, since the editor
  keeps TypeScript copies and definitions there for an external editor
  without listing them;
- a sound or music file that is not WebM Opus (`.webm`), the format the
  editor encodes imported audio to and Construct decodes itself on Safari
  and iOS [manual: interface/dialogs/import-audio.md];
- a script listed as both `.ts` and `.js`: Construct runs the `.js` and
  ignores the `.ts` [manual: scripting/using-scripting/typescript-construct.md].

Traps of the running game are warnings:

- a *Wait for signal* or *On signal* whose text tag no *Signal* action or
  `runtime.signal()` raises, which never ends or runs;
- a script that reads an event's local or parameter by its bare name
  instead of `localVars.name`, a `ReferenceError` when it runs;
- an action the manual allows only in a user input trigger, such as
  *Request fullscreen*, *Request permission* or *Request wake lock*, with no
  touch, mouse, keyboard or form control condition in its event or above
  it, which the browser refuses;
- with a Pathfinding behavior taking its obstacles from Solids, an action
  that creates, destroys, moves or resizes a Solid, switches one off or
  changes a Solid tilemap's tiles, when no *Regenerate* action is anywhere:
  the obstacle map is built once at startup;
- *Move along path* or a node expression in the same actions as the *Find
  path* that started the path, with no *Wait for previous actions to
  complete* between them: the path is there only after *On path found*;
- *Find path* in an event that runs every tick, with no trigger, *Every X
  seconds* or *Trigger once* in it or above it;
- text a Sprite Font cannot draw, in a layout instance's text or in a
  literal that *Set text*, *Append text* or *Typewriter text* joins at the
  top level of its expression: a character outside the Character set shows
  as an empty space; with *Enable BBCode* on, the tags are not counted;
- an effect action naming, in a literal, an effect the object and its
  families, the layer or every layout lack: it runs and changes nothing.

A gesture action or a *Find path* in a function passes, since a trigger may
call it.

## The rules the editor applies on opening and before preview

They surface here with an event number instead of one at a time in a dialog.
How each was read from the editor and confirmed:
`Construct3-RAG/docs/decisions/checker-editor-load-rules.md`.

| Rule | The editor's message |
|------|----------------------|
| One trigger per event and per branch of sub-events; a function or a custom action counts as one, so neither holds a trigger; an OR block may list several. *On collision* and *On timer* are triggers | `cannot add another trigger to event branch` |
| A trigger, a loop, *Else*, *Trigger once* and the conditions that only pick (*Pick all*, *Pick by comparison*, *Pick nearest/furthest*, *Pick children*) are never inverted | `condition not invertible` |
| *Else* is the first condition of an event that directly follows a plain event: not a trigger, not a loop, not a group or a variable, only comments between | `An Else condition cannot be placed here`, before preview and export |
| A plugin or behavior id is spelled as the editor spells it: `Arr`, `Json`, `TiledBg`, `EightDir`, `Sin`, `solid` | `missing plugin id` |
| An object or family name is not `self`, `true`, `false`, `system` or a system expression (`Floor`, `Time`, `Random`, `Max`) | `name is reserved` |
| Object types, families and the Functions object share one namespace, compared without case, and `project.c3proj` lists each object type once | `object class name 'X' already used`, `object type name 'X' already used` |
| A global or local variable or a function parameter is not named like a system expression (`mid`, `max`, `round`), compared without case: inside an expression the name reads as the system expression | `Invalid expressions ... parameter 0 does not take 'string'`, for a local `mid` passed to a function; `'round' does not accept 0 parameters`, for a parameter `round` |
| A function without parameters is called without parentheses: `Functions.settling`, not `Functions.settling()` | `Syntax error: ')' can't go here` |
| A function with a return type is read in an expression, never called as an action; one whose return type is `none` is called as an action, never read | `function 'X' has wrong return type`; `The function 'X' has a return type of 'None' so cannot be used as an expression` |
| No two variables of one scope share a name, compared without case: the top-level variables of every sheet are one scope, the variables of one list of events another, a function's parameters another. A global declared at the top of two sheets is declared twice | the editor opens the file, and every use of the name reaches the first; its variable dialog refuses the second name with `The name X is already used in this scope` |
| A local variable or function parameter is not named like a variable of another type already in scope, compared without case: the nearest scope wins, so a text `count` hides a number `COUNT` in its event and sub-events | `Type mismatch: - does not work with 'string' and 'number'`, for `COUNT - 1` below a text local `count` |
| A shared ACE of `plugins/_common.json` is used only on a plugin whose `commonAces` lists it: Text has no `set-default-color`, its colour is `set-font-color` | `missing action id 'set-default-color'` |
| `Self` stands only in a parameter of an object's own condition or action; in a System one (*For each ordered*, *Pick by comparison*, *Set variable*) it names nothing, and the finding writes the expression with the object the ACE names | `Invalid use of 'self'` |
| A name has no spaces or punctuation; an instance variable name starts with a letter | the editor renames it silently, and the events that use it fail with `cannot find object` |
| An instance variable, behavior or effect is not named like another one on the object or its families, nor like an expression of the object (`Angle`, `Width`, `Count`, `Text`) | `name already in object class namespace` |
| An expression uses Construct's operators: `=` compares, `<>` is not equal, `&` is and, `\|` is or, `^` is power; `==`, `!=`, `&&`, `\|\|`, `**` and `!` stand only inside a text literal | `Syntax error: '=' can't go here`, `Syntax error: '*' can't go here`, `Syntax error: Unknown character` |
| An expression parameter is never empty; empty text is the literal `""`, written `"\"\""` in the JSON | `Empty expression: You must enter an expression` |
| Every text literal is closed, a quote inside it doubled; a backslash stands only inside a literal, where it is a plain character | `Syntax error: String missing finishing "`, `Syntax error: Unknown character` |
| A comment event carries `text`, a group `description`, an event variable `comment`, each as text, `""` when empty | `Cannot read properties of undefined (reading 'endsWith')`, `expected string` |
| A function's `functionReturnType` is `none`, `number`, `string` or `any`; a custom action's `aceType` is `action` | `function has wrong return type`, `invalid ACE type` |
| Every file `rootFileFolders` lists is on disk: `general` in `files/`, `icon` in `icons/`, `sound` in `sounds/`, `music` in `music/`, `video` in `videos/`, `font` in `fonts/`, `script` in `scripts/` | `missing file path 'icons\icon-16.png'`, `missing file path 'videos\clip.webm'` |
| A sound parameter (*Play*, *Play at object*) names a sound or music file the project lists, without its extension, in any case: `SFX1` for `sfx1.webm` | `missing file '0'`, `missing file 'sfx1.webm'` |
| A key is a key code, a JSON number | `expected finite number` |
| An action does not write a constant. The editor finds a variable by its name without case, taking the nearest declaration and, within one list of events, the first: with a constant `PHASE` declared above a variable `phase`, *Add 1 to phase* writes `PHASE`, and the finding says to rename `phase` | `event variable phase is constant` |
| An ease is a built-in id such as `easeoutback`, unless the project has custom eases | the tween keeps no ease and fails later |
| An event variable's or a function parameter's `initialValue` is text, a boolean's `"true"` or `"false"` in lowercase; a parameter may also carry a JSON number | a boolean is read by comparing the text to `"true"`, so `false`, `true`, `"True"` and `"1"` all read as false; another JSON type in a parameter stops the load with `invalid type of initialValue` |
| An instance variable's `type` is `number`, `string` or `boolean`; the editor's Text type is `string` | not measured |
| A layout instance writes an instance variable as a JSON value of its type: `1`, `"a"`, `true` | a text `"1"` on a number reads through `parseFloat`, a boolean on a number reads as 0 |
| `project.c3proj` keeps the properties the editor writes: `description`, `version`, `author`, `authorEmail`, `authorWebsite`, `appId`, `fullscreenMode`, `fullscreenQuality`, `orientations`, `sampling`, `downscaling`, `loaderStyle`, and a viewport of at least 2 | `TypeError: expected string`, before the editor names a file |
| `savedWithRelease` is the release that saved the project; below r309 the editor reads an object type from `objectTypes/<name in lower case>.json` | no message: the object type file is not found |
| `project.c3proj` keeps the lists of what the project holds: `objectTypes`, `families`, `layouts` and `eventSheets` with an `items` and a `subfolders` array each, and `containers` as an array, empty when the project has none | `TypeError: expected object`, `TypeError: expected array` |
| A `Sprite` or a `Shape3D` object type carries an `animations` folder | `TypeError: expected object` |
| A layout has a `name`, a `width` and a `height` of at least 2, and a `layers` array | `TypeError: expected string`, `expected finite number`, `invalid layout width` |
| A layer has a `name`, `parallaxX`, `parallaxY`, `scaleRate`, a `blendMode` the editor knows, and an `instances` array, empty when nothing is on it | `TypeError: expected finite number`, `invalid blend mode` |
| An instance on a layer carries `world` with `x`, `y`, `width`, `height`, `originX` and `originY` | `TypeError: expected finite number` |
| An event sheet has a `name` and an `events` array | `TypeError: expected string`, `invalid event sheet name` |
| Every event is an object with an `eventType` the editor knows; a block, a function block and a custom action block have a `conditions` and an `actions` array, empty when they have none; a script event's `script` is text or a list of lines; `children`, when the key is there, is a list | `TypeError: expected object`, `invalid event type`, `invalid script data` |
| A layout instance's `world.angle` is in radians, within a full turn | an angle written in degrees turns the instance some other way; every official example stays within 2π |

*Trigger once* or *Every X seconds* in a triggered branch is a warning: the
editor no longer offers them there, and official examples that do it still
open.

## What a finding says

A finding says what to write where it can: the nearest id, the behavior that
owns an ACE written without `behaviorType`, the editor's id for a display
name (`Array` is `Arr`), the project's object behind a plugin name in an
expression (`JSON.Get` is `Levels.Get`), a combo value written with inner
quotes, a text value written without them. A file that lacks a key the editor
always writes stops the run with the key and the place, exit code 2. A long
report prints the findings that fit 10 000 characters, warnings in at most a
third of them and problems in the rest, and counts what it left out: fix
those and run again, or pass `--limit 0`.

A finding in an event sheet is placed as `sheet Game event 15 action 2`. The
event number is the editor's: the one in the margin of the event sheet and
in the **Where** column of Find results. Blocks, groups, function blocks,
custom action blocks and script blocks are counted per sheet in document
order, sub-events included. A variable, comment or include has no number of
its own: the margin leaves it blank and Find files it under the next
numbered event, so the locals right above event 15 are `Event 15` too.
Conditions and actions count from 1. `scripts/print_sheet.py --outline Game`
prints the numbering of a sheet with each event's sid, which is what to
search the JSON for, unnumbered rows in parentheses.

## Style, with `--style`

Seven warnings the editor never raises, for a project the agent wrote: the
generator template passes `--style`. `edit_sheet.py` holds the events a plan
creates to them, never the sheet's older events: the first four, whose fix
is one comment or one deleted condition, refuse the plan like a problem; the
other three, and any
finding on an event the plan moved or extended, are warnings under its
output. Each names the event and says what to write.

| Warning | Threshold | Over the 524 official examples |
|---------|-----------|-------------------------------|
| N actions in a row without a comment action | 8 or more | 113 in 50 projects; the studio games step a block every 3 actions at the median, 6 at the 90th percentile |
| no comment above it (a top-level event, function or custom action with actions or sub-events) | none, variables between allowed | 1184 in 278 projects; 93% of the studio games' top-level events have one, the rest are Scirra's feature demos and external games |
| none of its N case sub-events has a comment above it (an event with two or more sub-events that have actions or sub-events, no comment above any) | 2 or more cases | 435 in 116 projects; of the studio games' 1605 events with cases, 84% have a comment above at least one, and 75% of the 4382 cases have their own |
| Every tick beside N other condition(s) changes nothing (a block that is not an OR block) | 1 other condition | rare; the examples write Every tick as an event's one condition |
| sub-events N levels deep, every leaf calling one function | 3 levels, 3 or more leaves | 3, in shifting-dungeon, template-ladder-climbing, wall-walking |
| with events ..., the same conditions and actions N times over (sibling events of one shape, their values ignored) | 5 or more | 47 in 31 projects; 32 in 20 studio games, input ladders, a key per action, and else-if chains among them |
| counts seconds by hand (Every N seconds taking N off a variable in the same event: Subtract N, Add -N or Set v to v - N) | the amount equals the interval | none; the one example that subtracts every N seconds counts coins out. 73 of the 155 eval and small-model projects wrote it, every add-countdown run among them |

Why these thresholds: `Construct3-RAG/docs/decisions/event-sheet-design-guidance.md`.
A style warning is never an error: the editor accepts all seven, and an
official example may carry one. What the shape should be instead is
`Construct3-RAG/prompts/event-sheet-style.md`.

## What it does not see

What happens at runtime: which instances a condition picks, what order
triggers fire in, whether an expression means what the comment says. The
editor and the preview judge those; the observations in
`Construct3-RAG/prompts/event-sheet-pitfalls.md` and in
`editor-and-preview.md` beside this file came from previewing, not from the
checker. Expression syntax beyond those operators, argument counts and types, and
`function` and `template` parameters are not checked either.
The editor checks the types in an expression as it opens the project, and
`scripts/open_in_editor.py` prints its message, such as `Type mismatch: -
does not work with 'string' and 'number'`.

## How the rules were confirmed

Run over the official example projects (saved r168 to r472), the checker
fails a few, on parameters that a later release changed and on layers and
animations the examples name but no longer have; each is a real finding,
not a false one. None of them breaks an editor rule
of the table above, which is how each rule was confirmed before it became an
error. `Construct3-RAG/tests/test_skill_check_project.py` breaks the
stand-in game one rule at a time and reads the finding.

A new rule takes the same two steps: find the editor's message in its
project model, run the rule over the official examples, and only then make
it an error, with a test that breaks the stand-in project.
