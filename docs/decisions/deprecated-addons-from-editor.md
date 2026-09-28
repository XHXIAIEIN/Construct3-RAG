# Deprecated Addons From the Editor

Date: 2026-09-28
Schema: Construct 3 r495.2

## Problem

The export left out an addon only when the zh-CN language pack had no entry
for it. Three addons the editor has retired are still translated, so they were
in `data/c3-schemas/`, and `lookup_ace.py` and `POST /search` offered them to
an agent writing a new project:

- the NW.js plugin, `nodewebkit`. Release notes, beta r450: "Remove support
  for NW.js exporter and deprecate corresponding NW.js plugin". The manual,
  `tips-and-guides/deprecated-features.md`, section *NW.js exporter*, says
  the support was retired as of r450.
- the effects `warp` and `warpmask`. Release notes, beta r47: the old Warp
  and Warp mask effects are deprecated in favour of the revised ones.

The editor hides all three from its Add object and Add effect dialogs.

## Evidence

Plugins and behaviors. The Addon SDK reference documents
`SetIsDeprecated(isDeprecated)` on `IPluginInfo` and `IBehaviorInfo`: the
addon becomes invisible in the editor, and projects that already use it keep
loading. `allAces.json` and the language packs carry no such flag. The editor
bundles do:

- In `main.js`, `window.SDK.IPluginInfo` has
  `SetIsDeprecated(t){Ak.get(this).Fs(t)}`, and `window.SDK.IBehaviorInfo`
  `SetIsDeprecated(t){$k.get(this).Fs(t)}`.
- `plugins/allEditorPlugins.js` constructs 72 plugins, the keys of
  `plugins/allAces.json`. Eight call `this.p.Fs(!0)` in the constructor's own
  statements: ScirraArcadeV4, Function, gamecenter, NodeWebkit, pubcenter,
  Twitter, win8, XboxLive. They are the eight that `plugins/pluginList.json`
  files under `deprecated/`. The zh-CN pack lacks the first seven and
  translates NodeWebkit.
- `behaviors/allEditorBehaviors.js` constructs the 32 behaviors of
  `behaviors/allAces.json`; none calls the setter.
- The minified name changes between builds. In r503 beta both classes call
  `Fe`, and no constructor calls `Fs`; resolved through `SetIsDeprecated`,
  the same eight plugins come out.

Effects. The SDK guide `configuring-effects.md` documents `is-deprecated` in
an effect's `addon.json`: hidden from Add effect, kept in existing projects.
`allEffects.json`, which the export already reads, has it on `warp` and
`warpmask` and on no other effect.

Where the bundles come from. The r495.2 release directory is `r495-2/`, with
a dash; its `main.js`, `allEditorPlugins.js`, `allEditorBehaviors.js` and
`offline.json` are byte-identical to the copies at the CDN root. The fetcher
asks for `r495.2/`, gets 404 and falls back to the root, as it does for
`allAces.json`, so the flags and the ACEs come from the same build.

What depends on the three ids. The gold set, the tests, the prompts and the
skill do not name them. None of the 524 official examples uses NW.js or
`warpmask`; two use `warp`, and the checker now warns once that it has no
schema for that effect.

## Options

1. Keep the zh-CN rule and list the three ids. It fixes r495.2 and misses the
   next deprecation.
2. Read `SetIsDeprecated` from the bundles on every export, and `is-deprecated`
   from `allEffects.json`.
3. Extract the addon flags once into a committed file, as
   `common_aces.json` is for the shared ACEs. The export stays offline, but an
   addon deprecated in a later release passes until someone reruns the script
   for another reason.
4. Use the `deprecated/` folder of `pluginList.json`. It agrees at r495.2 and
   is small JSON, but it is a source layout, not the flag the editor reads.

## Decision

Option 2. `src/ingest/deprecated_addons.py` finds the setter behind
`SetIsDeprecated` in each SDK class of `main.js` and reads it from every
constructor in the bundle; `C3Fetcher.fetch_addon_deprecation()` fetches the
three files through the same cache and fallback as `allAces.json`.
`export_schemas()` leaves out an addon the editor marks deprecated and an
effect with `is-deprecated`. An addon of `allAces.json` the bundle does not
construct stops the export, so a bundle of another shape fails the update
instead of letting a deprecated addon through.

The zh-CN rule stays for addons, after the flag: every locale file takes its
ACE list from the zh-CN pack, so an addon the pack lacks would be written with
no ACEs. At r495.2 every addon it lacks is also flagged, so it removes nothing
on its own.

`common-aces-from-editor-bundle.md` rejected parsing `main.js` on every
export for the shared ACE block. This read is one method name per SDK class
and one call per constructor, not 136 literals with their guards, and it has
to follow every release, not only the ones that add a shared ACE. It costs
about 1.7 MB more per weekly export, cached like the rest.

The export now clears its schema directory before writing.
`export_to_data()` copies that directory whole, and a re-export of the same
release would otherwise keep the files of an addon it now leaves out.

Removed from `data/c3-schemas/`: `plugins/nodewebkit.json`,
`effects/warp.json` and `effects/warpmask.json` in both locales, and their
index entries.

## ACEs keep the zh-CN rule

An ACE is still left out when the zh-CN pack lacks it. `allAces.json` has the
editor's flag, `isDeprecated`, and at r495.2 the two disagree on 28 ACEs
outside the deprecated addons:

- 15 flagged and translated, so exported: System `windowwidth`,
  `windowheight`, `effects-are-supported`, `is-on-mobile-device`,
  `is-on-platform`, `renderer`, `rendererdetail`, `rgb`; Gamepad
  `lastbutton`; 3D shape `compare-z-height`, `set-z-height`, `z-height`; Pin
  `pin-to-object`; and in `_common`, `z-elevation` and `total-z-elevation`.
- 13 not flagged and untranslated, so missing: the Construct Game Services
  expressions such as `get-total-achievements`, which exist in r495.2.

Switching ACEs to the flag trades differently from addons. Counting
conditions and actions only, 31 official examples use a flagged ACE that is
exported today (`pin-to-object` in 14, `set-z-height` in 9,
`effects-are-supported` in 9), and 14 already use one the rule drops, such as
Mouse `set-cursor-style`. For those the checker reports a missing ACE in a
project the editor opens, and the sheet printer has no text to show. Keeping
deprecated ACEs with a flag that lookups hide and the checker names would fit
the editor better; it changes the lookup, the checker and the printer, and is
a decision of its own.

## Re-evaluate when

- The export stops with "the editor bundle constructs no plugin" or "no
  plugin constructor found": the constructor no longer builds its info as
  `this.p=X.m(self.<info>,ID)`; locate it again in `deprecated_addons.py`.
- The export stops on `window.SDK.IPluginInfo` or `SetIsDeprecated`: the SDK
  class was renamed or restructured.
- Scirra publishes addon deprecation on a JSON endpoint: read it there and
  drop the bundle read.
- The fetcher requests `r{release}-{patch}/` for a patch release: the root
  fallback described above no longer applies.
