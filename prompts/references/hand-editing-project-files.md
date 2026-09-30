# Hand-editing Construct project files

Read this when writing or changing `eventSheets/*.json`, `layouts/*.json`,
`objectTypes/**/*.json`, `families/*.json`, `project.c3proj` or clipboard
payloads without the editor. Events go into a sheet through the
`construct3-project` skill's `scripts/edit_sheet.py`, which takes them as a
plan, gives them their sids and checks the result before it writes; what
follows is how each entry of such a plan, or of a hand edit, is written.
Clipboard payloads use the same condition and action entries; the envelope
is documented in `Construct3-Clipboard/docs/clipboard-format.md`.

## Encodings

Each rule was read from the editor's loaders, from files it saved or from
the official examples (`docs/decisions/checker-editor-load-rules.md`).

- Comparison parameters are integers: 0 `=`, 1 `≠`, 2 `<`, 3 `≤`, 4 `>`, 5 `≥`.
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
  parameter reads as true.
- `plugin-id`, `behaviorId` and the `id` of a `usedAddons` entry are the
  editor's spelling, exactly: `originalId` in `data/c3-schemas/_index.json`.
  `Arr` is Array, `Json` JSON, `TiledBg` Tiled Background, `EightDir`
  8 Direction, `Sin` Sine; `solid`, `scrollto`, `jumpthru`, `bound`, `wrap`,
  `destroy` and `gamepad` are lowercase. Any other spelling stops the load
  with `missing plugin id`.
- An event variable's `initialValue` is text whatever its `type`: `"0"`,
  `"hello"` without inner quotes, and for a boolean `"true"` or `"false"`,
  lowercase. The editor reads a boolean by comparing the text to `"true"`:
  a JSON `false` or `true`, a `"True"` and a `"1"` all read as false. A
  number text that does not parse reads as 0. A function parameter's
  `initialValue` may also be a JSON number; anything else stops the load
  with `invalid type of initialValue`.
- A layout instance's `instanceVariables` map holds JSON values by type:
  `{"hp": 3, "dead": false, "label": "a"}`, no text around a number or a
  boolean.
- An instance's `world.angle` is in radians: 270 degrees is `4.7124`.
  `math.radians` in a generator; `Angle` in events stays in degrees.
- Function call: `{"callFunction": "name", "sid": N, "parameters": ["expr", ...]}`.
  Function block: `functionCopyPicked` (boolean) and `functionParameters`
  entries with `name`, `type`, `initialValue`, `comment`, `sid`.
- Custom action block: `"eventType": "custom-ace-block"`, `"aceType": "action"`,
  `"aceName"`, `"objectClass"` (the owning type or family), then the same
  `function*` keys as a function block; `functionCopyPicked` is *Copy all
  picked*. Call: `{"customAction": "name", "objectClass": "<row object>", "sid": N}`,
  with `"parameters": ["expr", ...]` exactly when the block declares
  parameters. Add `"customActionObjectClass": "<family>"` when the row
  object is a member type and the block belongs to the family; it is only
  needed where the member overrides the block and calls the family's.
- A `projectfile` parameter is the bare file name for a file at the root
  (`"file": "DefaultProfile.json"`) and `"file": {"path": "data/enemy.json"}`
  for a file in a subfolder; a bare name for a subfolder file loads and is
  rewritten to the object form on save.
- A family is `families/<Name>.json` (`name`, `plugin-id`, `sid`,
  `instanceVariables`, `behaviorTypes`, `effectTypes`, `members`), listed
  under `families` in `project.c3proj` like an object type. A container has
  no file: `project.c3proj` holds `"containers": [{"members": ["TankBase",
  "TankTurret"]}]`, its members object type names, no `selectMode`. Nothing
  under `objectTypes/` names a container.
- A family instance variable can be written through a member type:
  `"objectClass": "enemyBase"`, `"instance-variable": "hp"` with `hp`
  declared on family `EnemyGroup`.
- Parameters an ACE gained in a later release may be omitted; the editor
  fills defaults on load. `pick-nearestfurthest` loads with `which`, `x`,
  `y` alone, though the schema also lists `z` and `pick-all-tied`.
- `sid`: 15-digit integer, unique across the whole project. `uid`: unique
  across all layouts and the single-global object types, whose one
  instance keeps its `uid` in `objectTypes/<Name>.json` (the Timeline
  controller among them): a new layout instance numbered from the highest
  layout uid alone can collide with it. Files: UTF-8 with raw non-ASCII, tab indent, LF, no
  trailing newline. Python `json.dumps(obj, indent="\t", ensure_ascii=False)`
  reproduces the editor's output byte for byte.
- Local Storage is an IndexedDB database named `c3-localstorage-` plus the
  project's `uniqueId`, so it survives closing the preview and is separate
  per project. A tool that rewrites `project.c3proj` must keep `uniqueId`
  or the saved data is orphaned. [runtime: exported c3runtime.js
  `_GetProjectStorage`; manual:
  scripting/scripting-reference/interfaces/istorage.md "unique to the
  specific project"]
- A behavior declared on a family is used through a member type with the
  family's behavior name: `"objectClass": "DragonHead", "behaviorType":
  "Physics"` where only family `Parts` declares Physics. The member's layout
  instances carry the family behavior's properties block as if it were their
  own.
- A Sprite Font is `"plugin-id": "Spritefont2"` with an `image` block in
  its object type file, as a Tiled Background has, the picture at
  `images/<lowercase name>.png`, and a `usedAddons` entry `{"type":
  "plugin", "id": "Spritefont2", "name": "Sprite font", "author":
  "Scirra", "bundled": false}`. Its layout instance holds `text`,
  `enable-bbcode`, `character-width`, `character-height`,
  `character-set`, `spacing-data`, `scale`, `character-spacing`,
  `line-height`, `horizontal-alignment`, `vertical-alignment`, `wrapping`,
  `initially-visible`, `origin` and `read-aloud`. `spacing-data` is a
  string holding JSON, `"[[25,\".\"],[53,\"0123456789\"]]"`, or `""`
  for none. [examples: animated-spritefont-effects, 3d-castle-maze
  `TextFont`; a game project the editor r504 opened and previewed,
  2026-09-30]
- Instance `world` entries write Z elevation as `"z"` with a `"depth"` key;
  layers keep `zElevation`.

## Timelines and custom eases

Read from the editor's project loader and saver (`projectResources.js`,
r504), the official example `blacksmith-forge` and a game project the editor
r504 opened and previewed on 2026-09-30.

- A timeline is `timelines/<name>.json`, listed by name under `timelines`
  `items` in `project.c3proj`. A custom ease (the **Eases** folder, which the
  editor calls transitions) is `timelines/transitions/<name>.json`, listed
  under the first subfolder of `timelines`, the one without a `name`; a
  subfolder with a `name` is a timeline folder.
- A custom ease file is `{"name", "linear": false, "purpose": "any",
  "transitionKeyframes": [...]}`. Each keyframe is `x`, `y`, the start anchor
  `sax`, `say` and the end anchor `eax`, `eay` as offsets from the keyframe,
  `se` and `ee` for whether each anchor is used, and `sm` `"cubic"` or
  `"linear"`. The first keyframe is (0, 0) with its end anchor off, the last
  (1, 1) with its start anchor off, as the runtime's built-in eases are
  written. A timeline keyframe or a Tween action names it by its bare name.
- The Timeline controller is a single-global object type, `"plugin-id":
  "Timeline"`, with a `usedAddons` entry `{"type": "plugin", "id":
  "Timeline", "name": "Timeline controller", "author": "Scirra", "bundled":
  false}`.
- An instance track names one instance in a layout, `worldInstance` its uid
  and `objectType` its type, and `project` the project's `uniqueId`. A
  template instance in a layout that never runs works: *Set instance* puts
  the runtime instance in its place. `id` is the track ID that *Set
  instance* names.
- A property keyframe keeps `value` and `rValue`, read in relative mode, and
  `aValue`, read in absolute mode. Angles are radians; an `angle` addon
  gives the direction of the segment that starts at that keyframe,
  `closest`, `clockwise` or `anti-clockwise`, and extra `revolutions`. Its
  `ease` is a built-in ease id or a custom ease's name.
- The editor's *Use system timescale* is saved as `ignoreSystemTimescale`,
  and the name is inverted: `true` follows the system time scale, `false`
  ignores it, and a file without the key follows it. The export writes the
  key's value to the runtime's `useSystemTimescale`.

## Naming an event to the user

The JSON has no event numbers; the editor does. Its margin and its Find
results (`Event 15 action 2`) count blocks, groups and function blocks per
sheet in document order, sub-events included; variables, comments and
includes take no number and are filed under the next numbered event.
Quote those numbers, never JSON line numbers, and read a screenshot or a
pasted Find result back the same way. To find the JSON behind a number, run
the `construct3-project` skill's `scripts/print_sheet.py --outline <sheet>`
in the project folder: each row prints with its number and its `sid`, which
is the string to search the sheet file for. Without `--outline` it prints
the same rows with their conditions and actions as the editor words them;
read the sheet that way before and after an edit.

## Checks before handing over

Run the skill's `scripts/check_project.py` on the project folder, from the
copy installed in the project, `.agents/skills/construct3-project/`, or in
place here with `--project <folder>`. It checks that the JSON parses; that
every `objectClass`, instance variable and behavior name exists, families
included; that `sid` and `uid` are unique; that every ACE `id` and parameter
key is in `data/c3-schemas/`; that every called function is defined with
the right parameter count; that every object created at runtime has a
template instance in some layout; and the rules the editor applies on
opening, the table in
`skills/construct3-project/references/checker-rules.md`.

Once it passes, open and preview the project with the skill's
`scripts/open_in_editor.py --preview`, which prints `opened`, or the
editor's own message naming the sheet, event and parameter it refused, and
then the errors of the first 5 seconds of play, each with its event; an
expression whose types do not fit is caught there, not by the checker.

What the checks cannot answer is what the game does: which instances a
condition picks, what order triggers fire in, what happens once a player
acts.
Ask the user to open the project and preview it, and say what to look at.
