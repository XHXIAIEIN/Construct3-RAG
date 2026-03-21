# Architecture

## Overview

Pure retrieval service for Construct 3 documentation. No LLM generation — returns structured data for downstream consumers (Copilot, chat UI, etc.) to use.

```
User Query
    │
    ▼
POST /search (mode: auto/lookup/semantic)
    │
    ├── Lookup Engine (keyword/rule-based, <1ms)
    │   ├── Tier 0: Example tag matching
    │   ├── Tier 1: Rule-based regex + keyword inference
    │   ├── Tier 2: Embedding similarity
    │   └── Tier 3: LLM classification (optional)
    │
    ├── Semantic Search (vector-based, ~1-10s)
    │   ├── Embedding: query → vector
    │   ├── Qdrant: multi-collection search
    │   ├── Reranker: cross-encoder re-scoring
    │   └── Threshold filter: adaptive cutoff
    │
    └── Response Assembly
        ├── lookup: structured matches (ACE with en/zh locale)
        ├── semantic: doc/example/term results
        └── dedup: remove semantic ACEs when lookup hits
```

## Data Pipeline

```
Construct 3 CDN (editor.construct.net/{version}/)
    │
    ├── allAces.json ──────────┐
    ├── allEffects.json        │
    ├── precompiled-en-US.json ├── C3Fetcher → export_schemas()
    ├── precompiled-zh-CN.json │       │
    ├── example-project-data   │       ▼
    └── pluginList.json ───────┘  .cache/c3-cdn/{version}/schemas/
                                      ├── plugins/{name}.json
                                      └── behaviors/{name}.json
                                           │
                                           ▼
                                  SchemaParser → ACEEntry → vectordb docs
                                           │
                                           ▼
                                     Qdrant (10 collections)
```

### CDN Deprecation Filter

ACEs present in `allAces.json` but absent from `zh-CN` lang are treated as deprecated and excluded from indexing. This removes ~300 obsolete entries (e.g. old `Browser/screenwidth` replaced by `PlatformInfo/screen-width`).

## Collections

| Collection | Content | Source |
|-----------|---------|--------|
| `c3_guide` | Tutorials, overview, tips | Markdown manual |
| `c3_interface` | Editor UI docs | Markdown manual |
| `c3_project` | Project elements (events, objects) | Markdown manual |
| `c3_plugins` | Plugin reference docs | Markdown manual |
| `c3_behaviors` | Behavior + system reference | Markdown manual |
| `c3_scripting` | Script API docs | Markdown manual |
| `c3_ace` | Structured ACE data (per-entry) | CDN allAces + lang |
| `c3_effects` | Effect definitions | CDN allEffects |
| `c3_terms` | Bilingual translation pairs | CDN lang files |
| `c3_examples` | Example project metadata + events | CDN + c3proj files |

## Lookup Engine

Keyword/rule-based direct lookup. Returns structured `LookupMatch` objects instead of flat text.

### Tier System

| Tier | Method | Latency | Example |
|------|--------|---------|---------|
| 0 | Example tag matching | <1ms | "platformer 示例" |
| 1 | Regex + keyword inference | <1ms | "Sprite actions", "Sprite 碰撞检测" |
| 2 | Embedding similarity | ~50ms | Fuzzy plugin name matching |
| 3 | LLM classification | ~1-2s | Complex intent (optional, requires Ollama) |

### Keyword Matching

- **jieba full-mode**: `碰撞检测` → `[碰撞, 碰撞检测, 检测]` (respects word boundaries)
- **Synonym expansion**: `碰撞 → [碰撞, 重叠, collision, overlap]`
- **Category expansion**: matching `collisions` category pulls in all ACEs from that category
- **Scoring**: name/category hits score higher than description hits (description contains noise words like `检测` in 20% of conditions)

## Key Design Decisions

1. **zh-CN as deprecation signal**: Scirra stops translating deprecated ACEs. We use this to filter without maintaining a manual blacklist.
2. **Lookup before semantic**: Lookup is instant and precise for ACE queries. Semantic search supplements with docs/examples.
3. **Dedup on overlap**: When lookup hits, semantic ACE results are dropped (redundant). Only non-ACE results (docs, examples) survive.
4. **Context is plain text**: LLM-facing context uses compact text format, not JSON, to save tokens.
5. **Matches are structured**: API consumer gets full ACE data with `en`/`zh` locale objects for flexible rendering.
