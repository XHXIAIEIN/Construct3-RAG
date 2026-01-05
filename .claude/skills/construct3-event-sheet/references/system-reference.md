# System Object Reference

System object is the C3 engine core, available without adding to project.

## Data Source

Full ACE definitions: `data/project_analysis/system_reference.json`

Contains:
- 56 Conditions
- 81 Actions
- 135 Expressions
- Usage frequency statistics for each ACE

## Categories

| Category | Description |
|----------|-------------|
| `general` | General features |
| `global-local-variables` | Variable operations |
| `loops` | Loop control |
| `pick-instances` | Instance picking |
| `time` | Time related |
| `start-end` | Scene lifecycle |
| `layout` | Layout control |
| `layers` | Layer operations |
| `special-conditions` | Special conditions |
| `angles` | Angle calculations |
| `save-load` | Save/Load |

## Top 10 Conditions

| ID | Purpose | Parameters |
|----|---------|------------|
| `else` | Else branch | none |
| `evaluate-expression` | Expression is true | `value` |
| `for-each` | Iterate objects | `object` |
| `on-start-of-layout` | Scene start | none |
| `compare-eventvar` | Compare variable | `variable`, `comparison`, `value` |
| `compare-two-values` | Compare two values | `first-value`, `comparison`, `second-value` |
| `every-tick` | Every frame | none |
| `compare-boolean-eventvar` | Boolean check | `variable` |
| `for` | For loop | `name`, `start-index`, `end-index` |
| `every-x-seconds` | Timed execution | `interval-seconds` |

## Top 10 Actions

| ID | Purpose | Parameters |
|----|---------|------------|
| `set-eventvar-value` | Set variable | `variable`, `value` |
| `create-object` | Create object | `object-to-create`, `layer`, `x`, `y` |
| `wait` | Wait | `seconds` |
| `set-boolean-eventvar` | Set boolean | `variable`, `value` |
| `wait-for-previous-actions` | Wait async | none |
| `restart-layout` | Restart scene | none |
| `set-group-active` | Enable event group | `group-name`, `state` |
| `add-to-eventvar` | Add to variable | `variable`, `value` |
| `go-to-layout` | Switch scene | `layout` |
| `set-layer-visible` | Layer visibility | `layer`, `visibility` |

## Usage Examples

```json
// Scene start
{"id": "on-start-of-layout", "objectClass": "System", "parameters": {}}

// Compare variable
{"id": "compare-eventvar", "objectClass": "System", "parameters": {"variable": "Score", "comparison": 4, "value": "100"}}

// Create object
{"id": "create-object", "objectClass": "System", "parameters": {"object-to-create": "Bullet", "layer": "0", "x": "Player.X", "y": "Player.Y"}}

// Wait
{"id": "wait", "objectClass": "System", "parameters": {"seconds": "1"}}
```

## Common Expressions

See [parameter-types.md](parameter-types.md#expressions) for full list.

Quick reference:
- `dt` - Delta time
- `time` - Runtime
- `loopindex` / `loopindex("name")` - Loop index
- `random(a, b)` / `choose(a, b, c)` - Random
- `floor/ceil/round/abs/clamp/lerp` - Math
- `angle/distance` - Geometry
- `viewportleft/right/top/bottom(layer)` - Viewport
