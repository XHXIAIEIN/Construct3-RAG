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
parameters, 16 of them combos whose `items` match the pack. The bundle is
served only at the CDN root, `https://editor.construct.net/main.js`; the
release directory returns 404.

## Options

1. Parse `main.js` during every export. No committed file, but each export
   downloads 1.4 MB of minified code, the parse depends on the anchor and the
   literal shape surviving minification, and the root bundle is the current
   stable release, not necessarily `C3_VERSION`.
2. Extract the block once into `src/ingest/common_aces.json` with a script,
   commit it with its source, and have the exporter merge it like an
   `allAces.json` entry. The default export stays offline and deterministic;
   the file must be regenerated when a release adds a shared ACE.
3. Maintain the type mapping by hand. Same offline property as option 2, but
   147 parameters copied by eye with no way to reproduce them.

## Decision

Option 2. `scripts/extract_common_aces.py` fetches the bundle, cuts out the
block after the anchor and writes `src/ingest/common_aces.json`; the file
records the release it came from. `C3Fetcher.export_schemas()` loads it and
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

## Re-evaluate when

- `scripts/init.py` stops with the coverage error after a release: run the
  extraction script, review the diff, commit it with the data sync.
- The anchor or the literal shape disappears from `main.js`. The script then
  fails on the anchor count or on JSON conversion; option 1 is not a fallback,
  the block has to be located again.
- Scirra publishes the shared ACEs on a CDN endpoint. Then the file and the
  script should go and the exporter read the endpoint like `allAces.json`.
