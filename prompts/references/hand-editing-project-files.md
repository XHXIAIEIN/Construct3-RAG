# Hand-editing Construct project files

Read this to write or change `eventSheets/*.json`, `layouts/*.json`,
`objectTypes/**/*.json`, `families/*.json`, `project.c3proj` or clipboard
payloads without the editor. Put events into a sheet with the
`construct3-agent-plugin` skill's `scripts/edit_sheet.py`. It takes them as a
plan, gives them their sids and checks the result before it writes. This file
says how to write each entry of such a plan or of a hand edit. Clipboard
payloads use the same condition and action entries, and
`Construct3-Clipboard/docs/clipboard-format.md` documents their envelope.

## The project folder

Scirra's guide [Construct's project format](https://www.construct.net/en/tutorials/constructs-project-format-3275)
states what follows. The `llm-context.md` the editor writes into every
project links it, and this repository keeps a copy in
`data/c3-guides/constructs-project-format.md`. The format has no published
specification and changes between releases. An invalid edit can leave a
project that does not open, so end every hand edit with the checks at the
end of this file.

- `project.c3proj` lists every object type, family, layout, event sheet,
  timeline, flowchart, 3D model, script, sound, music, video, font, icon and
  file, in the folders of the Project Bar. The editor reads only what it lists
  and ignores any other file, so list a file you write by hand in the same
  change. Each JSON resource is in its folder (`objectTypes/`, `families/`,
  `layouts/`, `eventSheets/`, `timelines/`, `flowcharts/`, `3dmodels/`), under
  the subfolders the listing names.
- Images are in `images/`, without subfolders, named in lower case. A frame is
  `<object type>-<animation>-<frame>.png`, counted from 0 and padded to three
  digits (`player-default-000.png`). An object with a single image, a Tiled
  Background or a 9-patch has `<object type>.png`. The editor takes an image's
  size from the file and ignores the `width` and `height` of its entry, so you
  can redraw it at another size outside the editor. One imported as JPEG or
  AVIF and not edited in the editor keeps that format, which its entry's
  `fileType` names.
- Sound and music are WebM Opus, `.webm`. Fonts are WOFF, the only format
  browsers support consistently. The editor also takes TTF and OTF, as the
  official examples show. Icons and the loading logo are PNG. For video, MP4
  with H.264 is a good default. A file in `files/` is of any kind. Construct
  does not use it; the project's logic reads it, through AJAX for example.
- For TypeScript, list the `.ts` files alone, which Construct compiles, or the
  `.js` files alone, compiled outside from `.ts` files the project does not
  list. With both files of one script listed, Construct runs the `.js` [manual:
  scripting/using-scripting/typescript-construct.md].
- `*.uistate.json` files and `uistate` folders hold the state of the editor's
  interface; deleting them loses nothing else. Palettes and tilemap brushes
  have folders of their own, `palettes/` and `tilemapBrushes/`.

## Encodings

Each rule was read from the editor's loaders, from files it saved or from the
official examples (`docs/decisions/checker-editor-load-rules.md`).

- Comparison parameters are integers: 0 `=`, 1 `≠`, 2 `<`, 3 `≤`, 4 `>`, 5 `≥`.
- String parameters keep their quotes: `"tag": "\"attack\""`. `layer` is an
  index string `"2"` or a quoted name `"\"Graphics\""`. `create-hierarchy` is a
  JSON boolean. Inverted conditions have `"isInverted": true`.
- Everything that is not an expression has no inner quotes: a combo item
  (`"mouse-button": "left"`, `"loop": "no"`), an object, a layout, a variable,
  an ease id (`"ease": "easeoutback"`, the ids under `ui/bars/timeline/eases`
  in `data/c3-lang/en-US.json`). A quoted combo value is not an error to the
  editor: it silently keeps the default. A key is its key code as a JSON number
  (`"key": 32`); a string stops the load with `expected finite number`. A JSON
  string `"false"` in a boolean parameter reads as true.
- `plugin-id`, `behaviorId` and the `id` of a `usedAddons` entry use the
  editor's exact spelling, `originalId` in `data/c3-schemas/_index.json`. `Arr`
  is Array, `Json` JSON, `TiledBg` Tiled Background, `EightDir` 8 Direction and
  `Sin` Sine. `solid`, `scrollto`, `jumpthru`, `bound`, `wrap`, `destroy` and
  `gamepad` are lowercase. Any other spelling stops the load with
  `missing plugin id`.
- An event variable's `initialValue` is text whatever its `type`: `"0"`,
  `"hello"` without inner quotes, and for a boolean `"true"` or `"false"`,
  lowercase. The editor reads a boolean by comparing the text to `"true"`, so a
  JSON `false` or `true`, a `"True"` and a `"1"` all read as false. A number
  text that does not parse reads as 0. A function parameter's `initialValue`
  may also be a JSON number; anything else stops the load with
  `invalid type of initialValue`.
- A layout instance's `instanceVariables` map holds JSON values by type, with
  no quotes on a number or a boolean: `{"hp": 3, "dead": false, "label": "a"}`.
- An instance's `world.angle` is in radians: 270 degrees is `4.7124`. A
  generator uses `math.radians`; `Angle` in events stays in degrees.
- A function call is
  `{"callFunction": "name", "sid": N, "parameters": ["expr", ...]}`. A
  function block has `functionCopyPicked` (boolean) and `functionParameters`
  entries with `name`, `type`, `initialValue`, `comment`, `sid`.
- A custom action block has `"eventType": "custom-ace-block"`,
  `"aceType": "action"`, `"aceName"`, `"objectClass"` (the declaring type or
  family), then the same `function*` keys as a function block. Its
  `functionCopyPicked` is *Copy all picked*. A call is
  `{"customAction": "name", "objectClass": "<row object>", "sid": N}`, with
  `"parameters": ["expr", ...]` exactly when the block declares parameters. If
  the row object is a member type and the block is declared on the family, not
  on the member, the editor saves the call with
  `"customActionObjectClass": "<family>"`. A call that runs the member's own
  block is saved without it. A call written without the key still loads.
  [observed: Merge Game, r504, October 2026: 13 calls on `base` and `body`
  gained it on save, the calls of `base`'s own `arm` and `toTop` did not]
- A `projectfile` parameter is the bare file name for a file at the root
  (`"file": "DefaultProfile.json"`) and `"file": {"path": "data/enemy.json"}`
  for a file in a subfolder. A bare name for a subfolder file loads and is
  rewritten to the object form on save.
- A family is `families/<Name>.json` (`name`, `plugin-id`, `sid`,
  `instanceVariables`, `behaviorTypes`, `effectTypes`, `members`), listed under
  `families` in `project.c3proj` like an object type. A container has no file:
  `project.c3proj` holds `"containers": [{"members": ["TankBase",
  "TankTurret"]}]`, with object type names as members and no `selectMode`.
  Nothing under `objectTypes/` names a container.
- The editor sorts some lists of `project.c3proj` on save, so an entry appended
  at the end moves in the diff of the next save. `usedAddons` holds plugins,
  then behaviors, then effects, each sorted by `id` in code point order,
  uppercase before lowercase: `AJAX` before `AdvancedRandom`, `Touch` before
  `gamepad`. A container's `members` are sorted without regard to case:
  `enemyHpText` before `EnemyStats`. Insert an entry where the sort puts it.
  [observed: Merge Game, r504, October 2026: a save moved `Timeline`,
  `Spritefont2` and `Anchor` from the end of `usedAddons` into place and
  `CardFace` ahead of `CardShadow`]
- The editor saves every layout instance in one key order and number form, so a
  hand edit in another form comes back changed in the diff of the next save. An
  instance's key order is `type`, `properties`, `uid`, `sid`, `tags`,
  `instanceVariables`, `behaviors`, `effects`, `materialSurfaceType`,
  `sceneGraphData`, `showing`, `locked`, `world`. That of `world` is `x`, `y`,
  `width`, `height`, `originX`, `originY`, `color`, `z`, `angle`, `blendMode`.
  `properties` follow the order the plugin declares them in. A world instance
  without `materialSurfaceType` gets `"smooth"`, whatever its plugin and
  whether or not it has effects, and a nonworld instance gets none. Numbers are
  saved in their shortest form: `284.0` becomes `284`, `215.250` becomes
  `215.25`, `-0.0` becomes `0`. So a generator writes a whole float as an int.
  [observed: Merge Game, r504, October 2026: Download a copy of a layout with
  `effects` and `sceneGraphData` after `world`, `materialSurfaceType` removed
  from Sprite, Tiled Background, 9-patch and Sprite font instances, and
  `"y": 284.0` came back byte for byte as the editor had last saved it; a
  folder save made the same changes]
- A Save of a folder project writes only the files of what was edited. So a
  hand-written file keeps its form, including keys the editor would rewrite,
  until something in it is edited in the editor. Save as project folder and
  Download a copy write every file. [observed: Merge Game, r504, October 2026:
  a Save after opening an unedited folder wrote no file; the folder saves
  c30d3ce and 2063f77 rewrote only the edited layout and `project.c3proj`]
- The editor leaves empty lists out: an event without sub-events has no
  `children`, a function or custom action call without arguments no
  `parameters`, an animation frame without image points no `imagePoints`. A
  `[]` loads, and the next save of its file drops it. For no hierarchy, leave
  `sceneGraphData` out, because the save writes a full `sceneGraphData` block
  for `"sceneGraphData": null`. A behavior property an instance lacks is saved
  with its default (`"rotation-type": "2d"` for Rotate). An instance's
  `instanceVariables` are saved family variables first, then the type's own,
  each in declaration order. [observed: Merge Game, r504, October 2026: each of
  these written back by hand into a saved project came back as described from
  Save as project folder]
- The save rewrites a layout instance's `world.originX` and `originY` to the
  origin of the first frame of its initial animation, so write the frame's
  values. An instance written with `"originY": 1` over a frame whose origin is
  0.9929 is saved with 0.9929. [observed: Merge Game, r504, October 2026,
  instances whose `initial-frame` is 0, and folder save c30d3ce]
- A family instance variable can be written through a member type:
  `"objectClass": "enemyBase"`, `"instance-variable": "hp"` with `hp` declared
  on family `EnemyGroup`.
- You can omit parameters an ACE gained in a later release; the editor fills
  their defaults on load. `pick-nearestfurthest` loads with `which`, `x`, `y`
  alone, though the schema also lists `z` and `pick-all-tied`.
- A `sid` is a 15-digit random integer unique across the whole project, so
  content merges without renumbering. A `uid` is any value unique across all
  layouts and the single-global object types. A single-global type like the
  Timeline controller keeps the `uid` of its one instance in
  `objectTypes/<Name>.json`, so a layout instance numbered from the highest
  layout uid alone can collide with it. With UID numbering set to Random
  (`"uidAllocationMode": "random"`), Construct gives new instances six-digit
  random uids, which keep two branches of a project under source control apart
  (`docs/decisions/random-uid-allocation.md`).
- Files are UTF-8 with raw non-ASCII, tab indent, LF, no trailing newline and
  no byte order mark. Python `json.dumps(obj, indent="\t", ensure_ascii=False)`
  reproduces the editor's output byte for byte. A file that starts with a byte
  order mark still opens. [observed: the official examples carry none; an event
  sheet and a `project.c3proj` with one opened in the stable editor, October
  2026]
- Local Storage is an IndexedDB database named `c3-localstorage-` plus the
  project's `uniqueId`, so it survives closing the preview and is separate per
  project. A tool that rewrites `project.c3proj` must keep `uniqueId`, or the
  project loses its saved data. [runtime: exported c3runtime.js
  `_GetProjectStorage`; manual:
  scripting/scripting-reference/interfaces/istorage.md "unique to the specific
  project"]
- A behavior declared on a family is used through a member type with the
  family's behavior name: `"objectClass": "DragonHead", "behaviorType":
  "Physics"` where only family `Parts` declares Physics. The member's layout
  instances hold the family behavior's properties block as if it were their
  own.
- A project with Bundle addons set, the test project of an addon under
  development, holds `"bundleAddons": true` in `project.c3proj`, each bundled addon's `usedAddons` entry with
  `"bundled": true` and its `"version"`, and the addon itself at
  `addons/<type>/<id>.c3addon`, `addons/effect/<id>.c3addon` for an
  effect. An effect's color parameter on a layout instance is four
  numbers, `[1, 0.24, 0.27, 1]`. [observed in a project the editor r504
  saved, 2026-10-03]
- A Sprite Font has `"plugin-id": "Spritefont2"` and an `image` block in its
  object type file, as a Tiled Background has. Its picture is
  `images/<lowercase name>.png`, its `usedAddons` entry `{"type": "plugin",
  "id": "Spritefont2", "name": "Sprite font", "author": "Scirra", "bundled":
  false}`. Its layout instance holds `text`, `enable-bbcode`,
  `character-width`, `character-height`, `character-set`, `spacing-data`,
  `scale`, `character-spacing`, `line-height`, `horizontal-alignment`,
  `vertical-alignment`, `wrapping`, `initially-visible`, `origin` and
  `read-aloud`. `spacing-data` is a string holding JSON,
  `"[[25,\".\"],[53,\"0123456789\"]]"`, or `""` for none. [examples:
  animated-spritefont-effects, 3d-castle-maze `TextFont`; a game project the
  editor r504 opened and previewed, 2026-09-30]
- Instance `world` entries write Z elevation as `"z"` with a `"depth"` key;
  layers use `zElevation`.

## Timelines and custom eases

Each rule was read from the editor's project loader and saver
(`projectResources.js`, r504), the official example `blacksmith-forge` and a
game project the editor r504 opened and previewed on 2026-09-30.

- A timeline is `timelines/<name>.json`, listed by name under `timelines`
  `items` in `project.c3proj`. A custom ease (the **Eases** folder, which the
  editor calls transitions) is `timelines/transitions/<name>.json`, listed
  under the first subfolder of `timelines`, the one without a `name`; a
  subfolder with a `name` is a timeline folder.
- A custom ease file is `{"name", "linear": false, "purpose": "any",
  "transitionKeyframes": [...]}`. Each keyframe has `x`, `y`, the start anchor
  `sax`, `say` and the end anchor `eax`, `eay` as offsets from the keyframe,
  `se` and `ee` for whether each anchor is used, and `sm`, `"cubic"` or
  `"linear"`. The first keyframe is (0, 0) with its end anchor off, the last
  (1, 1) with its start anchor off, as in the runtime's built-in eases. A
  timeline keyframe or a Tween action names the ease by its bare name.
- The Timeline controller is a single-global object type,
  `"plugin-id": "Timeline"`, with a `usedAddons` entry `{"type": "plugin",
  "id": "Timeline", "name": "Timeline controller", "author": "Scirra",
  "bundled": false}`.
- An instance track names one instance in a layout: `worldInstance` is its uid,
  `objectType` its type and `project` the project's `uniqueId`. A template
  instance in a layout that never runs works, because *Set instance* puts the
  runtime instance in its place. `id` is the track ID that
  *Set instance* names.
- A property keyframe holds `value` and `rValue`, read in relative mode, and
  `aValue`, read in absolute mode. Angles are in radians. An `angle` addon
  gives the direction of the segment that starts at that keyframe, `closest`,
  `clockwise` or `anti-clockwise`, and extra `revolutions`. Its `ease` is a
  built-in ease id or a custom ease's name.
- The editor saves *Use system timescale* as `ignoreSystemTimescale`, and the
  name is inverted: `true` follows the system time scale, `false` ignores it,
  and a file without the key follows it. The export writes the key's value to
  the runtime's `useSystemTimescale`.
- An instance track's `virtualPosition` is the editor's preview offset of the
  instance while the playhead is dragged. The runtime does not read it. The
  editor writes `"relativeFlags": 16383, "version": 1` after the offsets
  whatever the file held, so a generator writes those. The 14 bits, low to
  high, are z elevation, origin Y, origin X, opacity, angle, height, width, Y,
  X, scale Y, scale X, depth, scale Z and 3D rotation. 2047 is the 2D ones
  alone, as files from before the 3D offsets have it. A timeline file also ends
  with `"nestedData": {}`, `"childrenNestedData": {}` and
  `"transitionsData": []`. A save sometimes fills `transitionsData` with copies
  of the custom eases the timeline uses. The editor reads them only when the
  timeline is pasted, so `[]` is right in a file. [editor r504
  `projectResources.js`; the exported `c3runtime.js` has no `virtualPosition`;
  observed: Merge Game, r504, October 2026: 2047 written with and without
  `version` came back 16383]

## Naming an event to the user

The JSON has no event numbers; the editor does. Its margin and its Find results
(`Event 15 action 2`) count blocks, groups, function blocks, custom action
blocks and script blocks per sheet in document order, sub-events included.
Variables, comments and includes take no number and are listed under the next
numbered event. Quote those numbers, never JSON line numbers, and read a
screenshot or a pasted Find result the same way. To find the JSON behind a
number, run the `construct3-agent-plugin` skill's
`scripts/print_sheet.py --outline <sheet>` in the project folder. It prints
each row with its number and its `sid`, the string to search the sheet file
for. Without `--outline` it prints the same rows with their conditions and
actions as the editor words them. Read the sheet that way before and after
an edit.

## Checks before handing over

Run the skill's `scripts/check_project.py` on the project folder, from the copy
installed in the project, `.agents/skills/construct3-agent-plugin/`, or in
place here with `--project <folder>`. It checks that:

- the JSON parses
- every `objectClass`, instance variable and behavior name exists, families
  included
- `sid` and `uid` are unique
- every ACE `id` and parameter key is in `data/c3-schemas/`
- every called function is defined with the right parameter count
- every object created at runtime has a template instance in some layout
- the project follows the rules the editor applies on opening, the table in
  `skills/construct3-agent-plugin/references/checker-rules.md`

If it passes, open and preview the project with the skill's
`scripts/open_in_editor.py --preview`. It prints `opened`, or the editor's own
message naming the sheet, event and parameter it refused. Then it prints the
errors of the first 5 seconds of play, each with its event. The preview, not
the checker, catches an expression whose types do not fit.

The checks cannot answer what the game does: which instances a condition picks,
what order triggers fire in, what happens once a player acts. So ask the user
to open the project and preview it, and say what to look at.
