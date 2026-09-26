# Data Pipeline

## Data Sources

| Source | Origin | Format | Updates |
|--------|--------|--------|---------|
| ACE definitions | `editor.construct.net/{ver}/plugins/allAces.json` | JSON | Each C3 release |
| Language (en/zh) | `editor.construct.net/{ver}/loader/lang/precompiled-{lang}.json` | JSON | Each C3 release |
| Effects | `editor.construct.net/{ver}/effects/allEffects.json` | JSON | Each C3 release |
| Example metadata | `editor.construct.net/{ver}/media/example-project-data.json` | JSON | Each C3 release |
| Shared world-object ACEs | `editor.construct.net/main.js`, extracted by `scripts/extract_common_aces.py` into `src/ingest/common_aces.json` | JSON | When a release adds a shared ACE |

The manual, the Addon SDK samples and the example projects are separate clones
(`Construct3-Manual`, `Construct-Addon-SDK`, `Construct-Example-Projects`).
Nothing here reads or copies them; `AGENTS.md` section 2 says where an agent
finds them.

## CDN Fetching (C3Fetcher)

`src/ingest/c3_fetcher.py` fetches and caches CDN data.

### Cache Strategy

- Cache directory: `.cache/c3-cdn/{release}/`
- Expiry: every Wednesday 08:00 Beijing time (aligned with Scirra's Tuesday UK evening releases)
- Within one cache period, each endpoint is fetched at most once
- `force=True` bypasses cache

### Schema Export

`C3Fetcher.export_schemas()` merges CDN structural data (`allAces.json`, `allEffects.json`, `example-project-data.json`) with per-locale text (`precompiled-{locale}.json`) into **per-language** schema files using CDN-native field names:

```
.cache/c3-cdn/{version}/schemas/
  _index.json                  — language-neutral index (plugin/behavior/effect counts, originalId)
  en-US/_index.json            — English names + file paths, same ids as the root index
  zh-CN/_index.json            — Chinese equivalent
  en-US/plugins/sprite.json       — English Sprite ACE definitions
  zh-CN/plugins/sprite.json       — Chinese Sprite ACE definitions
  en-US/behaviors/platform.json   — English Platform behavior ACEs
  en-US/effects/alphaclamp.json   — English effect definitions
  zh-CN/...                     — Chinese equivalents (same structure)

.cache/c3-cdn/{version}/examples/
  en-US/{id}.json               — English example project metadata
  zh-CN/{id}.json               — Chinese equivalent

.cache/c3-cdn/{version}/lang/
  en-US.json                    — raw precompiled language pack, re-indented
  zh-CN.json                    — Chinese equivalent
```

`C3Fetcher.export_lang()` writes the `lang/` files. They are the CDN text
unchanged apart from indentation, so a release-to-release diff of
`data/c3-lang/` shows exactly which strings Scirra added, removed, or
retranslated.

Each plugin/behavior file uses CDN field names:
- Conditions/actions: `list-name`, `display-text`, `description`
- Expressions: `translated-name`, `description`
- Params: `{param_id: {type, name, desc}}` (object keyed by param id)
- Structural fields from allAces: `scriptName`, `isTrigger`, `isFakeTrigger`, `isLooping`, `isInvertible`, `isCompatibleWithTriggers`, `isAsync`, `returnType`, `category`. `isTrigger` is also written for a CDN `isFakeTrigger` or `isFastTrigger`, since the editor holds all three to the same rules

`plugins/_common.json` goes through the same merge. Its structural side is
not on any CDN endpoint: the editor registers the shared ACEs in `main.js`,
and `scripts/extract_common_aces.py` copies that block into
`src/ingest/common_aces.json` in the `allAces` shape, with the release it was
taken from. The same script records which plugin gets which shared ACE: the
guards of that block (`AddCommonAppearanceACEs`, `SetSupportsColor` ...) as
`requires`, and the flags each built-in plugin's constructor sets in
`plugins/allEditorPlugins.js` as `plugins`. The export writes the result into
each plugin file as `commonAces`. The export stops when the language pack names a shared ACE or
parameter the file does not define; rerun the script, review the diff and
commit it with the data. See `docs/decisions/common-aces-from-editor-bundle.md`.

The ACE counts in `_index.json` are those of the written files, after the
deprecation filter below.

Consumers that need both languages use `_merge_bilingual()` in
`src/lookup/schema_index.py` to load `en-US` + `zh-CN` and produce a unified
in-memory format. `src/lookup/schema_layout.py` owns the typed `SchemaManifest`,
canonical locale names, manifest loading, completeness checks, counts, and
runtime path selection. A schema snapshot is complete only when `_index.json`
is valid, its plugin/behavior/effect sections are non-empty, every manifest
file exists as valid JSON under both `en-US` and `zh-CN`, and each locale's
`_index.json` names exactly the manifest's addons.

### Deprecation Filter

ACEs present in `allAces.json` but absent from `zh-CN` lang file are deprecated:
- **Plugin-level**: plugins without zh-CN translation are skipped entirely
- **ACE-level**: Individual ACEs removed from zh-CN (e.g. `Browser/devicepixelratio` → replaced by `PlatformInfo/device-pixel-ratio`) → skipped

`C3Fetcher.export_schemas()` applies it, so the committed schemas never hold a deprecated ACE.

## Version Update

`data/c3-schemas/_index.json` records the release `data/` holds.
`scripts/check_c3_version.py` compares it with the latest stable release in
the CDN's `versions.json`. When Construct 3 releases a new version:

```bash
# Fetch the latest stable release (or --version <release>), replace data/
python scripts/init.py

# Review, then commit data/
git diff --stat data/
```

`C3Fetcher.export_to_data()` is the one place that maps the cache onto
`data/`: it replaces `c3-schemas`, `c3-examples`, `c3-lang`, and `c3-ts-defs`
whole, leaving cache markers behind. `scripts/init.py` and the update workflow
both call it, so generated and committed layouts stay identical. The workflow
opens a pull request with the result.
