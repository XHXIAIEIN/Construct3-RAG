# Data Format

Everything under `data/` is committed and readable without the service.
`data/c3-schemas/_index.json` records the Construct version, the exported
locales, and per-addon ACE counts. Treat it as the source of truth. It is
language neutral; each locale directory has its own `_index.json` with the
display names in that language.

## Layout

```
data/
  c3-schemas/
    _index.json                    version, languages, plugins, behaviors, effects
    {locale}/_index.json           addon names in that language, same ids
    {locale}/plugins/{id}.json     conditions, actions, expressions, properties
    {locale}/plugins/_common.json  ACEs shared by every world object
    {locale}/behaviors/{id}.json   behavior ACEs
    {locale}/effects/{id}.json     effect parameters and categories
  c3-examples/{locale}/{id}.json   example project metadata
  c3-lang/{locale}.json            raw CDN language pack, pretty printed
  c3-ts-defs/
    autocomplete-data.json         scripting class to member listings
    plugins/**/*.d.ts              plugin instance interfaces
    behaviors/**/*.d.ts            behavior instance interfaces
    preview/**/*.d.ts              runtime base interfaces
    sdk/**/*.d.ts                  addon SDK interfaces
```

`{locale}` is one of the directories listed in `_index.json` under
`languages`, currently `en-US` and `zh-CN`. Every locale is a complete copy
with the same files and structure. Only text values differ.

## Index entries

The root index is language neutral:

```json
{
  "version": "...",
  "languages": ["en-US", "zh-CN"],
  "plugins": {
    "sprite": {
      "originalId": "Sprite",
      "file": "plugins/sprite.json",
      "conditions": 12,
      "actions": 16,
      "expressions": 15
    }
  },
  "behaviors": { "...": {} },
  "effects": { "pixellate": { "file": "effects/pixellate.json", "category": "color" } }
}
```

The key is the lowercase addon id used in file names. `originalId` is the
CDN id. `file` is relative to a locale directory. A top-level `examples`
number records how many example projects were exported.

Each locale directory carries the names for that language in
`{locale}/_index.json`, keyed by the same ids:

```json
{
  "version": "...",
  "language": "zh-CN",
  "plugins": { "sprite": { "name": "精灵", "file": "plugins/sprite.json" } },
  "behaviors": { "platform": { "name": "平台", "file": "behaviors/platform.json" } },
  "effects": { "pixellate": { "name": "像素化", "file": "effects/pixellate.json" } }
}
```

Use the root index to enumerate addons and counts. Use the locale index to
turn a localized name into an id without opening every schema file.

## Plugin and behavior files

Each file describes one addon. Field names match the official CDN.

| Field | Meaning |
|-------|---------|
| `id`, `type` | Addon id and `plugin` or `behavior`. Identical across locales. |
| `name`, `description` | Localized display name and summary. |
| `aceCategories` | Map of category id to localized label, for example `collisions: Collisions`. |
| `conditions`, `actions`, `expressions` | ACE lists, described below. |
| `properties` | Editor properties, described below. |

### ACE entries

| Field | Applies to | Meaning |
|-------|-----------|---------|
| `id` | all | Stable ACE id. Identical across locales. |
| `list-name` | conditions, actions | Name shown in the add condition or action dialog. |
| `display-text` | conditions, actions | Template shown in the event sheet, for example `Set animation to {0}`. |
| `translated-name` | expressions | In `en-US` the expression identifier, for example `AnimationFrame`, which is the name a project file holds; in another locale the localized name, `动画帧`. |
| `scriptName` | all | JavaScript API name. Identical across locales. |
| `category` | all | Key into `aceCategories`. Identical across locales. |
| `description` | all | Tooltip or help text. |
| `params` | all | Parameter map keyed by parameter id, described below. |
| `isTrigger` | conditions | `true` for every condition the editor draws and treats as a trigger, such as `On start of layout`, `On collision` and `On timer`: one per event branch, none inside a function, never inverted, no `Else` after it. Absent otherwise. |
| `isFakeTrigger` | conditions | `true`, next to `isTrigger`, when the runtime tests the condition in sheet order each tick instead of firing it out of band: `On collision with another object`, Timer `On timer`, the Gamepad button conditions. Absent otherwise. |
| `isLooping` | conditions | `true` for loops: `For`, `For each`, `Repeat`, `While`, Array `For each element`. A loop cannot be inverted and `Else` cannot follow it. Absent otherwise. |
| `isInvertible` | conditions | `false` where the editor does not allow invert: `Else`, `Trigger once` and the conditions that only pick, such as `Pick all`, `Pick by comparison`, `Pick nearest/furthest` and `Pick children`. Absent means invertible, unless the condition is a trigger or a loop. |
| `isCompatibleWithTriggers` | conditions | `false` for `Else`, `Trigger once` and `Every X seconds`, which the editor keeps out of a triggered branch. Absent means compatible. |
| `isAsync` | actions | `true` for actions that can be awaited. Absent otherwise. |
| `returnType` | expressions | `number`, `string`, or `any`. |

Structural fields are the same in every locale, so an ACE can be matched by
`id` in one locale and read in another.

### Parameters

| Field | Meaning |
|-------|---------|
| `type` | Editor parameter type such as `number`, `string`, `object`, `combo`, `animation`, `instancevar`, `cmp`. Identical across locales. |
| `name`, `desc` | Localized label and help text. |
| `items` | `combo` only: map of stable item id to localized label, for example `{"current-frame": "current frame", "beginning": "beginning"}`. |
| `initialValue` | `combo` only, when the CDN records a default: the item id selected by default. |

### Properties

`properties` is a map keyed by property id:

| Field | Meaning |
|-------|---------|
| `name`, `desc` | Localized label and help text. |
| `items` | Combo properties: map of item id to localized label. |
| `initial-value` | Initial text of a text property, when the CDN records one. |
| `link-text` | Label of a link property, for example `Edit` on the Sprite animations entry. |
| `separator` | Separator string of a composite property, such as `, ` for a 3D offset. |
| `written` | `_common.json` only: where the value is in a project file, and its unit when the properties bar shows another one. |

Property types are not exported. The language pack is the only CDN source
for properties, and it carries text only.

Conditions, actions, and expressions that every world object has, such as
`Is overlapping another object`, `Pick by unique ID`, `Set value`,
`Pick children`, `Move to top`, `X`, and `UID`, are exported once
to `plugins/_common.json` and are not repeated in each plugin file. The
complete ACE list of a Sprite is its own file plus `_common.json`. The
lookup service merges the two; a direct reader must open both. Not every
plugin gets every shared ACE: the editor registers a group only for a plugin
whose info asks for it, so a Text has no `set-default-color` and an Array no
`set-x`. A plugin file lists the ids it gets under `commonAces`, by type:

```json
"commonAces": {"conditions": ["compare-instance-variable", ...], "actions": [...], "expressions": [...]}
```

An id missing there is refused by the editor on that plugin. The file has
the same fields as a plugin file, including parameter `type`, combo `items`
and the editor `category` (`collisions`, `hierarchy`, `instance-variables`
...); its structure comes from the editor bundle, see
`docs/dev/data-pipeline.md`.

`_common.json` also carries the properties every world instance has, which
the properties bar groups under *Common*: position, size, angle, colour,
opacity, blend mode, UID and tags. Their text is the properties bar's, and
each entry's `written` field says where the value is in a project file,
because the two do not always agree: the bar shows an angle in degrees and
an opacity from 0 to 100, while a layout file stores `world.angle` in
radians and keeps the opacity in the fourth component of `world.color`.
`world.originX` and `world.originY` are in the file as well, the origin
normalized to the image (0.5 centres it, and a value outside 0 to 1 places
it outside the image), but they have no properties bar row: the origin is
set per animation frame in the animations editor. Rows that are not stored
on the instance are left out; the layer and the Z index are its place in the
layout, and instance variables, behaviors and effects have blocks of their
own. See `docs/decisions/common-instance-properties.md`.

### Worked example

The condition `is-animation-playing` in `en-US/plugins/sprite.json`:

```json
{
  "id": "is-animation-playing",
  "list-name": "Is playing",
  "display-text": "Is animation {0} playing",
  "description": "Test which of the object's animations is currently playing.",
  "scriptName": "IsAnimPlaying",
  "category": "animations",
  "params": {
    "animation": {
      "type": "animation",
      "name": "Animation",
      "desc": "Enter the name of the animation to check if playing."
    }
  }
}
```

The same entry in `zh-CN/plugins/sprite.json`:

```json
{
  "id": "is-animation-playing",
  "list-name": "正在播放",
  "display-text": "正在播放 {0} 动画",
  "description": "检测当前正在播放哪个的动画。",
  "scriptName": "IsAnimPlaying",
  "category": "animations",
  "params": {
    "animation": {
      "type": "animation",
      "name": "动画",
      "desc": "要检测的动画名称。"
    }
  }
}
```

Only the text values differ. Because `params.animation.type` is `animation`,
the editor offers a list of the object's animations for that parameter.

## Effect files

Each file in `effects/` describes one effect:

| Field | Meaning |
|-------|---------|
| `id` | Effect id. Identical across locales. |
| `name`, `description` | Localized display name and summary. |
| `category` | Editor group such as `color`, `blend`, `distortion`, `3d`. Identical across locales. |
| `blends-background`, `cross-sampling`, `animated` | Editor flags copied from the CDN. |
| `parameters` | List of `{id, type, name, desc}`. `type` is `float`, `percent`, or `color`. |

## Example projects

Each file in `c3-examples/{locale}/` describes one official example:

| Field | Meaning |
|-------|---------|
| `name`, `description` | Localized title and summary |
| `tags` | Topic tags for filtering |
| `used-addons` | Plugin and behavior ids the example uses |
| `open` | URL that opens the example in the Construct editor |

To find examples for a plugin, filter on `used-addons`. To find examples for
a topic, filter on `tags`.

## Language packs

`c3-lang/{locale}.json` is the editor's precompiled language pack for that
locale, saved exactly as the CDN serves it but re-indented with one string
per line. The `text` object holds every localized string: `plugins`,
`behaviors`, `effects`, `ui`, `runtime`, and more. Schema files are built
from the `plugins`, `behaviors`, and `effects` branches.

Use it to see how a string was translated, to find text that the schema
export does not carry, or to diff two releases:

```bash
git diff <old-commit> -- data/c3-lang/zh-CN.json
```

## Scripting interfaces

`autocomplete-data.json` maps a class name such as `ISpriteInstance` to its
methods and properties. The matching `.d.ts` file under `c3-ts-defs/` holds
full signatures and documentation comments. Look up the class first, then
open the `.d.ts` file for the plugin or behavior directory with the same name.

## Regeneration

Files here are produced by the exporter in `src/ingest/` and refreshed by
`scripts/init.py` or the update workflow in `.github/workflows/update.yml`.
Do not edit generated files by hand. Fix the exporter and regenerate, then
check `_index.json` counts. Details are in `docs/dev/data-pipeline.md`.
