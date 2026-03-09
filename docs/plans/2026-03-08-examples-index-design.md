# Examples Index & Vector Design

Date: 2026-03-08

## Goal

Add example project awareness to the RAG system:
1. Inverted index: plugin/behavior/tag → examples (fast lookup)
2. Vector collection: semantic search over example titles
3. Auto-attach related examples to ACE query results
4. New `example_find` intent for explicit example queries

## Data Sources

| File | Purpose |
|------|---------|
| `data/examples_browser_en_r475.json` | 529 examples from beta r475, English titles + desc + slug + data-tags |
| `data/examples_browser.json` | 529 examples, Chinese titles (for zh query matching) |
| `data/examples_index.json` | Built artifact: inverted index tag → examples |

### examples_browser_en_r475.json Schema

```json
{
  "title": "Cave Bridge",
  "desc": "Enter and explore the depths...",
  "slug": "cave-bridge",
  "exampleType": "examples",
  "slug_derived": false,
  "tags": ["beginner", "gameplay-mechanic", "event-sheets-only", "platformer", "plugin-Sprite", "behavior-Tween", "effect-noise"]
}
```

Tags follow the prefix convention: `plugin-*`, `behavior-*`, `effect-*`, plus bare tags for level/genre/category/coding.

URL format: `https://editor.construct.net/#open={slug}`

## Architecture

```
User query
  ├─ LookupEngine
  │    ├─ ExamplesIndex (inverted index, fast)
  │    │    ├─ intent: example_find → direct example recommendations
  │    │    └─ post-ACE hook → auto-append related examples
  │    └─ (existing SchemaIndex + TermIndex unchanged)
  └─ HybridRetriever
       └─ c3_examples collection (semantic search, top-3)
```

## Layer 1: Inverted Index (examples_index.json)

Built by `scripts/build_examples_index.py`:

```json
{
  "behavior-Tween": [
    {"title": "Cave Bridge", "slug": "cave-bridge", "genres": ["adventure"], "behaviors": ["Tween", "Platform"]},
    ...
  ],
  "plugin-Sprite": [...],
  "platformer": [...]
}
```

Keys: all `data-tag` values from the 529 examples.

## Layer 2: Vector Collection (c3_examples)

Single Qdrant collection. Embed text format:

```
"洞穴桥梁 | Cave Bridge | plugins: Sprite, Tween | behaviors: Platform, Tween | genres: Adventure, Platformer | level: Beginner | tags: Timeline | coding: Event sheets only"
```

- Chinese title prefix from `examples_browser.json` (matched by English title)
- All tag categories included
- Metadata: `title_en`, `title_zh`, `slug`, `example_type`, `plugins[]`, `behaviors[]`, `genres[]`, `level`, `tags[]`, `coding[]`

## Layer 3: LookupEngine Integration

### New ExamplesIndex class (src/rag/lookup.py)

- Loads `data/examples_index.json` at startup
- `search(tags: list[str], max_results=5) -> list[dict]`

### New intent: example_find

Triggered by: "有没有用 Tween 的示例", "platform game example", "示例推荐"

LLM context format (with genre/behavior tags):
```
Related examples: Cave Bridge (cave-bridge) [Adventure, Tween], Kiwi Story (kiwi-story) [Platformer, Platform]
```

### ACE query auto-append

After `_format_ace_list` / `_format_ace_detail`, append if related examples exist:
```
Related examples: Cave Bridge (cave-bridge), Kiwi Story (kiwi-story)
```

No tags in ACE-append format (LLM context already has full ACE info).

## Layer 4: Retrieval Integration

- Add `c3_examples` to retrieval path when query intent is `example_find`
- top-3 results
- Cross-lingual matching via bge-m3 + zh|en merged embed text

## Build Steps

1. `scripts/build_examples_index.py` → generates `data/examples_index.json`
2. Update `src/ingest/indexer.py` → index `c3_examples` from `examples_browser_en_r475.json` + zh title merge
3. Add `ExamplesIndex` class to `src/rag/lookup.py`
4. Add `example_find` intent to `IntentClassifier`
5. Hook examples into `_format_ace_list` / `_format_ace_detail`
6. Add `c3_examples` to retrieval path in `src/rag/retriever.py`

## Out of Scope

- Full event sheet content (only title + tags available)
- Per-example detail pages
- Automated slug verification for the 13 derived slugs
