# The Shared Instance Properties Carry Where They Are Written

Date: 2026-09-22
Schema: Construct 3 r495.2

## Problem

`plugins/_common.json` held `"properties": {}`. Every world instance has a
position, a size, an angle, a colour, an opacity, a blend mode, a UID and
tags, and none of them was in the data. An agent that wanted to colour an
object in a layout, rather than at runtime, had nothing to read, and the
checker had nothing to validate against.

Task: the agent looks up what a world instance has and where each one is in
a project file, from the committed data, in either language.

The default path calls it: `data/AGENTS.md` sends a reader to the plugin
file plus `_common.json` for what an object can do, and `check_project.py`
reads instances out of the layout files on every run.

## Why the export left it empty

The exporter fills a plugin's properties from its language pack entry,
`text.plugins.<id>.properties`. The CDN's `_common` entry has `name`,
`description`, `aceCategories`, `conditions`, `actions` and `expressions`
and no `properties` key at all, so the lookup returned the default. The text
is in the pack, under `ui.bars.properties.instance`, which the exporter
never read. Nothing was failing to fetch; the export was reading the wrong
place.

## Evidence

The three sources that describe these properties, all of them already in the
clone, and what each gives:

| Source | Gives |
|--------|-------|
| `ui.bars.properties.instance` of both language packs | `name` and `desc` per locale, the properties bar's own wording |
| `Construct3-Manual/project-primitives/objects/instances.md` | the semantics: a colour is normalized per channel and multiplied, an angle is shown in degrees |
| `data/c3-ts-defs/.../IWorldInstance.d.ts` | the scripting names and types: `x y z width height depth originX originY angle angleDegrees opacity colorRgb blendMode`, and `BlendModeParameter` as a string union |

None of the three describes a project file. Measured over the 33 225 world
instances of the 524 official examples:

- `color` is in every one of them, always four floats. The fourth is the
  opacity (31 589 are `1`, the rest `0.5`, `0.75`, `0`, `0.6` ...), and no
  world block has an `opacity` key. 835 have a channel below 1, a real tint.
- `angle` runs from 0 to 6.283: radians, where the bar and the manual both
  say degrees. `check_project.py` already errors above a full turn.
- `blendMode` is a name, `additive` 285 times, `destination-out` 86, and
  every value is in the SDK's union. It is absent when the mode is normal.
- `z` and `zElevation` never appear together. The 9 projects saved with
  release 47000 or later write `z`, the 511 saved with 46702 or earlier
  write `zElevation`. This is the Z axis scale that
  `tips-and-guides/deprecated-features.md` records: "Z elevation" was the
  2D-era name, 'Regular' became the default in 2025, and the manual's
  current instances page has only "X, Y and Z co-ordinates".
- `originX` and `originY` are in every world block, normalized to the image
  (0.5 in 25 857 of them), and occasionally outside 0 to 1 when the origin
  sits outside the image. They have no properties bar row.

## Options

1. **Text only, `{name, desc}` as every other plugin.** Faithful to the CDN
   and consistent, and it ships a contradiction: an entry that says an angle
   is in degrees and an opacity runs to 100, for a file that stores radians
   and has no opacity key. The reader most likely to need the entry is the
   one least likely to catch it.
2. **Text plus a `written` field, ids being the file's keys.** One field
   more than the other plugin files, in one file. It keeps the invariant
   that a property id is the key a project file holds, and puts the
   disagreement where it is read rather than in a guide.
3. **A separate file for the file format.** A second place to look up one
   instance, and nothing points at it from the schema.

Taken: 2. The failure this came from was a lookup whose answer was two lines
below a denial, read by a model that stopped at the first line; text that
contradicts the file, with the correction in a guide, is the same failure
one step later.

## Result

`COMMON_PROPERTIES` in `src/ingest/common_aces.py` maps each property to its
path in the language pack and to where it is written; the export stops when
the pack has no text at a path, as it already stops when the pack names a
shared ACE the bundle extract does not define. `_common.json` gains 12
properties in both locales.

Left out, and why: the layer and the Z index are the instance's place in the
layout rather than a value on it; instance variables, behaviors and effects
have blocks of their own; the origin is in the file but has no bar row and
so no localized text, and is documented in `docs/guide/data-format.md`
instead of being given an invented name.

Not done: `check_project.py` does not yet read these. A check becomes an
error only after the two steps in `references/checker-rules.md`, and a colour
or blend mode written wrong has no editor message recorded yet.
