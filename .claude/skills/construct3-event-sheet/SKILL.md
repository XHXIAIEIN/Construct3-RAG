---
name: construct3-event-sheet
description: >
  Generates Construct 3 event sheet JSON that can be pasted into the C3 editor.
  Invoked when generating clipboard-ready event blocks, querying ACE IDs and
  parameter formats, implementing game logic patterns (movement, collision, timers),
  or converting between Schema and editor ID formats. Based on 490 official examples.
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

1. **String parameters need nested quotes**: `"animation": "\"Walk\""`
2. **Behavior ACE needs behaviorType**: `"behaviorType": "8Direction"` (display name, not ID)
3. **Comparison is number**: `"comparison": 4` not `"comparison": ">"`
4. **Variable needs comment field**: `"comment": ""` (can be empty)

## Query Scripts

When reference files lack detail, query the full data:

```bash
# Query ACE schema
python scripts/query.py schema plugin sprite set-animation
python scripts/query.py schema behavior platform

# Query usage examples from 490 projects
python scripts/query.py example action create-object
python scripts/query.py example behavior tween

# Search across all data
python scripts/query.py search simulate-control

# Show top N by usage
python scripts/query.py top actions 20
```

## References

Load on-demand when needed:

| File | Purpose |
|------|---------|
| [templates.md](references/templates.md) | Copy-paste code patterns |
| [ace-reference.md](references/ace-reference.md) | ACE ID lookup |
| [object-patterns.md](references/object-patterns.md) | Behavior names and ACE |
| [parameter-types.md](references/parameter-types.md) | Format rules, key codes |
| [clipboard-format.md](references/clipboard-format.md) | JSON structure |
| [troubleshooting.md](references/troubleshooting.md) | Error fixes |
| [deprecated-features.md](references/deprecated-features.md) | What to avoid |
