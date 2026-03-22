# API Reference

Default: `http://localhost:8765`

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Service status |
| POST | `/search` | Search |
| GET | `/playground` | Test UI |

---

## POST /search

### Request

```json
{
  "query": "Sprite collision",
  "mode": "auto"
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `query` | string | required | Search query (max 500 chars) |
| `mode` | string | `"auto"` | `list` / `lookup` / `semantic` / `auto` |
| `scope` | string | `"eventsheet"` | `eventsheet` / `scripts` / `js` / `ts` / `all` |
| `lang` | string | auto | `en` / `zh` / `ja` / `ko` |
| `top_k` | int | 10 | Max results (1-50) |
| `include_context` | bool | false | Include compact LLM text |
| `debug` | bool | false | Include timing info |
| `plugin` | string | null | Filter by plugin name |
| `apply_threshold` | bool | true | Adaptive score filtering |

### Modes

| Mode | Lookup | Semantic | Output |
|------|--------|----------|--------|
| `list` | yes | no | ACE names grouped by type |
| `lookup` | yes | no | Full match objects |
| `auto` | yes | yes | Matches + semantic results |
| `semantic` | no | yes | Semantic results only |

### Response

Null fields are omitted from the response.

```json
{
  "query": "Sprite collision",
  "lang": "en",
  "mode": "lookup",
  "ms": 0.5,
  "lookup": { ... }
}
```

---

### mode=list

```json
{
  "query": "Sprite",
  "mode": "list",
  "ms": 0.5,
  "lookup": {
    "hit": true,
    "tier": 1,
    "confidence": 0.9,
    "intent": "ace_list",
    "plugin": {"id": "sprite", "name": "Sprite"},
    "conditions": ["Is playing", "On finished", "Collisions enabled"],
    "actions": ["Set animation", "Stop", "Start"],
    "expressions": ["AnimationFrame", "AnimationName", "AnimationSpeed"]
  }
}
```

### mode=lookup

```json
{
  "query": "Sprite collision",
  "mode": "lookup",
  "ms": 0.5,
  "lookup": {
    "hit": true,
    "tier": 1,
    "confidence": 0.85,
    "intent": "ace_search",
    "plugin": {"id": "sprite", "name": "Sprite"},
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
        "category": "common",
        "params": [{"name": "Object", "type": "object", "desc": "..."}]
      }
    ]
  }
}
```

With `lang=zh`, each match adds `localized` and the section adds `lang`:

```json
{
  "lookup": {
    "lang": "zh",
    "matches": [{
      "en": {"name": "On collision with another object"},
      "localized": {"name": "碰撞到其他对象", "desc": "...", "display": "碰撞到 {0}"}
    }]
  }
}
```

With `scope=scripts`, each match includes `script_name` instead of `display`.

### mode=semantic

```json
{
  "query": "how to detect collision",
  "mode": "semantic",
  "ms": 8500,
  "semantic": {
    "docs": [
      {"score": 0.385, "collection": "plugins", "title": "Sprite", "section": "properties", "content": "..."}
    ],
    "terms": [
      {"score": 0.08, "zh": "碰撞", "en": "collision"}
    ],
    "examples": [
      {"score": 0.53, "project": "Platformer Basics", "content": "..."}
    ]
  }
}
```

Empty groups are omitted.

### debug

When `debug=true`:

```json
{
  "debug": {
    "lookup_ms": 0.5,
    "semantic_ms": 8500,
    "semantic": {
      "collections": {"ace": {"hits": 3, "top_score": 0.99}},
      "total_candidates": 10,
      "after_dedup": 2
    }
  }
}
```

---

## GET /health

```json
{"status": "healthy", "qdrant": true, "embedding_model": "...", "total_documents": 36558}
```

Returns `"status": "lite"` when Qdrant is unavailable.

---

## Usage Examples

```bash
# List all Sprite ACEs
curl -X POST localhost:8765/search -H "Content-Type: application/json" \
  -d '{"query":"Sprite","mode":"list"}'

# Search with full details
curl -X POST localhost:8765/search -H "Content-Type: application/json" \
  -d '{"query":"Sprite collision","mode":"lookup"}'

# Scripting mode (shows script_name, hides display)
curl -X POST localhost:8765/search -H "Content-Type: application/json" \
  -d '{"query":"Platform jump","mode":"lookup","scope":"scripts"}'

# Full search with debug
curl -X POST localhost:8765/search -H "Content-Type: application/json" \
  -d '{"query":"how to detect collision","debug":true}'
```
