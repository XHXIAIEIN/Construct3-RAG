# Deprecated Addons and ACEs From the Editor

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

Where the bundles come from. Each release serves `main.js`,
`allEditorPlugins.js` and `allEditorBehaviors.js` in the same directory as its
`allAces.json`, `r495-2/` for r495.2 (`cdn-release-directory.md`). The fetcher
reads all of them there, so the flags and the ACEs come from the same build.

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
three files from the release directory, through the same cache as
`allAces.json`.
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

## Deprecated ACEs, and the list the tools read

An ACE is still left out when the zh-CN pack lacks it. `allAces.json` has the
editor's flag, `isDeprecated` (Addon SDK, `guide/defining-aces.md`), and at
r495.2 the two disagree on 28 ACEs outside the deprecated addons:

- 15 flagged and translated, so kept: System `windowwidth`, `windowheight`,
  `effects-are-supported`, `is-on-mobile-device`, `is-on-platform`,
  `renderer`, `rendererdetail`, `rgb`; Gamepad `lastbutton`; 3D shape
  `compare-z-height`, `set-z-height`, `z-height`; Pin `pin-to-object`; and in
  `_common`, `z-elevation` and `total-z-elevation`.
- 13 not flagged and untranslated, so missing: the Construct Game Services
  expressions such as `get-total-achievements`, which exist in r495.2.

The 15 stay in the schema, flagged `isDeprecated`. Counting conditions and
actions only, 31 official examples use one of them (`pin-to-object` in 14,
`set-z-height` in 9, `effects-are-supported` in 9); dropped, each use would
read to the checker as a missing ACE and to the sheet printer as a row it
cannot word.

`{locale}/_deprecated.json` lists what the editor has deprecated, kept in the
schema or not: 8 plugins, 2 effects and 166 ACEs at r495.2, with their names
and descriptions, English where a pack has no text. `current` names the
addon's ACE of the same kind and English name that is not deprecated and is
in the schema, when there is exactly one: 21 of the 166, such as
`pin-to-object-properties` for `pin-to-object` and `sort2` for Array `sort`.
The editor has no other link from a deprecated ACE to its successor; the
packs' descriptions name none. The skill's scripts read the list:

- `lookup_ace.py` says a deprecated addon given as OBJECT is one instead of
  calling it unknown, prints a kept deprecated ACE after the current ones,
  marked and with `current`, and lists a left-out one that has every word.
- `check_project.py` makes a deprecated addon, ACE or expression a warning,
  once per ACE or expression at its first use with the count of the others.
  The editor opens those projects, so by `checker-rules.md` they are no
  errors; the left-out ones were. Over the 524 official examples the checker
  passes 508 instead of 493: the 15 failed only on deprecated ACEs, Mouse
  `set-cursor-style`, Audio `advanced-audio-supported`, Multiplayer
  `sync-object`, System `set-minimum-framerate` and Browser `ExecJS` among
  them.
- `print_sheet.py` ends a deprecated condition or action with `[deprecated]`.

A model writing from memory repeats a deprecated expression: one small-model
game in the sweep uses `rgb` eleven times. A warning per use pushed 15 of its
errors out of the report cut to `--limit`. With one warning per expression,
and problems taking the room the warnings leave instead of a fixed two
thirds, 2 are left out, the report being 180 characters over the limit. The
old and new output of every script over the examples and the game projects
is in `.local/docs/evidence/skill-evals/construct3-agent-plugin/deprecated-list-2026-09-28/`.

`POST /search` does not read the list; it answers from the schema as before.

## Re-evaluate when

- The export stops with "the editor bundle constructs no plugin" or "no
  plugin constructor found": the constructor no longer builds its info as
  `this.p=X.m(self.<info>,ID)`; locate it again in `deprecated_addons.py`.
- The export stops on `window.SDK.IPluginInfo` or `SetIsDeprecated`: the SDK
  class was renamed or restructured.
- Scirra publishes addon deprecation on a JSON endpoint: read it there and
  drop the bundle read.
- A release directory stops serving the bundles: the fetch stops with a 404.
  Reading them from the CDN root instead would take the flags from whatever
  release is stable then (`cdn-release-directory.md`).
