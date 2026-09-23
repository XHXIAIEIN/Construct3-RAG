# The Checker Applies the Editor's Own Load Rules

Date: 2026-09-21
Schema: Construct 3 r495.2, the stable release `https://editor.construct.net/`
served on that date; the editor bundle was read from there

## Problem

`prompts/project-tools/check-project.py` is what stands between a generated
project and the editor. It checked that every ACE, parameter and name exists.
A project that passed could still be refused when the editor opened it, and
the agent then learned the rule from an error message the user pasted back,
one rule per round. With a strong model that costs a round or two. With a
small one it is where the session stalls: the message names no event, and the
model changes something else.

Task: a small model generates a whole project, runs the checker until it
prints `ok`, and the project opens and previews the first time. The default
path of the project tools calls the checker on every run.

## Evidence

Three generated projects in `folder project folder/` (2026-09-17 to 09-21):

- *new project - Doubao*: `python tools/check-project.py` stopped with
  `Construct3-RAG not found`. The project's `AGENTS.md` defines the folder
  once, `path-to = D:\...\GitHub\`, and keeps `Construct3-RAG:
  <path-to>/Construct3-RAG`; the two DeepSeek projects write `<path-to>:
  D:/...`. The checker skipped any value containing `<`, so in all three
  projects it could not find the schemas on its own.
- *Water Sort Puzzle - DeepSeek V41 Flash*: its README records the rules it
  met by bisection (`tools/probe.py` writes five `.c3p` files to open in
  turn), among them `cannot add another trigger to event branch`. Its final
  sheet still has `Tube: On tweens finished` inside the functions `StartPour`
  and `FinishPour`, and `"ease": "out-back"`. The checker reported neither;
  it skipped `ease` and `keyb` parameters outright.
- The same project holds 16 combo values written as string expressions
  (`"mouse-button": "\"left\""`). The checker listed the valid items and did
  not say what was wrong with the value.

The committed schemas disagreed with their own documentation.
`docs/guide/data-format.md` gave *On collision* as the example of
`isTrigger`; `plugins/_common.json` had no such flag on
`on-collision-with-another-object`, nor `behaviors/timer.json` on `on-timer`,
nor the six Gamepad button conditions. The CDN marks those `isFakeTrigger`,
and the exporter copied `isTrigger` only.

The rules themselves were read from the editor's project model,
`projectResources.js`, by the messages it throws:

| Editor message | Rule |
|----------------|------|
| `cannot add another trigger to event branch` | One trigger per event, and per branch from the top-level event to a leaf. `isTrigger`, `isFakeTrigger` and `isFastTrigger` all count. A function block and a custom action block count as holding one. An OR block may list several. |
| `condition not invertible` | No `isInverted` on a trigger, a loop (`isLooping`) or a condition with `isInvertible: false`. |
| `function blocks cannot be OR blocks` | As it says. |
| `expected finite number` | A `keyb` parameter is a key code, a JSON number. |
| `event variable X is constant` | An action cannot name a constant in an `eventvar` parameter. |
| `missing plugin id 'x'` | Addon ids are looked up exactly: `Arr`, `Json`, `TiledBg`, `EightDir`, `Sin`, `solid`. |
| `name is reserved`, `invalid name`, `name 'x' already in object class 'y' namespace` | An object name is not `self`, `true`, `false`, `system`, a DOS device name or a system expression. Names pass a filter that drops spaces and punctuation and the result is what the editor keeps. Instance variables, behaviors, effects and the plugin's expressions share one namespace per object, families included, compared without case. |
| `unexpected object type name` | The `name` inside the file is the name listed in `project.c3proj`. |
| `Invalid use of 'self'` (added 2026-09-22) | `Self` in an expression is resolved to the object of the condition or action that holds the parameter; when that object's plugin is `system` the editor throws `.invalid-self`. Seen in the Doubao snake project: `Self.IID` as the order of *For each ordered*, which opened with `Game, event 45, condition 1: Invalid use of 'self'`. The finding rewrites the expression with the object a parameter of the same ACE names, `SnakeBody.IID`. Over the 525 projects of the sweep no other run changed. |
| no message: a boolean `initialValue` that is not the text `"true"` reads as false (added 2026-09-22) | The variable loader copies `initialValue` as it is and the getter is `"true" === value`, in the editor and in the export step; a function parameter's loader takes a string or a number and throws `invalid type of initialValue` for anything else. The user reported a Doubao project whose boolean global the editor would not take; its file now holds `"false"`. The checker requires text for every variable and parameter, `"true"` or `"false"` for a boolean, a finite number for a number. In the official examples the 303 boolean variables and 74 boolean parameters are all `"true"` or `"false"`. |
| no message: a layout instance variable of the wrong JSON type, an instance angle in degrees (added 2026-09-22) | The instance loader reads a number through `parseFloat` and a boolean through `"true" === text` or `Boolean(value)`, so a wrong type is taken silently; `world.angle` is radians, and the 6053 non-zero angles of the examples all stay within 2π. The checker requires the JSON type of the declared variable type and an angle within a full turn. |
| not measured: an instance variable `type` outside `number`, `string`, `boolean` (added 2026-09-22) | A Doubao run wrote `"type": "text"` for a text variable, the editor's name for the type in its UI, and the checker stopped with `missing key 'text'` from its own type table, a sentence about the wrong thing that cost the run a read of the checker's source. The checker now names the variable and the three types, as it does for event variables, and the value check skips a type it does not know. What the editor does with such a file is not measured; the 1225 instance variables of the official examples are all one of the three, and the sweep adds no finding. |
| `TypeError: expected string` (added 2026-09-23) | Opening a project reads the whole `properties` block before it reads a file of the project, and asserts each value as it reads it: `description`, `version`, `author`, `authorEmail`, `authorWebsite` and `appId` are text, `fullscreenMode`, `fullscreenQuality`, `orientations`, `sampling`, `downscaling` and `loaderStyle` are one of the editor's values, and the viewport is a number of at least 2. The user opened a project generated for the skill evals and got the message with no file and no key in it; `projectResources.js` reads it in `d$`, the first call being `this.j(s.description)`. A `project.c3proj` written by hand, or reduced to the keys the tools read, has none of them. The generator fills them when the folder was not saved by the editor. |
| `TypeError: expected array`, `TypeError: expected object` (added 2026-09-23) | `QAn` reads the lists project.c3proj keeps before it has read a file: `containers` is an array (`tPn`, `hN`), and `objectTypes`, `families`, `layouts` and `eventSheets` are objects whose `items` and `subfolders` it walks. A missing list is not an empty one: 71 of the 140 eval artifacts had no `containers`, and the user hit it on the second open, after the properties were filled in. The rule was written from the call list of `QAn` rather than from the message, so that the rest of the sequence is covered at once: `rootFileFolders`, `models3d`, `timelines` and `flowcharts` return early when they are missing, and `name`, `uniqueId`, `firstLayout` and `functionsName` are read without an assertion. |
| `TypeError: expected object` on an object type (added 2026-09-23) | The animations folder of an animated plugin is read as the type opens (`KR`, `_tt`). Which plugins are animated is the editor's flag and not in the schemas; in the examples only `Sprite` and `Shape3D` carry the folder, and all 2930 Sprite and 785 Shape3D types have one. |
| `TypeError: expected finite number`, `invalid blend mode`, `invalid layout width` (added 2026-09-23) | The rest of the open, read the same way: `fon` calls the layout's `BO` and `d$` (`name`, `width`, `height` through `jM`/`_M`, at least 2) and `AU(a.layers)`; each layer's `Son` reads `name`, `parallaxX`, `parallaxY`, `scaleRate` through `ye`, `blendMode` against the editor's map, and walks `instances`; a world instance's `BO` reads `world.x`, `y`, `width`, `height`, `originX`, `originY` through `ye`; an event sheet's `BO` reads `name` and walks `events`. A key that is read behind `hasOwnProperty` (`sampling`, `vpX`, `zElevation`, `subLayers`, `angle`, `effectTypes`, `nonworld-instances`) is not required. A layout or sheet name with spaces or punctuation is filtered rather than refused, so it stays out of the checker. The keys were also counted over the examples: all 2615 layers, 32519 instances, 898 layouts and 549 sheets carry every one. |
| `invalid event type`, `invalid script data` (added 2026-09-23) | The last loader of the chain: `Lst` reads every event through `_tt` and its `eventType` through `bp` before it picks the class, and a block's `BO` loops over `conditions` and `actions` without looking first, as do the function block and the custom action block that extend it. `children` is null-or-array (`g6`), so a group without children opens and the checker no longer stops on it. Over the corpus: 30 261 events, all 13 726 blocks and the 1228 blocks of the other two kinds carry both lists. |
| no message: an object type file that is not found (added 2026-09-23) | `savedWithRelease` decides where an object type is read from: below r309 it is `objectTypes/<name in lower case>.json`, and a project without the key is read as r86. 249 of the 524 examples are older than r309 and all of them hold the lower-case files. |
| `An Else condition cannot be placed here` (language pack, shown before preview and export) | Else is the first condition of a block that is not an OR block and has no trigger; the sibling before it, comments skipped, is a block without a trigger or a loop and is not a lone Else. |

The manual states the first two: `project-primitives/events/how-events-work.md`
"Triggers", `sub-events.md` "Triggers in sub-events", `conditions.md`
"Inverting conditions"; the Addon SDK guide `defining-aces.md` defines
`isFakeTrigger`, `isLooping`, `isInvertible` and `isCompatibleWithTriggers`.

Each rule was run over the 524 official example projects before it was
written into the checker. None of them breaks a rule: 493 passed before and
493 pass now, and no project gained a finding. *Trigger once* and *Every X
seconds* inside a triggered branch do occur (abductractor, demonoire,
template-ladder-climbing; tank-movement has one inside a function), so that
is a warning, and not raised inside a function.

The rules of 2026-09-23 came one editor message at a time until the third
open; from then on they were read from the loader's whole call chain, and the
keys every one of the 524 examples carries were counted at each level (project,
properties, layout, layer, instance, world, sheet, object type). The generated
project was compared with that count, which is now
`test_generated_project_carries_what_the_editor_writes_into_every_project`. It
leaves out `rootFileFolders` and `timelines`, the two keys the examples all have
and the loader returns without.

The rules of 2026-09-23 were measured the same way: over the 524 examples
and the two game projects, 2041 runs of the four scripts, no check run changed
its exit code or its output (`evals/sweep_outputs.py`). The check for the
lower-case object type file reads the names the folder holds rather than
asking the file system for one: on Windows `Coin.json` answers for `coin.json`
and the rule would never fire.

## Options

1. Leave the checker at schema membership and let the editor report the rest.
   Nothing to maintain. Every rule above costs a round trip through the user,
   and the message carries no event number.
2. Encode the editor's rules in the checker, each one read from the bundle
   and proven against the official examples, with a message that names the
   event and says what to write instead. The rules are few and have been
   stable across releases; the bundle is minified, so they are located by
   their message strings.
3. Drive the real editor and read its error. It is the only complete oracle.
   On editor.construct.net, observed r495.2 on 2026-09-15, a session without
   a licence is capped at a few dozen events and cannot preview a project
   that uses families, `#open=` takes an example id and not an arbitrary URL,
   and a folder project opens through a native dialog. It cannot be the
   default path. These are limits on the oracle, not on what a project may
   contain, and they are kept out of the prompts the agent reads: a model
   told an editor caps events trims the sheet it was asked to write.

## Decision

Option 2.

- The exporter writes `isTrigger` for every condition the editor treats as a
  trigger, and keeps `isFakeTrigger`, `isLooping`, `isInvertible: false` and
  `isCompatibleWithTriggers: false`. `data/` was regenerated from the cached
  r495.2 payloads; the diff is those flags on 35 conditions per locale, 8 of
  them newly marked as triggers.
- The checker applies the rules in the table. They are errors; the
  trigger-incompatible condition is a warning.
- `ease` is checked against the built-in ids in the language pack, unless the
  project declares custom eases.
- A finding says what to write: the nearest id, the behavior that owns an ACE
  written without `behaviorType`, the editor's id for a display name
  (`Array` is `Arr`), the object behind a plugin name in an expression
  (`JSON.` is `Levels.`), a quoted combo or a bare text value.
- The `Construct3-RAG:` line may use `<path-to>` with a `path-to = <folder>`
  line above it, and the checker run from the clone finds the clone.
- A missing key stops the run with one sentence instead of a traceback.
- `tests/test_project_tools.py` generates the stand-in project, breaks it one
  rule at a time and reads the finding.

Two read-only modes went in with it, because the same projects showed what
the agent reads, not only what it writes, going wrong:

- `--ace OBJECT [WORD ...]` prints the ACEs of an object, a plugin or a
  behavior that match, with each parameter's encoding and the JSON to write.
  `plugins/system.json` is 4801 lines and `plugins/_common.json` 2081; a file
  tool that returns 2000 lines at a time shows an agent the conditions and
  part of the actions of System and none of its expressions, and the SOP
  says an ACE that is not in the schema does not exist. The encoding mistakes
  in the Flash project (combos quoted, comparisons as strings, Tween flags as
  booleans) are what the printed JSON and the per-type legend settle. Reading
  the JSON directly stays the SOP; this is the route for the long files. The
  lookup service answers the same question over HTTP and needs a server.
- `--print [SHEET]` prints a sheet as the editor words it, under the editor's
  event numbers, from the schema's `display-text`. Over the 524 examples it
  is 4.9 MB against 17.8 MB of event sheet JSON, and the design guide sends
  the agent to those sheets for the shape of an interaction. It ran on all
  524 without an error.

Not done, because nothing here shows it is needed: parsing expressions for
syntax, argument counts and types; checking `function`, `template` and
`audiofile` parameters.

## Re-evaluate when

- An official example fails one of these rules after a data sync: the rule
  changed in that release. Find the message in `projectResources.js` again.
- The editor gains a way to open a project without a dialog and an account:
  option 3 then replaces guesswork for everything the checker cannot see.
- A generated project passes the checker and the editor still refuses it:
  the message it gives is the next row of the table.

## Update 2026-09-21: the tools are a skill

`check-project.py` is `skills/construct3-project/scripts/check_project.py`,
`--print` and `--outline` are `print_sheet.py`, `--ace` is `lookup_ace.py`,
and a game project gets them through `install.py` instead of a copy in
`tools/`. The rules, the messages and the output are the same
(`project-tools-skill.md`).

## Update 2026-09-22: the evidence behind the hand-editing reference

`prompts/references/hand-editing-project-files.md` states each file encoding
as a rule and nothing else. A model writing a sheet has no use for the count
behind a rule, and a release number in a rule reads as a version to target.
What each rule was read from is here.

Sources: editor-written files (the mergeGame project, `savedWithRelease:
50000`, 2026-09-14; a new project saved by r502, 2026-09-17), the official
example projects, the editor bundle `projectResources.js` of r495.2, and
`data/c3-lang/en-US.json`.

| Rule | Evidence |
|------|----------|
| Comparison parameters are the integers 0 to 5 | The order of `ui/dialogs/parameters/controls/comparison` in the language pack |
| A key is a JSON number | Parameter loader, `expected finite number`; the 1238 Keyboard `key` parameters in the examples are all numbers |
| A quoted combo keeps the default; a `"false"` string in a boolean parameter reads as true | Parameter loaders, r495.2, 2026-09-21 |
| Addon ids are the editor's spelling | The addon table is a map keyed by id, `missing plugin id` otherwise |
| Event variable `initialValue` is text; a boolean is `"true"` or `"false"` | The row of 2026-09-22 in the table above; the getter runs in the editor and again on export |
| Instance variables are JSON values by type | Examples: 12 450 numbers, 6970 booleans, 1934 strings, no other form |
| `world.angle` is radians | The row of 2026-09-22 in the table above |
| Custom action block and call form | 152 blocks and 333 calls across the examples, 2026-09-17. In every example the row object owns a block of the name itself; `customActionObjectClass` appears in custom-action-overrides only, where a member with its own override calls the family block. The call through a member without an override is inferred from that and loaded in mergeGame, r502 |
| `projectfile` is a bare name at the root, `{"path": ...}` in a subfolder | Examples write the bare name; the editor writes the object form for a subfolder; a hand-written bare `"enemy.json"` loaded and was rewritten to the object form on save, mergeGame r502, 2026-09-17 |
| Family file keys; a container is a row of `project.c3proj` without `selectMode` | 153 family files in 82 examples, 159 container rows in 85, every member an object type; `"selectMode": "normal"` in the 110 rows saved r184 to r263 and in none of the 49 saved r342 to r470 |
| A family instance variable written through a member type | Loaded and applied at runtime, mergeGame r502, 2026-09-17 |
| Parameters an ACE gained later may be omitted | Every example using `pick-nearestfurthest`, saved r184 to r437, writes `which`, `x`, `y`; the r495.2 schema also lists `z` and `pick-all-tied` |
| `json.dumps(obj, indent="\t", ensure_ascii=False)` reproduces the editor's bytes | Roundtrip on mergeGame |
| A family's behavior used through a member type | drag-on, r466: `DragonHead` with `"behaviorType": "Physics"`, declared on family `Parts` only |
| Instances write `z` with `depth`, layers `zElevation` | pixel-data-reader, r472, writes `z` and `depth`; drag-on, r466, writes `zElevation`. An empty layout saved by r502 has `sampling` and `ambientLight` and no `scene-graphs-folder-root` |

## Update 2026-09-23: the eval opens projects in the editor

`skills/construct3-project/evals/open_in_editor.py` does option 3 for the
evals, without the user. It starts its own Chromium through Playwright,
opens `https://editor.construct.net/` in a fresh profile, and drops the
project on it as a `.c3p`, the way a user drops a file from the desktop.
The editor then either shows the project's name in the window title or
says in a dialog why it did not open, and logs the exception with the
loader's stack.

Checked on a project the editor itself saved, which opens; on a generated
project that passes the checker, which opens; and on the same kind of project
with an empty `properties` block, which fails with `TypeError: expected
string`, the message the user reported.

The checker stays the judge inside a game project: the default path is
offline, and the editor needs a network connection, a browser and a
Playwright install. What changes is the eval. "Passes the checker" and
"opens in the editor" can now be compared over every run, and a project the
checker passes and the editor refuses gives the next row of the table
without a round trip through the user.

## Update 2026-09-23: two rules from the LiquidVolume project

The r495.2 editor refused the LiquidVolume project twice where the checker
had passed it. Both are errors now, after the two steps of
`skills/construct3-project/references/checker-rules.md`.

- A local number `mid` passed as `Functions.areaBelow(mid)` was read as the
  system expression `mid()`: `Invalid expressions ... parameter 0 does not
  take 'string'`. None of the 2697 event variables of the 524 official
  examples has the name of a system expression of `plugins/system.json`,
  compared without case, so the checker refuses every such name, not only
  the one whose arguments break. A name that loads, `time` for instance,
  still reads the system value instead of the variable.
- Set color on a Text: `missing action id 'set-default-color'`. Which shared
  ACE a plugin gets is read from the editor bundle and exported as each
  plugin file's `commonAces`
  (`docs/decisions/common-aces-from-editor-bundle.md`); over the examples,
  none of 7811 uses of a shared condition or action falls outside it.

## Update 2026-09-24: the agent opens the project before handing it over

The editor checks what the checker does not: the types of an expression.
A local text variable that differed from a global number constant only by
case hid it, `LAYERS - 1` was read on the text, and the editor refused the
project with `Type mismatch: - does not work with 'string' and 'number'`,
naming the sheet, event and condition, after the checker had passed it.
Each such case cost a round trip through the user.

The opener moved from `evals/` to `scripts/`, so it ships with the skill,
and the check loop of `SKILL.md` gained a step: after `ok:`, run
`scripts/open_in_editor.py`; `opened` is the hand-over, `failed` prints the
editor's dialog and the exception it logged. `generating-a-project.md` and
`hand-editing-project-files.md` carry the same step.

- Reproduced on a copy of `data/c3-new-project` with the case above: the
  checker ends with `ok:`, the opener prints the editor's dialog with
  `Event sheet 1, event 2, condition 1`, the number `print_sheet.py` gives
  the same event. The unchanged template prints `opened`. Both in about
  13 seconds, r495.2 and, with `--release r502`, the r502 beta.
- Without a PATH it opens the project the current directory is in, as the
  other scripts find theirs. It starts Playwright's Chromium, else Edge,
  else Chrome, so a Windows machine needs `pip install playwright` and no
  browser download. A dialog with a **Not now** button (a newer beta on
  offer) is declined and not read as a failure.
- The checker stays offline and first: it names every finding at once, the
  editor one dialog at a time. The opener needs a network connection and
  Playwright; when either is missing it exits 2 and says to ask the user to
  open the project and paste the dialog's text, which is the step it
  replaces.
