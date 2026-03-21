# /search Response Redesign

## Design Principle

Response is designed for **AI consumption** — an LLM reading these results to answer user questions about Construct 3. Each result type carries the fields that type needs, not a flat one-size-fits-all schema.

## Response Structure

```json
{
  "query": "Sprite 碰撞检测",
  "lang": "zh",
  "route": "lookup+semantic",
  "latency_ms": 850,

  "results": [
    {
      "type": "ace",
      "score": 0.994,
      "plugin": { "id": "sprite", "name": "Sprite", "name_zh": "精灵" },
      "ace_type": "condition",
      "id": "collisions-enabled",
      "name": "Collisions enabled",
      "name_zh": "已启用碰撞",
      "description": "True if the object's collisions are enabled.",
      "description_zh": "检测对象的碰撞功能是否已启用，并且允许触发碰撞事件。",
      "script_name": "IsCollisionEnabled",
      "params": [],
      "is_trigger": false
    },
    {
      "type": "ace",
      "score": 0.88,
      "plugin": { "id": "_common", "name": "Common", "name_zh": "公共" },
      "ace_type": "condition",
      "id": "on-collision-with-another-object",
      "name": "On collision with another object",
      "name_zh": "碰撞到其他对象",
      "description": "Triggered when this object collides with another object.",
      "description_zh": "当前对象碰撞到另一个对象时触发。",
      "script_name": "on-collision-with-another-object",
      "params": [
        { "name": "Object", "name_zh": "对象", "type": "object" }
      ],
      "is_trigger": true
    },
    {
      "type": "doc",
      "score": 0.33,
      "source": "plugin-reference/common-features/common-conditions.md",
      "collection": "plugins",
      "title": "Common conditions",
      "section": "Collisions",
      "content": "**Is overlapping another object** True if any instance of this object..."
    },
    {
      "type": "doc",
      "score": 0.21,
      "source": "behavior-reference/platform.md",
      "collection": "behaviors",
      "title": "Platform behavior",
      "section": "Implementing reliable platform movements",
      "content": "For the most reliable platform movements..."
    },
    {
      "type": "example",
      "score": 0.15,
      "source": "event_block",
      "project": "Stealth game example",
      "content": "IF Sprite.OnCollision(Other) THEN Sprite.Destroy()"
    }
  ]
}
```

## Result Types

### `ace` — Action/Condition/Expression definition
Best for: answering "how to do X", "what actions does Y have", code generation.

| Field | Type | Description |
|-------|------|-------------|
| plugin | object | `{id, name, name_zh}` — which plugin/behavior |
| ace_type | string | `condition` / `action` / `expression` |
| id | string | ACE identifier |
| name | string | English display name |
| name_zh | string | Chinese display name |
| description | string | English description |
| description_zh | string | Chinese description |
| script_name | string | JavaScript method name |
| params | array | `[{name, name_zh, type, desc}]` |
| is_trigger | bool | Is this a trigger condition? |
| is_async | bool | Is this an async action? |
| return_type | string | For expressions: return type |
| category | string | ACE category within plugin |

### `doc` — Documentation chunk
Best for: explaining concepts, tutorials, reference reading.

| Field | Type | Description |
|-------|------|-------------|
| source | string | File path (e.g. `plugin-reference/sprite.md`) |
| collection | string | Which collection (plugins, guide, scripting, etc.) |
| title | string | Document H1 title |
| section | string | H2 section title |
| content | string | Section text content |

### `example` — Example project code
Best for: showing how things work in practice.

| Field | Type | Description |
|-------|------|-------------|
| source | string | `event_block` or `script_code` |
| project | string | Example project name |
| project_zh | string | Chinese project name |
| content | string | Event block or script code |

### `term` — Translation entry
Best for: term lookup, translation queries.

| Field | Type | Description |
|-------|------|-------------|
| zh | string | Chinese term |
| en | string | English term |
| category | string | Term category (plugins, behaviors, ui, etc.) |
| path | string | Term key path |

### `lookup` — Structured lookup result (ACE list, property list, etc.)
Best for: direct answers to "list all X" queries.

| Field | Type | Description |
|-------|------|-------------|
| intent | string | What was matched (ace_list, prop_list, etc.) |
| plugin | string | Which plugin |
| content | string | Formatted result text |

## Why This Design

1. **AI can filter by type** — "give me only ACE results" or "give me only docs"
2. **Structured ACE data** — AI can directly generate code from script_name + params
3. **doc has title/section** — AI knows the context without parsing markdown
4. **Bilingual fields** — AI can respond in user's language
5. **No redundant metadata** — each type only has fields it needs
6. **Flat score** — unified relevance ranking across all types
