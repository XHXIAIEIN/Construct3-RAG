# Hand-editing Construct project files

Read this when writing or changing `eventSheets/*.json`, `layouts/*.json`,
`objectTypes/**/*.json`, `families/*.json`, `project.c3proj` or clipboard
payloads without the editor. Events go into a sheet through the
`construct3-agent-plugin` skill's `scripts/edit_sheet.py`, which takes them as a
plan, gives them their sids and checks the result before it writes; what
follows is how each entry of such a plan, or of a hand edit, is written.
Clipboard payloads use the same condition and action entries; the envelope
is documented in `Construct3-Clipboard/docs/clipboard-format.md`.

## The project folder

Scirra's guide [Construct's project format](https://www.construct.net/en/tutorials/constructs-project-format-3275),
which the `llm-context.md` the editor writes into every project links,
states what follows. The format has no published specification and changes
between releases, and an invalid edit can leave a project that does not
open, which is why every hand edit ends with the checks at the end of this
file.

- `project.c3proj` lists every object type, family, layout, event sheet,
  timeline, flowchart, 3D model, script, sound, music, video, font, icon and
  file, in the folders of the Project Bar. The editor reads only what it
  lists and ignores any other file, so a file written by hand is listed in
  the same change. Each JSON resource is in its folder (`objectTypes/`,
  `families/`, `layouts/`, `eventSheets/`, `timelines/`, `flowcharts/`,
  `3dmodels/`), under the subfolders the listing names.
- Images are in `images/`, without subfolders, named in lower case:
  `<object type>-<animation>-<frame>.png`, the frame counted from 0 and
  padded to three digits (`player-default-000.png`), and `<object
  type>.png` for an object with a single image, a Tiled Background or a
  9-patch. The editor takes an image's size from the file and ignores the
  `width` and `height` of its entry, so an image may be redrawn at another
  size outside the editor. One imported as JPEG or AVIF and not edited in
  the editor keeps that format, which its entry's `fileType` names.
- Sound and music are WebM Opus, `.webm`. Fonts are best WOFF, the one
  format every browser reads; the editor also takes TTF and OTF, as the
  official examples show. Icons and the loading logo are PNG. Video is best
  MP4 with H.264. A file in `files/` is of any kind; Construct does not use
  it, the project's logic reads it, through AJAX for one.
- TypeScript is the `.ts` files alone, which Construct compiles, or the
  `.js` files alone, compiled outside from `.ts` files the project does not
  list. With both of one script listed, Construct runs the `.js`
  [manual: scripting/using-scripting/typescript-construct.md].
- `*.uistate.json` files and `uistate` folders hold the state of the
  editor's interface; deleting them loses nothing else. Palettes and tilemap
  brushes have folders of their own, `palettes/` and `tilemapBrushes/`.

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
  parameters. When the row object is a member type and the block is
  declared on the family and not on the member, the editor saves the call
  with `"customActionObjectClass": "<family>"`; a call that runs the
  member's own block is saved without it. A call written without the key
  still loads. [observed: Merge Game, r504, October 2026: 13 calls on
  `base` and `body` gained it on save, the calls of `base`'s own `arm` and
  `toTop` did not]
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
- The editor saves some lists of `project.c3proj` sorted, and an entry
  appended at the end comes back moved in the diff of its next save.
  `usedAddons` holds plugins, then behaviors, then effects, each sorted by
  `id` in code point order, uppercase before lowercase: `AJAX` before
  `AdvancedRandom`, `Touch` before `gamepad`. A container's `members` are
  sorted without regard to case: `enemyHpText` before `EnemyStats`. Insert a
  new entry where the sort puts it. [observed: Merge Game, r504, October
  2026: a save moved `Timeline`, `Spritefont2` and `Anchor` from the end of
  `usedAddons` into place and `CardFace` ahead of `CardShadow`]
- The editor rewrites every layout instance it saves in one key order and
  number form, and a hand edit that departs from them comes back changed in
  the diff of the next save. An instance's keys run `type`, `properties`,
  `uid`, `sid`, `tags`, `instanceVariables`, `behaviors`, `effects`,
  `materialSurfaceType`, `sceneGraphData`, `showing`, `locked`, `world`;
  those of `world` run `x`, `y`, `width`, `height`, `originX`, `originY`,
  `color`, `z`, `angle`, `blendMode`; `properties` follow the order the
  plugin declares them in. A world instance without `materialSurfaceType`
  gets `"smooth"`, whatever its plugin and whether or not it has effects;
  a nonworld instance gets none. Numbers are written in their shortest
  form: `284.0` becomes `284`, `215.250` becomes `215.25`, `-0.0` becomes
  `0`, so a generator writes a whole float as an int. [observed: Merge
  Game, r504, October 2026: Download a copy of a layout with `effects` and
  `sceneGraphData` after `world`, `materialSurfaceType` removed from
  Sprite, Tiled Background, 9-patch and Sprite font instances, and
  `"y": 284.0` came back byte for byte as the editor had last saved it; a
  folder save made the same changes]
- A Save of a folder project writes only the files of what was edited, and
  a hand-written file keeps its form, keys the editor would rewrite
  included, until something in it is edited in the editor. Save as project
  folder and Download a copy write every file. [observed: Merge Game, r504,
  October 2026: a Save after opening an unedited folder wrote no file; the
  folder saves c30d3ce and 2063f77 rewrote only the edited layout and
  `project.c3proj`]
- The editor leaves empty lists out: an event without sub-events has no
  `children`, a function or custom action call without arguments no
  `parameters`, an animation frame without image points no `imagePoints`.
  A `[]` loads and is dropped by the next save of its file.
  `"sceneGraphData": null` does not mean no hierarchy: the save writes a
  full `sceneGraphData` block for it, so leave the key out. A behavior
  property an instance lacks is written with its default (`"rotation-type":
  "2d"` for Rotate), and an instance's `instanceVariables` are written
  family variables first, then the type's own, each in declaration order.
  [observed: Merge Game, r504, October 2026: each of these written back by
  hand into a saved project came back as described from Save as project
  folder]
- A layout instance's `world.originX` and `originY` are rewritten on save to
  the origin of the first frame of its initial animation, so write the
  frame's values: an instance written with `"originY": 1` over a frame whose
  origin is 0.9929 is saved with 0.9929. [observed: Merge Game, r504,
  October 2026, instances whose `initial-frame` is 0, and folder save
  c30d3ce]
- A family instance variable can be written through a member type:
  `"objectClass": "enemyBase"`, `"instance-variable": "hp"` with `hp`
  declared on family `EnemyGroup`.
- Parameters an ACE gained in a later release may be omitted; the editor
  fills defaults on load. `pick-nearestfurthest` loads with `which`, `x`,
  `y` alone, though the schema also lists `z` and `pick-all-tied`.
- `sid`: 15-digit random integer, unique across the whole project, so
  content merges without renumbering. `uid`: any value, unique across all
  layouts and the single-global object types, whose one
  instance keeps its `uid` in `objectTypes/<Name>.json` (the Timeline
  controller among them): a new layout instance numbered from the highest
  layout uid alone can collide with it. With UID numbering set to Random
  (`"uidAllocationMode": "random"`), Construct gives new instances
  six-digit random uids, which keep two branches of a project under source
  control apart (`docs/decisions/random-uid-allocation.md`). Files: UTF-8 with raw non-ASCII, tab indent, LF, no
  trailing newline, no byte order mark. Python `json.dumps(obj, indent="\t", ensure_ascii=False)`
  reproduces the editor's output byte for byte. A file that starts with a
  byte order mark still opens. [observed: the official examples carry none;
  an event sheet and a `project.c3proj` with one opened in the stable
  editor, October 2026]
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
- An instance track's `virtualPosition` is the editor's preview offset of
  the instance while the playhead is dragged; the runtime does not read it.
  The editor writes `"relativeFlags": 16383, "version": 1` after the offsets
  whatever the file held, so a generator writes those. The 14 bits, low to
  high, are z elevation, origin Y, origin X, opacity, angle, height, width,
  Y, X, scale Y, scale X, depth, scale Z and 3D rotation; 2047 is the 2D
  ones alone, as files from before the 3D offsets have it. A timeline file
  also ends with `"nestedData": {}`, `"childrenNestedData": {}` and
  `"transitionsData": []`. A save sometimes fills `transitionsData` with
  copies of the custom eases the timeline uses; the editor reads them only
  when the timeline is pasted, so `[]` is right in a file. [editor r504
  `projectResources.js`; the exported `c3runtime.js` has no
  `virtualPosition`; observed: Merge Game, r504, October 2026: 2047 written
  with and without `version` came back 16383]

## Naming an event to the user

The JSON has no event numbers; the editor does. Its margin and its Find
results (`Event 15 action 2`) count blocks, groups, function blocks, custom
action blocks and script blocks per sheet in document order, sub-events
included; variables, comments and includes take no number and are filed
under the next numbered event. Quote those numbers, never JSON line
numbers, and read a screenshot or a pasted Find result back the same way.
To find the JSON behind a number, run the `construct3-agent-plugin` skill's
`scripts/print_sheet.py --outline <sheet>`
in the project folder: each row prints with its number and its `sid`, which
is the string to search the sheet file for. Without `--outline` it prints
the same rows with their conditions and actions as the editor words them;
read the sheet that way before and after an edit.

## Checks before handing over

Run the skill's `scripts/check_project.py` on the project folder, from the
copy installed in the project, `.agents/skills/construct3-agent-plugin/`, or in
place here with `--project <folder>`. It checks that the JSON parses; that
every `objectClass`, instance variable and behavior name exists, families
included; that `sid` and `uid` are unique; that every ACE `id` and parameter
key is in `data/c3-schemas/`; that every called function is defined with
the right parameter count; that every object created at runtime has a
template instance in some layout; and the rules the editor applies on
opening, the table in
`skills/construct3-agent-plugin/references/checker-rules.md`.

Once it passes, open and preview the project with the skill's
`scripts/open_in_editor.py --preview`, which prints `opened`, or the
editor's own message naming the sheet, event and parameter it refused, and
then the errors of the first 5 seconds of play, each with its event; an
expression whose types do not fit is caught there, not by the checker.

What the checks cannot answer is what the game does: which instances a
condition picks, what order triggers fire in, what happens once a player
acts.
Ask the user to open the project and preview it, and say what to look at.
