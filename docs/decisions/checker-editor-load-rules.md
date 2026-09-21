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
  <path-to>/Construct3-RAG`; the DeepSeek projects write `<path-to>: D:/...`.
  The checker skipped any value containing `<`. Two of two real projects
  write the path this way.
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
   A guest session is capped at 25 events and a free account at 50, `#open=`
   does not take an arbitrary URL, and a folder project opens through a native
   dialog (`prompts/references/hand-editing-project-files.md`). It cannot be
   the default path.

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
