# Hand-editing Construct project files

Read this when writing or changing `eventSheets/*.json`, `layouts/*.json`,
`objectTypes/**/*.json`, `families/*.json`, `project.c3proj` or clipboard
payloads without the editor. Clipboard payloads use the same condition and
action entries; the envelope is documented in
`Construct3-Clipboard/docs/clipboard-format.md`.

## Encodings

Observed in editor-written files (mergeGame, `savedWithRelease: 50000`,
2026-09-14) and in official example projects.

- Comparison parameters are integers: 0 `=`, 1 `≠`, 2 `<`, 3 `≤`, 4 `>`, 5 `≥`.
  Order: `data/c3-lang/en-US.json`, `ui/dialogs/parameters/controls/comparison`.
- String parameters carry their quotes: `"tag": "\"attack\""`. `layer` is an
  index string `"2"` or a quoted name `"\"Graphics\""`. `create-hierarchy` is a
  JSON boolean. Inverted conditions carry `"isInverted": true`.
- Everything that is not an expression is written bare: a combo item
  (`"mouse-button": "left"`, `"loop": "no"`), an object, a layout, a
  variable, an ease id (`"ease": "easeoutback"`, the ids under
  `ui/bars/timeline/eases` in `data/c3-lang/en-US.json`). A quoted combo
  value is not an error to the editor: it silently keeps the default. A key
  is its key code as a JSON number (`"key": 32`); a string stops the load
  with `expected finite number`. A JSON string `"false"` in a boolean
  parameter reads as true. [editor bundle `projectResources.js`, parameter
  loaders, r495.2, 2026-09-21; the 1238 Keyboard `key` parameters in the
  official examples are all numbers]
- `plugin-id`, `behaviorId` and the `id` of a `usedAddons` entry are the
  editor's spelling, exactly: `originalId` in `data/c3-schemas/_index.json`.
  `Arr` is Array, `Json` JSON, `TiledBg` Tiled Background, `EightDir`
  8 Direction, `Sin` Sine; `solid`, `scrollto`, `jumpthru`, `bound`, `wrap`,
  `destroy` and `gamepad` are lowercase. [same source: the addon table is a
  map keyed by id, `missing plugin id` otherwise]
- Function call: `{"callFunction": "name", "sid": N, "parameters": ["expr", ...]}`.
  Function block: `functionCopyPicked` (boolean) and `functionParameters`
  entries with `name`, `type`, `initialValue`, `comment`, `sid`.
- Custom action block: `"eventType": "custom-ace-block"`, `"aceType": "action"`,
  `"aceName"`, `"objectClass"` (the owning type or family), then the same
  `function*` keys as a function block; `functionCopyPicked` is *Copy all
  picked*. Call: `{"customAction": "name", "objectClass": "<row object>", "sid": N}`,
  with `"parameters": ["expr", ...]` exactly when the block declares
  parameters, plus `"customActionObjectClass": "<family>"` when the row object
  is a member type and the block belongs to the family. In every official
  example the row object owns a block of that name itself; the family key
  appears only where a member with its own override calls the family block.
  [152 blocks and 333 calls across the example projects, 2026-09-17; family
  key: custom-action-overrides; the member-without-override call form is
  inferred from it and loads in the editor, mergeGame r502, 2026-09-17]
- A `projectfile` parameter is the bare file name for a file at the root
  (`"file": "DefaultProfile.json"`, official examples); the editor writes a
  file inside a subfolder as `"file": {"path": "data/enemy.json"}`. The
  hand-written bare name `"enemy.json"` loaded and was rewritten to the
  object form on save. [observed: mergeGame r502, 2026-09-17]
- A family instance variable can be written through a member type
  (`"objectClass": "enemyBase"`, `"instance-variable": "hp"` with `hp`
  declared on family `EnemyGroup`); the editor loads it and the runtime
  applies it. [observed: mergeGame r502, 2026-09-17]
- Parameters an ACE gained in a later release may be omitted; the editor fills
  defaults on load. Every official example that uses `pick-nearestfurthest`
  (saved r184 to r437) writes only `which`, `x`, `y`; the r495.2 schema also
  lists `z` and `pick-all-tied`.
- `sid`: 15-digit integer, unique across the whole project. `uid`: unique
  across all layouts. Files: UTF-8 with raw non-ASCII, tab indent, LF, no
  trailing newline. Python `json.dumps(obj, indent="\t", ensure_ascii=False)`
  reproduces the editor's output byte for byte (roundtrip checked on mergeGame).
- A behavior declared on a family is used through a member type with the
  family's behavior name: `"objectClass": "DragonHead", "behaviorType":
  "Physics"` where only family `Parts` declares Physics. The member's layout
  instances carry the family behavior's properties block as if it were their
  own. [example: drag-on, r466]
- Instance `world` entries write Z elevation as `"z"` with a `"depth"` key
  from r472 (`"zElevation"` in r466); layers keep `zElevation`. An empty
  layout saved by r502 has `sampling` and `ambientLight` and no
  `scene-graphs-folder-root`. [examples: pixel-data-reader r472, drag-on r466;
  observed: new project r502, 2026-09-17]

## Naming an event to the user

The JSON has no event numbers; the editor does. Its margin and its Find
results (`Event 15 action 2`) count blocks, groups and function blocks per
sheet in document order, sub-events included; variables, comments and
includes take no number and are filed under the next numbered event.
Quote those numbers, never JSON line numbers, and read a screenshot or a
pasted Find result back the same way. To find the JSON behind a number, run
`python <Construct3-RAG>/prompts/project-tools/check-project.py --outline
<sheet>` in the project folder: each row prints with its number and its
`sid`, which is the string to search the sheet file for. `--print <sheet>`
prints the same rows with their conditions and actions as the editor words
them; read the sheet that way before and after an edit.

## Checks before handing over

Without the editor: JSON parses; every `objectClass`, instance variable and
behavior name exists, families included; `sid` and `uid` are unique; every ACE
`id` and parameter key is present in `data/c3-schemas/` (shared world ACEs in
`plugins/_common.json`); every called function is defined with the right
parameter count; every object created at runtime has a template instance in
some layout; and the rules the editor applies on opening: one trigger per
branch and none inside a function or custom action, nothing inverted that
cannot be, *Else* only after a plain event, names the editor keeps and does
not reserve (the table in `prompts/project-tools/README.md`).
`prompts/project-tools/check-project.py` runs these checks on a project
folder; copy it into the project's `tools/` and run it from there, or run it
in place with the project folder as the argument.

On editor.construct.net (observed r495.2, 2026-09-15): a guest session is
capped at 25 events and a verified free account at 50; families are a paid
feature, so a project using them cannot be previewed without a licensed
account. `#open=<example-id>` opens official examples; opening a project from
an arbitrary URL through `#open=` did not work in that test. Ask the user to
open and preview instead, and tell them what to look at.
