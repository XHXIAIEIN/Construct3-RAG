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
- Function call: `{"callFunction": "name", "sid": N, "parameters": ["expr", ...]}`.
  Function block: `functionCopyPicked` (boolean) and `functionParameters`
  entries with `name`, `type`, `initialValue`, `comment`, `sid`.
- Parameters an ACE gained in a later release may be omitted; the editor fills
  defaults on load. Every official example that uses `pick-nearestfurthest`
  (saved r184 to r437) writes only `which`, `x`, `y`; the r495.2 schema also
  lists `z` and `pick-all-tied`.
- `sid`: 15-digit integer, unique across the whole project. `uid`: unique
  across all layouts. Files: UTF-8 with raw non-ASCII, tab indent, LF, no
  trailing newline. Python `json.dumps(obj, indent="\t", ensure_ascii=False)`
  reproduces the editor's output byte for byte (roundtrip checked on mergeGame).

## Checks before handing over

Without the editor: JSON parses; every `objectClass`, instance variable and
behavior name exists, families included; `sid` and `uid` are unique; every ACE
`id` and parameter key is present in `data/c3-schemas/` (shared world ACEs in
`plugins/_common.json`); every called function is defined with the right
parameter count; every object created at runtime has a template instance in
some layout.

On editor.construct.net (observed r495.2, 2026-09-15): a guest session is
capped at 25 events and a verified free account at 50; families are a paid
feature, so a project using them cannot be previewed without a licensed
account. `#open=<example-id>` opens official examples; opening a project from
an arbitrary URL through `#open=` did not work in that test. Ask the user to
open and preview instead, and tell them what to look at.
