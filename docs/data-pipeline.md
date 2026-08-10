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
  en-US/plugins/sprite.json       — English Sprite ACE definitions
  zh-CN/plugins/sprite.json       — Chinese Sprite ACE definitions
  en-US/behaviors/platform.json   — English Platform behavior ACEs
  en-US/effects/alphaclamp.json   — English effect definitions
  zh-CN/...                     — Chinese equivalents (same structure)

.cache/c3-cdn/{version}/examples/
  en-US/{id}.json               — English example project metadata
  zh-CN/{id}.json               — Chinese equivalent
```

Each plugin/behavior file uses CDN field names:
- Conditions/actions: `list-name`, `display-text`, `description`
- Expressions: `translated-name`, `description`
- Params: `{param_id: {type, name, desc}}` (object keyed by param id)
- Structural fields from allAces: `scriptName`, `isTrigger`, `isAsync`, `returnType`, `category`

Consumers that need both languages use `_merge_bilingual()` in
`src/lookup/schema_index.py` to load `en-US` + `zh-CN` and produce a unified
in-memory format. `src/schema_layout.py` owns the typed `SchemaManifest`,
canonical locale names, manifest loading, completeness checks, counts, and
runtime path selection. A schema snapshot is complete only when `_index.json`
is valid, its plugin/behavior/effect sections are non-empty, and every manifest
file exists as valid JSON under both `en-US` and `zh-CN`.

### Deprecation Filter

ACEs present in `allAces.json` but absent from `zh-CN` lang file are deprecated:
- **Plugin-level**: plugins without zh-CN translation are skipped entirely
- **ACE-level**: Individual ACEs removed from zh-CN (e.g. `Browser/devicepixelratio` → replaced by `PlatformInfo/device-pixel-ratio`) → skipped

This is applied in both `SchemaParser` (vector indexing) and `C3Fetcher.export_schemas()` (lookup schemas).

## Collection Registry

`src/collections.json` is the data authority for:

- stable collection keys and Qdrant names;
- which collections receive manual documents;
- manual-directory routing;
- manual subcategory taxonomy.

`src/collection_registry.py` validates that data into typed `CollectionSpec`
and `CollectionCatalog` values. `src/collections.py` is a compatibility facade
that derives the historical `COLLECTIONS`, `DOC_COLLECTIONS`,
`ALL_COLLECTIONS`, `DIR_TO_COLLECTION`, and `SUBCATEGORY_MAPPING` exports. Code
must not maintain a second copy of this registry.

## Indexing Contracts

`src/ingest/contracts.py` defines the boundary between source-specific parsers
and vector storage.

### VectorDocument

Every prepared row becomes a validated `VectorDocument` with:

- `document_id`: rebuild-stable source identity;
- `collection_name`: resolved Qdrant collection name;
- `text`: the exact text sent to dense and sparse encoders;
- `metadata`: JSON-serializable source metadata.

`text` and `document_id` are reserved payload keys and cannot be supplied by
metadata. The Qdrant adapter may hash `document_id` into a backend-compatible
point ID, but the original `document_id` is always retained in the payload.

`Indexer.index_documents()` still accepts the historical
`{id, text, metadata}` mapping for compatibility. It converts and validates
every mapping as a `VectorDocument` before embedding or upserting it.

### VectorMode

`VectorMode` makes the collection schema and the upsert shape one explicit
decision:

| Mode | Qdrant vectors | Sparse source |
|------|-----------------|---------------|
| `dense` | named `dense` | none |
| `dense_bm25` | named `dense` + named `sparse` | persisted BM25 vocabulary |
| `dense_native_sparse` | named `dense` + named `sparse` | embedding backend lexical weights |

Dense vectors are named `dense` in every mode. Native sparse takes precedence
when the configured embedding backend actually supports it; otherwise the
pipeline selects BM25 when enabled, or dense-only mode. Backend fallback is
resolved before the collection schema is created.

The canonical encoder implementations live under `src/vector/`. The historical
`src/ingest/embedding.py` and `src/ingest/sparse.py` modules are compatibility
re-exports.

## Staged Indexing Pipeline

`python -m src.ingest.indexer --rebuild`

`src/ingest/qdrant_adapter.py` contains the canonical Qdrant adapter.
`src/ingest/indexer.py` is a compatibility facade that retains the historical
exports, CLI, and `index_all_data()` wrapper. The orchestration lives in
`src/ingest/pipeline.py` and follows four reported stages:

### 1. Prepare

All enabled sources are read before Qdrant is mutated:

- manual Markdown is split at H2 boundaries and routed through the collection
  catalog;
- CDN terms, ACEs, and effects are rendered as bilingual documents;
- CDN example metadata is enriched with `project.c3proj` when the local example
  repository is available;
- example event blocks and JavaScript/TypeScript chunks are added to the same
  examples collection;
- Addon SDK manual and code sources are prepared;
- contextual prefixes, when enabled, are applied before the final
  `VectorDocument` is created.

The result is a fully materialized `collection -> list[VectorDocument]` map.
Parsers and builders do not write to Qdrant during this stage.

### 2. Validate

`VectorDocument` construction has already rejected non-JSON metadata, reserved
payload keys, and empty text/IDs. The Validate stage then rejects unknown
collections, mismatched collection membership, and duplicate `document_id`
values within a collection.

After validation, BM25 is fitted from the exact final `VectorDocument.text`
corpus when `dense_bm25` mode is active. This corpus includes event/script
documents and any contextual prefixes; it is not reconstructed by separately
calling the parsers a second time. Native-sparse and dense-only modes do not fit
BM25.

### 3. Publish

Collections are created or reused in registry order, then validated documents
are embedded and upserted in batches. With `--rebuild`, each existing
collection is deleted immediately before that collection is recreated.

Publication is currently **sequential per collection**. There is no temporary
collection plus alias swap, transactional rollback, or atomic all-collection
publish. A process failure during this stage can therefore leave a partially
rebuilt set of collections. Without `--rebuild`, publication is upsert-only and
does not remove points for source documents that disappeared.

### 4. Verify

After publication, the pipeline reads every managed collection and verifies its
point count is at least the prepared count. A missing or undersized collection
raises an error. This verifies existence and minimum cardinality; it is not a
payload checksum or transactional rollback mechanism.

### Failure Boundary

- Source, contract, duplicate-ID, and BM25 fitting failures occur before the
  first Qdrant collection mutation.
- Publish failures are surfaced immediately, but earlier collections may
  already have been updated.
- Verify failures report incomplete publication after the write phase; they do
  not automatically restore the previous index.

The offline contract and orchestration tests use fake adapters, so they validate
stage order, exact BM25 corpus selection, vector layout, payload identity, and
the no-publish-on-validation-failure boundary without a Qdrant service.

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

Bilingual text lets Chinese and English queries find the same ACE.

## Version Update

When Construct 3 releases a new version:

```bash
# Set C3_VERSION=<release> in .env

# Re-initialize (fetches new CDN data, re-exports schemas)
python scripts/init.py --version <release>

# Rebuild index
python -m src.ingest.indexer --rebuild
```

The update workflow copies every exported locale directory instead of naming
locales itself. This keeps generated and committed layouts identical.
