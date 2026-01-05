---
name: construct3-event-sheet
description: >
  Generates Construct 3 event sheet JSON for clipboard paste. Triggers: Construct 3,
  C3, event sheet, game logic, movement, collision, keyboard, tween, platform, bullet.
  中文：事件表、精灵、平铺图、文本、键盘、鼠标、触控、音频、粒子、八方向、
  平台、子弹、补间动画、计时器、实体、物理、寻路、淡入淡出、闪烁、旋转。
---

# Generate C3 Event Sheet JSON

## 1. Output This Format

```json
{"is-c3-clipboard-data": true, "type": "TYPE", "items": [...]}
```

| type | Paste Location |
|------|----------------|
| `"events"` | Event sheet margin |
| `"object-types"` | Project Bar → Object types |
| `"world-instances"` | Layout view (with positions) |
| `"layouts"` | Project Bar → Layouts (complete layout) |
| `"event-sheets"` | Project Bar → Event sheets (complete sheet) |

## 2. Use This Structure

```json
{"eventType": "block",
 "conditions": [{"id": "{ace-id}", "objectClass": "{Object}", "parameters": {...}}],
 "actions": [{"id": "{ace-id}", "objectClass": "{Object}", "parameters": {...}}]}
```

For behavior ACE, add `"behaviorType": "{BehaviorName}"`.

## 3. Format Parameters Correctly

| Type | Format | Example |
|------|--------|---------|
| Number | Direct | `"x": "400"` |
| String | **Nested quotes** | `"text": "\"Hello\""` |
| Expression | Direct | `"x": "Player.X + 100"` |
| Comparison | 0-5 | `0`=, `1`≠, `2`<, `3`≤, `4`>, `5`≥ |
| Key code | Number | `87`=W, `65`=A, `83`=S, `68`=D, `32`=Space |

## 4. Apply These Rules

1. **String params must have nested quotes**: `"animation": "\"Walk\""`
2. **Behavior ACE requires behaviorType**: `"behaviorType": "8Direction"`
3. **Comparison must be number**: `4` not `">"`
4. **Variable must have comment field**: `"comment": ""`
5. **behaviorType uses display name**: EightDir→`8Direction`, Sin→`Sine`

## 5. Choose Output Format

**Option A: Separate JSONs** (more control)
1. Object types JSON → paste to Project Bar → Object types
2. Events JSON → paste to Event sheet margin

**Option B: Complete Layout** (one paste)
- `layouts` type JSON → paste to Project Bar → Layouts
- Includes objects + instances + positions

**Option C: Complete Event Sheet** (one paste)
- `event-sheets` type JSON → paste to Project Bar → Event sheets

Get templates from [layout-templates.md](references/layout-templates.md).

## 6. Validate Before Output

```bash
python3 scripts/validate_output.py '<json>'
```

## 7. Query Schema When Unsure

```bash
python3 scripts/query_schema.py plugin sprite set-animation
python3 scripts/query_schema.py behavior platform simulate-control
python3 scripts/query_examples.py action create-object
```

## Quick Templates

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

## References (consult when needed)

| When | File |
|------|------|
| Need object-types JSON | [object-templates.md](references/object-templates.md) |
| Need complete layout JSON | [layout-templates.md](references/layout-templates.md) |
| Need event templates | [clipboard-format.md](references/clipboard-format.md) |
| Chinese user input | [zh-cn.md](references/zh-cn.md) |
| Unsure behavior name | [behavior-names.md](references/behavior-names.md) |
| Check deprecated APIs | [deprecated-features.md](references/deprecated-features.md) |
| Debug paste errors | [troubleshooting.md](references/troubleshooting.md) |
