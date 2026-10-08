# What `check_project.py` checks

Read this when a finding needs explaining, when the editor reports an error
the checker let through, or before adding a rule. For an error the checker
let through, `scripts/open_in_editor.py` also prints a report for the user to
send to the skill's repository, once per refusal; it is sent only when the
user says so.

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

What a project folder holds, the files `project.c3proj` lists, their names
and formats, is stated in Scirra's guide to the project format, kept in
`Construct3-RAG/data/c3-guides/constructs-project-format.md`. These findings
about files are warnings, since the editor opens the project:

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
- Timer *Start timer* in an event that runs every tick, when every condition
  of its branch tests a variable or `Count`. The timer then starts over each
  tick, and *On timer* never fires. It passes when an action of the branch
  sets that variable, creates or destroys that type, calls a function or
  leaves the group or layout, and when the branch tests *Is timer running*
  or what changes as the game plays: an overlap, a key, a position, a
  function;
- a variable flipped in an event that runs every tick: *Toggle*, or *Set*
  to `N - x`, `-x`, `x * -1` or `x = a ? b : a` of the same variable. The
  event runs again on the next tick and flips it back, so the value an
  input reads depends on the tick it arrives in [manual:
  project-primitives/events/how-events-work.md "Events run top to
  bottom"]. It passes when an action of the branch, or of a function it
  calls, changes what a condition tests: it sets a variable, creates or
  destroys a type, or acts on an object that the condition names or reads.
  It also passes when an action leaves the group or layout. An event that
  starts with *Else* also tests the event it answers. The finding names
  the triggering event to move the flip into, and, for a value that runs
  out such as the time left of a turn, the *Set* that puts it back in the
  same actions. Under *Trigger once*
  alone, with conditions that test values, the flip happens once each time
  they turn true, not once per input: a warning that `edit_sheet.py` does
  not refuse, since a flip once a round is sound;
- *Simulate control* of a Platform's left or right, or of any 8 Direction or
  Car control, in a branch with a trigger: the control holds for the tick
  it runs in, so the object moves one tick and stops [manual:
  behavior-reference.md "Custom controls"]. A Platform jump and Tile
  movement, which take one tick as a whole move, pass;
- in one layout, instances of two or more object types with a movement
  behavior whose *Default controls* is on, or absent from the instance's
  properties, which the editor reads as on: each moves with the arrow
  keys, so a crate given Platform to be
  pushed walks with the player [manual: behavior-reference/platform.md
  "Default controls"]. Instances of one type steered together, two knights
  that move as one, pass. Over the official examples it adds no finding;
- `X.Count = 0`, `≤ 0` or `< 1` in a condition that runs after a *Destroy*
  of X in the same top-level event: the destroyed instance counts until
  that event ends, so the test fails for the last one
  [`Construct3-RAG/prompts/pitfalls/picking.md`]. The official examples
  compare with 1 there, which passes, as does a test after a *Wait*;
- `X.PickedCount = 0`, `≤ 0` or `< 1` below a condition of its branch that
  picks X, such as *Pick all*, *For each* or a condition on X: a condition
  that picks no X stops its event, and *Pick all* is false when no X
  exists, so the test never holds [manual:
  project-primitives/events/how-events-work.md];
- text a Sprite Font cannot draw, in a layout instance's text or in a
  literal that *Set text*, *Append text* or *Typewriter text* joins at the
  top level of its expression: a character outside the Character set shows
  as an empty space; with *Enable BBCode* on, the tags are not counted. A
  layout text whose part a *Set text* replaces in the object's own text,
  `###` for `replace(Self.Text, "###", ProjectVersion)`, is checked without
  that part. An instance without a Character set is read with the editor's
  default set, and one without *Enable BBCode* with it off, as the editor
  reads them;
- a Sprite Font instance without *Character set*, *Character width* or
  *Character height*: the editor fills the values that fit its own font
  image, so an image drawn in another order or cell size shows the wrong
  characters;
- `find` or `findcase` whose first argument is a one-character text literal
  and whose second is not a literal: `find(text, find)` searches the first,
  so `find("^", LASTPOP)` is -1 unless `LASTPOP` is `^` or empty. None of
  the 23 `find` calls in the official examples has a literal first;
- an effect action naming, in a literal, an effect the object and its
  families, the layer or every layout lack: it runs and changes nothing;
- in one list of actions, a *Create object*, *Spawn another object* or
  *Recreate initial objects*, or a call to a function or custom action that
  creates instances through its own events or the functions they call,
  followed by a call to a function that picks that type, or a family of
  it, by a condition anywhere in its events or the functions they call
  (*For each*, *Pick all*, a comparison, an overlap): the new instances
  join the others only when the top-level event or trigger ends, so the
  second function misses them
  [`Construct3-RAG/prompts/pitfalls/creating-objects.md`]. A pick that
  starts from *Pick by unique ID*, *Pick last created* or a hierarchy link
  passes, and so does a function that waits or copies the caller's picked
  instances after a direct create; the actions after a wait are not
  followed. Over the 524 official examples it adds no finding.

*Find path*, *Start timer* and a flipped variable ask whether an event runs
every tick. For them, a condition of an addon without a schema counts as a
trigger when its id starts with `on-`.

`edit_sheet.py` refuses the findings on *Find path*, *Start timer*,
*Simulate control*, `Count`, `PickedCount` and a variable flipped every
tick in an event a plan creates, as it refuses the style findings below; in
the user's own events they stay warnings. A gesture action, a *Find path*,
a *Start timer*, a *Simulate control* or a flip in a function passes, since
a trigger or an event that runs every tick may call it.

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
| An object or family name is not `self`, `true`, `false`, a device name Windows reserves (`con`, `nul`, `com1`) or a system expression (`Floor`, `Time`, `Random`, `Max`), compared without case | `Not an object: 'Floor' is not an object name`, for `Floor.X` in an expression; `Invalid use of 'self'`, for `self.X` in a System action; `name is reserved`, for `Com1`, which the editor renames to the reserved `Com2`. Otherwise the project opens with the object renamed, `Floor` to `Floor2`, and its conditions and actions follow it |
| Object types, families, the Functions object and the System object share one namespace, compared without case, and `project.c3proj` lists each object type once | `object class name 'X' already used`, `object type name 'X' already used` |
| Functions are built in: `project.c3proj` names the object in `functionsName`, and no object type has that name, compared without case. A plugin or behavior id that `usedAddons` lists by Scirra is in `Construct3-RAG/data/c3-schemas/_index.json`, which holds every addon by Scirra; an id by another author is a third-party addon, a warning | `Missing addons ... Plugin Functions (Functions) by Scirra (legacy SDK v1)` |
| A global or local variable or a function parameter is not named like a system expression (`mid`, `max`, `round`), compared without case: inside an expression the name reads as the system expression | `Invalid expressions ... parameter 0 does not take 'string'`, for a local `mid` passed to a function; `'round' does not accept 0 parameters`, for a parameter `round` |
| A function without parameters is called without parentheses: `Functions.settling`, not `Functions.settling()` | `Syntax error: ')' can't go here` |
| A call to a function or a custom action writes `parameters` as a list, `"parameters": ["1"]`, or leaves the key out when it passes none | `TypeError: expected array`, for `"parameters": {}` |
| A function with a return type is read in an expression, never called as an action; one whose return type is `none` is called as an action, never read | `function 'X' has wrong return type`; `The function 'X' has a return type of 'None' so cannot be used as an expression` |
| No two variables of one scope share a name, compared without case: the top-level variables of every sheet are one scope, the variables of one list of events another, a function's parameters another. A global declared at the top of two sheets is declared twice | the editor opens the file. It keeps two globals, and every use refers to the first. It renames the second of two locals of one list (`STEP` to `STEP2`) and every parameter of a function but the last, and every use refers to the one that keeps its name. Its variable dialog refuses the second name with `The name X is already used in this scope` |
| A local variable or function parameter is not named like a local or parameter of a scope that holds it, compared without case: a parameter like a variable of its function's group or of a group around it, a local of a function's sub-events like its parameter, a local of a sub-event like a variable of its group or of an event above | the project opens, and the editor renames the one that comes later in the sheet. Both names then refer to the other one where it is in scope, so a parameter after its group's constant reads the constant. If the group's variable comes later, the editor renames that one, and a use of it elsewhere in the group stops the open with `Unknown expression 'SPEED': This is not a system expression or variable name in this scope` |
| A local variable or function parameter is not named like a global of another type, compared without case: the nearest scope wins, so a text `count` hides a number `COUNT` in its event and sub-events. One of the same type under another case is a warning: the project opens, and the global's name refers to the local there | `Type mismatch: - does not work with 'string' and 'number'`, for `COUNT - 1` below a text local `count` |
| No two functions, and no two custom actions of one object, share a name, compared without case | the project opens, and the editor renames the second, `Beep` to `Beep2`; a call by either name runs the first |
| A shared ACE of `plugins/_common.json` is used only on a plugin whose `commonAces` lists it: Text has no `set-default-color`, its colour is `set-font-color` | `missing action id 'set-default-color'` |
| `Self` stands only in a parameter of an object's own condition or action; in a System one (*For each ordered*, *Pick by comparison*, *Set variable*) it names nothing, and the finding writes the expression with the object the ACE names. A variable or parameter named `self` in scope is what a bare `self` reads; `self.X` is still Self | `Invalid use of 'self'` |
| A name has no spaces or punctuation; an instance variable name starts with a letter | the editor renames it silently, and the events that use it fail with `cannot find object` |
| An instance variable, behavior or effect is not named like another one on the object or its families, compared without case, nor like an expression of the object (`Angle`, `Width`, `Count`, `Text`) | `name 'HP' already in object class 'Enemy' namespace`, for instance variables `hp` and `HP` |
| An expression uses Construct's operators: `=` compares, `<>` is not equal, `&` is and, `\|` is or, `^` is power; `==`, `!=`, `&&`, `\|\|`, `**` and `!` stand only inside a text literal | `Syntax error: '=' can't go here`, `Syntax error: '*' can't go here`, `Syntax error: Unknown character` |
| An expression call passes the parameters its schema lists, counted at the top level of the call: `LocalStorage.ItemValue` takes none, `clamp` three. An expression the schema marks `isVariadicParameters` takes more after them: `Mouse.X("HUD")`, `Array.At(x, y)`, `random(1, 5)`, `max(a, b, c)` | `Incorrect parameters: 'LocalStorage.ItemValue' does not accept 1 parameters` |
| An expression parameter is never empty, the template name of *Create object* among them; empty text is the literal `""`, written `"\"\""` in the JSON | `Empty expression: You must enter an expression` |
| Every text literal is closed, a quote inside it doubled; a backslash stands only inside a literal, where it is a plain character | `Syntax error: String missing finishing "`, `Syntax error: Unknown character` |
| A comment event carries `text`, a group `description`, an event variable `comment`, each as text, `""` when empty | `Cannot read properties of undefined (reading 'endsWith')`, `expected string` |
| A function's `functionReturnType` is `none`, `number`, `string` or `any`; a custom action's `aceType` is `action` | `function has wrong return type`, `invalid ACE type` |
| Every timeline and flowchart `project.c3proj` lists has its file, `timelines/<name>.json` and `flowcharts/<name>.json`: a list copied from a new project keeps `Timeline 1` and `Flowchart 1` | `missing file path 'timelines\Timeline 1.json'` |
| Every file `rootFileFolders` lists is on disk: `general` in `files/`, `icon` in `icons/`, `sound` in `sounds/`, `music` in `music/`, `video` in `videos/`, `font` in `fonts/`, `script` in `scripts/` | `missing file path 'icons\icon-16.png'`, `missing file path 'videos\clip.webm'` |
| A sound parameter (*Play*, *Play at object*) names a sound or music file the project lists, without its extension, in any case: `SFX1` for `sfx1.webm` | `missing file '0'`, `missing file 'sfx1.webm'` |
| A key is a key code, a JSON number | `expected finite number` |
| An action does not write a constant. The editor finds a variable by its name without case, of two globals the first and in a local's scope the local: with a constant `PHASE` declared above a variable `phase`, *Add 1 to phase* writes `PHASE`, and the finding says to rename `phase` | `event variable phase is constant` |
| An ease is a built-in id such as `easeoutback`, unless the project has custom eases | the tween keeps no ease and fails later |
| An event variable's or a function parameter's `initialValue` is text, a boolean's `"true"` or `"false"` in lowercase; a parameter may also carry a JSON number | a boolean is read by comparing the text to `"true"`, so `false`, `true`, `"True"` and `"1"` all read as false; another JSON type in a parameter stops the load with `invalid type of initialValue` |
| An instance variable's `type` is `number`, `string` or `boolean`; the editor's Text type is `string` | not measured |
| A layout instance writes an instance variable as a JSON value of its type: `1`, `"a"`, `true` | a text `"1"` on a number reads through `parseFloat`, a boolean on a number reads as 0 |
| `project.c3proj` keeps the properties the editor writes: `description`, `version`, `author`, `authorEmail`, `authorWebsite`, `appId`, `fullscreenMode`, `fullscreenQuality`, `orientations`, `sampling`, `downscaling`, `loaderStyle`, and a viewport of at least 2 | `TypeError: expected string`, before the editor names a file |
| `savedWithRelease` is the release that saved the project; below r309 the editor reads an object type from `objectTypes/<name in lower case>.json` | no message: the object type file is not found |
| `project.c3proj` keeps the lists of what the project holds: `objectTypes`, `families`, `layouts` and `eventSheets` with an `items` and a `subfolders` array each, and `containers` as an array, empty when the project has none | `TypeError: expected object`, `TypeError: expected array` |
| A `Sprite` or a `Shape3D` object type carries an `animations` folder | `TypeError: expected object` |
| A frame's `collisionPoly` holds three or more x, y pairs; a frame without the key takes the whole image | the project opens, and the preview stops on the crash report `assertion failure: must have at least three points in a collision poly`, or `must have an even number of elements in collision poly points array` |
| An object type's or family's `instanceVariables`, `behaviorTypes` and `effectTypes` are each an array, `[]` when empty, never a folder `{"items": [], "subfolders": []}` | `TypeError: ... is not iterable` |
| A `TiledBg`, `Spritefont2`, `Particles`, `Tilemap` or `NinePatch` object type carries one `image` block, not `animations`: `width` and `height` of `images/<name in lower case>.png`, `originX`, `originY`, `originalSource`, `exportFormat`, `exportQuality`, `imageSpriteId`, `useCollisionPoly` | `TypeError: expected object` |
| Every `image` block and every animation frame has an `imageSpriteId` that no other image or frame in the project uses. An object type copied from another one's JSON keeps the original's ids, so give the copy new ones | `id already in use` |
| A layout has a `name`, a `width` and a `height` of at least 2, and a `layers` array | `TypeError: expected string`, `expected finite number`, `invalid layout width` |
| A layer has a `name`, `parallaxX`, `parallaxY`, `scaleRate`, a `blendMode` the editor knows, and an `instances` array, empty when nothing is on it | `TypeError: expected finite number`, `invalid blend mode` |
| An instance on a layer carries `world` with `x`, `y`, `width`, `height`, `originX` and `originY` | `TypeError: expected finite number` |
| Each behavior in an instance's `behaviors` block is `{"properties": {...}}`: `"Tween": {"properties": {"enabled": true}}`, never `"Tween": {}`. An instance needs no `effects` block for its type's effects | `TypeError: Cannot convert undefined or null to object` |
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

Ten warnings the editor never raises, for a project the agent wrote: the
generator template passes `--style`. `edit_sheet.py` holds the events a plan
creates to them, never the sheet's older events: the first four, whose fix
is one comment or one deleted condition, refuse the plan like a problem; the
other six, and any
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
| chooseindex(c, a, b) is a two-way choice on a condition (the first argument a comparison, `&`, `\|` or a boolean variable, two choices after it); the finding writes `c ? b : a` | any | none: no example calls chooseindex, and 77 sheets use `?:`. A generated card game got 36, and reversed the branches twice while fixing bugs |
| with events ..., picks a branch by testing X for the codes ... with find (sibling events or Else branches whose conditions call `find(X, "<literal>")` or `findcase` on the same X); `find` matches any part and ignores case, so the finding names a code that matches another | 2 or more events | none; the one example that tests outputs with find, quest-flowcharts, does it inside one event or in separate functions. A generated card game dispatched its enemy moves and card effects this way, 3 times |
| mid("<letters>", ...find("<letters>", X)..., ...) looks X up through the letters, a table written as text; the finding writes the cycle as `(X + 1) % N` | any | none: no example calls find with a literal first. A generated card game wrote its element cycle so, 3 times |

Why these thresholds: `Construct3-RAG/docs/decisions/event-sheet-design-guidance.md`.
A style warning is never an error: the editor accepts all ten, and an
official example may carry one. What the shape should be instead is
`Construct3-RAG/prompts/event-sheet-style.md`, and for the last three the
Native first table of `Construct3-RAG/prompts/event-sheet-thinking.md`.

## What it does not see

What happens at runtime: which instances a condition picks, what order
triggers fire in, whether an expression means what the comment says. The
editor and the preview judge those; the observations in
`Construct3-RAG/prompts/event-sheet-pitfalls.md` and in
`editor-and-preview.md` beside this file came from previewing, not from the
checker. Expression syntax beyond those operators, argument types, and
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
