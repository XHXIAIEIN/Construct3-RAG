# ID Mappings Reference

ID format conversion table for correct identifier usage in different contexts.

## Data Source

Full mappings: `data/project_analysis/id_mappings.json`

## Behavior ID Mappings

Editor display name to internal behaviorId:

| Display Name | behaviorId | Description |
|--------------|------------|-------------|
| 8Direction | EightDir | 8-directional movement |
| Solid | solid | Solid collision |
| Scroll To | scrollto | Camera follow |
| Line of Sight | LOS | Line of sight detection |
| Drag & Drop | DragnDrop | Drag and drop |
| Destroy outside layout | destroy | Destroy when leaving layout |
| Bound to layout | bound | Constrain to layout bounds |
| Sine | Sin | Sine wave motion |

### In Event Sheet JSON

```json
// behaviorType uses display name
{"id": "simulate-control", "objectClass": "Player", "behaviorType": "8Direction", "parameters": {...}}
{"id": "is-on-floor", "objectClass": "Player", "behaviorType": "Platform", "parameters": {}}
{"id": "start-timer", "objectClass": "GameManager", "behaviorType": "Timer", "parameters": {...}}
```

### In Object Type Definitions

```json
// behaviorId uses internal ID
"behaviorTypes": [
  {"behaviorId": "EightDir", "name": "8Direction"},
  {"behaviorId": "Platform", "name": "Platform"},
  {"behaviorId": "solid", "name": "Solid"},
  {"behaviorId": "Tween", "name": "Tween"}
]
```

## Plugin ID Mappings

| Display Name | plugin-id | Description |
|--------------|-----------|-------------|
| Sprite font | Spritefont2 | Sprite font |
| Array | Arr | Array |
| 3D camera | Camera3D | 3D camera |
| Gamepad | gamepad | Gamepad controller |
| 9-patch | NinePatch | 9-patch image |
| Tiled Background | TiledBg | Tiled background |
| 3D shape | Shape3D | 3D shape |
| Drawing canvas | DrawingCanvas | Drawing canvas |

### In Object Type Definitions

```json
{"name": "Player", "plugin-id": "Sprite"}
{"name": "Background", "plugin-id": "TiledBg"}
{"name": "ScoreText", "plugin-id": "Spritefont2"}
{"name": "Inventory", "plugin-id": "Arr"}
{"name": "Camera", "plugin-id": "Camera3D"}
```

## Condition/Action ID Rules

### Naming Convention
- Use `kebab-case` (lowercase + hyphens)
- Examples: `on-start-of-layout`, `set-eventvar-value`, `is-overlapping-another-object`

### Common ID Patterns

| Pattern | Examples | Description |
|---------|----------|-------------|
| `on-*` | `on-created`, `on-collision-with-another-object` | Triggers |
| `is-*` | `is-on-floor`, `is-moving`, `is-playing` | State checks |
| `compare-*` | `compare-eventvar`, `compare-two-values` | Comparisons |
| `set-*` | `set-text`, `set-animation`, `set-position` | Set properties |
| `add-*` | `add-to-eventvar`, `add-child` | Add operations |
| `pick-*` | `pick-by-evaluate`, `pick-random-instance` | Instance picking |

## Schema Query

### Find Condition/Action IDs
```bash
# Search in Schema files
grep -n "simulate-control" data/schemas/behaviors/*.json
grep -n "create-object" data/schemas/plugins/system.json
```

### Schema File Locations
- Plugins: `data/schemas/plugins/{plugin-id}.json`
- Behaviors: `data/schemas/behaviors/{behavior-id}.json`

## Common Errors

### Behavior Name Error
```json
// Wrong - used behaviorId
"behaviorType": "EightDir"

// Correct - use display name
"behaviorType": "8Direction"
```

### Plugin ID Error
```json
// Wrong - used display name
"plugin-id": "Array"

// Correct - use plugin-id
"plugin-id": "Arr"
```

### ACE ID Case Error
```json
// Wrong - used camelCase
"id": "setAnimation"

// Correct - use kebab-case
"id": "set-animation"
```
