---
name: construct3-event-sheet
description: >
  生成可粘贴到 Construct 3 编辑器的事件表 JSON。当用户提到 Construct 3、C3、
  事件表、游戏逻辑、移动控制、碰撞检测、键盘输入、Tween 动画时使用此 Skill。
  Generates Construct 3 event sheet JSON for clipboard paste. Use when user mentions
  Construct 3, C3, event sheets, game logic, movement, collision, keyboard, or tween.
---

# Construct 3 Event Sheet Code Generation

## Output Format

```json
{"is-c3-clipboard-data": true, "type": "events", "items": [...]}
```

Write to clipboard: `navigator.clipboard.write([new ClipboardItem({'text/plain': new Blob([json], {type: 'text/plain'})})])`

## Event Block Structure

```json
{"eventType": "block",
 "conditions": [{"id": "{ace-id}", "objectClass": "{Object}", "parameters": {...}}],
 "actions": [{"id": "{ace-id}", "objectClass": "{Object}", "parameters": {...}}]}
```

Behavior ACE: add `"behaviorType": "{BehaviorName}"` field.

## Parameter Formats

| Type | Format | Example |
|------|--------|---------|
| Number | Direct | `"x": "400"` |
| String | Nested quotes | `"text": "\"Hello\""` |
| Expression | Direct | `"x": "Player.X + 100"` |
| Comparison | 0-5 | `0`=, `1`≠, `2`<, `3`≤, `4`>, `5`≥ |
| Key code | Number | `87`=W, `65`=A, `83`=S, `68`=D, `32`=Space |

## Essential Templates

**Variable** (comment field required):
```json
{"eventType": "variable", "name": "{Name}", "type": "number", "initialValue": "0", "comment": ""}
```

**On Start**:
```json
{"conditions": [{"id": "on-start-of-layout", "objectClass": "System", "parameters": {}}], ...}
```

**Collision**:
```json
{"conditions": [{"id": "on-collision-with-another-object", "objectClass": "{A}", "parameters": {"object": "{B}"}}], ...}
```

**Keyboard Input**:
```json
{"conditions": [{"id": "key-is-down", "objectClass": "Keyboard", "parameters": {"key": 87}}], ...}
```

**Create Object**:
```json
{"actions": [{"id": "create-object", "objectClass": "System", "parameters": {"object-to-create": "{Obj}", "layer": "0", "x": "400", "y": "300"}}]}
```

## Critical Rules

1. **String params need nested quotes**: `"animation": "\"Walk\""`
2. **Behavior ACE needs behaviorType**: `"behaviorType": "8Direction"` (display name, not ID)
3. **Comparison is number**: `"comparison": 4` not `">"`
4. **Variable needs comment field**: `"comment": ""`

## Workflow

1. Generate JSON from templates
2. Validate: `python scripts/validate_output.py '<json>'`
3. Fix errors and re-validate
4. Copy to clipboard when passed

## Query Scripts

```bash
# Query ACE schema
python scripts/query_schema.py plugin sprite set-animation
python scripts/query_schema.py behavior platform

# Query usage examples
python scripts/query_examples.py action create-object
python scripts/query_examples.py top actions 20
```

## References

| File | Purpose |
|------|---------|
| [zh-cn.md](references/zh-cn.md) | 中文术语查询 |
| [templates.md](references/templates.md) | Code patterns |
| [behavior-names.md](references/behavior-names.md) | behaviorId → behaviorType |
| [deprecated-features.md](references/deprecated-features.md) | What NOT to use |
| [troubleshooting.md](references/troubleshooting.md) | Error fixes |
