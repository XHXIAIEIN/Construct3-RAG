# API Reference

Base URL: `http://localhost:{RAG_SERVER_PORT}` (default `8765`)

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Service health check |
| POST | `/search` | Unified search (lookup + semantic) |
| POST | `/restart` | Restart server (clears caches, triggers reload) |
| GET | `/playground` | Interactive test UI |

---

## GET /health

```json
{
  "status": "healthy",
  "qdrant": true,
  "embedding_model": "BAAI/bge-m3",
  "message": "10 collections, 36851 documents",
  "collections": {"c3_guide": 120, "c3_ace": 2761, ...},
  "total_documents": 36851,
  "missing_collections": []
}
```

---

## POST /search

### Request

```json
{
  "query": "Sprite collision",
  "mode": "auto",
  "top_k": 10,
  "lang": null,
  "collections": null,
  "plugin": null,
  "section_types": null,
  "apply_threshold": true,
  "debug": false
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `query` | string | required | Search query (max 500 chars) |
| `mode` | string | `"auto"` | `"auto"` (lookup+semantic), `"lookup"` (keyword), `"list"` (names only), `"semantic"` (vector) |
| `scope` | string | `"eventsheet"` | `"eventsheet"`, `"scripts"` (js+ts), `"js"`, `"ts"`, `"all"` |
| `top_k` | int | 10 | Max results (1-50) |
| `lang` | string | auto | Language hint: `zh`/`en`/`ja`/`ko`. Auto-detected if omitted |
| `include_context` | bool | false | Include compact LLM text in lookup results |
| `collections` | string[] | null | Limit to specific collections |
| `plugin` | string | null | Filter by plugin name |
| `section_types` | string[] | null | Filter by section type |
| `apply_threshold` | bool | true | Apply adaptive score threshold |
| `debug` | bool | false | Include debug timing info |

### Response

```json
{
  "query": "Sprite collision",
  "lang": "en",
  "mode": "auto",
  "latency_ms": 1234.5,
  "lookup": { ... },
  "semantic": [ ... ],
  "debug": null
}
```

### Lookup Section

Present when `mode` is `auto` or `lookup` and a match is found. `null` otherwise.

```json
{
  "hit": true,
  "tier": 1,
  "confidence": 0.85,
  "intent": "ace_search",
  "plugin": {
    "id": "sprite",
    "name": "Sprite",
    "name_zh": "精灵"
  },
  "keywords": ["collision"],
  "matches": [
    {
      "ace_id": "on-collision-with-another-object",
      "ace_type": "condition",
      "plugin_id": "_common",
      "en": {
        "name": "On collision with another object",
        "desc": "Triggered when the object collides with another object.",
        "display": "On collision with {0}"
      },
      "zh": {
        "name": "碰撞到其他对象",
        "desc": "当前对象碰撞到另一个对象时触发。",
        "display": "碰撞到 {0}"
      },
      "plugin_name_zh": "精灵",
      "script_name": "on-collision-with-another-object",
      "category": "common",
      "relevance": 1,
      "params": [
        {"name": "Object", "type": "object", "desc": "Select the object to test for a collision with."}
      ],
      "is_trigger": false,
      "is_async": false,
      "return_type": null
    }
  ],
  "context": "[C] On collision with another object: Triggered when... display=\"On collision with {0}\" params=Object(object)"
}
```

#### Intent Types

| Intent | Description | Example query |
|--------|-------------|---------------|
| `ace_list` | List all ACEs of a type | "Sprite actions" |
| `ace_detail` | Detail for specific ACE | "Sprite Set animation 怎么用" |
| `ace_search` | Search ACEs by keyword | "Sprite 碰撞检测" |
| `prop_list` | List properties | "Platform 属性" |
| `term_translate` | Translate C3 term | "翻译 Destroy" |
| `example_find` | Find example projects | "platformer 示例" |

### Semantic Section

List of search results from vector search. Empty when `mode=lookup` or all results deduped by lookup.

Result types:

**ACE Result** (`type: "ace"`):
```json
{
  "type": "ace",
  "score": 0.994,
  "plugin": {"id": "Sprite", "name": "Sprite", "name_zh": "精灵"},
  "ace_type": "condition",
  "id": "collisions-enabled",
  "name": "Collisions enabled",
  "name_zh": "已启用碰撞",
  "description": "...",
  "description_zh": "...",
  "script_name": "IsCollisionEnabled",
  "category": "collisions"
}
```

**Doc Result** (`type: "doc"`):
```json
{
  "type": "doc",
  "score": 0.385,
  "source": "plugin-reference/sprite.md",
  "collection": "plugins",
  "title": "Sprite",
  "section": "Sprite properties",
  "content": "..."
}
```

**Term Result** (`type: "term"`):
```json
{"type": "term", "score": 0.08, "zh": "销毁", "en": "Destroy", "category": "actions"}
```

**Example Result** (`type: "example"`):
```json
{"type": "example", "score": 0.53, "source": "...", "project": "Platformer Basics", "content": "..."}
```

### Debug Section

Present when `debug=true`. `null` otherwise.

```json
{
  "timing_ms": {
    "lookup": 0.3,
    "semantic": 8500.0,
    "total": 8500.5
  },
  "semantic": {
    "collections": {
      "ace": {"hits": 3, "top_score": 0.994},
      "plugins": {"hits": 1, "top_score": 0.385}
    },
    "total_candidates": 4,
    "after_dedup": 0
  }
}
```

### Deduplication

When lookup hits, the API removes redundant results from semantic:
- All ACE-type results (lookup.matches is authoritative)
- Doc results whose title matches the lookup plugin name

---

## POST /restart

Clears cached singletons (embedding model, lookup engine, CDN fetcher) and touches source file to trigger uvicorn reload.

```json
{"status": "restarting"}
```

---

## Usage Examples

```bash
# Keyword lookup only (instant, no GPU)
curl -X POST localhost:8765/search \
  -H "Content-Type: application/json" \
  -d '{"query":"Sprite actions","mode":"lookup"}'

# Full search with debug
curl -X POST localhost:8765/search \
  -H "Content-Type: application/json" \
  -d '{"query":"how to detect collision","mode":"auto","debug":true}'

# Plugin-specific search
curl -X POST localhost:8765/search \
  -H "Content-Type: application/json" \
  -d '{"query":"animation","plugin":"Sprite","section_types":["actions"]}'
```
