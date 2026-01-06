---
name: construct3-copilot
description: >
  Generates Construct 3 event sheet JSON for clipboard paste. Triggers: Construct 3,
  C3, event sheet, game logic, movement, collision, keyboard, tween, platform, bullet.
---

# Construct 3 Copilot

Generate Construct 3 clipboard-compatible JSON that can be directly pasted into the C3 editor.

## Quick Start

### What This Skill Does

1. **Generate Events** - Create game logic (movement, collision, scoring, etc.)
2. **Generate Objects** - Create sprites, text, tilemaps with valid imageData
3. **Generate Layouts** - Create complete scenes with objects + instances + events

### How to Use

Simply describe what you want in natural language:

```
"Create a platformer with WASD controls"
"Add collision detection between Player and Enemy"
"Make a breakout game with mouse-controlled paddle"
```

The skill will generate JSON that you paste into Construct 3.

## Output Types

| Type | Paste Location | Use Case |
|------|----------------|----------|
| `events` | Event sheet margin | Game logic |
| `object-types` | Project Bar → Object types | New objects |
| `layouts` | Project Bar → Layouts | Complete scenes |

## Clipboard Format

All output follows this structure:

```json
{"is-c3-clipboard-data": true, "type": "TYPE", "items": [...]}
```

### Event Block Structure

```json
{
  "eventType": "block",
  "conditions": [{"id": "ace-id", "objectClass": "Object", "parameters": {...}}],
  "actions": [{"id": "ace-id", "objectClass": "Object", "parameters": {...}}]
}
```

### Parameter Rules

| Type | Format | Example |
|------|--------|---------|
| Number | Direct | `"x": "400"` |
| String | **Nested quotes** | `"text": "\"Hello\""` |
| Expression | Direct | `"x": "Player.X + 100"` |
| Comparison | 0-5 | `0`=, `1`≠, `2`<, `3`≤, `4`>, `5`≥ |
| Key code | Number | `87`=W, `65`=A, `83`=S, `68`=D |

## Available Scripts

### Generate ImageData

Create valid PNG base64 data for sprites:

```bash
# Colored shapes (Kenney style by default)
python3 scripts/generate_imagedata.py --color red --width 32 --height 32
python3 scripts/generate_imagedata.py --color blue --shape circle -W 16 -H 16

# Kenney presets
python3 scripts/generate_imagedata.py --kenney player --color blue
python3 scripts/generate_imagedata.py --kenney coin --color gold

# Animation frames
python3 scripts/generate_imagedata.py --anim coin-spin --c3-object Coin

# From image file
python3 scripts/generate_imagedata.py --file sprite.png
```

### Generate Complete Layout

Create complete scenes with objects and instances:

```bash
# Platformer preset
python3 scripts/generate_layout.py --preset platformer -W 640 -H 480 -o layout.json

# Breakout preset
python3 scripts/generate_layout.py --preset breakout -W 640 -H 480 -o layout.json
```

### Query ACE Schema

Look up correct ACE IDs:

```bash
python3 scripts/query_schema.py plugin sprite set-animation
python3 scripts/query_schema.py behavior platform simulate-control
```

### Validate Output

Check JSON before pasting:

```bash
python3 scripts/validate_output.py '<json>'
```

## Quick Templates

### Variable (comment field required)

```json
{"eventType": "variable", "name": "Score", "type": "number", "initialValue": "0", "comment": ""}
```

### Collision Detection

```json
{"eventType": "block",
 "conditions": [{"id": "on-collision-with-another-object", "objectClass": "Player", "parameters": {"object": "Enemy"}}],
 "actions": [{"id": "destroy", "objectClass": "Enemy", "parameters": {}}]}
```

### Keyboard Control

```json
{"eventType": "block",
 "conditions": [{"id": "key-is-down", "objectClass": "Keyboard", "parameters": {"key": 87}}],
 "actions": [{"id": "simulate-control", "objectClass": "Player", "behaviorType": "Platform", "parameters": {"control": "jump"}}]}
```

### Mouse Follow

```json
{"eventType": "block",
 "conditions": [{"id": "every-tick", "objectClass": "System", "parameters": {}}],
 "actions": [{"id": "set-x", "objectClass": "Paddle", "parameters": {"x": "Mouse.X"}}]}
```

## Important Rules

1. **String params must have nested quotes**: `"animation": "\"Walk\""`
2. **Behavior ACE requires behaviorType**: `"behaviorType": "8Direction"`
3. **Comparison must be number**: `4` not `">"`
4. **Variable must have comment field**: `"comment": ""`
5. **NEVER hallucinate ACE IDs** - Query schema when unsure

## References

| Document | Purpose |
|----------|---------|
| [clipboard-format.md](references/clipboard-format.md) | Full JSON format specification |
| [object-templates.md](references/object-templates.md) | Object type templates with imageData |
| [layout-templates.md](references/layout-templates.md) | Complete layout templates |
| [behavior-names.md](references/behavior-names.md) | behaviorId ↔ behaviorType mapping |
| [zh-cn.md](references/zh-cn.md) | Chinese terminology reference |
| [troubleshooting.md](references/troubleshooting.md) | Debug paste errors |
