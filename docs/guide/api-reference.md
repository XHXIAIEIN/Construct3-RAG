# API Reference

Default: `http://localhost:8765`

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Service status |
| POST | `/search` | Direct Lookup |
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
| `mode` | string | `"auto"` | `list` / `lookup` / `auto` |
| `scope` | string | `"eventsheet"` | `eventsheet` / `scripts` / `js` / `ts` / `all` |
| `lang` | string | auto | `en` / `zh` / `ja` / `ko`, detected from the query when omitted; `zh` adds the Chinese names |
| `context` | bool | false | Include compact compatibility text; never establishes a lookup hit by itself |
| `debug` | bool | false | Include timing and lookup routing diagnostics |

### Validation Errors

- `422 Unprocessable Entity`: blank `query`, unsupported `lang`, invalid
  `mode`/`scope`, or a field that is not in the table above. The service
  rejects what it cannot honor instead of ignoring it.

### Modes

| Mode | Output |
|------|--------|
| `list` | ACE names grouped by type |
| `lookup` | Full match objects |
| `auto` | The same as `lookup` |

A how-to, comparison or concept question is not a lookup. The service declines
it: the response has no `lookup` section, and the manual and the example
projects are the caller's to read (`AGENTS.md` section 2).

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
            "category": "collisions",
            "params": [{"name": "Object", "type": "object", "desc": "..."}],
            "relevance": 1,
            "is_trigger": true,
            "is_async": false
          }
        ]
      }
    }
  }
}
```

The grouping keys carry the stable `plugin_id` and plural `ace_type`; each item
carries `ace_id`. `is_trigger` and `is_async` are always present; expressions
carry `return_type` instead. `relevance` is the number of query keywords the
ACE name matched; it is omitted when the handler did not score, as in `list`
mode. With `lang=zh`, the localized value is added under `name.zh`:

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
    }
  }
}
```

---

## GET /health

```json
{
  "status": "ok",
  "schema_ready": true,
  "message": "Lookup ready"
}
```

`schema_ready` reports whether Direct Lookup has a complete bilingual schema
dataset. If it does not, `status` is `"unavailable"` and `message` names the
command that fetches the data, `python scripts/init.py`.

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

# Routing diagnostics
curl -X POST localhost:8765/search -H "Content-Type: application/json" \
  -d '{"query":"Sprite collision","debug":true}'
```
