# ACE Reference

Actions, Conditions, and Expressions lookup based on 490 official examples.

## Contents

- [System Object](#system-object)
- [Top Conditions](#top-conditions)
- [Top Actions](#top-actions)
- [Common Expressions](#common-expressions)

---

## System Object

Core engine object, always available.

**Data source**: `data/project_analysis/system_reference.json` (56 conditions, 81 actions, 135 expressions)

### Categories

| Category | Purpose |
|----------|---------|
| `general` | General features |
| `global-local-variables` | Variable operations |
| `loops` | Loop control (for, for-each, repeat) |
| `pick-instances` | Instance picking |
| `time` | Time (every-x-seconds, wait) |
| `start-end` | Lifecycle (on-start-of-layout) |
| `layout` | Layout control |

---

## Top Conditions

| # | ID | Object | Parameters |
|---|-----|--------|------------|
| 1 | `else` | System | - |
| 2 | `evaluate-expression` | System | `value` |
| 3 | `key-is-down` | Keyboard | `key` |
| 4 | `for-each` | System | `object` |
| 5 | `on-key-pressed` | Keyboard | `key` |
| 6 | `on-start-of-layout` | System | - |
| 7 | `compare-eventvar` | System | `variable`, `comparison`, `value` |
| 8 | `compare-two-values` | System | `first-value`, `comparison`, `second-value` |
| 9 | `every-tick` | System | - |
| 10 | `is-button-down` | Gamepad | `gamepad`, `button` |
| 11 | `compare-boolean-eventvar` | System | `variable` |
| 12 | `for` | System | `name`, `start-index`, `end-index` |
| 13 | `pick-by-evaluate` | System | `object`, `expression` |
| 14 | `every-x-seconds` | System | `interval-seconds` |
| 15 | `repeat` | System | `count` |
| 16 | `is-on-floor` | Platform | - |
| 17 | `on-collision-with-another-object` | Sprite | `object` |
| 18 | `is-overlapping-another-object` | Sprite | `object` |
| 19 | `on-created` | Sprite | - |
| 20 | `on-timer` | Timer | `tag` |

---

## Top Actions

| # | ID | Object | Parameters |
|---|-----|--------|------------|
| 1 | `set-eventvar-value` | System | `variable`, `value` |
| 2 | `create-object` | System | `object-to-create`, `layer`, `x`, `y` |
| 3 | `wait` | System | `seconds` |
| 4 | `set-boolean-eventvar` | System | `variable`, `value` |
| 5 | `wait-for-previous-actions` | System | - |
| 6 | `set-animation` | Sprite | `animation`, `from` |
| 7 | `play` | Audio | `audio-file`, `loop`, `volume` |
| 8 | `restart-layout` | System | - |
| 9 | `set-group-active` | System | `group-name`, `state` |
| 10 | `add-to-eventvar` | System | `variable`, `value` |
| 11 | `tween-one-property` | Tween | `tags`, `property`, `end-value`, `time`, `ease` |
| 12 | `simulate-control` | Platform/8Direction | `control` |
| 13 | `destroy` | Sprite | - |
| 14 | `go-to-layout` | System | `layout` |
| 15 | `set-text` | Text | `text` |
| 16 | `spawn-another-object` | Sprite | `object`, `layer`, `image-point` |
| 17 | `start-timer` | Timer | `duration`, `type`, `tag` |
| 18 | `set-position` | Sprite | `x`, `y` |
| 19 | `add-child` | Sprite | `child`, `transform-x/y/a`, `destroy-with-parent` |
| 20 | `set-instvar-value` | Any | `instance-variable`, `value` |

---

## Common Expressions

### System

| Expression | Purpose |
|------------|---------|
| `dt` | Delta time (frame time) |
| `time` | Total runtime (seconds) |
| `loopindex` | Current loop index |
| `loopindex("name")` | Named loop index |

### Math

| Expression | Purpose |
|------------|---------|
| `random(a, b)` | Random between a and b |
| `choose(a, b, c, ...)` | Random choice |
| `floor(x)` / `ceil(x)` / `round(x)` | Rounding |
| `abs(x)` | Absolute value |
| `clamp(x, min, max)` | Clamp value |
| `lerp(a, b, t)` | Linear interpolation |
| `min(a, b)` / `max(a, b)` | Min/max |

### Geometry

| Expression | Purpose |
|------------|---------|
| `angle(x1, y1, x2, y2)` | Angle between points |
| `distance(x1, y1, x2, y2)` | Distance between points |
| `cos(a)` / `sin(a)` | Trigonometry (degrees) |

### Viewport

| Expression | Purpose |
|------------|---------|
| `viewportleft(layer)` | Viewport left edge |
| `viewportright(layer)` | Viewport right edge |
| `viewporttop(layer)` | Viewport top edge |
| `viewportbottom(layer)` | Viewport bottom edge |

### Object

| Expression | Purpose |
|------------|---------|
| `Object.X` / `Object.Y` | Position |
| `Object.Width` / `Object.Height` | Size |
| `Object.Angle` | Angle |
| `Object.Count` | Instance count |
| `Self.X` / `Self.Y` | Current instance position |
