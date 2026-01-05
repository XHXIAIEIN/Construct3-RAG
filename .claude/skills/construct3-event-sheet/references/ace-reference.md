# ACE Reference

Actions, Conditions, Expressions lookup. For code examples, see [templates.md](templates.md).

## Top 20 Conditions

| ID | Object | Parameters |
|----|--------|------------|
| `else` | System | - |
| `evaluate-expression` | System | `value` |
| `key-is-down` | Keyboard | `key` |
| `for-each` | System | `object` |
| `on-key-pressed` | Keyboard | `key` |
| `on-start-of-layout` | System | - |
| `compare-eventvar` | System | `variable`, `comparison`, `value` |
| `compare-two-values` | System | `first-value`, `comparison`, `second-value` |
| `every-tick` | System | - |
| `is-button-down` | Gamepad | `gamepad`, `button` |
| `compare-boolean-eventvar` | System | `variable` |
| `for` | System | `name`, `start-index`, `end-index` |
| `pick-by-evaluate` | System | `object`, `expression` |
| `every-x-seconds` | System | `interval-seconds` |
| `repeat` | System | `count` |
| `is-on-floor` | Platform | - |
| `on-collision-with-another-object` | Sprite | `object` |
| `is-overlapping-another-object` | Sprite | `object` |
| `on-created` | Sprite | - |
| `on-timer` | Timer | `tag` |

## Top 20 Actions

| ID | Object | Parameters |
|----|--------|------------|
| `set-eventvar-value` | System | `variable`, `value` |
| `create-object` | System | `object-to-create`, `layer`, `x`, `y` |
| `wait` | System | `seconds` |
| `set-boolean-eventvar` | System | `variable`, `value` |
| `wait-for-previous-actions` | System | - |
| `set-animation` | Sprite | `animation`, `from` |
| `play` | Audio | `audio-file`, `loop`, `volume` |
| `restart-layout` | System | - |
| `set-group-active` | System | `group-name`, `state` |
| `add-to-eventvar` | System | `variable`, `value` |
| `tween-one-property` | Tween | `tags`, `property`, `end-value`, `time`, `ease` |
| `simulate-control` | Platform/8Dir | `control` |
| `destroy` | Sprite | - |
| `go-to-layout` | System | `layout` |
| `set-text` | Text | `text` |
| `spawn-another-object` | Sprite | `object`, `layer`, `image-point` |
| `start-timer` | Timer | `duration`, `type`, `tag` |
| `set-position` | Sprite | `x`, `y` |
| `add-child` | Sprite | `child`, transforms |
| `set-instvar-value` | Any | `instance-variable`, `value` |

## Common Expressions

| Expression | Purpose |
|------------|---------|
| `dt` | Delta time |
| `time` | Runtime |
| `loopindex` | Loop index |
| `random(a,b)` | Random number |
| `choose(a,b,c)` | Random choice |
| `floor/ceil/round` | Rounding |
| `clamp(x,min,max)` | Clamp |
| `lerp(a,b,t)` | Interpolation |
| `angle(x1,y1,x2,y2)` | Angle |
| `distance(x1,y1,x2,y2)` | Distance |
| `Object.X/Y` | Position |
| `Object.Count` | Instance count |
