# Object & Behavior Patterns

Plugin and behavior usage patterns based on 490 official examples.

## Contents

- [Top Plugins](#top-plugins)
- [Top Behaviors](#top-behaviors)
- [Behavior Configurations](#behavior-configurations)
- [Plugin Patterns](#plugin-patterns)
- [Common Combinations](#common-combinations)

---

## Top Plugins

| # | Plugin | Usage | Common Behaviors |
|---|--------|-------|------------------|
| 1 | Sprite | 3404 | Tween, Platform, 8Direction, Bullet |
| 2 | Text | 573 | Tween, Anchor |
| 3 | Keyboard | 252 | - (singleton) |
| 4 | Audio | - | - (singleton) |
| 5 | Mouse | 111 | - (singleton) |
| 6 | Touch | - | - (singleton) |
| 7 | Array | - | - (data object) |

---

## Top Behaviors

| # | behaviorId | Display Name | Usage |
|---|------------|--------------|-------|
| 1 | Tween | Tween | 1018 |
| 2 | solid | Solid | 310 |
| 3 | Timer | Timer | 238 |
| 4 | Sin | Sine | 214 |
| 5 | Bullet | Bullet | 181 |
| 6 | Platform | Platform | 81 |
| 7 | EightDir | 8Direction | 66 |
| 8 | Physics | Physics | 78 |

**Note**: In event sheet JSON, use display name (`behaviorType: "8Direction"`), not behaviorId.

---

## Behavior Configurations

### Platform

Properties: `max-speed`, `acceleration`, `deceleration`, `jump-strength`, `gravity`, `double-jump`, `default-controls`

| Condition | Parameters |
|-----------|------------|
| `is-on-floor` | - |
| `is-jumping` | - |
| `is-falling` | - |
| `on-landed` | - |

| Action | Parameters |
|--------|------------|
| `simulate-control` | `control`: `left`/`right`/`jump` |
| `set-vector-y` | `vector-y` |
| `set-max-speed` | `max-speed` |

### 8Direction

Properties: `max-speed`, `acceleration`, `deceleration`, `directions` (dir-8/dir-4), `default-controls`

| Condition | Parameters |
|-----------|------------|
| `is-moving` | - |

| Action | Parameters |
|--------|------------|
| `simulate-control` | `control`: `up`/`down`/`left`/`right` |
| `set-max-speed` | `max-speed` |
| `set-enabled` | `state` |

### Tween

| Action | Parameters |
|--------|------------|
| `tween-one-property` | `tags`, `property`, `end-value`, `time`, `ease`, `destroy-on-complete`, `loop`, `ping-pong` |
| `tween-value` | `tags`, `start-value`, `end-value`, `time`, `ease` |

Properties: `x`, `y`, `width`, `height`, `angle`, `opacity`, `z-elevation`

Easing: `linear`, `in-sine`, `out-sine`, `in-out-sine`, `in-back`, `out-back`, `in-elastic`, `out-elastic`, `in-bounce`, `out-bounce`

### Timer

| Action | Parameters |
|--------|------------|
| `start-timer` | `duration`, `type` (`once`/`regular`), `tag` |

| Condition | Parameters |
|-----------|------------|
| `on-timer` | `tag` |

### Bullet

Properties: `speed`, `acceleration`, `gravity`, `bounce-off-solids`, `set-angle`

---

## Plugin Patterns

### Keyboard

```json
{"id": "key-is-down", "objectClass": "Keyboard", "parameters": {"key": 87}}
{"id": "on-key-pressed", "objectClass": "Keyboard", "parameters": {"key": 32}}
```

Key codes: W=87, A=65, S=83, D=68, Space=32, Enter=13, Arrows=37-40

### Mouse

```json
{"id": "on-click", "objectClass": "Mouse", "parameters": {"mouse-button": "left", "click-type": "clicked"}}
{"id": "cursor-is-over-object", "objectClass": "Mouse", "parameters": {"object": "Button"}}
```

### Audio

```json
{"id": "play", "objectClass": "Audio", "parameters": {"audio-file": "Jump", "loop": "not-looping", "volume": "0"}}
{"id": "fade-volume", "objectClass": "Audio", "parameters": {"tag": "\"bgm\"", "db": "-60", "duration": "1"}}
```

### Text

```json
{"id": "set-text", "objectClass": "ScoreText", "parameters": {"text": "\"Score: \" & Score"}}
```

### Array

```json
{"id": "push-back", "objectClass": "Inventory", "parameters": {"where": "back", "value": "\"item\"", "axis": "x"}}
```

Expression: `Array.At(index)`, `Array.Width`

---

## Common Combinations

### Platform Character
```json
"behaviorTypes": [
  {"behaviorId": "Platform", "name": "Platform"},
  {"behaviorId": "Tween", "name": "Tween"},
  {"behaviorId": "Flash", "name": "Flash"}
]
```

### Top-Down Character
```json
"behaviorTypes": [
  {"behaviorId": "EightDir", "name": "8Direction"},
  {"behaviorId": "Tween", "name": "Tween"}
]
```

### Projectile
```json
"behaviorTypes": [
  {"behaviorId": "Bullet", "name": "Bullet"},
  {"behaviorId": "destroy", "name": "DestroyOutsideLayout"}
]
```
