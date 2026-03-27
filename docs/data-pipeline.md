# Data Pipeline

## Data Sources

| Source | Origin | Format | Updates |
|--------|--------|--------|---------|
| ACE definitions | `editor.construct.net/{ver}/plugins/allAces.json` | JSON | Each C3 release |
| Language (en/zh) | `editor.construct.net/{ver}/loader/lang/precompiled-{lang}.json` | JSON | Each C3 release |
| Effects | `editor.construct.net/{ver}/effects/allEffects.json` | JSON | Each C3 release |
| Example metadata | `editor.construct.net/{ver}/media/example-project-data.json` | JSON | Each C3 release |
| Manual docs | Construct3-Manual repository (Markdown) | Markdown | Manual sync |
| Example projects | Construct-Example-Projects repository | .c3proj | Manual sync |

## CDN Fetching (C3Fetcher)

`src/ingest/c3_fetcher.py` fetches and caches CDN data.

### Cache Strategy

- Cache directory: `.cache/c3-cdn/{C3_VERSION}/`
- Expiry: every Wednesday 08:00 Beijing time (aligned with Scirra's Tuesday UK evening releases)
- Within one cache period, each endpoint is fetched at most once
- `force=True` bypasses cache

### Schema Export

`C3Fetcher.export_schemas()` merges CDN structural data (`allAces.json`, `allEffects.json`, `example-project-data.json`) with per-locale text (`precompiled-{locale}.json`) into **per-language** schema files using CDN-native field names:

```
.cache/c3-cdn/{version}/schemas/
  _index.json                  — language-neutral index (plugin/behavior/effect counts, originalId)
  en/plugins/sprite.json       — English Sprite ACE definitions
  zh/plugins/sprite.json       — Chinese Sprite ACE definitions
  en/behaviors/platform.json   — English Platform behavior ACEs
  en/effects/alphaclamp.json   — English effect definitions
  en/examples/{id}.json        — English example project metadata (name, description, tags, open URL)
  en/editor/index.json         — English editor UI element names
  zh/...                       — Chinese equivalents (same structure)
```

Each plugin/behavior file uses CDN field names:
- Conditions/actions: `list-name`, `display-text`, `description`
- Expressions: `translated-name`, `description`
- Params: `{param_id: {type, name, desc}}` (object keyed by param id)
- Structural fields from allAces: `scriptName`, `isTrigger`, `isAsync`, `returnType`, `category`

Consumers that need both languages use `_merge_bilingual()` (in `src/rag/lookup.py`) to load en/ + zh/ and produce a unified in-memory format.

### Deprecation Filter

ACEs present in `allAces.json` but absent from `zh-CN` lang file are deprecated:
- **Plugin-level**: 7 plugins without zh-CN translation (gamecenter, win8, xboxlive, etc.) → skipped entirely
- **ACE-level**: Individual ACEs removed from zh-CN (e.g. `Browser/devicepixelratio` → replaced by `PlatformInfo/device-pixel-ratio`) → skipped

This is applied in both `SchemaParser` (vector indexing) and `C3Fetcher.export_schemas()` (lookup schemas).

## Indexing (Indexer)

`python -m src.ingest.indexer --rebuild`

### Pipeline

1. **Markdown parsing**: Split manual docs into chunks by H2 headings, map to collections via `DIR_TO_COLLECTION`
2. **CDN data**: Fetch + export schemas
3. **BM25 fitting**: Build sparse retrieval index from all text corpus
4. **Per-collection indexing**: Embed chunks → upsert to Qdrant

### Collection mapping

| Manual directory | Collection |
|-----------------|------------|
| `getting-started/`, `overview/`, `tips-and-guides/` | `c3_guide` |
| `interface/` | `c3_interface` |
| `project-primitives/` | `c3_project` |
| `plugin-reference/` | `c3_plugins` |
| `behavior-reference/`, `system-reference/` | `c3_behaviors` |
| `scripting/` | `c3_scripting` |

### ACE text format for embedding

```
插件 精灵(Sprite) 的条件: 碰撞到其他对象 (On collision with another object)
描述: 当前对象碰撞到另一个对象时触发。
Description: Triggered when the object collides with another object.
脚本名称/Script: on-collision-with-another-object
用途: 碰撞检测、碰撞判定、碰撞事件。
```

Multilingual text ensures queries in any supported language can find the same ACE.

## Version Update

When Construct 3 releases a new version:

```bash
# Update version
echo "C3_VERSION=r477" >> .env

# Re-initialize (fetches new CDN data, re-exports schemas)
python scripts/init.py --version r477

# Rebuild index
python -m src.ingest.indexer --rebuild
```

No code changes needed — version is config-driven.
