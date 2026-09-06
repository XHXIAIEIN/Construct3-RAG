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
| `top_k` | int | 10 | Requested semantic result budget (1-50); complexity routing may raise it, while Direct Schema lists remain complete |
| `context` | bool | false | Include compact compatibility text; never establishes a lookup hit by itself |
| `debug` | bool | false | Include timing and lookup/semantic routing diagnostics |
| `plugin` | string | null | Full-mode semantic filter by plugin name; bypasses Direct Lookup |
| `section_types` | string[] | null | Full-mode section filter used with `plugin` |
| `collections` | string[] | null | Full-mode semantic collection filter; bypasses Direct Lookup |
| `apply_threshold` | bool | true | Apply adaptive filtering to semantic results in full mode |

### Validation Errors

- `422 Unprocessable Entity`: blank `query`, unsupported `lang`, invalid
  `mode`/`scope`, out-of-range `top_k`, or any semantic filter (`plugin`,
  `section_types`, `collections`) combined with `mode=lookup` or `mode=list`.
- `400 Bad Request`: a requested semantic collection is not in the collection
  registry.

### Modes

| Mode | Lookup | Semantic | Output |
|------|--------|----------|--------|
| `list` | yes | no | ACE names grouped by type |
| `lookup` | yes | no | Full match objects |
| `auto` | yes | full mode only | Lookup plus semantic results when `LITE_MODE=false` |
| `semantic` | no | full mode only | Semantic results when explicitly enabled |

The default service runs with `LITE_MODE=true`. In that mode, `semantic` returns
a normal response with no `semantic` section, and semantic-only filters cannot
produce results. `plugin`, `section_types`, and `collections` all bypass Direct
Lookup rather than being silently ignored. Use `scripts/setup.py --full` for
those request shapes.

### Response

Canonical response types live in `src/interfaces/http/models.py`. Null fields
are omitted from the response.

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
  "lang": "en",
  "mode": "list",
  "ms": 0.5,
  "lookup": {
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
  "lang": "en",
  "mode": "lookup",
  "ms": 0.5,
  "lookup": {
    "matches": {
      "_common": {
        "conditions": [
          {
            "ace_id": "on-collision-with-another-object",
            "name": {
              "en": {
                "name": "On collision with another object",
                "desc": "Triggered when the object collides with another object.",
                "display": "On collision with {0}"
              }
            },
            "category": "common",
            "params": [{"name": "Object", "type": "object", "desc": "..."}]
          }
        ]
      }
    }
  }
}
```

The grouping keys carry the stable `plugin_id` and plural `ace_type`; each item
carries `ace_id`. With `lang=zh`, the localized value is added under `name.zh`:

```json
{
  "lookup": {
    "matches": {
      "_common": {
        "conditions": [{
          "ace_id": "on-collision-with-another-object",
          "name": {
            "en": {"name": "On collision with another object"},
            "zh": {"name": "碰撞到其他对象", "desc": "...", "display": "碰撞到 {0}"}
          }
        }]
      }
    }
  }
}
```

With `scope=scripts`, each match includes `script_name` and omits `display`.
The presence of a non-empty `lookup` section is the hit signal; there is no
separate `lookup.hit` field.

### mode=semantic

```json
{
  "query": "how to detect collision",
  "lang": "en",
  "mode": "semantic",
  "ms": 8500,
  "semantic": {
    "docs": [
      {"score": 0.91, "collection": "plugins", "title": "Sprite", "section": "properties", "content": "...", "context_tier": "full"}
    ],
    "terms": [
      {"score": 0.55, "zh": "碰撞", "en": "collision", "context_tier": "normal"}
    ],
    "examples": [
      {"score": 0.32, "project": "Platformer Basics", "content": "...", "context_tier": "brief"}
    ]
  }
}
```

Empty groups are omitted. Every semantic item has a relative `context_tier` of
`full`, `normal`, or `brief`.

### debug

When `debug=true`:

```json
{
  "debug": {
    "lookup_ms": 0.5,
    "lookup": {
      "plugin": "sprite",
      "tier": 1,
      "confidence": 0.9,
      "intent": "ace_search",
      "keywords": ["collision"]
    },
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
{
  "status": "lite",
  "qdrant": false,
  "schema_ready": true,
  "embedding_model": "",
  "message": "Lite mode: lookup only",
  "collections": {},
  "total_documents": 0,
  "missing_collections": []
}
```

Returns `"status": "lite"` for the default lookup-only service. An explicitly
enabled full service reports its semantic backend state (for example,
`"unavailable"` when Qdrant cannot be reached); initialization failure can fall
back to `"lite"` when the local schema remains usable. `schema_ready` reports
whether Direct Lookup has a complete bilingual schema dataset. Run
`scripts/setup.py --full` to prepare and enable semantic retrieval.

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
