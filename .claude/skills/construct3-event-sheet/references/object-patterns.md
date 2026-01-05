# Object & Behavior Lookup

Use this to find correct behaviorType names and property names.

## Behavior Name Mapping

**CRITICAL**: In event JSON, use Display Name (behaviorType), NOT behaviorId.

| behaviorId | behaviorType (use this) |
|------------|------------------------|
| EightDir | 8Direction |
| Platform | Platform |
| Bullet | Bullet |
| Tween | Tween |
| Timer | Timer |
| solid | Solid |
| Sin | Sine |
| Physics | Physics |
| LOS | Line of sight |
| DragnDrop | Drag & Drop |
| destroy | DestroyOutsideLayout |

## Behavior ACE Quick Lookup

### Platform
- Conditions: `is-on-floor`, `is-jumping`, `is-falling`, `on-landed`
- Actions: `simulate-control` (control: `left`/`right`/`jump`), `set-vector-y`, `set-max-speed`

### 8Direction
- Conditions: `is-moving`
- Actions: `simulate-control` (control: `up`/`down`/`left`/`right`), `set-max-speed`, `set-enabled`

### Tween
- Actions: `tween-one-property`
  - property: `x`, `y`, `width`, `height`, `angle`, `opacity`, `z-elevation`
  - ease: `linear`, `in-out-sine`, `out-back`, `out-elastic`, `out-bounce`
- Conditions: `is-playing`, `on-tween-end`

### Timer
- Actions: `start-timer` (type: `once`/`regular`)
- Conditions: `on-timer`

### Bullet
- Properties: `speed`, `acceleration`, `gravity`, `bounce-off-solids`

## Plugin ACE Quick Lookup

### Keyboard
- Conditions: `key-is-down`, `on-key-pressed`, `on-key-released`
- Parameter: `key` (number)

### Mouse
- Conditions: `on-click`, `cursor-is-over-object`, `mouse-button-is-down`
- Parameter: `mouse-button` (`left`/`right`/`middle`)

### Audio
- Actions: `play`, `stop`, `fade-volume`
- Parameter: `loop` (`not-looping`/`looping`)

### Text
- Actions: `set-text`, `append-text`

### Sprite
- Conditions: `on-collision-with-another-object`, `is-overlapping-another-object`, `on-created`
- Actions: `set-animation`, `set-mirrored`, `spawn-another-object`, `destroy`, `set-position`
