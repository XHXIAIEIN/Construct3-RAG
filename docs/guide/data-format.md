# Data Format

Everything under `data/` is committed and readable without the service.
`data/c3-schemas/_index.json` records the Construct version, the exported
locales, and per-addon ACE counts. Treat it as the source of truth.

## Layout

```
data/
  c3-schemas/
    _index.json                    version, languages, plugins, behaviors, effects
    {locale}/plugins/{id}.json     conditions, actions, expressions, properties
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

```json
{
  "version": "...",
  "languages": ["en-US", "zh-CN"],
  "plugins": {
    "sprite": {
      "originalId": "Sprite",
      "name_en": "Sprite",
      "name_zh": "精灵",
      "file": "plugins/sprite.json",
      "conditions": 12,
      "actions": 16,
      "expressions": 15
    }
  },
  "behaviors": { "...": {} },
  "effects": { "...": {} }
}
```

The key is the lowercase addon id used in file names. `originalId` is the
CDN id. `file` is relative to a locale directory.

## ACE entries

Each schema file groups ACEs into `conditions`, `actions`, and `expressions`.
Field names match the official CDN.

| Field | Applies to | Meaning |
|-------|-----------|---------|
| `id` | all | Stable ACE id. Identical across locales. |
| `list-name` | conditions, actions | Name shown in the add condition or action dialog. |
| `display-text` | conditions, actions | Template shown in the event sheet, for example `Set animation to {0}`. |
| `translated-name` | expressions | Expression identifier, for example `AnimationFrame`. |
| `scriptName` | all | JavaScript API name. Identical across locales. |
| `category` | all | Grouping used in the editor dialogs. Identical across locales. |
| `description` | all | Tooltip or help text. |
| `params` | all | Parameter map: `{id: {type, name, desc}}`. `type` is identical across locales. |

Structural fields are the same in every locale, so an ACE can be matched by
`id` in one locale and read in another.

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
