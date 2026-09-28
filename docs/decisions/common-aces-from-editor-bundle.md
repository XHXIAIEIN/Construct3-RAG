# Shared ACE Definitions From the Editor Bundle

Date: 2026-09-18
Schema: Construct 3 r495.2

## Problem

`plugins/_common.json` holds the conditions, actions and expressions every
world object shares. The exporter built it from the language pack alone,
because `allAces.json` does not list them. The pack has names, descriptions
and the labels of combo items, but no structure, so every parameter was
written as `"type": "object"` with no `items`, `scriptName` was the ACE id and
`category` the placeholder `common`. A reader could type-check the parameters
of `Sprite` but not of `compare-instance-variable`, `pick-children` or
`set-boolean-instvar`, and had to open `data/c3-lang/` for the combo values.

## Evidence

None of the CDN payloads the fetcher already reads contains the shared ACEs:
`plugins/allAces.json`, `behaviors/allAces.json`, `offline.json` and
`media/autocomplete-data.json` were searched for the ids. `offline.json` lists
`preview/events/commonACEs.js`, but that is the runtime implementation and
carries no parameter types. The definitions are registered in the editor
bundle `main.js`, in the function that follows the string
`"plugins._common"`, as object literals in the `allAces` shape:

```js
t.Qcs({id:"compare-instance-variable",c2id:-7,scriptName:"CompareInstanceVar",
  params:[{id:"instance-variable",type:"instancevar"},{id:"comparison",type:"cmp"},
          {id:"value",type:"any"}]})
```

All 136 shared ACEs of the r495.2 language pack are there, with 147
parameters, 16 of them combos whose `items` match the pack. Each release
serves its own bundle in its CDN directory,
`https://editor.construct.net/r495-2/main.js` for r495.2
(`cdn-release-directory.md`).

## Options

1. Parse `main.js` during every export. No committed file, but every export
   would depend on the anchor and the literal shape surviving minification,
   not only an export whose language pack adds a shared ACE.
2. Extract the block once into `src/ingest/common_aces.json` with a script,
   commit it with its source, and have the exporter merge it like an
   `allAces.json` entry. The default export stays offline and deterministic;
   the file must be regenerated when a release adds a shared ACE.
3. Maintain the type mapping by hand. Same offline property as option 2, but
   147 parameters copied by eye with no way to reproduce them.

## Decision

Option 2. `scripts/extract_common_aces.py` fetches the bundle of the latest
stable release from that release's directory, cuts out the block after the
anchor and writes `src/ingest/common_aces.json`; the file records the release
it came from. `C3Fetcher.export_schemas()` loads it and
feeds `_common` through the same loop as every plugin, so `_common.json` has
the same structural fields as any plugin file: real `type`, `items` labelled
per locale, `initialValue`, `scriptName`, the editor category, `isTrigger`
and `returnType`. Parameters keep the editor's order, which is what the
`{n}` placeholders of `display-text` index.

A language pack that names a shared ACE or parameter the file does not define
stops the export with the missing ids instead of writing untyped parameters.
`tests/test_common_aces.py` makes the same check against the committed packs,
so the gap is caught before a sync PR as well.

Two consequences outside `_common.json`:

- The root index counts now equal the ACEs written to each file. They used to
  count `allAces.json` entries, including deprecated ACEs the export skips,
  so 24 addons showed more ACEs than their files contain.
- `category` of a `_common` ACE is the editor category (`collisions`,
  `hierarchy`, `instance-variables` ...) rather than `common`. The lookup
  result carries it through unchanged.

## Which plugin gets which shared ACE

Not every world object gets every shared ACE: the editor refuses *Set
color* on a Text with `missing action id 'set-default-color'`. The block
registers each group behind a guard on the plugin's info, so the extraction
reads both sides from the editor:

- the guards of the `_common` block, named through the public methods of
  `window.SDK.IPluginInfo` that set them (`AddCommonAppearanceACEs`,
  `SetSupportsColor` ...). A guard with no public method (collisions, mesh,
  DOM elements, templates) is named `editor:<first ACE it registers>`;
- the setters each built-in plugin calls in its constructor in
  `plugins/allEditorPlugins.js`, at the constructor's own level, so that a
  call inside a property callback does not count.

`common_aces.json` keeps both, `requires` per ACE and `plugins` per plugin,
and the export writes each plugin's resolved ids as `commonAces`. Text
calls `AddCommonAppearanceACEs` but not `SetSupportsColor`. No official
example uses a shared condition or action outside its plugin's
`commonAces`; a plugin's own ACE of the same id (`set-size` of Array) is
found first.

## Re-evaluate when

- `scripts/init.py` stops with the coverage error after a release: run the
  extraction script, review the diff, commit it with the data sync.
- `window.SDK.IPluginInfo` is renamed, or a plugin's constructor stops
  building its info the way the script expects: it fails on the anchor or
  on the plugin id.
- The anchor or the literal shape disappears from `main.js`. The script then
  fails on the anchor count or on JSON conversion; option 1 is not a fallback,
  the block has to be located again.
- Scirra publishes the shared ACEs on a CDN endpoint. Then the file and the
  script should go and the exporter read the endpoint like `allAces.json`.
