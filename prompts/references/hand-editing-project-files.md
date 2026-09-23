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
the official examples; the evidence is in
`docs/decisions/checker-editor-load-rules.md`, "the evidence behind the
hand-editing reference".

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
  across all layouts. Files: UTF-8 with raw non-ASCII, tab indent, LF, no
  trailing newline. Python `json.dumps(obj, indent="\t", ensure_ascii=False)`
  reproduces the editor's output byte for byte.
- A behavior declared on a family is used through a member type with the
  family's behavior name: `"objectClass": "DragonHead", "behaviorType":
  "Physics"` where only family `Parts` declares Physics. The member's layout
  instances carry the family behavior's properties block as if it were their
  own.
- Instance `world` entries write Z elevation as `"z"` with a `"depth"` key;
  layers keep `zElevation`.

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

Once it passes, open the project with the skill's
`scripts/open_in_editor.py`, which prints `opened`, or the editor's own
message naming the sheet, event and parameter it refused; an expression
whose types do not fit is caught there, not by the checker.

What the checks cannot answer is what the game does: which instances a
condition picks, what order triggers fire in, what a tick later looks like.
Ask the user to open the project and preview it, and say what to look at.
