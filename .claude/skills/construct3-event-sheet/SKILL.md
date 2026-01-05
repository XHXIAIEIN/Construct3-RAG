---
name: construct3-event-sheet
description: >
  Generates Construct 3 event sheet JSON for clipboard paste. Triggers: Construct 3,
  C3, event sheet, game logic, movement, collision, keyboard, tween, platform, bullet.
  中文：事件表、精灵、平铺图、文本、键盘、鼠标、触控、音频、粒子、八方向、
  平台、子弹、补间动画、计时器、实体、物理、寻路、淡入淡出、闪烁、旋转。
---

# Construct 3 Event Sheet Generator

## Output Format

```json
{"is-c3-clipboard-data": true, "type": "events", "items": [...]}
```

Valid types: `events`, `conditions`, `actions`

## Event Block

```json
{"eventType": "block",
 "conditions": [{"id": "{ace-id}", "objectClass": "{Object}", "parameters": {...}}],
 "actions": [{"id": "{ace-id}", "objectClass": "{Object}", "parameters": {...}}]}
```

Behavior ACE: add `"behaviorType": "{BehaviorName}"`.

## Parameters

| Type | Format | Example |
|------|--------|---------|
| Number | Direct | `"x": "400"` |
| String | Nested quotes | `"text": "\"Hello\""` |
| Expression | Direct | `"x": "Player.X + 100"` |
| Comparison | 0-5 | `0`=, `1`≠, `2`<, `3`≤, `4`>, `5`≥ |
| Key code | Number | `87`=W, `65`=A, `83`=S, `68`=D, `32`=Space |

## Templates

**Variable** (comment required):
```json
{"eventType": "variable", "name": "{Name}", "type": "number", "initialValue": "0", "comment": ""}
```

**Collision**:
```json
{"conditions": [{"id": "on-collision-with-another-object", "objectClass": "{A}", "parameters": {"object": "{B}"}}], "actions": [...]}
```

**Keyboard**:
```json
{"conditions": [{"id": "key-is-down", "objectClass": "Keyboard", "parameters": {"key": 87}}], "actions": [...]}
```

More: [clipboard-format.md](references/clipboard-format.md)

## Critical Rules

1. String params: `"animation": "\"Walk\""`
2. Behavior ACE: `"behaviorType": "8Direction"` (display name)
3. Comparison: number `4` not string `">"`
4. Variable: `"comment": ""` required
5. behavior-id differs: EightDir→8Direction, Sin→Sine, LOS→Line of sight, DragnDrop→Drag & Drop

## Dependencies

Events reference objects that must exist in project. Before outputting JSON:

1. **Check user context** for object names → use them
2. **If not mentioned** → output dependency line first:

```
Required: Keyboard(plugin), Player(Sprite+Platform), Enemy(Sprite), Ground(Sprite+Solid)
```

Format: `{Name}({Type}+{Behavior})` or `{Name}(plugin)`

## Workflow

1. Query schema if needed: `python3 scripts/query_schema.py behavior platform`
2. Generate JSON
3. Validate: `python3 scripts/validate_output.py '<json>'`
4. Fix errors if any

## Query

```bash
python3 scripts/query_schema.py plugin sprite set-animation
python3 scripts/query_schema.py behavior platform simulate-control
python3 scripts/query_examples.py action create-object
```

## References

- [clipboard-format.md](references/clipboard-format.md) - Format spec & templates
- [zh-cn.md](references/zh-cn.md) - Chinese context
- [behavior-names.md](references/behavior-names.md) - ID mapping
- [deprecated-features.md](references/deprecated-features.md) - Avoid these
- [troubleshooting.md](references/troubleshooting.md) - Error fixes

## Advanced (project root)

- `src/rag/eventsheet_generator.py` - SchemaLoader, ClipboardValidator, EventGenerator
- `src/rag/prompts.py` - LLM prompt templates
