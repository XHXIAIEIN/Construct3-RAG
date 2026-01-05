---
name: construct3-event-sheet
description: >
  Generates Construct 3 event sheet JSON that can be pasted into the C3 editor.
  Invoked when generating clipboard-ready event blocks, querying ACE IDs and
  parameter formats, implementing game logic patterns (movement, collision, timers),
  or converting between Schema and editor ID formats. Based on 490 official examples.
---

# Construct 3 Event Sheet Code Generation Guide

## Quick Start

### Clipboard JSON Structure

```json
{"is-c3-clipboard-data": true, "type": "events", "items": [...]}
```

### Type Values

| type | Purpose | Paste Location |
|------|---------|----------------|
| `"events"` | Complete event blocks | Event sheet margin |
| `"conditions"` | Conditions only | After selecting condition |
| `"actions"` | Actions only | After selecting action |

### Writing to Clipboard

```javascript
// Must use ClipboardItem + Blob, NOT writeText()
const blob = new Blob([json], {type: 'text/plain'});
await navigator.clipboard.write([new ClipboardItem({'text/plain': blob})])
```

### Minimal Example

```json
{"is-c3-clipboard-data":true,"type":"events","items":[
  {"eventType":"block",
   "conditions":[{"id":"every-x-seconds","objectClass":"System","parameters":{"interval-seconds":"2"}}],
   "actions":[{"id":"create-object","objectClass":"System","parameters":{"object-to-create":"Sprite","layer":"0","x":"400","y":"300"}}]}
]}
```

## Core Concepts

### Event Block Structure

```json
{
  "eventType": "block",
  "conditions": [
    {"id": "condition-id", "objectClass": "ObjectName", "parameters": {...}}
  ],
  "actions": [
    {"id": "action-id", "objectClass": "ObjectName", "parameters": {...}}
  ],
  "children": [...]  // Optional: sub-events
}
```

### Behavior ACE

```json
{"id": "simulate-control", "objectClass": "Player", "behaviorType": "8Direction", "parameters": {"control": "up"}}
```

### Other eventType Values

| eventType | Purpose |
|-----------|---------|
| `"variable"` | Variable definition |
| `"comment"` | Comment |
| `"group"` | Event group |
| `"function-block"` | Function definition |

### Parameter Types Quick Reference

| Type | Format | Example |
|------|--------|---------|
| Number | Direct | `"x": "400"` |
| String | Nested quotes | `"text": "\"Hello\""` |
| Expression | Direct | `"x": "Player.X + 100"` |
| String concat | & operator | `"text": "\"Score: \" & Score"` |
| Comparison | Number 0-5 | `"comparison": 0` (=) |
| Key code | Number | `"key": 87` (W) |

### Comparison Operators

0=Equal, 1=NotEqual, 2=Less, 3=LessOrEqual, 4=Greater, 5=GreaterOrEqual

See [parameter-types.md](references/parameter-types.md) for details.

## Directory Structure

```
construct3-event-sheet/
├── SKILL.md              # This file
├── references/           # Documentation files
├── scripts/              # Executable validation tools
└── assets/               # Test data and lookup tables
```

## Reference Documents

| Document | Purpose |
|----------|---------|
| [clipboard-format.md](references/clipboard-format.md) | Full JSON format, Object Types, World Instances |
| [parameter-types.md](references/parameter-types.md) | Parameter types, key codes, comparison operators |
| [id-mappings.md](references/id-mappings.md) | behaviorId ↔ behaviorType conversion |
| [templates.md](references/templates.md) | Ready-to-use code templates |
| [system-reference.md](references/system-reference.md) | System object ACE |
| [plugin-patterns.md](references/plugin-patterns.md) | Sprite/Keyboard/Audio plugin usage |
| [behavior-config.md](references/behavior-config.md) | Platform/Tween/Timer behavior config |
| [deprecated-features.md](references/deprecated-features.md) | Deprecated feature warnings |
| [top-actions.md](references/top-actions.md) | Top 20 most used actions |
| [top-conditions.md](references/top-conditions.md) | Top 20 most used conditions |

## Scripts

| Script | Purpose |
|--------|---------|
| [validate_output.py](scripts/validate_output.py) | Validate generated JSON before pasting |

## Assets

| File | Purpose |
|------|---------|
| [evaluations.json](assets/evaluations.json) | Test cases for skill evaluation |

## Code Templates

Copy and modify templates. Replace `{placeholder}` with actual values.

Full template library: [templates.md](references/templates.md)

### Core Templates

**Event Block**
```json
{"eventType":"block","conditions":[{"id":"{condition-id}","objectClass":"{Object}","parameters":{...}}],"actions":[{"id":"{action-id}","objectClass":"{Object}","parameters":{...}}]}
```

**Variable Definition** (comment field required)
```json
{"eventType":"variable","name":"{VarName}","type":"number","initialValue":"0","comment":""}
```

**Collision Detection**
```json
{"eventType":"block","conditions":[{"id":"on-collision-with-another-object","objectClass":"{Object1}","parameters":{"object":"{Object2}"}}],"actions":[...]}
```

**On Layout Start**
```json
{"eventType":"block","conditions":[{"id":"on-start-of-layout","objectClass":"System","parameters":{}}],"actions":[...]}
```

**Function Call**
```json
{"callFunction":"{FuncName}","parameters":[...]}
```

## Best Practices

### Avoid Deprecated Features

See [deprecated-features.md](references/deprecated-features.md)

### ID Naming

- ACE ID: `kebab-case` → `"set-animation"`, `"on-collision-with-another-object"`
- Object name: PascalCase → `"Player"`, `"GameManager"`
- Behavior name: Match editor display → `"8Direction"`, `"Platform"`

### String Parameters

```json
// Wrong - missing nested quotes
"animation": "Walk"

// Correct - must have nested quotes
"animation": "\"Walk\""
```

## Troubleshooting

### Paste Not Working

| Cause | Solution |
|-------|----------|
| Used `writeText()` | Use `ClipboardItem + Blob` |
| Focus not on target | Click event sheet margin first |
| Invalid JSON | Check JSON syntax |

### Action/Condition Error

| Cause | Solution |
|-------|----------|
| Wrong ID | Check [system-reference.md](references/system-reference.md) |
| Wrong parameter name | Check Schema definition |
| Missing behaviorType | Behavior ACE requires behavior name |

### String Parameter Failed

| Cause | Solution |
|-------|----------|
| Missing nested quotes | Use `"\"value\""` format |
| Special characters | Escape properly |

## Data Source

Based on 490 official example projects. See `data/project_analysis/sorted_indexes.json` for statistics.
